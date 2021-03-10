import os

import requests
from tqdm import tqdm

from metadata import TrackMetadata
from util import safe_get
from qobuz_dl.exceptions import NonStreamable

EXTENSION = {
    5: ".mp3",
    6: ".flac",
    7: ".flac",
    27: ".flac",
}


class Track:
    def __init__(self, track_id=None, client=None, meta=None, **kwargs):
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
        track = album["tracks"]["items"][pos]
        meta = TrackMetadata(album=album)
        meta.add_track_meta(album["tracks"]["items"][pos])
        return cls(track_id=track["id"], client=client, meta=meta)

    def __getitem__(self, key):
        return self.meta[key]

    def __setitem__(self, key, val):
        self.meta[key] = val

    def get(self, *keys, default=None):
        return safe_get(self.meta, *keys, default=default)

    def set(self, key, val):
        self[key] = val


class AbstractTrackGroup:
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
    def __init__(self, client, album_id, **kwargs):
        self.client = client
        self.meta = client.get_album_meta(album_id)
        if not self["streamable"]:
            raise NonStreamable("This release is not streamable")

        self.tracklist = self._load_tracks()

        for k, v in kwargs.items():
            setattr(self, k, v)

    def _load_tracks(self):
        tracklist = []
        for i, track in enumerate(self.meta["tracks"]["items"]):
            tracklist.append(Track(meta=track, pos=i, client=self.client))

    @property
    def title(self):
        album_title = self["title"]
        version = self.get("version")
        if version is not None and version not in album_title:
            album_title = f"{album_title} ({version})"

        return album_title

    def download(self, quality=7, folder="downloads", progress_bar=True):
        os.makedirs(folder, exist_ok=True)
        for track in self.tracklist:
            track.download(quality, folder, progress_bar)
            track.tag(album_meta=self.meta)
