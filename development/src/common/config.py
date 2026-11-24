from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

def load_config():
    load_dotenv(ROOT / '.env')
