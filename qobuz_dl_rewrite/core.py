import re

from clients import QobuzClient, DeezerClient, TidalClient
from downloader import Album, Track
from .db import QobuzDB


class QobuzDL:
    def __init__(
        self,
        directory="Downloads",
        quality=6,
        downloads_db=None,
        config=None
    ):
        pass

    def handle_url(self, url):
        # should be able to handle urls cross platform
        pass

    def parse_url(self, url):
        pass

    def from_txt(self, filepath):
        pass

    def search(self, query, media_type):
        pass
