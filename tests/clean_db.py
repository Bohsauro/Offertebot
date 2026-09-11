import sqlite3
import re
from core.analyzer import DealAnalyzer

db_path = '/app/data/offertebot.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('SELECT id, title, price, search_query, url FROM deals')
rows = c.fetchall()
analyzer = DealAnalyzer()

deleted = 0
for r in rows:
    deal_id, title, price, q, url = r
    # Verifica se e' un gioco o accessorio
    is_bad = analyzer.is_accessory_or_game(title, price, q or 'console')
    
    # Verifica se e' venduto su Vinted
    is_sold = False
    if 'vinted' in deal_id.lower() or 'vinted.it' in url:
        # Se e' gia' stato segnato o controllato
        from scrapers.vinted import VintedScraper
        vs = VintedScraper()
        is_sold = vs.is_item_sold(url)
    
    if is_bad or is_sold:
        reason = 'VENDUTO' if is_sold else 'NON CONSOLE / GIOCO'
        print(f'Eliminazione [{reason}]: {title} ({price} EUR)')
        c.execute('DELETE FROM deals WHERE id = ?', (deal_id,))
        deleted += 1

conn.commit()
print(f'Pulizia completata: eliminati {deleted} su {len(rows)} annunci dal database.')
conn.close()
