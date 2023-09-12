import logging
import os
import sys

import requests
from bs4 import BeautifulSoup as bso
from pathvalidate import sanitize_filename

from qobuz_dl.bundle import Bundle
from qobuz_dl import downloader, qopy
from qobuz_dl.color import CYAN, OFF, RED, YELLOW, DF, RESET
from qobuz_dl.exceptions import NonStreamable
from qobuz_dl.db import create_db, handle_download_id
from qobuz_dl.utils import (
    get_url_info,
    make_m3u,
    smart_discography_filter,
    format_duration,
    create_and_return_dir,
    PartialFormatter,
)

WEB_URL = "https://play.qobuz.com/"
ARTISTS_SELECTOR = "td.chartlist-artist > a"
TITLE_SELECTOR = "td.chartlist-name > a"
QUALITIES = {
    5: "5 - MP3",
    6: "6 - 16 bit, 44.1kHz",
    7: "7 - 24 bit, <96kHz",
    27: "27 - 24 bit, >96kHz",
}

logger = logging.getLogger(__name__)


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
        cover_og_quality=False,
        no_cover=False,
        downloads_db=None,
        folder_format="{artist} - {album} ({year}) [{bit_depth}B-"
        "{sampling_rate}kHz]",
        track_format="{tracknumber}. {tracktitle}",
        smart_discography=False,
    ):
        self.directory = create_and_return_dir(directory)
        self.quality = quality
        self.embed_art = embed_art
        self.lucky_limit = lucky_limit
        self.lucky_type = lucky_type
        self.interactive_limit = interactive_limit
        self.ignore_singles_eps = ignore_singles_eps
        self.no_m3u_for_playlists = no_m3u_for_playlists
        self.quality_fallback = quality_fallback
        self.cover_og_quality = cover_og_quality
        self.no_cover = no_cover
        self.downloads_db = create_db(downloads_db) if downloads_db else None
        self.folder_format = folder_format
        self.track_format = track_format
        self.smart_discography = smart_discography

    def initialize_client(self, email, pwd, app_id, secrets):
        self.client = qopy.Client(email, pwd, app_id, secrets)
        logger.info(f"{YELLOW}Set max quality: {QUALITIES[int(self.quality)]}\n")

    def get_tokens(self):
        bundle = Bundle()
        self.app_id = bundle.get_app_id()
        self.secrets = [
            secret for secret in bundle.get_secrets().values() if secret
        ]  # avoid empty fields

    def download_from_id(self, item_id, album=True, alt_path=None):
        if handle_download_id(self.downloads_db, item_id, add_id=False):
            logger.info(
                f"{OFF}This release ID ({item_id}) was already downloaded "
                "according to the local database.\nUse the '--no-db' flag "
                "to bypass this."
            )
            return
        try:
            dloader = downloader.Download(
                self.client,
                item_id,
                alt_path or self.directory,
                int(self.quality),
                self.embed_art,
                self.ignore_singles_eps,
                self.quality_fallback,
                self.cover_og_quality,
                self.no_cover,
                self.folder_format,
                self.track_format,
            )
            dloader.download_id_by_type(not album)
            handle_download_id(self.downloads_db, item_id, add_id=True)
        except (requests.exceptions.RequestException, NonStreamable) as e:
            logger.error(f"{RED}Error getting release: {e}. Skipping...")

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
            url_type, item_id = get_url_info(url)
            type_dict = possibles[url_type]
        except (KeyError, IndexError):
            logger.info(
                f'{RED}Invalid url: "{url}". Use urls from ' "https://play.qobuz.com!"
            )
            return
        if type_dict["func"]:
            content = [item for item in type_dict["func"](item_id)]
            content_name = content[0]["name"]
            logger.info(
                f"{YELLOW}Downloading all the music from {content_name} "
                f"({url_type})!"
            )
            new_path = create_and_return_dir(
                os.path.join(self.directory, sanitize_filename(content_name))
            )

            if self.smart_discography and url_type == "artist":
                # change `save_space` and `skip_extras` for customization
                items = smart_discography_filter(
                    content,
                    save_space=True,
                    skip_extras=True,
                )
            else:
                items = []
                for item in content:
                    items.extend(item[type_dict["iterable_key"]]["items"])

            logger.info(f"{YELLOW}{len(items)} downloads in queue")
            for item in items:
                self.download_from_id(
                    item["id"],
                    True if type_dict["iterable_key"] == "albums" else False,
                    new_path,
                )
            if url_type == "playlist" and not self.no_m3u_for_playlists:
                make_m3u(new_path)
        else:
            self.download_from_id(item_id, type_dict["album"])

    def download_list_of_urls(self, urls):
        if not urls or not isinstance(urls, list):
            logger.info(f"{OFF}Nothing to download")
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
                urls = [
                    line.replace("\n", "")
                    for line in txt.readlines()
                    if not line.strip().startswith("#")
                ]
            except Exception as e:
                logger.error(f"{RED}Invalid text file: {e}")
                return
            logger.info(
                f"{YELLOW}qobuz-dl will download {len(urls)}"
                f" urls from file: {txt_file}"
            )
            self.download_list_of_urls(urls)

    def lucky_mode(self, query, download=True):
        if len(query) < 3:
            logger.info(f"{RED}Your search query is too short or invalid")
            return

        logger.info(
            f'{YELLOW}Searching {self.lucky_type}s for "{query}".\n'
            f"{YELLOW}qobuz-dl will attempt to download the first "
            f"{self.lucky_limit} results."
        )
        results = self.search_by_type(query, self.lucky_type, self.lucky_limit, True)

        if download:
            self.download_list_of_urls(results)

        return results

    def search_by_type(self, query, item_type, limit=10, lucky=False):
        if len(query) < 3:
            logger.info("{RED}Your search query is too short or invalid")
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
                        format_duration(i["duration"]),
                        "HI-RES" if i["hires_streamable"] else "LOSSLESS",
                    )

                url = "{}{}/{}".format(WEB_URL, item_type, i.get("id", ""))
                item_list.append({"text": text, "url": url} if not lucky else url)
            return item_list
        except (KeyError, IndexError):
            logger.info(f"{RED}Invalid type: {item_type}")
            return

    def interactive(self, download=True):
        try:
            from pick import pick
        except (ImportError, ModuleNotFoundError):
            if os.name == "nt":
                sys.exit(
                    "Please install curses with "
                    '"pip3 install windows-curses" to continue'
                )
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
            logger.info(f"{YELLOW}Ok, we'll search for " f"{selected_type}s{RESET}")
            final_url_list = []
            while True:
                query = input(
                    f"{CYAN}Enter your search: [Ctrl + c to quit]\n" f"-{DF} "
                )
                logger.info(f"{YELLOW}Searching...{RESET}")
                options = self.search_by_type(
                    query, selected_type, self.interactive_limit
                )
                if not options:
                    logger.info(f"{OFF}Nothing found{RESET}")
                    continue
                title = (
                    f'*** RESULTS FOR "{query.title()}" ***\n\n'
                    "Select [space] the item(s) you want to download "
                    "(one or more)\nPress Ctrl + c to quit\n"
                    "Don't select anything to try another search"
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
                        "Items were added to queue to be downloaded. "
                        "Keep searching?",
                    )
                    if y_n[0][0] == "N":
                        break
                else:
                    logger.info(f"{YELLOW}Ok, try again...{RESET}")
                    continue
            if final_url_list:
                desc = (
                    "Select [intro] the quality (the quality will "
                    "be automatically\ndowngraded if the selected "
                    "is not found)"
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
            logger.info(f"{YELLOW}Bye")
            return

    def download_lastfm_pl(self, playlist_url):
        # Apparently, last fm API doesn't have a playlist endpoint. If you
        # find out that it has, please fix this!
        try:
            r = requests.get(playlist_url, timeout=10)
        except requests.exceptions.RequestException as e:
            logger.error(f"{RED}Playlist download failed: {e}")
            return
        soup = bso(r.content, "html.parser")
        artists = [artist.text for artist in soup.select(ARTISTS_SELECTOR)]
        titles = [title.text for title in soup.select(TITLE_SELECTOR)]

        track_list = []
        if len(artists) == len(titles) and artists:
            track_list = [
                artist + " " + title for artist, title in zip(artists, titles)
            ]

        if not track_list:
            logger.info(f"{OFF}Nothing found")
            return

        pl_title = sanitize_filename(soup.select_one("h1").text)
        pl_directory = os.path.join(self.directory, pl_title)
        logger.info(
            f"{YELLOW}Downloading playlist: {pl_title} " f"({len(track_list)} tracks)"
        )

        for i in track_list:
            track_id = get_url_info(self.search_by_type(i, "track", 1, lucky=True)[0])[
                1
            ]
            if track_id:
                self.download_from_id(track_id, False, pl_directory)

        if not self.no_m3u_for_playlists:
            make_m3u(pl_directory)
