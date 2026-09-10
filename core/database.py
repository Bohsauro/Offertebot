import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import aiosqlite

from core.config import settings
from scrapers.base import DealItem

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path=None):
        self.db_path = str(db_path or settings.db_path)

    async def init_db(self):
        """Inizializza le tabelle SQLite se non esistono."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            
            # Tabella ricerche monitorate
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tracked_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    target_price REAL,
                    min_score REAL DEFAULT 7.0,
                    exclude_broken INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_checked_at TIMESTAMP
                );
            """)

            # Tabella offerte viste / notificate
            await db.execute("""
                CREATE TABLE IF NOT EXISTS deals (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    search_query TEXT NOT NULL,
                    title TEXT NOT NULL,
                    price REAL NOT NULL,
                    shipping_cost REAL DEFAULT 0.0,
                    total_price REAL NOT NULL,
                    url TEXT NOT NULL,
                    image_url TEXT,
                    location TEXT,
                    score REAL NOT NULL,
                    defect_severity TEXT,
                    defect_labels TEXT,
                    description TEXT,
                    notified INTEGER DEFAULT 0,
                    found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Indici per ricerche veloci
            await db.execute("CREATE INDEX IF NOT EXISTS idx_deals_score ON deals (score DESC);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_deals_query ON deals (search_query);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_tracked_active ON tracked_searches (is_active);")

            await db.commit()
            logger.info("Database SQLite inizializzato con successo.")

            # Inserimento ricerche di default se la tabella è vuota
            await self._seed_default_searches(db)

    async def _seed_default_searches(self, db: aiosqlite.Connection):
        cursor = await db.execute("SELECT COUNT(*) FROM tracked_searches;")
        row = await cursor.fetchone()
        count = row[0] if row else 0

        default_chat_id = settings.telegram_chat_id or "default"
        if count == 0 and settings.default_searches:
            for s in settings.default_searches:
                await db.execute("""
                    INSERT INTO tracked_searches (chat_id, query, target_price, min_score, exclude_broken, is_active)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (
                    default_chat_id,
                    s.query,
                    s.target_price,
                    settings.min_alert_score,
                    1 if s.exclude_broken else 0,
                    1 if s.enabled else 0
                ))
            await db.commit()
            logger.info(f"Caricate {len(settings.default_searches)} ricerche predefinite.")

    async def add_search(
        self,
        chat_id: str,
        query: str,
        target_price: Optional[float] = None,
        min_score: float = 7.0,
        exclude_broken: bool = False
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO tracked_searches (chat_id, query, target_price, min_score, exclude_broken, is_active)
                VALUES (?, ?, ?, ?, ?, 1);
            """, (chat_id, query.strip(), target_price, min_score, 1 if exclude_broken else 0))
            await db.commit()
            return cursor.lastrowid

    async def get_searches_by_chat_id(self, chat_id: str) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM tracked_searches WHERE chat_id = ? ORDER BY id DESC;
            """, (chat_id,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_all_active_searches(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM tracked_searches WHERE is_active = 1;
            """)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def update_last_checked(self, search_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE tracked_searches SET last_checked_at = CURRENT_TIMESTAMP WHERE id = ?;
            """, (search_id,))
            await db.commit()

    async def delete_search(self, search_id: int, chat_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                DELETE FROM tracked_searches WHERE id = ? AND chat_id = ?;
            """, (search_id, chat_id))
            await db.commit()
            return cursor.rowcount > 0

    async def toggle_search(self, search_id: int, chat_id: str) -> Optional[bool]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT is_active FROM tracked_searches WHERE id = ? AND chat_id = ?;
            """, (search_id, chat_id))
            row = await cursor.fetchone()
            if not row:
                return None
            new_state = 0 if row[0] == 1 else 1
            await db.execute("""
                UPDATE tracked_searches SET is_active = ? WHERE id = ? AND chat_id = ?;
            """, (new_state, search_id, chat_id))
            await db.commit()
            return new_state == 1

    async def is_deal_seen(self, deal_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT 1 FROM deals WHERE id = ?;", (deal_id,))
            row = await cursor.fetchone()
            return row is not None

    async def save_deal(self, deal: DealItem, notified: bool = False):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO deals (
                    id, source, search_query, title, price, shipping_cost,
                    total_price, url, image_url, location, score,
                    defect_severity, defect_labels, description, notified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                deal.id,
                deal.source,
                deal.search_query,
                deal.title,
                deal.price,
                deal.shipping_cost,
                deal.total_price,
                deal.url,
                deal.image_url,
                deal.location,
                deal.score,
                deal.defect_severity,
                json.dumps(deal.defect_labels, ensure_ascii=False),
                deal.description[:500] if deal.description else "",
                1 if notified else 0
            ))
            await db.commit()

    async def get_top_deals(
        self,
        query: Optional[str] = None,
        min_score: float = 6.0,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if query:
                cursor = await db.execute("""
                    SELECT * FROM deals
                    WHERE search_query LIKE ? AND score >= ?
                    ORDER BY score DESC, found_at DESC
                    LIMIT ?;
                """, (f"%{query}%", min_score, limit))
            else:
                cursor = await db.execute("""
                    SELECT * FROM deals
                    WHERE score >= ?
                    ORDER BY score DESC, found_at DESC
                    LIMIT ?;
                """, (min_score, limit))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


db = Database()
