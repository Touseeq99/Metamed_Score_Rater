import os
import sys
import logging
import json
import time
import asyncio
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional

# Configure logging first
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import cache utility
try:
    from utils.file_cache import get_cache
    CACHE_AVAILABLE = True
    logger.info("✅ File cache imported successfully")
except ImportError as e:
    logger.warning(f"❌ File cache import failed: {e}")
    CACHE_AVAILABLE = False

# Import RAG ingestion function
try:
    from Rag_Service.ingestion import ingestion_docs_doctor
    RAG_AVAILABLE = True
    logger.info("✅ RAG Service imported successfully - RAG processing enabled")
except ImportError as e:
    logger.warning(f"❌ RAG Service import failed: {e}")
    logger.warning("RAG Service not found. Vector database ingestion will be skipped.")
    RAG_AVAILABLE = False
except Exception as e:
    logger.error(f"❌ Unexpected error importing RAG Service: {e}")
    RAG_AVAILABLE = False

# Import database models
try:
    from database.models import ResearchPaper, ResearchPaperScore, ResearchPaperKeyword, ResearchPaperComment
    from database.database import SessionLocal
    DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Database module not available: {e}. Running in local mode only.")
    DB_AVAILABLE = False

# ---------------------------------------------------------------------
# STEP 1: CREATE THE CLARA AI SYSTEM PROMPT
# ---------------------------------------------------------------------

# Initialize OpenAI client with optimized settings
def get_openai_client():
    """Get optimized OpenAI client with connection pooling."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not found in environment variables")
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    return OpenAI(
        api_key=api_key,
        max_retries=3,  # Enable automatic retries
        timeout=60.0,   # 60 second timeout
    )

# Global client instance for connection reuse
_client = None

def get_client():
    """Get or create global OpenAI client instance."""
    global _client
    if _client is None:
        _client = get_openai_client()
    return _client

client = get_client()
clara_prompt = """
You are CLARA-2, an expert Context-Aware Clinical Evidence Appraiser.
You evaluate biomedical studies using the structured scoring framework described in the attached specification document (clara2.docx).
Your outputs must be reproducible, transparent, and standards-aligned with CONSORT, PRISMA, and STROBE reporting guidelines.

📘 Description of Source Document (clara2.docx)

The file defines the CLARA-2 Scoring Framework, a quantitative system (0–100 scale) used to assess the methodological quality, statistical robustness, transparency, and clinical value of research papers in health sciences.

It includes:

Study Design Hierarchy (max 15 pts)
Ranking from Randomized Controlled Trials (RCT) to Case Reports, using keyword detection (e.g., “randomized,” “cohort,” “cross-sectional,” “case-control”).

Sample Size & Power Analysis (max 8 pts)
Based on a priori power calculations, achieved sample thresholds, or underpowered study flags.

Statistical Analysis Quality (max 10 pts)
Evaluates appropriateness of statistical tests, regression adjustments, and robustness (e.g., pre-specified SAP, multiple imputation, model validation).

Pre-registration (max 8 pts)
Determines prospective vs. retrospective registry compliance and adherence (e.g., ClinicalTrials.gov, PROSPERO, ISRCTN).

Effect Size & Precision (max 7 pts)
Measures reporting completeness and CI tightness relative to the effect magnitude.

Reporting Transparency (max 7 pts)
Assesses guideline adherence and completeness (CONSORT, PRISMA, STROBE).

Reproducibility & Access (max 5 pts)
Checks for data/code availability, FAIR repository use, and documentation.

External Validity (max 7 pts)
Evaluates representativeness, real-world settings, and diversity.

Clinical Relevance (max 6 pts)
Measures use of hard vs. surrogate endpoints and clinical meaningfulness.

Novelty & Incremental Value (max 7 pts)
Captures contribution strength and potential to change practice.

Ethics & COI (max 5 pts)
Checks for IRB approval, informed consent, DSMB oversight, and COI transparency.

Penalty & Cap Rules

Outcome switching (−8)

Selective reporting (−6)

Undisclosed COI (−6)

p-hacking indicators (−3 to −6)

No ethics approval → Final = 0 (hard floor)

Critical flaws in SR/MA → Cap = 60

Confidence & Abstention Policy

Output confidence ∈ [0,1].

If evidence <0.6 or missing → low-confidence.

If context insufficient → score = 0, rationale = “Unknown/Abstain”.

🧩 Prompt Structure
Input Parameters
{
  "file_name": "<name_of_input_document>",
  "study_text": "<full_text_or_abstract_of_study>"
}

Task Objective

Analyze study_text using the CLARA-2 scoring rules from clara2.docx.
Extract evidence for each scoring dimension, calculate sub-scores, apply penalties or caps if triggered, and compute an overall weighted score (0–100).

🧮 Core Logic

Detect Study Design → Assign points (0–15)

Evaluate Power & Sample Size → Assign (0–8)

Assess Statistical Analysis Quality → Assign (0–10)

Verify Pre-registration → Assign (0–8)

Score Effect Size & Precision → Assign (0–7)

Assess Reporting Transparency → Assign (0–7)

Evaluate Reproducibility & Data Access → Assign (0–5)

Check External Validity → Assign (0–7)

Assess Clinical Relevance → Assign (0–6)

Evaluate Novelty & Incremental Value → Assign (0–7)

Check Ethics & COI → Assign (0–5)

Apply Penalties / Caps

Compute Confidence Level

📤 Expected Output Format
{
  "scores": {
    "study_design": {"score": 15, "rationale": "randomized controlled trial"},
    "sample_size_power": {"score": 8, "rationale": "a priori power achieved"},
    "stats_quality": {"score": 10, "rationale": "pre-specified SAP and corrections"},
    "registration": {"score": 8, "rationale": "prospectively registered"},
    "effect_precision": {"score": 5, "rationale": "narrow 95% CI"},
    "reporting": {"score": 5, "rationale": "CONSORT checklist followed"},
    "reproducibility": {"score": 4, "rationale": "data and code shared"},
    "external_validity": {"score": 5, "rationale": "multicenter diverse sample"},
    "clinical_relevance": {"score": 5, "rationale": "hard clinical endpoints"},
    "novelty": {"score": 5, "rationale": "practice-changing potential"},
    "ethics_coi": {"score": 5, "rationale": "IRB approval and transparent COI"}
  },
  "penalties": ["Based on above logic of penalities cap"],
  "total_score": 89,
  "confidence": 0.94,
  "comments": [
    "High methodological rigor and full transparency.",
    "No detected outcome switching or undisclosed COI."
  ]
  "Keywords": ["keyword1", "keyword2", "keyword3"]
  "paper_type": "research_journal | report | thesis | article"
}

📏 Output Constraints

Be deterministic: same text → same score.

Never fabricate missing details (mark as Unknown/Abstain).

All rationales must cite exact text evidence if possible.

Maintain confidence calibration per framework.
"""

# ---------------------------------------------------------------------
# STEP 2: UPLOAD THE FILE TO OPENAI
# ---------------------------------------------------------------------

def upload_file_to_openai(file_path):
    """Upload file to OpenAI with retry logic and optimized settings."""
    client = get_client()
    
    original_filename = os.path.basename(file_path)
    logger.info(f"📄 Uploading file: {file_path}")
    
    max_retries = 3
    retry_delay = 1.0  # Start with 1 second delay
    
    for attempt in range(max_retries):
        try:
            with open(file_path, "rb") as file_obj:
                uploaded_file = client.files.create(file=file_obj, purpose="assistants")
            logger.info(f"✅ Uploaded successfully | File ID: {uploaded_file.id} | Filename: {original_filename}")
            return uploaded_file
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Upload attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"❌ File upload failed after {max_retries} attempts: {e}")
                raise

# ---------------------------------------------------------------------
# STEP 3: RUN THE CLARA-2 EVALUATION
# ---------------------------------------------------------------------

def run_clara_evaluation(uploaded_file):
    """Run CLARA evaluation with retry logic and optimized settings."""
    client = get_client()
    
    logger.info("🧠 Running CLARA AI evaluation via Responses API...")
    
    max_retries = 3
    retry_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            response = client.responses.create(
                model="gpt-4.1-mini",  # or "gpt-4o" for higher accuracy
                input=[
                {
                    "role": "system",
                    "content": clara_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Evaluate the quality of the uploaded research paper and return the JSON output."},
                        {"type": "input_file", "file_id": uploaded_file.id}
                    ]
                }
            ]
        )
                
            result_text = response.output[0].content[0].text
            logger.info("\n✅ Evaluation Completed Successfully.")
            logger.info("🧾 Output JSON:\n%s", result_text)
            return result_text
            
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Evaluation attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"❌ Error during evaluation after {max_retries} attempts: {e}")
                return None

# ---------------------------------------------------------------------
# STEP 4: DELETE THE FILE FROM OPENAI AFTER PROCESSING
# ---------------------------------------------------------------------

def delete_file_from_openai(uploaded_file):
    """Delete file from OpenAI with retry logic."""
    client = get_client()
    
    logger.info("\n🧹 Cleaning up temporary uploaded file from OpenAI...")
    
    max_retries = 2
    retry_delay = 0.5
    
    for attempt in range(max_retries):
        try:
            client.files.delete(uploaded_file.id)
            logger.info(f"🗑️ File {uploaded_file.id} deleted successfully from OpenAI.")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Delete attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error(f"⚠️ Failed to delete file from OpenAI after {max_retries} attempts: {e}")
                # Don't raise - cleanup failure shouldn't break the main flow

def process_rater_output(result_text):
    """
    Process the rater output into a structured format for database storage.
    Returns a dictionary with 'scores' and 'metadata' keys.
    """
    try:
        # Parse the JSON response
        result = json.loads(result_text)
        logger.info(f"DEBUG: Parsed JSON keys: {list(result.keys())}")
        logger.info(f"DEBUG: Total score in JSON: {result.get('total_score')}")
        logger.info(f"DEBUG: Paper type in JSON: {result.get('paper_type')}")
        
        # Initialize the output structure
        processed = {
            'scores': [],
            'metadata': {}
        }
        
        # Process scores
        if 'scores' in result:
            for category, details in result['scores'].items():
                processed['scores'].append({
                    'category': category.replace('_', ' ').title(),
                    'score': details.get('score', 0),
                    'rationale': details.get('rationale', 'No rationale provided')
                })
        
        # Add metadata with default values
        metadata_fields = {
            'total_score': 0,
            'confidence': 0,
            'comments': [],
            'Keywords': [],
            'paper_type': 'Unknown'  # Default value for Paper_Type
        }
        
        # Update with actual values from result
        for field, default in metadata_fields.items():
            actual_value = result.get(field, default)
            logger.info(f"DEBUG: Field '{field}' -> {actual_value}")
            processed['metadata'][field] = actual_value
        
        logger.info(f"DEBUG: Final metadata: {processed['metadata']}")
        
        # Add penalties if any
        if 'penalties' in result and result['penalties']:
            processed['metadata']['penalties'] = result['penalties']
        
        return processed
    
    except json.JSONDecodeError:
        logger.error("Error: Failed to parse the response as JSON")
        return None
    except Exception as e:
        logger.error(f"Error processing rater output: {str(e)}")
        return None

def save_to_database(processed_output, file_path):
    """
    Save the processed output to the database using optimized bulk operations.
    
    Args:
        processed_output (dict): The processed output from process_rater_output()
        file_path (str): Path to the processed file
    
    Returns:
        int: The ID of the created ResearchPaper record, or None if failed
    """
    if not processed_output:
        logger.error("Error: No processed output to save")
        return None
    
    db = SessionLocal()
    try:
        # Create ResearchPaper record
        metadata = processed_output['metadata']
        research_paper = ResearchPaper(
            file_name=os.path.basename(file_path),
            total_score=metadata.get('total_score', 0),
            confidence=int(metadata.get('confidence', 0) * 100),
            paper_type=metadata.get('paper_type', '')
        )
        db.add(research_paper)
        db.flush()  # Flush to get the ID for relationships
        
        # Prepare bulk insert operations
        scores_to_insert = []
        keywords_to_insert = []
        comments_to_insert = []
        
        # Collect scores for bulk insert
        for score_data in processed_output['scores']:
            scores_to_insert.append(ResearchPaperScore(
                research_paper_id=research_paper.id,
                category=score_data['category'],
                score=score_data['score'],
                rationale=score_data['rationale'],
                max_score=10  # Default max score, adjust if needed
            ))
        
        # Collect keywords for bulk insert
        for keyword in metadata.get('Keywords', []):
            keywords_to_insert.append(ResearchPaperKeyword(
                research_paper_id=research_paper.id,
                keyword=keyword[:255]  # Ensure it fits in the String field
            ))
        
        # Collect comments for bulk insert
        for comment in metadata.get('comments', []):
            is_penalty = any(penalty_word in comment.lower() 
                           for penalty_word in ['penalty', 'penalized', 'violation'])
            
            comments_to_insert.append(ResearchPaperComment(
                research_paper_id=research_paper.id,
                comment=comment,
                is_penalty=is_penalty
            ))
        
        # Add penalties from the penalties list
        for penalty in metadata.get('penalties', []):
            comments_to_insert.append(ResearchPaperComment(
                research_paper_id=research_paper.id,
                comment=penalty,
                is_penalty=True
            ))
        
        # Perform bulk inserts
        if scores_to_insert:
            db.bulk_save_objects(scores_to_insert, return_defaults=True)
            logger.info(f"✅ Bulk inserted {len(scores_to_insert)} scores")
        
        if keywords_to_insert:
            db.bulk_save_objects(keywords_to_insert, return_defaults=True)
            logger.info(f"✅ Bulk inserted {len(keywords_to_insert)} keywords")
        
        if comments_to_insert:
            db.bulk_save_objects(comments_to_insert, return_defaults=True)
            logger.info(f"✅ Bulk inserted {len(comments_to_insert)} comments")
        
        # Single commit for all operations
        db.commit()
        logger.info(f"✅ Successfully saved to database with ID: {research_paper.id}")
        return research_paper.id
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error saving to database: {str(e)}")
        import traceback
        logger.error(f"📚 Database Error traceback: {traceback.format_exc()}")
        return None
    finally:
        db.close()

def process_paper(file_path: str, skip_rag: bool = False, skip_db: bool = False) -> dict:
    """
    Process a research paper using the CLARA-2 scoring framework with caching.
    
    Args:
        file_path: Path to the research paper PDF file
        skip_rag: If True, skip RAG processing
        skip_db: If True, skip database operations
        
    Returns:
        dict: Processed output with scores and metadata
    """
    # Validate file exists
    if not os.path.isfile(file_path):
        logger.error(f"File not found: {file_path}")
        raise FileNotFoundError(f"File not found: {file_path}")

    # Check cache first
    if CACHE_AVAILABLE:
        try:
            cache = get_cache()
            cached_result = cache.get(file_path)
            
            if cached_result:
                logger.info(f"🚀 Using cached result for {Path(file_path).name}")
                
                # Still perform RAG and DB operations if needed and not skipped
                if not skip_rag and RAG_AVAILABLE:
                    try:
                        logger.info("🚀 Starting RAG processing for cached result...")
                        rag_metadata = {
                            'paper_id': cached_result.get('paper_id'),
                            'paper_type': cached_result.get('metadata', {}).get('paper_type', 'Unknown'),
                            'file_name': os.path.basename(file_path),
                            'total_score': cached_result.get('metadata', {}).get('total_score', 0),
                            'confidence': cached_result.get('metadata', {}).get('confidence', 0)
                        }
                        
                        rag_metadata = {k: v for k, v in rag_metadata.items() if v is not None}
                        logger.info(f"📋 RAG metadata prepared: {rag_metadata}")
                        
                        rag_result = ingestion_docs_doctor(
                            file=file_path,
                            rating_metadata=rag_metadata
                        )
                        logger.info(f"✅ RAG processing completed: {rag_result}")
                        cached_result['rag_processed'] = True
                    except Exception as e:
                        logger.error(f"❌ RAG processing failed: {e}")
                        cached_result['rag_processed'] = False
                        cached_result['rag_error'] = str(e)
                
                if not skip_db and DB_AVAILABLE and not cached_result.get('paper_id'):
                    try:
                        paper_id = save_to_database(cached_result, file_path)
                        if paper_id:
                            logger.info(f"✅ Saved cached result to database with ID: {paper_id}")
                            cached_result['paper_id'] = paper_id
                    except Exception as e:
                        logger.error(f"❌ Database save failed for cached result: {e}")
                
                return cached_result
                
        except Exception as e:
            logger.warning(f"⚠️ Cache check failed: {e}. Proceeding with normal processing.")

    # Normal processing flow (no cache or cache miss)
    start_time = time.time()
    logger.info(f"🔄 Processing {Path(file_path).name} from scratch")
    
    # Upload the file to OpenAI
    uploaded_file = upload_file_to_openai(file_path)
    
    # Run CLARA-2 evaluation
    result_text = run_clara_evaluation(uploaded_file)
    
    # Process the result
    processed_output = process_rater_output(result_text)
    
    if not processed_output:
        raise ValueError("Failed to process rater output")
    
    # Save to database if enabled
    if DB_AVAILABLE and not skip_db:
        paper_id = save_to_database(processed_output, file_path)
        if paper_id:
            logger.info(f"✅ Successfully saved to database with ID: {paper_id}")
            processed_output['paper_id'] = paper_id
    
    # Process with RAG if enabled
    logger.info(f"🔍 Checking RAG availability - RAG_AVAILABLE: {RAG_AVAILABLE}")
    if RAG_AVAILABLE:
        try:
            logger.info("🚀 Starting RAG processing...")
            # Ensure all metadata values are serializable and not None
            rag_metadata = {
                'paper_id': processed_output.get('paper_id'),
                'paper_type': processed_output.get('metadata', {}).get('paper_type', 'Unknown'),
                'file_name': os.path.basename(file_path),
                'total_score': processed_output.get('metadata', {}).get('total_score', 0),
                'confidence': processed_output.get('metadata', {}).get('confidence', 0)
            }
            
            # Filter out any None values
            rag_metadata = {k: v for k, v in rag_metadata.items() if v is not None}
            logger.info(f"📋 RAG metadata prepared: {rag_metadata}")
            
            rag_result = ingestion_docs_doctor(
                file=file_path,
                rating_metadata=rag_metadata
            )
            logger.info(f"✅ RAG processing completed: {rag_result}")
            processed_output['rag_processed'] = True
        except Exception as e:
            logger.error(f"❌ RAG processing failed: {e}")
            import traceback
            logger.error(f"📚 RAG Error traceback: {traceback.format_exc()}")
            processed_output['rag_processed'] = False
            processed_output['rag_error'] = str(e)
    else:
        logger.warning("⚠️ RAG processing skipped - RAG Service not available")
        processed_output['rag_processed'] = False
        processed_output['rag_error'] = 'RAG Service not available in production'
    
    # Delete the file from OpenAI
    delete_file_from_openai(uploaded_file)
    
    # Cache the result
    if CACHE_AVAILABLE:
        try:
            cache = get_cache()
            cache.set(file_path, processed_output)
        except Exception as e:
            logger.warning(f"⚠️ Failed to cache result: {e}")
    
    processing_time = time.time() - start_time
    logger.info(f"✅ Processing completed for {Path(file_path).name} in {processing_time:.2f}s")
    
    return processed_output

