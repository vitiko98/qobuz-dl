import logging
import os
import re
from typing import Generator, Optional, Sequence, Tuple, Union

import click

from .clients import DeezerClient, QobuzClient, TidalClient
from .config import Config
from .constants import CONFIG_PATH, DB_PATH, QOBUZ_URL_REGEX
from .db import QobuzDB
from .downloader import Album, Artist, Playlist, Track
from .exceptions import InvalidSourceError, ParsingError

logger = logging.getLogger(__name__)


MEDIA_CLASS = {"album": Album, "playlist": Playlist, "artist": Artist, "track": Track}
CLIENTS = {"qobuz": QobuzClient, "tidal": TidalClient, "deezer": DeezerClient}
Media = Union[Album, Playlist, Artist]  # type hint


class QobuzDL:
    def __init__(
        self,
        config: Optional[Config] = None,
        source: str = "qobuz",
        database: Optional[str] = None,
    ):
        logger.debug(locals())

        self.source = source
        self.url_parse = re.compile(QOBUZ_URL_REGEX)
        self.config = config
        if self.config is None:
            self.config = Config(CONFIG_PATH)
            self.config.load()

        self.client = CLIENTS[source]()

        logger.debug("Using client: %s", self.client)

        if database is None:
            self.db = QobuzDB(DB_PATH)
        else:
            assert isinstance(database, QobuzDB)
            self.db = database

    def load_creds(self):
        if isinstance(self.client, (QobuzClient, TidalClient)):
            creds = self.config.creds(self.source)
            if not creds.get("app_id") and isinstance(self.client, QobuzClient):
                self.client.login(**creds)
                app_id, secrets = self.client.get_tokens()
                self.config["qobuz"]["app_id"] = app_id
                self.config["qobuz"]["secrets"] = secrets
                self.config.save()
            else:
                self.client.login(**creds)

    def handle_url(self, url: str):
        """Download an url

        :param url:
        :type url: str
        :raises InvalidSourceError
        :raises ParsingError
        """
        assert self.source in url, f"{url} is not a {self.source} source"
        url_type, item_id = self.parse_url(url)
        self.handle_item(url_type, item_id)

    def handle_item(self, media_type, item_id):
        arguments = {
            # TODO: add option for album/playlist subfolders
            "parent_folder": self.config.downloads["folder"],
            "quality": self.config.downloads["quality"],
            "embed_cover": self.config.metadata["embed_cover"],
        }

        item = MEDIA_CLASS[media_type](client=self.client, id=item_id)
        if isinstance(item, Artist):
            keys = self.config.filters.keys()
            filters_ = tuple(key for key in keys if self.config.filters[key])
            arguments["filters"] = filters_
            logger.debug("Added filter argument for artist/label: %s", filters_)

        logger.debug("Arguments from config: %s", arguments)

        item.load_meta()
        item.download(**arguments)

    def parse_url(self, url: str) -> Tuple[str, str]:
        """Returns the type of the url and the id.

        Compatible with urls of the form:
            https://www..com/us-en/{type}/{name}/{id}
            https://open.qobuz.com/{type}/{id}
            https://play.qobuz.com/{type}/{id}
            /us-en/{type}/-/{id}

            https://www.deezer.com/us/{type}/{id}
            https://tidal.com/browse/{type}/{id}

        :raises exceptions.ParsingError
        """
        parsed = self.url_parse.search(url)

        if parsed is not None:
            parsed = parsed.groups()

            if len(parsed) == 2:
                return tuple(parsed)  # Convert from Seq for the sake of typing

        raise ParsingError(f"Error parsing URL: `{url}`")

    def from_txt(self, filepath: Union[str, os.PathLike]):
        """
        Handle a text file containing URLs. Lines starting with `#` are ignored.

        :param filepath:
        :type filepath: Union[str, os.PathLike]
        :raises OSError
        :raises exceptions.ParsingError
        """
        with open(filepath) as txt:
            lines = (
                line for line in txt.readlines() if not line.strip().startswith("#")
            )

            click.secho(f"URLs found in text file: {len(lines)}")

            for line in lines:
                self.handle_url(line)

    def search(
        self, query: str, media_type: str = "album", limit: int = 200
    ) -> Generator:
        results = self.client.search(query, media_type, limit)

        if isinstance(results, Generator):  # QobuzClient
            for page in results:
                for item in page[f"{media_type}s"]["items"]:
                    yield MEDIA_CLASS[media_type].from_api(item, self.client)
        else:
            for item in results.get("data") or results.get("items"):
                yield MEDIA_CLASS[media_type].from_api(item, self.client)
