import os

import requests
from tqdm import tqdm

from .exceptions import NonStreamable
from .metadata import TrackMetadata
from .util import safe_get

EXTENSION = {
    5: ".mp3",
    6: ".flac",
    7: ".flac",
    27: ".flac",
}


class Track:
    """Represents a downloadable track returned by the qobuz api."""

    def __init__(self, track_id=None, client=None, meta=None, **kwargs):
        """__init__.

        :param track_id: id returned by qobuz API
        :param client: qopy.Client object
        :param meta: TrackMetadata object
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
            raise Exception("meta is None")

        for k, v in kwargs.items():
            self.__dict__[k] = v

    def download(self, quality=None, folder=None, progress_bar=True):
        """Download the track.

        :param quality:
        :param folder:
        :param progress_bar:
        """
        quality, folder = quality or self.quality, folder or self.folder
        dl_info = self.client.get_track_url(self.id, quality)
        if "sample" in dl_info or not dl_info["sampling_rate"]:
            return

        self.temp_file = os.path.join(folder, f"{self['tracknumber']:02}.tmp")
        self.final_file = self.get_final_path(folder)
        if os.path.isfile(self.final_file):
            return
        self._download_file(dl_info["url"], progress_bar=progress_bar)

    def _download_file(self, url, progress_bar=True):
        r = requests.get(url, allow_redirects=True, stream=True)
        total = int(r.headers.get("content-length", 0))
        with open(self.temp_file, "wb") as file, tqdm(
            total=total, unit="iB", unit_scale=True, unit_divisor=1024
        ) as bar:
            for data in r.iter_content(chunk_size=1024):
                size = file.write(data)
                bar.update(size)

    def get_final_path(self):
        return self.track_file_format.format(dict(self.meta))

    @classmethod
    def from_album_meta(cls, album, pos, client):
        """Create a new Track object from album metadata.

        :param album: album metadata returned by API
        :param pos: index of the track
        :param client: qopy client
        """
        track = album["tracks"]["items"][pos]
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

    def __init__(self, client, album_id, **kwargs):
        """Create a new Album object.

        :param client: a qopy client instance
        :param album_id: album id returned by qobuz api
        :param kwargs:
        """
        self.client = client
        self.meta = client.get_album_meta(album_id)
        if not self["streamable"]:
            raise NonStreamable("This release is not streamable")

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
        self, quality: int = 7, folder: str = "downloads", progress_bar: bool = True
    ):
        """Download the entire album.

        :param quality: (5, 6, 7, 27)
        :type quality: int
        :param folder: the folder to download the album to
        :type folder: str
        :param progress_bar: turn on/off a tqdm progress bar
        :type progress_bar: bool
        """
        os.makedirs(folder, exist_ok=True)
        for track in self.tracklist:
            track.download(quality, folder, progress_bar)
            track.tag(album_meta=self.meta)
