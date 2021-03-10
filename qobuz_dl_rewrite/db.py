import logging
import sqlite3

from qobuz_dl.color import RED, YELLOW

logger = logging.getLogger(__name__)


class QobuzDB:
    """Simple interface for the downloaded track database."""

    def __init__(self, db_path: str):
        """Create a QobuzDB object

        :param db_path: filepath of the database
        :type db_path: str
        """
        self.path = db_path

    def create(self):
        """Create a database at `self.path`"""
        with sqlite3.connect(self.path) as conn:
            try:
                conn.execute("CREATE TABLE downloads (id TEXT UNIQUE NOT NULL);")
                logger.info(f"{YELLOW}Download-IDs database created")
            except sqlite3.OperationalError:
                pass
            return self.path

    def __contains__(self, item_id: str) -> bool:
        """Checks whether the database contains an id.

        :param item_id: the id to check
        :type item_id: str
        :rtype: bool
        """
        with sqlite3.connect(self.path) as conn:
            return conn.execute(
                "SELECT id FROM downloads where id=?", (item_id,)
            ).fetchone()

    def add(self, item_id: str):
        """Adds an id to the database.

        :param item_id:
        :type item_id: str
        """
        with sqlite3.connect(self.path) as conn:
            try:
                conn.execute(
                    "INSERT INTO downloads (id) VALUES (?)",
                    (item_id,),
                )
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"{RED}Unexpected DB error: {e}")
