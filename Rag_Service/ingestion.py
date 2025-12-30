import sys
import os
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_utils.document_parser import DocumentChunker
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone.vectorstores import PineconeVectorStore
from data_utils.vector_db import init_doctor_db, init_patient_db
from langchain_core.documents import Document


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    logger.info("🔍 Initializing DocumentChunker...")
    chunker = DocumentChunker()
    logger.info("✅ DocumentChunker initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize DocumentChunker: {e}")
    raise

try:
    logger.info("🔍 Initializing doctor database...")
    index = init_doctor_db()
    logger.info("✅ Doctor database initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize doctor database: {e}")
    raise

try:
    logger.info("🔍 Initializing OpenAI embeddings...")
    embeddings = OpenAIEmbeddings()
    logger.info("✅ OpenAI embeddings initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize OpenAI embeddings: {e}")
    raise

try:
    logger.info("🔍 Initializing PineconeVectorStore...")
    vector_Db_doc=PineconeVectorStore(index , embeddings)
    logger.info("✅ PineconeVectorStore initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize PineconeVectorStore: {e}")
    raise



def flatten_metadata(metadata):
    """Flatten nested metadata dictionaries into top-level keys with dot notation."""
    flat_metadata = {}
    for key, value in metadata.items():
        if key == 'page_metadata' and isinstance(value, dict):
            # Flatten page_metadata with a prefix
            for subkey, subvalue in value.items():
                flat_key = f"page_{subkey}"
                # Convert None to empty string or default value
                if subvalue is None:
                    flat_metadata[flat_key] = ""
                else:
                    flat_metadata[flat_key] = subvalue
        elif isinstance(value, (str, int, float, bool)):
            flat_metadata[key] = value
        elif value is None:
            # Convert None to empty string to avoid Pinecone null value error
            flat_metadata[key] = ""
        elif isinstance(value, list) and all(isinstance(x, str) for x in value):
            flat_metadata[key] = value
        elif isinstance(value, dict):
            # Recursively flatten nested dictionaries
            for subkey, subvalue in value.items():
                flat_key = f"{key}_{subkey}"
                # Convert None to empty string
                if subvalue is None:
                    flat_metadata[flat_key] = ""
                else:
                    flat_metadata[flat_key] = subvalue
    return flat_metadata

def ingestion_docs_doctor(file: str, rating_metadata: dict = None):
    """
    Ingest a document into the vector database with only rating metadata.
    
    Args:
        file (str): Path to the document file
        rating_metadata (dict, optional): Rating metadata from the rater.
            Should contain 'scores' and 'metadata' keys.
    """
    try:
        logger.info(f"Processing file: {file}")
        chunks = chunker.chunk_pdf(file)
        
        # Prepare rating metadata if provided
        rating_meta = {}
        if rating_metadata:
            # Handle the structure passed by rater (direct metadata, not nested)
            metadata_source = rating_metadata  # Rater passes metadata directly, not nested
            
            rating_meta.update({
                'file_name': metadata_source.get('file_name'),
                'total_score': metadata_source.get('total_score'),
                'rating_keywords': ', '.join(metadata_source.get('Keywords', [])),
                'rating_comments': ' | '.join(metadata_source.get('comments', [])),
                'rating_penalties': ' | '.join(metadata_source.get('penalties', [])),
                'is_rated': True,
                'rating_source': 'CLARA-2',
                'paper_type': metadata_source.get('paper_type', 'Unknown')  # Default to 'Unknown' if None
            })
            
            # Add individual scores - rater doesn't pass scores in rag_metadata
            # Only basic metadata is passed for RAG processing
        else:
            rating_meta['is_rated'] = False
        
        for chunk in chunks:
            # Create document with only rating metadata
            # Flatten metadata and ensure no None values for Pinecone compatibility
            clean_metadata = flatten_metadata(rating_meta)
            doc = Document(
                page_content=chunk['text'],
                metadata=clean_metadata
            )
            logger.debug(f"Adding chunk to vector database with rating metadata: {clean_metadata}")
            try:
                vector_Db_doc.add_documents([doc])
            except Exception as pinecone_error:
                logger.error(f"Pinecone error: {pinecone_error}")
                # Continue without RAG processing
                return None
        
        # Return success status after processing all chunks
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

        
        
    