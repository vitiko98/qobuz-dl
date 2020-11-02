# Wrapper for Qo-DL Reborn. This is a sligthly modified version
# of qopy, originally written by Sorrow446. All credits to the
# original author.

import hashlib
import time

import requests

from qo_utils import spoofbuz
from qo_utils.exceptions import (
    AuthenticationError,
    IneligibleError,
    InvalidAppIdError,
    InvalidAppSecretError,
)


class Client:
    def __init__(self, email, pwd):
        print("Getting tokens...")
        self.spoofer = spoofbuz.Spoofer()
        self.id = self.spoofer.getAppId()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:67.0) Gecko/20100101 Firefox/67.0",
                "X-App-Id": self.id,
            }
        )
        self.base = "https://www.qobuz.com/api.json/0.2/"
        self.auth(email, pwd)
        self.cfg_setup()

    def api_call(self, epoint, **kwargs):
        if epoint == "user/login?":
            params = {
                "email": kwargs["email"],
                "password": kwargs["pwd"],
                "app_id": self.id,
            }
        elif epoint == "track/get?":
            params = {"track_id": kwargs["id"]}
        elif epoint == "album/get?":
            params = {"album_id": kwargs["id"]}
        elif epoint == "track/search?":
            params = {"query": kwargs["query"], "limit": kwargs["limit"]}
        elif epoint == "album/search?":
            params = {"query": kwargs["query"], "limit": kwargs["limit"]}
        elif epoint == "userLibrary/getAlbumsList?":
            unix = time.time()
            r_sig = "userLibrarygetAlbumsList" + str(unix) + kwargs["sec"]
            r_sig_hashed = hashlib.md5(r_sig.encode("utf-8")).hexdigest()
            params = {
                "app_id": self.id,
                "user_auth_token": self.uat,
                "request_ts": unix,
                "request_sig": r_sig_hashed,
            }
        elif epoint == "track/getFileUrl?":
            unix = time.time()
            track_id = kwargs["id"]
            fmt_id = kwargs["fmt_id"]
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
        r = self.session.get(self.base + epoint, params=params)
        # Do ref header.
        if epoint == "user/login?":
            if r.status_code == 401:
                raise AuthenticationError("Invalid credentials.")
            elif r.status_code == 400:
                raise InvalidAppIdError("Invalid app id.")
            else:
                print("Logged: OK")
        elif epoint in ["track/getFileUrl?", "userLibrary/getAlbumsList?"]:
            if r.status_code == 400:
                raise InvalidAppSecretError("Invalid app secret.")
        r.raise_for_status()
        return r.json()

    def auth(self, email, pwd):
        usr_info = self.api_call("user/login?", email=email, pwd=pwd)
        if not usr_info["user"]["credential"]["parameters"]:
            raise IneligibleError("Free accounts are not eligible to download tracks.")
        self.uat = usr_info["user_auth_token"]
        self.session.headers.update({"X-User-Auth-Token": self.uat})
        self.label = usr_info["user"]["credential"]["parameters"]["short_label"]
        print("Membership: {}".format(self.label))

    def get_album_meta(self, id):
        return self.api_call("album/get?", id=id)

    def get_track_meta(self, id):
        return self.api_call("track/get?", id=id)

    def get_track_url(self, id, fmt_id):
        return self.api_call("track/getFileUrl?", id=id, fmt_id=fmt_id)

    def search_albums(self, query, limit):
        return self.api_call("album/search?", query=query, limit=limit)

    def search_tracks(self, query, limit):
        return self.api_call("track/search?", query=query, limit=limit)

    def test_secret(self, sec):
        try:
            r = self.api_call("userLibrary/getAlbumsList?", sec=sec)
            return True
        except InvalidAppSecretError:
            return False

    def cfg_setup(self):
        for secret in self.spoofer.getSecrets().values():
            if self.test_secret(secret):
                self.sec = secret
                break
