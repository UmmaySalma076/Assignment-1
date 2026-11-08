from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "tasks.db"


class Settings:
    database_path: str = str(DEFAULT_DATABASE_PATH)


settings = Settings()
