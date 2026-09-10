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


class BaseScraper(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def search(self, query: str, max_results: int = 20) -> List[DealItem]:
        """Esegue una ricerca asincrona sulla piattaforma e restituisce una lista di DealItem."""
        pass
