from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Telegram bot token
bot_token = "7969743275:AAG2R5TA_cPqDZ1fq2gjCSa4B-iPnCQREo4"

# Example: ADMIN_IDS = {123456789, 987654321}
ADMIN_IDS = set()

# Main class representative (entry year 1402 dentistry)
MAIN_REP_STUDENT_NUMBER = "40211272003"
MAIN_REP_TELEGRAM_ID = 6230456748

# Core data paths (kept under a single folder for easy backup/migration)
DB_PATH = str(DATA_DIR / "students.db")
DEFAULT_STUDENTS_CSV = str(DATA_DIR / "default_students.csv")

# Optional fallback image used when a student has no Telegram profile photo.
# Keep runtime assets under data/ to preserve the repository contract.
DEFAULT_VERIFICATION_PHOTO_PATH = DATA_DIR / "default_verification_photo.png"
