import logging
import sqlite3

from qobuz_dl.color import RED, YELLOW

logger = logging.getLogger(__name__)


class QobuzDB:
    def __init__(self, db_path):
        self.path = db_path

    def create(self):
        with sqlite3.connect(self.path) as conn:
            try:
                conn.execute("CREATE TABLE downloads (id TEXT UNIQUE NOT NULL);")
                logger.info(f"{YELLOW}Download-IDs database created")
            except sqlite3.OperationalError:
                pass
            return self.path

    def __contains__(self, item_id):
        with sqlite3.connect(self.path) as conn:
            return conn.execute(
                "SELECT id FROM downloads where id=?", (item_id,)
            ).fetchone()

    def add(self, item_id):
        with sqlite3.connect(self.path) as conn:
            try:
                conn.execute(
                    "INSERT INTO downloads (id) VALUES (?)",
                    (item_id,),
                )
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"{RED}Unexpected DB error: {e}")
