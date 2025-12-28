import os
import sys
import logging
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import RAG ingestion function
try:
    from Rag_Service.ingestion import ingestion_docs_doctor
    RAG_AVAILABLE = True
except ImportError:
    logger.warning("RAG Service not found. Vector database ingestion will be skipped.")
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
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
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
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not found in environment variables")
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    
    original_filename = os.path.basename(file_path)
    logger.info(f"📄 Uploading file: {file_path}")
    
    try:
        with open(file_path, "rb") as file_obj:
            uploaded_file = client.files.create(file=file_obj, purpose="assistants")
        logger.info(f"✅ Uploaded successfully | File ID: {uploaded_file.id} | Filename: {original_filename}")
        return uploaded_file
    except Exception as e:
        logger.error(f"❌ File upload failed: {e}")
        sys.exit(1)

# ---------------------------------------------------------------------
# STEP 3: RUN THE CLARA-2 EVALUATION
# ---------------------------------------------------------------------

def run_clara_evaluation(uploaded_file):
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not found in environment variables")
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    logger.info("🧠 Running CLARA AI evaluation via Responses API...")
    
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
        logger.error(f"❌ Error during evaluation: {e}")
        return None

# ---------------------------------------------------------------------
# STEP 4: DELETE THE FILE FROM OPENAI AFTER PROCESSING
# ---------------------------------------------------------------------

def delete_file_from_openai(uploaded_file):
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not found in environment variables")
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    logger.info("\n🧹 Cleaning up temporary uploaded file from OpenAI...")
    
    try:
        client.files.delete(uploaded_file.id)
        logger.info(f"🗑️ File {uploaded_file.id} deleted successfully from OpenAI.")
    except Exception as e:
        logger.error(f"⚠️ Failed to delete file from OpenAI: {e}")

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

def save_to_database(processed_output , file_path):
    """
    Save the processed output to the database using SQLAlchemy models.
    
    Args:
        processed_output (dict): The processed output from process_rater_output()
    
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
        
        # Add scores
        for score_data in processed_output['scores']:
            score = ResearchPaperScore(
                research_paper_id=research_paper.id,
                category=score_data['category'],
                score=score_data['score'],
                rationale=score_data['rationale'],
                max_score=10  # Default max score, adjust if needed
            )
            db.add(score)
        
        # Add keywords
        for keyword in metadata.get('Keywords', []):
            kw = ResearchPaperKeyword(
                research_paper_id=research_paper.id,
                keyword=keyword[:255]  # Ensure it fits in the String field
            )
            db.add(kw)
        
        # Add comments and penalties
        for comment in metadata.get('comments', []):
            is_penalty = any(penalty_word in comment.lower() 
                           for penalty_word in ['penalty', 'penalized', 'violation'])
            
            comment_obj = ResearchPaperComment(
                research_paper_id=research_paper.id,
                comment=comment,
                is_penalty=is_penalty
            )
            db.add(comment_obj)
        
        # Add penalties from the penalties list
        for penalty in metadata.get('penalties', []):
            penalty_obj = ResearchPaperComment(
                research_paper_id=research_paper.id,
                comment=penalty,
                is_penalty=True
            )
            db.add(penalty_obj)
        
        db.commit()
        logger.info(f" Successfully saved to database with ID: {research_paper.id}")
        return research_paper.id
        
    except Exception as e:
        db.rollback()
        logger.error(f" Error saving to database: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()

def process_paper(file_path: str, skip_rag: bool = False, skip_db: bool = False) -> dict:
    """
    Process a research paper using the CLARA-2 scoring framework.
    
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

    # Upload the file to OpenAI
    uploaded_file = upload_file_to_openai(file_path)
    
    # Run CLARA-2 evaluation
    result_text = run_clara_evaluation(uploaded_file)
    
    # Process the result
    processed_output = process_rater_output(result_text)
    
    # Save to database if enabled
    if DB_AVAILABLE and not skip_db:
        paper_id = save_to_database(processed_output , file_path)
        if paper_id:
            logger.info(f" Successfully saved to database with ID: {paper_id}")
            processed_output['paper_id'] = paper_id
    
    # Process with RAG if enabled
    if RAG_AVAILABLE:
        try:
            # Ensure all metadata values are serializable and not None
            rag_metadata = {
                'paper_id': paper_id,
                'paper_type': processed_output.get('metadata', {}).get('paper_type', 'Unknown'),
                'file_name': os.path.basename(file_path),
                'total_score': processed_output.get('metadata', {}).get('total_score', 0),
                'confidence': processed_output.get('metadata', {}).get('confidence', 0)
            }
            
            # Filter out any None values
            rag_metadata = {k: v for k, v in rag_metadata.items() if v is not None}
            
            rag_result = ingestion_docs_doctor(
                file=file_path,
                rating_metadata=rag_metadata
            )
            logger.info(f"✅ RAG processing completed: {rag_result}")
            processed_output['rag_processed'] = True
        except Exception as e:
            logger.error(f"❌ RAG processing failed: {e}")
            processed_output['rag_processed'] = False
            processed_output['rag_error'] = str(e)
    
    # Delete the file from OpenAI
    delete_file_from_openai(uploaded_file)
    
    return processed_output

