from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class DealItem:
    id: str
    title: str
    price: float
    shipping_cost: float = 0.0
    total_price: float = 0.0
    currency: str = "EUR"
    url: str = ""
    image_url: Optional[str] = None
    source: str = ""  # 'subito', 'ebay', 'wallapop', 'vinted'
    description: str = ""
    location: str = "Italia"
    is_international: bool = False
    condition_text: str = ""
    is_new: bool = False

    # Campi calcolati da DealAnalyzer
    detected_defects: List[str] = field(default_factory=list)
    defect_severity: str = "NONE"  # 'CRITICAL', 'MODERATE', 'MINOR', 'MINT', 'NONE'
    defect_labels: List[str] = field(default_factory=list)
    score: float = 5.0
    score_breakdown: Dict[str, Any] = field(default_factory=dict)
    search_query: str = ""
    found_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if self.total_price <= 0 and self.price > 0:
            self.total_price = round(self.price + self.shipping_cost, 2)

    @classmethod
    def from_db_row(cls, d: Dict[str, Any]) -> "DealItem":
        import json
        labels = []
        raw_labels = d.get("defect_labels")
        if raw_labels:
            try:
                labels = json.loads(raw_labels) if isinstance(raw_labels, str) else raw_labels
            except Exception:
                labels = []

        return cls(
            id=d["id"],
            title=d["title"],
            price=d.get("price", 0.0),
            shipping_cost=d.get("shipping_cost", 0.0),
            total_price=d.get("total_price", 0.0),
            url=d.get("url", ""),
            image_url=d.get("image_url"),
            source=d.get("source", ""),
            description=d.get("description", ""),
            location=d.get("location") or "Italia",
            score=d.get("score", 5.0),
            defect_severity=d.get("defect_severity") or "NONE",
            defect_labels=labels,
            search_query=d.get("search_query", "")
        )


class BaseScraper(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def search(self, query: str, max_results: int = 20) -> List[DealItem]:
        """Esegue una ricerca asincrona sulla piattaforma e restituisce una lista di DealItem."""
        pass
