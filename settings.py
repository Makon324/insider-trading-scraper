from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# File paths
SCRIPT_DIR = Path(__file__).resolve().parent
LINK = SCRIPT_DIR / os.getenv("LINK", "scrapes.csv")

# Scraping constants
CSV_SEP = os.getenv("CSV_SEP", ";")
NUM_PROCESSES = int(os.getenv("NUM_PROCESSES", 1))
SEC_REQUEST_DELAY = float(os.getenv("SEC_BET_REQ", 0.2))
USER_AGENT = os.getenv("USER_AGENT", "InsiderTradingBot/1.0")