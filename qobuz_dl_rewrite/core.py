import logging
import re
# ------- Testing ----------
from secrets import qobuz_email, qobuz_id, qobuz_pwd, qobuz_secrets
from typing import Tuple

from .clients import QobuzClient
from .constants import QOBUZ_URL_REGEX
from .db import QobuzDB
from .downloader import Album, Artist, Playlist

# --------------------------

logger = logging.getLogger(__name__)


MEDIA_CLASS = {"album": Album, 'playlist': Playlist, 'artist': Artist}


class QobuzDL:
    def __init__(
        self, directory="Downloads", quality=6, downloads_db=None, config=None
    ):
        self.client = QobuzClient()
        self.client.login(
            qobuz_email, qobuz_pwd, app_id=qobuz_id, secrets=qobuz_secrets
        )
        self.qobuz_url_parse = re.compile(QOBUZ_URL_REGEX)

    def handle_url(self, url: str):
        url_type, item_id = self.parse_url(url)
        item = MEDIA_CLASS[url_type](client=self.client, id=item_id)
        item.load_meta()
        item.download(quality=6)

    def parse_url(self, url: str) -> Tuple[str, str]:
        """Returns the type of the url and the id.

        Compatible with urls of the form:
            https://www.qobuz.com/us-en/{type}/{name}/{id}
            https://open.qobuz.com/{type}/{id}
            https://play.qobuz.com/{type}/{id}
            /us-en/{type}/-/{id}
        """

        r = self.qobuz_url_parse.search(url)
        return r.groups()

    def from_txt(self, filepath):
        with open(filepath) as txt:
            return self.qobuz_url_parse.findall(txt.read())

    def search(self, query, media_type):
        search_results = self.client.search(query, media_type=media_type)
        key = media_type + "s"
        return (
            MEDIA_CLASS[media_type].from_api(item, self.client)
            for item in search_results[key]["items"]
        )
