import os
from dotenv import load_dotenv

load_dotenv()

# Chunking
EMBEDDING_MODEL      = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
BATCH_SIZE           = int(os.getenv("BATCH_SIZE", "32"))
CHUNK_MIN_TOKENS     = int(os.getenv("CHUNK_MIN_TOKENS", "300"))
CHUNK_MAX_TOKENS     = int(os.getenv("CHUNK_MAX_TOKENS", "500"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("CHUNK_OVERLAP_TOKENS", "50"))
PARAGRAPH_BREAK_NEWLINES = int(os.getenv("PARAGRAPH_BREAK_NEWLINES", "2"))

# OpenSearch
OPENSEARCH_HOST     = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT     = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_USER     = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "C#emlabs2026!")

# Search / RAG
MIN_RELEVANCE_SCORE = float(os.getenv("MIN_RELEVANCE_SCORE", "0.5"))
INDEX_NAMES         = os.getenv("INDEX_NAMES", "").strip()
DATA_DIR            = os.getenv("DATA_DIR", "")

# LLM
LLM_PROVIDER      = os.getenv("LLM_PROVIDER", "gemini")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL      = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
LLM_MODEL         = os.getenv("LLM_MODEL_CPU_FALLBACK", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
MAX_ANSWER_LENGTH = int(os.getenv("MAX_ANSWER_LENGTH", "500"))

# Ingestion (DB)
MAX_ROWS_PER_TABLE = int(os.getenv("MAX_ROWS_PER_TABLE", "50000"))
LOOKUP_MAX_ROWS    = int(os.getenv("LOOKUP_MAX_ROWS", "5000"))
STREAM_BATCH       = int(os.getenv("STREAM_BATCH", "2000"))
