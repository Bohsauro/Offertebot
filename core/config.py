import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "offertebot.db"
CONFIG_FILE = BASE_DIR / "config.yaml"


class SearchTarget(BaseModel):
    query: str
    target_price: Optional[float] = None
    exclude_broken: bool = False
    enabled: bool = True


class DamageCategory(BaseModel):
    penalty: float = 0.0
    bonus: float = 0.0
    label: str
    keywords: List[str] = Field(default_factory=list)


class Settings:
    def __init__(self):
        self.telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.check_interval_minutes: int = int(os.getenv("CHECK_INTERVAL_MINUTES", "15"))
        self.min_alert_score: float = float(os.getenv("MIN_ALERT_SCORE", "7.0"))
        self.exclude_broken: bool = os.getenv("EXCLUDE_BROKEN", "false").lower() in ("true", "1", "yes")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

        self.db_path: Path = DB_PATH
        self.config_data: Dict[str, Any] = self._load_yaml_config()

    def _load_yaml_config(self) -> Dict[str, Any]:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    @property
    def damage_categories(self) -> Dict[str, DamageCategory]:
        raw = self.config_data.get("damage_keywords", {})
        categories = {}
        for cat_name, cat_data in raw.items():
            categories[cat_name] = DamageCategory(
                penalty=cat_data.get("penalty", 0.0),
                bonus=cat_data.get("bonus", 0.0),
                label=cat_data.get("label", cat_name),
                keywords=[k.lower().strip() for k in cat_data.get("keywords", [])]
            )
        return categories

    @property
    def default_searches(self) -> List[SearchTarget]:
        raw = self.config_data.get("default_searches", [])
        return [SearchTarget(**item) for item in raw]

    @property
    def default_estimated_shipping_international(self) -> float:
        return float(self.config_data.get("general", {}).get("default_estimated_shipping_international", 9.99))


settings = Settings()
