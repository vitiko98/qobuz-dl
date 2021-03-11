import logging
import os
from tempfile import gettempdir
from typing import Optional, Union

import requests
from mutagen.flac import FLAC
from mutagen.id3 import ID3, ID3NoHeaderError
from tqdm import tqdm

from .constants import EXT
from .exceptions import InvalidQuality, NonStreamable
from .metadata import TrackMetadata
from .util import safe_get

logger = logging.getLogger(__name__)


# TODO: fix issue with the ClientInterface types
class Track:
    """Represents a downloadable track returned by the qobuz api."""

    def __init__(
        self,
        client,
        **kwargs,
    ):
        """Create a track object.

        :param track_id: track id returned by Qobuz API
        :type track_id: Optional[Union[str, int]]
        :param client: qopy client
        :type client: Optional
        :param meta: TrackMetadata object
        :type meta: Optional[TrackMetadata]
        :param kwargs:
        """
        self.client = client
        self.__dict__.update(kwargs)

        # adjustments after blind attribute sets
        self.track_file_format = (
            kwargs.get("filepath_format") or "{tracknumber}. {title}"
        )
        self.__is_downloaded = False
        for attr in ("quality", "folder", "meta"):
            setattr(self, attr, None)

        if isinstance(kwargs.get("meta"), TrackMetadata):
            self.meta = kwargs["meta"]
        else:
            self.meta = None

    def download(
        self,
        quality: int = 7,
        folder: Optional[Union[str, os.PathLike]] = None,
        progress_bar: bool = True,
    ):
        """Download the track

        :param quality: (5, 6, 7, 27)
        :type quality: int
        :param folder: folder to download the files to
        :type folder: Union[str, os.PathLike]
        :param progress_bar: turn on/off progress bar
        :type progress_bar: bool
        """
        assert not self.__is_downloaded
        self.quality, self.folder = quality or self.quality, folder or self.folder
        dl_info = self.client.get_track_url(self.id, quality)

        if dl_info.get("sample") or not dl_info.get("sampling_rate"):
            logger.debug("Track is a sample: %s", dl_info)
            return

        self.temp_file = os.path.join(gettempdir(), "~qdl_track.tmp")

        logger.debug("Temporary file path: %s", self.temp_file)

        if os.path.isfile(self.format_final_path()):
            logger.debug("File already exists: %s", self.final_path)
            return

        self._download_file(dl_info["url"], progress_bar=progress_bar)

    def _download_file(self, url: str, progress_bar: bool = True):
        """Downloads a file given the url, optionally with a progress bar.

        :param url: url to file
        :type url: str
        :param progress_bar: turn on/off progress bar
        :type progress_bar: bool
        """
        # Fixme: add the conditional to the progress_bar bool
        r = requests.get(url, allow_redirects=True, stream=True)
        total = int(r.headers.get("content-length", 0))
        with open(self.temp_file, "wb") as file, tqdm(
            total=total, unit="iB", unit_scale=True, unit_divisor=1024
        ) as bar:
            for data in r.iter_content(chunk_size=1024):
                size = file.write(data)
                bar.update(size)

        self.__is_downloaded = True

    def format_final_path(self) -> str:
        """Return the final filepath of the downloaded file."""
        if not hasattr(self, "final_path"):
            filename = self.track_file_format.format(self.meta.get_formatter())
            self.final_path = os.path.join(self.folder, filename) + EXT[self.quality]

        logger.debug("Formatted path: %s", self.final_path)

        return self.final_path

    @classmethod
    def from_album_meta(cls, album: dict, pos: int, client: Optional):
        """Create a new Track object from album metadata.

        :param album: album metadata returned by API
        :param pos: index of the track
        :param client: qopy client object
        :raises IndexError
        """
        track = album.get("tracks", {}).get("items", [])[pos]
        meta = TrackMetadata(album=album)
        meta.add_track_meta(album["tracks"]["items"][pos])
        return cls(track_id=track["id"], client=client, meta=meta)

    def tag(self, extra_meta=None):
        """Tag the track.

        :param extra_meta: extra metadata that should be applied
        """
        assert isinstance(self.meta, TrackMetadata), "meta must be TrackMetadata"
        assert self.__is_downloaded, "file must be downloaded before tagging"

        # TODO: add compatibility with ALAC, AAC m4a
        # TODO: implement `extra_meta`
        if self.quality in (6, 7, 27):
            codec = "mp3"
            try:
                audio = ID3(self.final_path)
            except ID3NoHeaderError:
                audio = ID3()
        elif self.quality == 5:
            codec = "flac"
            audio = FLAC(self.final_path)
        else:
            raise InvalidQuality('invalid quality "{self.quality}"')

        for k, v in self.meta.tags(codec=codec):
            audio[k] = v

        if codec == "mp3":
            audio.save(self.final_path, "v2_version=3")
        elif codec == "flac":
            audio.save()
        else:
            raise ValueError('error saving file with codec "{codec}"')

    def get(self, *keys, default=None):
        """Safe get method that allows for layered access.

        :param keys:
        :param default:
        """
        return safe_get(self.meta, *keys, default=default)

    def set(self, key, val):
        """Equivalent to __setitem__. Implemented only for
        consistency.

        :param key:
        :param val:
        """
        self[key] = val

    def __getitem__(self, key):
        """Dict-like interface for Track metadata.

        :param key:
        """
        return self.meta[key]

    def __setitem__(self, key, val):
        """Dict-like interface for Track metadata.

        :param key:
        :param val:
        """
        self.meta[key] = val


class Tracklist(list):
    """A base class for tracklist-like objects."""

    def __getitem__(self, key):
        if isinstance(key, str):
            return getattr(self, key)

        if isinstance(key, int):
            return super().__getitem__(key)

        raise TypeError(f"Bad type for key. Expected str or int, found {type(key)}")

    def __setitem__(self, key, val):
        if isinstance(key, str):
            setattr(self, key, val)

        if isinstance(key, int):
            super().__setitem__(key, val)

        raise TypeError(f"Bad type for value. Expected str or int, found {type(val)}")

    def get(self, key, default=None):
        if isinstance(key, str):
            if hasattr(self, key):
                return getattr(self, key)
            else:
                return default

        if isinstance(key, int):
            if key < len(self):
                return super().__getitem__(key)
            else:
                return default

        raise TypeError(f"Bad type for key. Expected str or int, found {type(key)}")

    def set(self, key, val):
        self.__setitem__(key, val)


class Album(Tracklist):
    """Represents a downloadable Qobuz album."""

    def __init__(self, client, **kwargs):
        """Create a new Album object.

        :param client: a qopy client instance
        :param album_id: album id returned by qobuz api
        :type album_id: Union[str, int]
        :param kwargs:
        """
        self.client = client

        for k, v in kwargs.items():
            setattr(self, k, v)

        # to improve from_api method speed
        if kwargs.get("load_on_init"):
            self.load_meta()

    def load_meta(self):
        self.meta = self.client.get_album_meta(self.id)
        self.title = self.meta.get("title")
        self.version = self.meta.get("version")

        if not self["streamable"]:
            raise NonStreamable(f"This album is not streamable ({self.id} ID)")

        self._load_tracks()

    def _load_tracks(self):
        """Load tracks from the album metadata."""
        # theres probably a cleaner way to do this
        for i in range(len(self.meta["tracks"]["items"])):
            self.append(
                Track.from_album_meta(album=self.meta, pos=i, client=self.client)
            )

    @classmethod
    def from_api(cls, item: dict, client, source: str = "qobuz"):
        """Create an Album object from the api response of Qobuz, Tidal,
        or Deezer.

        :param resp: response dict
        :type resp: dict
        :param source: in ('qobuz', 'deezer', 'tidal')
        :type source: str
        """
        if source == "qobuz":
            # only collect minimal information for identification purposes
            info = {
                "title": item["title"],
                "albumartist": item["artist"]["name"],
                "id": item["id"],  # this is the important part
                "version": item["version"],
                "url": item["url"],
                "quality": (item["maximum_bit_depth"], item["maximum_sampling_rate"]),
                "streamable": item["streamable"],
            }
        elif source == "tidal":
            info = {
                "title": item.name,
                "id": item.id,
                "albumartist": item.artist.name,
            }
        elif source == "deezer":
            info = {
                "title": item["title"],
                "albumartist": item["artist"]["name"],
                "id": item["id"],
                "url": item["link"],
                "quality": (16, 44.1),
            }
        else:
            raise ValueError

        return cls(client=client, **info)

    @property
    def title(self) -> str:
        """Return the title of the album.

        :rtype: str
        """
        album_title = self._title
        if self.get("version"):
            if self.version not in album_title:
                album_title = f"{album_title} ({self.version})"

        return album_title

    @title.setter
    def title(self, val):
        self._title = val

    def download(
        self,
        quality: int = 7,
        folder: Union[str, os.PathLike] = "downloads",
        progress_bar: bool = True,
    ):
        """Download the entire album.

        :param quality: (5, 6, 7, 27)
        :type quality: int
        :param folder: the folder to download the album to
        :type folder: Union[str, os.PathLike]
        :param progress_bar: turn on/off a tqdm progress bar
        :type progress_bar: bool
        """
        os.makedirs(folder, exist_ok=True)
        logger.debug("Directory created: %s", folder)

        for track in self:
            track.download(quality, folder, progress_bar)
            track.tag(album_meta=self.meta)

    def __repr__(self) -> str:
        return f"Album: {self.albumartist} {self.title}"


class Playlist(Tracklist):
    pass


class Artist(Tracklist):
    pass
