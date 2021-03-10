# Wrapper for Qo-DL Reborn. This is a sligthly modified version
# of qopy, originally written by Sorrow446. All credits to the
# original author.

import hashlib
import logging
import time

import requests

from .exceptions import (AuthenticationError, IneligibleError,
                         InvalidAppIdError, InvalidAppSecretError,
                         InvalidQuality)
from .spoofbuz import Spoofer

logger = logging.getLogger(__name__)


class ClientInterface:
    """Common API for clients of all platforms."""

    def search(self, query: str, type='album'):
        """Search API for query.

        :param query:
        :type query: str
        :param type:
        """
        pass

    def get(self, meta_id, type='album'):
        """Get metadata.

        :param meta_id:
        :param type:
        """
        pass

    def get_file_url(self, track_id):
        pass


class SecureClientInterface(ClientInterface):
    def login(self, **kwargs):
        """Authenticate the client.

        :param kwargs:
        """
        pass


class QobuzClient(SecureClientInterface):
    # ------- Public Methods -------------
    def login(self, email: str, pwd: str, **kwargs):
        logger.info("Logging...")
        if not kwargs.get('app_id') or kwargs.get('secrets'):
            spoofer = Spoofer()
            kwargs['app_id'] = spoofer.get_app_id()
            kwargs['secrets'] = spoofer.get_secrets()

        self.id = kwargs['app_id']
        self.secrets = kwargs['secrets']
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0) Gecko/20100101 Firefox/83.0",
                "X-App-Id": self.id,
            }
        )
        self.base = "https://www.qobuz.com/api.json/0.2/"
        self.auth(email, pwd)
        self.cfg_setup()

    def search(self, query: str, media_type: str = 'album', limit: int = 500):
        if media_type.endswith('s'):
            media_type = media_type[:-1]

        f_map = {
            'album': self.search_albums,
            'artist': self.search_artists,
            'playlist': self.search_playlists,
            'track': self.search_tracks,
        }

        return f_map[media_type](query)

    def get(self, meta_id: str, media_type: str = 'album'):
        f_map = {
            'album': self.get_album_meta,
            'artist': self.get_artist_meta,
            'playlist': self.get_playlist_meta,
            'track': self.get_track_meta,
        }
        return f_map[media_type](meta_id)

    def get_file_url(self, meta_id: str, quality: int = 7):
        return self.api_call("track/getFileUrl", id=id, fmt_id=quality)

    # ---------- Private Methods ---------------
    def api_call(self, epoint, **kwargs):
        if epoint == "user/login":
            params = {
                "email": kwargs["email"],
                "password": kwargs["pwd"],
                "app_id": self.id,
            }
        elif epoint == "track/get":
            params = {"track_id": kwargs["id"]}
        elif epoint == "album/get":
            params = {"album_id": kwargs["id"]}
        elif epoint == "playlist/get":
            params = {
                "extra": "tracks",
                "playlist_id": kwargs["id"],
                "limit": 500,
                "offset": kwargs["offset"],
            }
        elif epoint == "artist/get":
            params = {
                "app_id": self.id,
                "artist_id": kwargs["id"],
                "limit": 500,
                "offset": kwargs["offset"],
                "extra": "albums",
            }
        elif epoint == "label/get":
            params = {
                "label_id": kwargs["id"],
                "limit": 500,
                "offset": kwargs["offset"],
                "extra": "albums",
            }
        elif epoint == "userLibrary/getAlbumsList":
            unix = time.time()
            r_sig = "userLibrarygetAlbumsList" + str(unix) + kwargs["sec"]
            r_sig_hashed = hashlib.md5(r_sig.encode("utf-8")).hexdigest()
            params = {
                "app_id": self.id,
                "user_auth_token": self.uat,
                "request_ts": unix,
                "request_sig": r_sig_hashed,
            }
        elif epoint == "track/getFileUrl":
            unix = time.time()
            track_id = kwargs["id"]
            fmt_id = kwargs["fmt_id"]
            if int(fmt_id) not in (5, 6, 7, 27):
                raise InvalidQuality("Invalid quality id: choose between 5, 6, 7 or 27")
            r_sig = "trackgetFileUrlformat_id{}intentstreamtrack_id{}{}{}".format(
                fmt_id, track_id, unix, self.sec
            )
            r_sig_hashed = hashlib.md5(r_sig.encode("utf-8")).hexdigest()
            params = {
                "request_ts": unix,
                "request_sig": r_sig_hashed,
                "track_id": track_id,
                "format_id": fmt_id,
                "intent": "stream",
            }
        else:
            params = kwargs
        r = self.session.get(self.base + epoint, params=params)
        if epoint == "user/login":
            if r.status_code == 401:
                raise AuthenticationError("Invalid credentials.")
            elif r.status_code == 400:
                raise InvalidAppIdError("Invalid app id.")
            else:
                logger.info(f"Logged: OK")
        elif epoint in ["track/getFileUrl", "userLibrary/getAlbumsList"]:
            if r.status_code == 400:
                raise InvalidAppSecretError("Invalid app secret.")
        r.raise_for_status()
        return r.json()

    def auth(self, email, pwd):
        usr_info = self.api_call("user/login", email=email, pwd=pwd)
        if not usr_info["user"]["credential"]["parameters"]:
            raise IneligibleError("Free accounts are not eligible to download tracks.")
        self.uat = usr_info["user_auth_token"]
        self.session.headers.update({"X-User-Auth-Token": self.uat})
        self.label = usr_info["user"]["credential"]["parameters"]["short_label"]
        logger.info(f"Membership: {self.label}")

    def multi_meta(self, epoint, key, id, type):
        total = 1
        offset = 0
        while total > 0:
            if type in ["tracks", "albums"]:
                j = self.api_call(epoint, id=id, offset=offset, type=type)[type]
            else:
                j = self.api_call(epoint, id=id, offset=offset, type=type)
            if offset == 0:
                yield j
                total = j[key] - 500
            else:
                yield j
                total -= 500
            offset += 500

    def get_album_meta(self, id):
        return self.api_call("album/get", id=id)

    def get_track_meta(self, id):
        return self.api_call("track/get", id=id)

    def get_artist_meta(self, id):
        return self.multi_meta("artist/get", "albums_count", id, None)

    def get_plist_meta(self, id):
        return self.multi_meta("playlist/get", "tracks_count", id, None)

    def get_label_meta(self, id):
        return self.multi_meta("label/get", "albums_count", id, None)

    def search_albums(self, query, limit):
        return self.api_call("album/search", query=query, limit=limit)

    def search_artists(self, query, limit):
        return self.api_call("artist/search", query=query, limit=limit)

    def search_playlists(self, query, limit):
        return self.api_call("playlist/search", query=query, limit=limit)

    def search_tracks(self, query, limit):
        return self.api_call("track/search", query=query, limit=limit)

    def get_favorite_albums(self, offset, limit):
        return self.api_call(
            "favorite/getUserFavorites", type="albums", offset=offset, limit=limit
        )

    def get_favorite_tracks(self, offset, limit):
        return self.api_call(
            "favorite/getUserFavorites", type="tracks", offset=offset, limit=limit
        )

    def get_favorite_artists(self, offset, limit):
        return self.api_call(
            "favorite/getUserFavorites", type="artists", offset=offset, limit=limit
        )

    def get_user_playlists(self, limit):
        return self.api_call("playlist/getUserPlaylists", limit=limit)

    def test_secret(self, sec):
        try:
            r = self.api_call("userLibrary/getAlbumsList", sec=sec)
            return True
        except InvalidAppSecretError:
            return False

    def cfg_setup(self):
        for secret in self.secrets:
            if self.test_secret(secret):
                self.sec = secret
                break
        if not hasattr(self, "sec"):
            raise InvalidAppSecretError("Invalid app secret.")


class DeezerClient(ClientInterface):
    pass


class TidalClient(SecureClientInterface):
    pass

