import logging
import re
import json

from .constants import COPYRIGHT, PHON_COPYRIGHT


logger = logging.getLogger(__name__)


class TrackMetadata:
    """Contains all of the metadata needed to tag the file."""

    def __init__(self, track=None, album=None):
        if track and album is None:
            return

        if track is not None:
            self.add_track_meta(track)
            # prefer track['album'] over album
            if "album" in track:
                album = track.get("album")

        if album is not None:
            self.add_album_meta(album)

    def add_album_meta(self, album):
        self.album = album.get("title")
        self.tracktotal = str(album.get("tracks_count", 1))
        self.genre = album.get("genres_list", [])
        self.date = album.get("release_date_original")
        self.copyright = album.get("copyright")
        self.albumartist = album.get("artist", {}).get("name")

        if album.get("label"):
            self.label = album["label"].get("name")

    def add_track_meta(self, track):
        self.title = track.get("title")
        if track.get("version"):
            self.title = f"{self.title} ({track['version']})"
        if track.get("work"):
            self.title = f"{track['work']}: {self.title}"

        self.tracknumber = str(track.get("track_number", 1))
        self.discnumber = str(track.get("media_number", 1))
        try:
            self.artist = track["performer"]["name"]
        except KeyError:
            if hasattr(self, "albumartist"):
                self.artist = self.albumartist

    @property
    def artist(self):
        if self._artist is None and self.albumartist is not None:
            return self.albumartist
        elif self._artist is not None:
            return self._artist

    @artist.setter
    def artist(self, val):
        self._artist = val

    @property
    def genre(self) -> str:
        genres = re.findall(r"([^\u2192\/]+)", "/".join(self._genres))
        no_repeats = []
        [no_repeats.append(g) for g in genres if g not in no_repeats]
        return ", ".join(no_repeats)

    @genre.setter
    def genre(self, val: list):
        assert type(val) == list
        self._genres = val

    @property
    def copyright(self) -> str:
        if hasattr(self, "_copyright"):
            cr = self.__copyright.replace("(P)", PHON_COPYRIGHT)
            cr = self.__copyright.replace("(C)", COPYRIGHT)
        else:
            cr = None
        return cr

    @copyright.setter
    def copyright(self, val: str):
        self.__copyright = val

    @property
    def year(self):
        if hasattr(self, "_year"):
            return self._year

        return self.date[:4]

    @year.setter
    def year(self, val):
        self._year = val

    def __setitem__(self, key, val):
        setattr(self, key, val)

    def __getitem__(self, key):
        return getattr(self, key)

    def __repr__(self):
        return json.dumps(self.__dict__, indent=2)
