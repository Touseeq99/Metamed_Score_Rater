import os
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Union
import logging
from pathlib import Path
import tempfile
import shutil
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import the rater module
from Score_Rater.rater import process_paper, clara_prompt

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MetaMed Research Paper Rater",
    description="Web interface for evaluating research papers using the CLARA-2 scoring framework",
    version="1.0.0"
)

# Set up templates
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="templates/static"), name="static")

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class RatingResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processed_files: Optional[List[str]] = None

# Helper functions
def save_upload_file(upload_file: UploadFile, destination: Path) -> str:
    """Save an uploaded file to the specified destination."""
    try:
        with destination.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return str(destination)
    finally:
        upload_file.file.close()

def process_uploaded_item(item_path: Path, skip_rag: bool, skip_db: bool) -> Dict[str, Any]:
    """Process a single file or directory."""
    results = {
        "successful": [],
        "failed": []
    }
    
    if item_path.is_file() and item_path.suffix.lower() == '.pdf':
        try:
            result = process_paper(
                file_path=str(item_path),
                skip_rag=skip_rag,
                skip_db=skip_db
            )
            results["successful"].append({
                "file_path": str(item_path),
                "result": result
            })
        except Exception as e:
            logger.error(f"Error processing {item_path}: {str(e)}", exc_info=True)
            results["failed"].append({
                "file_path": str(item_path),
                "error": str(e)
            })
    elif item_path.is_dir():
        # Recursively process all PDFs in the directory
        for file_path in item_path.rglob('*.pdf'):
            try:
                result = process_paper(
                    file_path=str(file_path),
                    skip_rag=skip_rag,
                    skip_db=skip_db
                )
                results["successful"].append({
                    "file_path": str(file_path),
                    "result": result
                })
            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}", exc_info=True)
                results["failed"].append({
                    "file_path": str(file_path),
                    "error": str(e)
                })
    
    return results

def process_single_file(file_data: tuple) -> Dict[str, Any]:
    """Process a single uploaded file - designed for concurrent execution."""
    file, temp_dir, skip_rag, skip_db = file_data
    
    try:
        # Handle potential folder structure in filename
        file_path = Path(file.filename)
        
        # Create necessary subdirectories in temp folder
        target_dir = temp_dir
        if len(file_path.parts) > 1:
            # Create all parent directories
            target_dir = temp_dir / file_path.parent
            target_dir.mkdir(parents=True, exist_ok=True)
        
        # Save the uploaded file to a temporary location with proper path handling
        target_file = target_dir / file_path.name
        with target_file.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process the file or directory
        process_results = process_uploaded_item(target_file, skip_rag, skip_db)
        
        # Clean up the temporary file
        if target_file.exists():
            if target_file.is_file():
                target_file.unlink()
            else:
                shutil.rmtree(target_file)
                
        # Clean up empty directories
        if len(file_path.parts) > 1:
            try:
                target_dir.rmdir()  # Remove if empty
            except OSError:
                pass  # Directory not empty, leave it
        
        return {
            "filename": file.filename,
            "results": process_results
        }
                
    except Exception as e:
        logger.error(f"Error processing {file.filename}: {str(e)}", exc_info=True)
        return {
            "filename": file.filename,
            "error": str(e)
        }

# Web Interface
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# API Documentation
@app.get("/api", include_in_schema=False)
async def api_docs():
    return {"message": "Welcome to MetaMed Research Paper Rater API. Use the web interface at the root URL."}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/api/rate/upload", response_model=RatingResponse)
async def rate_uploaded_paper(
    request: Request,
    files: List[UploadFile] = File(...),
    skip_rag: bool = False,
    skip_db: bool = False
):
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided"
        )
    
    temp_dir = Path("temp_uploads")
    temp_dir.mkdir(exist_ok=True)
    
    results = {
        "successful": [],
        "failed": []
    }
    
    try:
        # Determine optimal number of concurrent workers
        # Limit to avoid overwhelming OpenAI API and system resources
        max_workers = min(len(files), 5)  # Process max 5 files concurrently
        
        logger.info(f"Processing {len(files)} files with {max_workers} concurrent workers")
        
        # Prepare file data for concurrent processing
        file_data_list = [(file, temp_dir, skip_rag, skip_db) for file in files]
        
        # Process files concurrently using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(process_single_file, file_data): file_data[0] 
                for file_data in file_data_list
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_file):
                original_file = future_to_file[future]
                try:
                    result = future.result()
                    
                    if "error" in result:
                        results["failed"].append({
                            "file": result["filename"],
                            "error": result["error"]
                        })
                    else:
                        file_results = result["results"]
                        results["successful"].extend(file_results["successful"])
                        results["failed"].extend(file_results["failed"])
                        
                except Exception as e:
                    logger.error(f"Unexpected error processing {original_file.filename}: {str(e)}", exc_info=True)
                    results["failed"].append({
                        "file": original_file.filename,
                        "error": str(e)
                    })
        
        # Prepare response
        response_data = RatingResponse(
            success=bool(results["successful"]),
            message=f"Processed {len(results['successful'])} file(s) successfully" + 
                   (f", {len(results['failed'])} failed" if results['failed'] else ""),
            data={"results": results},
            processed_files=[f["file_path"] for f in results["successful"]]
        )
        
        # If no files were processed successfully, return an error
        if not results["successful"] and results["failed"]: 
            response_data.success = False
            response_data.error = "Failed to process all files"
            
        return response_data
        
    except Exception as e:
        logger.error(f"Error processing uploaded files: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing files: {str(e)}"
        )

