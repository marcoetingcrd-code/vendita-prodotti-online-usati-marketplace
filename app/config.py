import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR}/data/marketplace.db")

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_IDS = [
    cid.strip() for cid in os.getenv("OWNER_CHAT_IDS", "").split(",") if cid.strip()
]

# Uploads
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
ORIGINALS_DIR = UPLOAD_DIR / "originals"
PROCESSED_DIR = UPLOAD_DIR / "processed"
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))

# Ensure directories exist
for d in [ORIGINALS_DIR, PROCESSED_DIR, BASE_DIR / "data"]:
    d.mkdir(parents=True, exist_ok=True)
