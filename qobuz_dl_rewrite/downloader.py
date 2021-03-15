import logging
import os
import shutil
from tempfile import gettempdir
from typing import Any, Optional, Union

import requests
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, ID3NoHeaderError
from pathvalidate import sanitize_filename

from .clients import ClientInterface
from .constants import EXT, FLAC_MAX_BLOCKSIZE
from .exceptions import InvalidQuality, NonStreamable, TooLargeCoverArt
from .metadata import TrackMetadata
from .util import quality_id, safe_get, tqdm_download

logger = logging.getLogger(__name__)


class Track:
    """Represents a downloadable track returned by the qobuz api.

    Loading metadata as a single track:
    >>> t = Track(client, id='20252078')
    >>> t.load_meta()  # load metadata from api

    Loading metadata as part of an Album:
    >>> t = Track.from_album_meta(api_track_dict, client)

    where `api_track_dict` is a track entry in an album tracklist.

    Downloading and tagging:
    >>> t.download()
    >>> t.tag()
    """

    def __init__(
        self,
        client: ClientInterface,
        **kwargs,
    ):
        """Create a track object.

        The only required parameter is client, but passing at an id is
        highly recommended. Every value in kwargs will be set as an attribute
        of the object. (TODO: make this safer)

        :param track_id: track id returned by Qobuz API
        :type track_id: Optional[Union[str, int]]
        :param client: qopy client
        :type client: ClientInterface
        :param meta: TrackMetadata object
        :type meta: Optional[TrackMetadata]
        :param kwargs: id, filepath_format, meta, quality, folder
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
            # `load_meta` must be called at some point
            logger.debug("Track: meta not provided")

    def load_meta(self):
        """Send a request to the client to get metadata for this Track."""
        assert hasattr(self, "id"), "id must be set before loading metadata"

        track_meta = self.client.get(self.id, media_type="track")
        self.meta = TrackMetadata(track=track_meta)  # meta dict -> TrackMetadata object

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
        :type folder: Optional[Union[str, os.PathLike]]
        :param progress_bar: turn on/off progress bar
        :type progress_bar: bool
        """
        assert not self.__is_downloaded
        self.quality, self.folder = quality or self.quality, folder or self.folder

        dl_info = self.client.get_file_url(self.id, quality)  # dict

        if not (dl_info.get("url") or dl_info.get("sampling_rate")) or dl_info.get(
            "sample"
        ):
            logger.debug("Track is a sample: %s", dl_info)
            return

        logger.debug("Downloadable URL found: %s", dl_info["url"])

        self.temp_file = os.path.join(gettempdir(), "~qdl_track.tmp")

        logger.debug("Temporary file path: %s", self.temp_file)

        if os.path.isfile(self.format_final_path()):
            self.__is_downloaded = True
            logger.debug("File already exists: %s", self.final_path)
            return

        tqdm_download(dl_info["url"], self.temp_file)  # downloads file
        shutil.move(self.temp_file, self.final_path)

        self.__is_downloaded = True

    def format_final_path(self) -> str:
        """Return the final filepath of the downloaded file.

        This uses the `get_formatter` method of TrackMetadata, which returns
        a dict with the keys allowed in formatter strings, and their values in
        the TrackMetadata object.
        """
        if not hasattr(self, "final_path"):
            formatter = self.meta.get_formatter()
            filename = self.track_file_format.format(**formatter)
            self.final_path = (
                os.path.join(self.folder, sanitize_filename(filename))[:250]
                + EXT[self.quality]  # file extension dict
            )

        logger.debug("Formatted path: %s", self.final_path)

        return self.final_path

    @classmethod
    def from_album_meta(cls, album: dict, pos: int, client: ClientInterface):
        """Return a new Track object initialized with info from the album dicts
        returned by the "album/get" API requests.

        :param album: album metadata returned by API
        :param pos: index of the track
        :param client: qopy client object
        :type client: ClientInterface
        :raises IndexError
        """
        track = album.get("tracks", {}).get("items", [])[pos]
        meta = TrackMetadata(album=album, track=track)
        meta.add_track_meta(album["tracks"]["items"][pos])
        return cls(client=client, meta=meta, id=track["id"])

    def tag(self, album_meta: dict = None, cover: Union[Picture, APIC] = None):
        """Tag the track using the stored metadata.

        The info stored in the TrackMetadata object (self.meta) can be updated
        with album metadata if necessary. The cover must be a mutagen cover-type
        object that already has the bytes loaded.

        :param album_meta: album metadata to update Track with
        :type album_meta: dict
        :param cover: initialized mutagen cover object
        :type cover: Union[Picture, APIC]
        """
        assert isinstance(self.meta, TrackMetadata), "meta must be TrackMetadata"
        if not self.__is_downloaded:
            logger.info(
                "Track %s not tagged because it was not downloaded", self["title"]
            )
            return

        if album_meta is not None:
            self.meta.add_album_meta(album_meta)  # extend meta with album info

        if self.quality in (6, 7, 27):
            container = "flac"
            logger.debug("Tagging file with %s container", container)
            audio = FLAC(self.final_path)
        elif self.quality == 5:
            container = "mp3"
            logger.debug("Tagging file with %s container", container)
            try:
                audio = ID3(self.final_path)
            except ID3NoHeaderError:
                audio = ID3()
        elif self.quality == 4:  # tidal and deezer
            # TODO: add compatibility with MP4 container
            raise NotImplementedError("Qualities < 320kbps not implemented")
        else:
            raise InvalidQuality(f'Invalid quality: "{self.quality}"')

        # automatically generate key, value pairs for a given container
        for k, v in self.meta.tags(container):
            audio[k] = v

        assert cover is not None  # remove this later with no_embed option
        if container == "flac":
            audio.add_picture(cover)
            audio.save()
        elif container == "mp3":
            audio.add(cover)
            audio.save(self.final_path, "v2_version=3")
        else:
            raise ValueError(f'Error saving file with container "{container}"')

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
        self.__setitem__(key, val)

    def __getitem__(self, key):
        """Dict-like interface for Track metadata.

        :param key:
        """
        return getattr(self.meta, key)

    def __setitem__(self, key, val):
        """Dict-like interface for Track metadata.

        :param key:
        :param val:
        """
        setattr(self.meta, key, val)


class Tracklist(list):
    """A base class for tracklist-like objects.

    Implements methods to give it dict-like behavior. If a Tracklist
    subclass is subscripted with [s: str], it will return an attribute s.
    If it is subscripted with [i: int] it will return the i'th track in
    the tracklist.

    >>> tlist = Tracklist()
    >>> tlist.tracklistname = 'my tracklist'
    >>> tlist.append('first track')
    >>> tlist[0]
    'first track'
    >>> tlist['tracklistname']
    'my tracklist'
    >>> tlist[2]
    IndexError
    """

    def __getitem__(self, key: Union[str, int]):
        if isinstance(key, str):
            return getattr(self, key)

        if isinstance(key, int):
            return super().__getitem__(key)

    def __setitem__(self, key: Union[str, int], val: Any):
        if isinstance(key, str):
            setattr(self, key, val)

        if isinstance(key, int):
            super().__setitem__(key, val)

    def get(self, key: Union[str, int], default: Optional[Any]):
        if isinstance(key, str):
            if hasattr(self, key):
                return getattr(self, key)

            return default

        if isinstance(key, int):
            if 0 <= key < len(self):
                return super().__getitem__(key)

            return default

    def set(self, key, val):
        self.__setitem__(key, val)

    @staticmethod
    def get_cover_obj(cover_path: str, quality: int) -> Union[Picture, APIC]:
        """Given the path to an image and a quality id, return an initialized
        cover object that can be used for every track in the album.

        :param cover_path:
        :type cover_path: str
        :param quality:
        :type quality: int
        :rtype: Union[Picture, APIC]
        """
        cover_type = {5: APIC, 6: Picture, 7: Picture, 27: Picture}

        cover = cover_type.get(quality)
        if cover is Picture:
            size_ = os.path.getsize(cover_path)
            if size_ > FLAC_MAX_BLOCKSIZE:
                raise TooLargeCoverArt(
                    "Not suitable for Picture embed: {size_ * 10 ** 6}MB"
                )
        elif cover is None:
            raise InvalidQuality(f"Quality {quality} not allowed")

        cover_obj = cover()
        cover_obj.type = 3
        cover_obj.mime = "image/jpeg"
        with open(cover_path, "rb") as img:
            cover_obj.data = img.read()

        return cover_obj


class Album(Tracklist):
    """Represents a downloadable Qobuz album."""

    def __init__(self, client: ClientInterface, **kwargs):
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
        self.meta = self.client.get(self.id, media_type="album")
        self.title = self.meta.get("title")
        self._artist = self.meta.get("artist") or self.meta.get("performer")
        self.albumartist = self._artist.get("name")
        self.version = self.meta.get("version")
        self.cover_urls = self.meta.get("image")
        self.streamable = self.meta.get("streamable")

        if not self.get("streamable", False):
            raise NonStreamable(f"This album is not streamable ({self.id} ID)")

        self._load_tracks()

    def _load_tracks(self):
        """Given an album metadata dict returned by the API, append all of its
        tracks to `self`.

        This uses a classmethod to convert an item into a Track object, which
        stores the metadata inside a TrackMetadata object.
        """
        for i in range(self.meta.get("tracks", {}).get("total", [])):
            # append method inherited from superclass list
            self.append(
                Track.from_album_meta(album=self.meta, pos=i, client=self.client)
            )

    @classmethod
    def from_api(cls, item: dict, client: ClientInterface, source: str = "qobuz"):
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
                "title": item.get("title"),
                "albumartist": item.get("artist", {}).get("name")
                or item.get("performer", {}).get("name"),  # KeyError
                "id": item.get("id"),  # this is the important part
                "version": item.get("version"),  # KeyError
                "url": item.get("url"),
                "quality": quality_id(
                    item.get("maximum_bit_depth"), item.get("maximum_sampling_rate")
                ),
                "streamable": item.get("streamable", False),
            }
        elif source == "tidal":
            info = {
                "title": item.name,
                "id": item.id,
                "albumartist": item.artist.name,
            }
        elif source == "deezer":
            info = {
                "title": item.get("title"),
                "albumartist": item.get("artist", {}).get("name"),
                "id": item.get("id"),
                "url": item.get("link"),
                "quality": 6,
            }
        else:
            raise ValueError(f"invalid source '{source}'")

        # equivalent to Album(client=client, **info)
        return cls(client=client, **info)

    @property
    def title(self) -> str:
        """Return the title of the album.

        It is formatted so that "version" keys are included.

        :rtype: str
        """
        album_title = self._title
        if self.get("version", False):  # Avoid TypeError
            if self.version.lower() not in album_title.lower():
                album_title = f"{album_title} ({self.version})"

        return album_title

    @title.setter
    def title(self, val):
        """Sets the internal _title attribute to the given value.

        :param val: title to set
        """
        self._title = val

    def download(
        self,
        quality: int = 7,
        folder: Union[str, os.PathLike] = "download",
        progress_bar: bool = True,
        tag_tracks: bool = True,
        cover_key: str = "large",
    ):
        """Download all of the tracks in the album.

        :param quality: (5, 6, 7, 27)
        :type quality: int
        :param folder: the folder to download the album to
        :type folder: Union[str, os.PathLike]
        :param progress_bar: turn on/off a tqdm progress bar
        :type progress_bar: bool
        """
        os.makedirs(folder, exist_ok=True)
        logger.debug("Directory created: %s", folder)

        # choose optimal cover size and download it
        cover = None
        cover_path = os.path.join(folder, "cover.jpg")

        if os.path.isfile(cover_path):
            logger.debug("Cover already downloaded: %s. Skipping", cover_path)

        else:
            if self.cover_urls:  # Could be []
                cover_url = self.cover_urls.get(cover_key)

                img = requests.head(cover_url)

                if int(img.headers["Content-Length"]) > 5 * 10 ** 6:  # 5MB
                    logger.debug("Requested key (%s) size is too large. Falling back")
                    cover_url = self.cover_urls.get("small")

                tqdm_download(cover_url, cover_path)

        # create a single cover object and use them for all tracks
        # TODO: avoid this method if embeded covers are not requested
        cover = self.get_cover_obj(cover_path, quality)

        for track in self:
            logger.debug("Downloading track to %s with quality %s", folder, quality)
            track.download(quality, folder, progress_bar)
            if tag_tracks:
                logger.debug("Tagging track")
                track.tag(album_meta=self.meta, cover=cover)

    def __repr__(self) -> str:
        """Return a string representation of this Album object.
        Useful for pprint and json.dumps.

        :rtype: str
        """
        # Avoid AttributeError if load_on_init key is not set
        if hasattr(self, "albumartist"):
            return f"<Album: {self.albumartist} - {self.title}>"

        return f"<Album: V/A - {self.title}>"


class Playlist(Tracklist):
    """Represents a downloadable Qobuz playlist."""

    def __init__(self, client: ClientInterface, **kwargs):
        """Create a new Playlist object.

        :param client: a qopy client instance
        :param album_id: playlist id returned by qobuz api
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
        self.meta = list(self.client.get(self.id, media_type="playlist"))[
            0
        ]  # generator
        self.name = self.meta.get("name")

        self._load_tracks()

    def _load_tracks(self):
        for track in self.meta.get("tracks", {}).get("items", []):
            logger.debug("Appending track: %s", track.get("title"))
            self.append(Track(self.client, id=track.get("id")))

        logger.debug(f"Loaded {len(self)} tracks from playlist {self.name}")

    @classmethod
    def from_api(cls, item: dict, client: ClientInterface, source: str = "qobuz"):
        """Create a Playlist object from the api response of Qobuz, Tidal,
        or Deezer.

        :param resp: response dict
        :type resp: dict
        :param source: in ('qobuz', 'deezer', 'tidal')
        :type source: str
        """
        if source in ("qobuz", "deezer"):
            info = {
                "name": item.get("name"),
                "id": item.get("id"),
            }
        elif source == "tidal":
            info = {
                "name": item.name,
                "id": item.id,
            }
        else:
            raise ValueError(f"invalid source '{source}'")

        # equivalent to Playlist(client=client, **info)
        return cls(client=client, **info)

    def __repr__(self) -> str:
        """Return a string representation of this Playlist object.
        Useful for pprint and json.dumps.

        :rtype: str
        """
        return f"<Playlist: {self.name}>"


class Artist(Tracklist):
    """Represents a downloadable Qobuz artist."""

    def __init__(self, client: ClientInterface, **kwargs):
        """Create a new Artist object.

        :param client: a qopy client instance
        :param album_id: artist id returned by qobuz api
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
        response = self.client.get(self.id, media_type="artist")
        for page in response:  # hacky solution, fix later
            self.meta = page
            self._load_albums()

        self.name = self.meta.get("name")

    def _load_albums(self):
        for album in self.meta.get("albums", {}).get("items", []):
            logger.debug("Appending album: %s", album.get("title"))
            self.append(Album(self.client, **album))

    @classmethod
    def from_api(cls, item: dict, client: ClientInterface, source: str = "qobuz"):
        """Create an Artist object from the api response of Qobuz, Tidal,
        or Deezer.

        :param resp: response dict
        :type resp: dict
        :param source: in ('qobuz', 'deezer', 'tidal')
        :type source: str
        """
        logging.debug("Loading item from API")
        if source in ("qobuz", "deezer"):
            info = {
                "name": item.get("name"),
                "id": item.get("id"),
            }
        elif source == "tidal":
            info = {
                "name": item.name,
                "id": item.id,
            }
        else:
            raise ValueError(f"invalid source '{source}'")
        logging.debug(f"Loaded info {info}")

        # equivalent to Artist(client=client, **info)
        return cls(client=client, **info)

    def __repr__(self) -> str:
        """Return a string representation of this Artist object.
        Useful for pprint and json.dumps.

        :rtype: str
        """
        return f"<Artist: {self.name}>"
