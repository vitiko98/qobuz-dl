import logging
import os
from typing import Optional, Union

import requests
from tqdm import tqdm

from .exceptions import NonStreamable
from .metadata import TrackMetadata
from .qopy import Client
from .util import safe_get

EXTENSION = {
    5: ".mp3",
    6: ".flac",
    7: ".flac",
    27: ".flac",
}

logger = logging.getLogger(__name__)


class Track:
    """Represents a downloadable track returned by the qobuz api."""

    def __init__(
        self,
        track_id: Optional[Union[str, int]] = None,
        client: Optional[Client] = None,
        meta: Optional[TrackMetadata] = None,
        **kwargs,
    ):
        """Create a track object.

        :param track_id: track id returned by Qobuz API
        :type track_id: Optional[Union[str, int]]
        :param client: qopy client
        :type client: Optional[Client]
        :param meta: TrackMetadata object
        :type meta: Optional[TrackMetadata]
        :param kwargs:
        """
        self.id = track_id
        self.client = client
        self.track_file_format = "{tracknumber}. {title}"
        for attr in ("quality", "folder", "meta"):
            setattr(self, attr, None)

        if isinstance(meta, TrackMetadata):
            self.meta = meta
        elif meta is not None:
            raise TypeError("meta can't be NoneType")

        for k, v in kwargs.items():
            self.__dict__[k] = v

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
        quality, folder = quality or self.quality, folder or self.folder
        dl_info = self.client.get_track_url(self.id, quality)

        if dl_info.get("sample") or not dl_info.get("sampling_rate"):
            logger.debug("Track is a sample: %s", dl_info)
            return

        self.temp_file = os.path.join(folder, f"{self['tracknumber']:02}.tmp")
        self.final_file = self.get_final_path(folder)

        if os.path.isfile(self.final_file):
            logger.debug("File already exists: %s", self.final_file)
            return

        self._download_file(dl_info["url"], progress_bar=progress_bar)

    def _download_file(self, url: str, progress_bar: bool = True):
        """Downloads a file given the url, optionally with a progress bar.

        :param url: url to file
        :type url: str
        :param progress_bar: turn on/off progress bar
        :type progress_bar: bool
        """
        r = requests.get(url, allow_redirects=True, stream=True)
        total = int(r.headers.get("content-length", 0))
        with open(self.temp_file, "wb") as file, tqdm(
            total=total, unit="iB", unit_scale=True, unit_divisor=1024
        ) as bar:
            for data in r.iter_content(chunk_size=1024):
                size = file.write(data)
                bar.update(size)

    def get_final_path(self) -> str:
        """Return the final filepath of the downloaded file.

        :rtype: str
        """
        return self.track_file_format.format(dict(self.meta))

    @classmethod
    def from_album_meta(cls, album: dict, pos: int, client: Client):
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


class AbstractTrackGroup:
    """A base class for classes that have some sort of tracklist.
    Think of it like a smarter list of Track objects."""

    def __getitem__(self, key):
        return getattr(self.meta, key)

    def __setitem__(self, key, val):
        setattr(self.meta, key, val)

    def get(self, *keys, default=None):
        return safe_get(self.meta, *keys, default=default)

    def set(self, key, val):
        self[key] = val

    def apply_common_metadata(self, track):
        pass


class Album(AbstractTrackGroup):
    """Represents a downloadable Qobuz album."""

    def __init__(self, client: Client, album_id: Union[str, int], **kwargs):
        """Create a new Album object.

        :param client: a qopy client instance
        :type client: Client
        :param album_id: album id returned by qobuz api
        :type album_id: Union[str, int]
        :param kwargs:
        """
        self.client = client
        self.meta = client.get_album_meta(album_id)
        if not self["streamable"]:
            raise NonStreamable(f"This album is not streamable ({album_id} ID)")

        self.tracklist = self._load_tracks()

        for k, v in kwargs.items():
            setattr(self, k, v)

    def _load_tracks(self):
        """Load tracks from the album metadata."""
        tracklist = []
        for i, track in enumerate(self.meta["tracks"]["items"]):
            tracklist.append(Track(meta=track, pos=i, client=self.client))

    @property
    def title(self) -> str:
        """Return the title of the album.

        :rtype: str
        """
        album_title = self["title"]
        version = self.get("version")
        if version is not None and version not in album_title:
            album_title = f"{album_title} ({version})"

        return album_title

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
        for track in self.tracklist:
            track.download(quality, folder, progress_bar)
            track.tag(album_meta=self.meta)
