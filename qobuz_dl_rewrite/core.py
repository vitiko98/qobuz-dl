import logging
import os
import re

# ------- Testing ----------
from typing import Generator, Sequence, Tuple, Union

from .clients import QobuzClient
from .constants import QOBUZ_URL_REGEX
from .db import QobuzDB
from .downloader import Album, Artist, Playlist
from .exceptions import ParsingError

# --------------------------

logger = logging.getLogger(__name__)


MEDIA_CLASS = {"album": Album, "playlist": Playlist, "artist": Artist}


class QobuzDL:
    def __init__(
        self,
        creds: Tuple[str, str],
        directory="Downloads",
        quality=6,
        downloads_db=None,
        config=None,
        **kwargs,
    ):
        self.client = QobuzClient()
        self.client.login(creds[0], creds[1], **kwargs)
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

        :raises exceptions.ParsingError
        """
        parsed = self.qobuz_url_parse.search(url)

        if parsed is not None:
            parsed = parsed.groups()

            if len(parsed) == 2:
                return tuple(parsed)  # Convert from Seq for the sake of typing

        raise ParsingError(f"Error parsing URL: `{url}`")

    def from_txt(self, filepath: Union[str, os.PathLike]) -> Sequence[Tuple[str, str]]:
        """
        Returns a sequence of tuples from a text file containing URLs. Lines
        starting with `#` are ignored.

        :param filepath:
        :type filepath: Union[str, os.PathLike]
        :rtype: Sequence[tuple]
        :raises OSError
        :raises exceptions.ParsingError
        """
        with open(filepath) as txt:
            lines = [
                line.replace("\n", "")
                for line in txt.readlines()
                if not line.strip().startswith("#")
            ]

            logger.debug("Parsed lines from text file: %d", len(lines))

            parsed = self.qobuz_url_parse.findall(",".join(lines))
            if parsed:
                logger.debug("Parsed URLs from regex: %s", parsed)
                return parsed

        raise ParsingError("Error parsing URLs from file `{filepath}`")

    def search(self, query: str, media_type: str, limit: int = 200) -> Generator:
        search_results = self.client.search(query, media_type=media_type, limit=limit)
        key = media_type + "s"
        return (
            MEDIA_CLASS[media_type].from_api(item, self.client)
            for item in search_results[key]["items"]
        )
