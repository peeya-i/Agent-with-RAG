"""Configuration settings for Agent-with-RAG application."""
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Base Directory paths
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

# Load environment variables
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# Google AI Studio / Gemini API Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Web Server Port configuration
DEFAULT_PORT = int(os.getenv("PORT", 5000))

def get_configured_port() -> int:
    """Parse command line argument --port or fallback to .env / default port."""
    parser = argparse.ArgumentParser(description="Agent With RAG Server")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to run the Flask application on (default: {DEFAULT_PORT})",
    )
    # Parse known args so other args or test runners don't cause errors
    args, _ = parser.parse_known_args()
    return args.port

# Core Defaults per Specification
DEFAULT_LLM_MODEL = "gemma-4-26b-a4b-it"
DEFAULT_CUSTOM_ENDPOINT = "http://127.0.0.1:8000/v1/chat/completions"

DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4096
DEFAULT_MAX_TURNS = 3
DEFAULT_RAG_CHUNKS = 5
DEFAULT_SKILL_THRESHOLD = 0.2
DEFAULT_DOC_THRESHOLD = 0.3

# Ollama and Vector DB Defaults
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_EMBEDDER_MODEL = "bge-m3"

# Directory & File Paths
DATABASE_DIR = BASE_DIR / "database"
DATABASE_DIR.mkdir(exist_ok=True)

CHROMA_DB_DIR = DATABASE_DIR / "chroma"
CHROMA_DB_DIR.mkdir(exist_ok=True)

LOG_FILE_PATH = DATABASE_DIR / "log.json"

SAMPLE_DOCS_DIR = BASE_DIR / "sample_docs"
SAMPLE_DOCS_DIR.mkdir(exist_ok=True)

SKILLS_DIR = BASE_DIR / "skills"
SKILLS_DIR.mkdir(exist_ok=True)

STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
