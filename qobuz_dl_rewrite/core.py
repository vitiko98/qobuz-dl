import re
import logging

from .clients import QobuzClient, DeezerClient, TidalClient
from .downloader import Album, Track
from .db import QobuzDB

# ------- Testing ----------
from secrets import qobuz_email, qobuz_pwd
# --------------------------

logger = logging.getLogger(__name__)


class QobuzDL:
    def __init__(
        self,
        directory="Downloads",
        quality=6,
        downloads_db=None,
        config=None
    ):
        client = QobuzClient()
        client.login(qobuz_email, qobuz_pwd)

    def handle_url(self, url):
        # should be able to handle urls cross platform
        pass

    def parse_url(self, url):
        pass

    def from_txt(self, filepath):
        pass

    def search(self, query, media_type):
        pass
