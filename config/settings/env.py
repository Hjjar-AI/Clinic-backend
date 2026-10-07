import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env from BASE_DIR
load_dotenv(BASE_DIR / '.env')