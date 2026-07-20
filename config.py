import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "").strip().rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# Treat PDF as scanned when embedded text is shorter than this
MIN_TEXT_CHARS = int(os.getenv("MIN_TEXT_CHARS", "40"))
PDF_RENDER_SCALE = float(os.getenv("PDF_RENDER_SCALE", "2.0"))
