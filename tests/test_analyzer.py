import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.base import DealItem
from core.analyzer import DealAnalyzer


def test_analyzer_damage_detection():
    analyzer = DealAnalyzer()

    # Caso 1: Prodotto rotto / per ricambi
    item_broken = DealItem(
        id="1",
        title="iPhone 13 128GB - Display rotto non funzionante",
        price=100.0,
        shipping_cost=10.0,
        description="Il telefono ha preso una botta, schermo nero non si accende, vendo per ricambi.",
        source="subito"
    )
    score = analyzer.calculate_score(item_broken, target_price=400.0)
    assert item_broken.defect_severity == "CRITICAL"
    assert score <= 3.5  # Non deve essere valutato come un affare anche se costa solo 100€

    # Caso 2: Prodotto con negazione ("senza graffi", "perfetto")
    item_clean = DealItem(
        id="2",
        title="iPhone 13 128GB Perfetto pari al nuovo",
        price=280.0,
        shipping_cost=5.0,
        description="Senza graffi, nessun difetto, batteria 98% con scontrino e scatola.",
        source="subito"
    )
    score_clean = analyzer.calculate_score(item_clean, target_price=400.0)
    assert item_clean.defect_severity in ("MINT", "NONE")
    assert score_clean >= 8.0  # Ottimo affare!

    # Caso 3: Prodotto con normale usura
    item_wear = DealItem(
        id="3",
        title="iPhone 13 128GB",
        price=320.0,
        shipping_cost=0.0,
        description="Funziona perfettamente, presenta normali segni di usura e qualche micrograffio sulla scocca.",
        source="subito"
    )
    score_wear = analyzer.calculate_score(item_wear, target_price=400.0)
    assert item_wear.defect_severity == "MINOR"
    assert 6.0 <= score_wear <= 8.5


if __name__ == "__main__":
    test_analyzer_damage_detection()
    print("All analyzer tests passed successfully!")
