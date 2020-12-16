import os
import re
import string
import sys
import time

import requests
from bs4 import BeautifulSoup as bso
from pathvalidate import sanitize_filename

import qobuz_dl.spoofbuz as spoofbuz
from qobuz_dl import downloader, qopy

from mutagen.flac import FLAC
from mutagen.mp3 import EasyMP3

WEB_URL = "https://play.qobuz.com/"
ARTISTS_SELECTOR = "td.chartlist-artist > a"
TITLE_SELECTOR = "td.chartlist-name > a"
EXTENSIONS = (".mp3", ".flac")


class PartialFormatter(string.Formatter):
    def __init__(self, missing="n/a", bad_fmt="n/a"):
        self.missing, self.bad_fmt = missing, bad_fmt

    def get_field(self, field_name, args, kwargs):
        try:
            val = super(PartialFormatter, self).get_field(field_name, args, kwargs)
        except (KeyError, AttributeError):
            val = None, field_name
        return val

    def format_field(self, value, spec):
        if not value:
            return self.missing
        try:
            return super(PartialFormatter, self).format_field(value, spec)
        except ValueError:
            if self.bad_fmt:
                return self.bad_fmt
            raise


class QobuzDL:
    def __init__(
        self,
        directory="Qobuz Downloads",
        quality=6,
        embed_art=False,
        lucky_limit=1,
        lucky_type="album",
        interactive_limit=20,
        ignore_singles_eps=False,
        no_m3u_for_playlists=False,
        quality_fallback=True,
    ):
        self.directory = self.create_dir(directory)
        self.quality = quality
        self.embed_art = embed_art
        self.lucky_limit = lucky_limit
        self.lucky_type = lucky_type
        self.interactive_limit = interactive_limit
        self.ignore_singles_eps = ignore_singles_eps
        self.no_m3u_for_playlists = no_m3u_for_playlists
        self.quality_fallback = quality_fallback

    def initialize_client(self, email, pwd, app_id, secrets):
        self.client = qopy.Client(email, pwd, app_id, secrets)

    def get_tokens(self):
        spoofer = spoofbuz.Spoofer()
        self.app_id = spoofer.getAppId()
        self.secrets = [
            secret for secret in spoofer.getSecrets().values() if secret
        ]  # avoid empty fields

    def create_dir(self, directory=None):
        fix = os.path.normpath(directory)
        os.makedirs(fix, exist_ok=True)
        return fix

    def get_id(self, url):
        return re.match(
            r"https?://(?:w{0,3}|play|open)\.qobuz\.com/(?:(?:album|track|artist"
            "|playlist|label)/|[a-z]{2}-[a-z]{2}/album/-?\w+(?:-\w+)*-?/|user/"
            "library/favorites/)(\w+)",
            url,
        ).group(1)

    def download_from_id(self, item_id, album=True, alt_path=None):
        downloader.download_id_by_type(
            self.client,
            item_id,
            self.directory if not alt_path else alt_path,
            str(self.quality),
            album,
            self.embed_art,
            self.ignore_singles_eps,
            self.quality_fallback,
        )

    def handle_url(self, url):
        possibles = {
            "playlist": {
                "func": self.client.get_plist_meta,
                "iterable_key": "tracks",
            },
            "artist": {
                "func": self.client.get_artist_meta,
                "iterable_key": "albums",
            },
            "label": {
                "func": self.client.get_label_meta,
                "iterable_key": "albums",
            },
            "album": {"album": True, "func": None, "iterable_key": None},
            "track": {"album": False, "func": None, "iterable_key": None},
        }
        try:
            url_type = url.split("/")[3]
            type_dict = possibles[url_type]
            item_id = self.get_id(url)
        except (KeyError, IndexError):
            print(
                'Invalid url: "{}". Use urls from https://play.qobuz.com!'.format(url)
            )
            return
        if type_dict["func"]:
            content = [item for item in type_dict["func"](item_id)]
            content_name = content[0]["name"]
            print(
                "\nDownloading all the music from {} ({})!".format(
                    content_name, url_type
                )
            )
            new_path = self.create_dir(
                os.path.join(self.directory, sanitize_filename(content_name))
            )
            items = [item[type_dict["iterable_key"]]["items"] for item in content][0]
            print("{} downloads in queue".format(len(items)))
            for item in items:
                self.download_from_id(
                    item["id"],
                    True if type_dict["iterable_key"] == "albums" else False,
                    new_path,
                )
            if url_type == "playlist":
                self.make_m3u(new_path)
        else:
            self.download_from_id(item_id, type_dict["album"])

    def download_list_of_urls(self, urls):
        if not urls or not isinstance(urls, list):
            print("Nothing to download")
            return
        for url in urls:
            if "last.fm" in url:
                self.download_lastfm_pl(url)
            elif os.path.isfile(url):
                self.download_from_txt_file(url)
            else:
                self.handle_url(url)

    def download_from_txt_file(self, txt_file):
        with open(txt_file, "r") as txt:
            try:
                urls = txt.read().strip().split()
            except Exception as e:
                print("Invalid text file: " + str(e))
                return
            print(
                'qobuz-dl will download {} urls from file: "{}"\n'.format(
                    len(urls), txt_file
                )
            )
            self.download_list_of_urls(urls)

    def lucky_mode(self, query, download=True):
        if len(query) < 3:
            sys.exit("Your search query is too short or invalid!")

        print(
            'Searching {}s for "{}".\n'
            "qobuz-dl will attempt to download the first {} results.".format(
                self.lucky_type, query, self.lucky_limit
            )
        )
        results = self.search_by_type(query, self.lucky_type, self.lucky_limit, True)

        if download:
            self.download_list_of_urls(results)

        return results

    def format_duration(self, duration):
        return time.strftime("%H:%M:%S", time.gmtime(duration))

    def search_by_type(self, query, item_type, limit=10, lucky=False):
        if len(query) < 3:
            print("Your search query is too short or invalid!")
            return

        possibles = {
            "album": {
                "func": self.client.search_albums,
                "album": True,
                "key": "albums",
                "format": "{artist[name]} - {title}",
                "requires_extra": True,
            },
            "artist": {
                "func": self.client.search_artists,
                "album": True,
                "key": "artists",
                "format": "{name} - ({albums_count} releases)",
                "requires_extra": False,
            },
            "track": {
                "func": self.client.search_tracks,
                "album": False,
                "key": "tracks",
                "format": "{performer[name]} - {title}",
                "requires_extra": True,
            },
            "playlist": {
                "func": self.client.search_playlists,
                "album": False,
                "key": "playlists",
                "format": "{name} - ({tracks_count} releases)",
                "requires_extra": False,
            },
        }

        try:
            mode_dict = possibles[item_type]
            results = mode_dict["func"](query, limit)
            iterable = results[mode_dict["key"]]["items"]
            item_list = []
            for i in iterable:
                fmt = PartialFormatter()
                text = fmt.format(mode_dict["format"], **i)
                if mode_dict["requires_extra"]:

                    text = "{} - {} [{}]".format(
                        text,
                        self.format_duration(i["duration"]),
                        "HI-RES" if i["hires_streamable"] else "LOSSLESS",
                    )

                url = "{}{}/{}".format(WEB_URL, item_type, i.get("id", ""))
                item_list.append({"text": text, "url": url} if not lucky else url)
            return item_list
        except (KeyError, IndexError):
            print("Invalid mode: " + item_type)
            return

    def interactive(self, download=True):
        try:
            from pick import pick
        except (ImportError, ModuleNotFoundError):
            if os.name == "nt":
                print('Please install curses with "pip3 install windows-curses"')
                return
            raise

        qualities = [
            {"q_string": "320", "q": 5},
            {"q_string": "Lossless", "q": 6},
            {"q_string": "Hi-res =< 96kHz", "q": 7},
            {"q_string": "Hi-Res > 96 kHz", "q": 27},
        ]

        def get_title_text(option):
            return option.get("text")

        def get_quality_text(option):
            return option.get("q_string")

        try:
            item_types = ["Albums", "Tracks", "Artists", "Playlists"]
            selected_type = pick(item_types, "I'll search for:\n[press Intro]")[0][
                :-1
            ].lower()
            print("Ok, we'll search for " + selected_type + "s")
            final_url_list = []
            while True:
                query = input("\nEnter your search: [Ctrl + c to quit]\n- ")
                print("Searching...")
                options = self.search_by_type(
                    query, selected_type, self.interactive_limit
                )
                if not options:
                    print("Nothing found!")
                    continue
                title = (
                    '*** RESULTS FOR "{}" ***\n\n'
                    "Select [space] the item(s) you want to download "
                    "(one or more)\nPress Ctrl + c to quit\n"
                    "Don't select anything to try another search".format(query.title())
                )
                selected_items = pick(
                    options,
                    title,
                    multiselect=True,
                    min_selection_count=0,
                    options_map_func=get_title_text,
                )
                if len(selected_items) > 0:
                    [final_url_list.append(i[0]["url"]) for i in selected_items]
                    y_n = pick(
                        ["Yes", "No"],
                        "Items were added to queue to be downloaded. Keep searching?",
                    )
                    if y_n[0][0] == "N":
                        break
                else:
                    print("\nOk, try again...")
                    continue
            if final_url_list:
                desc = (
                    "Select [intro] the quality (the quality will be automat"
                    "ically\ndowngraded if the selected is not found)"
                )
                self.quality = pick(
                    qualities,
                    desc,
                    default_index=1,
                    options_map_func=get_quality_text,
                )[0]["q"]

                if download:
                    self.download_list_of_urls(final_url_list)

                return final_url_list
        except KeyboardInterrupt:
            print("\nBye")
            return

    def download_lastfm_pl(self, playlist_url):
        # Apparently, last fm API doesn't have a playlist endpoint. If you
        # find out that it has, please fix this!
        r = requests.get(playlist_url)
        soup = bso(r.content, "html.parser")
        artists = [artist.text for artist in soup.select(ARTISTS_SELECTOR)]
        titles = [title.text for title in soup.select(TITLE_SELECTOR)]

        if len(artists) == len(titles) and artists:
            track_list = [
                artist + " " + title for artist, title in zip(artists, titles)
            ]

        if not track_list:
            print("Nothing found")
            return

        pl_title = sanitize_filename(soup.select_one("h1").text)
        pl_directory = os.path.join(self.directory, pl_title)
        print("Downloading playlist: {} ({} tracks)".format(pl_title, len(track_list)))

        for i in track_list:
            track_id = self.get_id(self.search_by_type(i, "track", 1, lucky=True)[0])
            if track_id:
                self.download_from_id(track_id, False, pl_directory)

        self.make_m3u(pl_directory)

    def make_m3u(self, pl_directory):
        if self.no_m3u_for_playlists:
            return

        track_list = ["#EXTM3U"]
        rel_folder = os.path.basename(os.path.normpath(pl_directory))
        pl_name = rel_folder + ".m3u"
        for local, dirs, files in os.walk(pl_directory):
            dirs.sort()
            audio_rel_files = [
                # os.path.abspath(os.path.join(local, file_))
                # os.path.join(rel_folder, os.path.basename(os.path.normpath(local)), file_)
                os.path.join(os.path.basename(os.path.normpath(local)), file_)
                for file_ in files
                if os.path.splitext(file_)[-1] in EXTENSIONS
            ]
            audio_files = [
                os.path.abspath(os.path.join(local, file_))
                for file_ in files
                if os.path.splitext(file_)[-1] in EXTENSIONS
            ]
            if not audio_files or len(audio_files) != len(audio_rel_files):
                continue

            for audio_rel_file, audio_file in zip(audio_rel_files, audio_files):
                try:
                    pl_item = (
                        EasyMP3(audio_file)
                        if ".mp3" in audio_file
                        else FLAC(audio_file)
                    )
                    title = pl_item["TITLE"][0]
                    artist = pl_item["ARTIST"][0]
                    length = int(pl_item.info.length)
                    index = "#EXTINF:{}, {} - {}\n{}".format(
                        length, artist, title, audio_rel_file
                    )
                except:  # noqa
                    continue
                track_list.append(index)

        if len(track_list) > 1:
            with open(os.path.join(pl_directory, pl_name), "w") as pl:
                pl.write("\n\n".join(track_list))
