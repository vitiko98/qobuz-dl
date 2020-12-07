import argparse
import os
import re
import sys

from pick import pick

import config
from qo_utils import downloader, qopy
from qo_utils.search import Search


def getArgs():
    parser = argparse.ArgumentParser(prog="python3 main.py")
    parser.add_argument("-a", action="store_true", help="enable albums-only search")
    parser.add_argument(
        "-i",
        metavar="Album/track URL",
        help="run Qobuz-Dl on URL input mode (download by url)",
    )
    parser.add_argument(
        "-q",
        metavar="int",
        default=config.default_quality,
        help="quality for url input mode (5, 6, 7, 27) (default: 6)",
    )
    parser.add_argument(
        "-l",
        metavar="int",
        default=config.default_limit,
        help="limit of search results by type (default: 10)",
    )
    parser.add_argument(
        "-d",
        metavar="PATH",
        default=config.default_folder,
        help="custom directory for downloads (default: '{}')".format(
            config.default_folder
        ),
    )
    return parser.parse_args()


def musicDir(dir):
    fix = os.path.normpath(dir)
    if not os.path.isdir(fix):
        os.mkdir(fix)
    return fix


def get_id(url):
    return re.match(
        r"https?://(?:w{0,3}|play|open)\.qobuz\.com/(?:(?:album|track|artist"
        "|playlist|label)/|[a-z]{2}-[a-z]{2}/album/-?\w+(?:-\w+)*-?/|user/library/favorites/)(\w+)",
        url,
    ).group(1)


def processSelected(Qz, path, albums, ids, types, quality):
    q = ["5", "6", "7", "27"]
    quality = q[quality[1]]
    for alb, id_, type_ in zip(albums, ids, types):
        for al in alb:
            downloader.iterateIDs(
                Qz, id_[al[1]], path, quality, True if type_[al[1]] else False
            )


def fromUrl(Qz, id, path, quality, album=True):
    downloader.iterateIDs(Qz, id, path, str(quality), album)


def handle_urls(url, client, path, quality):
    possibles = {
        "playlist": {"func": client.get_plist_meta, "iterable_key": "tracks"},
        "artist": {"func": client.get_artist_meta, "iterable_key": "albums"},
        "label": {"func": client.get_label_meta, "iterable_key": "albums"},
        "album": {"album": True, "func": None, "iterable_key": None},
        "track": {"album": False, "func": None, "iterable_key": None},
    }
    try:
        url_type = url.split("/")[3]
        type_dict = possibles[url_type]
        item_id = get_id(url)
        print("Downloading {}...".format(url_type))
    except KeyError:
        print("Invalid url. Use urls from https://play.qobuz.com!")
        return
    if type_dict["func"]:
        items = [
            item[type_dict["iterable_key"]]["items"]
            for item in type_dict["func"](item_id)
        ][0]
        for item in items:
            fromUrl(
                client,
                item["id"],
                path,
                quality,
                True if type_dict["iterable_key"] == "albums" else False,
            )
    else:
        fromUrl(client, item_id, path, quality, type_dict["album"])


def interactive(Qz, path, limit, tracks=True):
    while True:
        Albums, Types, IDs = [], [], []
        try:
            while True:
                query = input("\nEnter your search: [Ctrl + c to quit]\n- ")
                print("Searching...")
                if len(query.strip()) == 0:
                    break
                start = Search(Qz, query, limit)
                start.getResults(tracks)
                if len(start.Total) == 0:
                    break
                Types.append(start.Types)
                IDs.append(start.IDs)

                title = (
                    "Select [space] the item(s) you want to download "
                    "(zero or more)\nPress Ctrl + c to quit\n"
                )
                Selected = pick(
                    start.Total, title, multiselect=True, min_selection_count=0
                )
                if len(Selected) > 0:
                    Albums.append(Selected)

                    y_n = pick(
                        ["Yes", "No"],
                        "Items were added to queue to be downloaded. Keep searching?",
                    )
                    if y_n[0][0] == "N":
                        break
                else:
                    break

            if len(Albums) > 0:
                desc = (
                    "Select [intro] the quality (the quality will be automat"
                    "ically\ndowngraded if the selected is not found)"
                )
                Qualits = ["320", "Lossless", "Hi-res =< 96kHz", "Hi-Res > 96 kHz"]
                quality = pick(Qualits, desc, default_index=1)
                processSelected(Qz, path, Albums, IDs, Types, quality)
        except KeyboardInterrupt:
            sys.exit("\nBye")


def main():
    arguments = getArgs()
    directory = musicDir(arguments.d) + "/"
    Qz = qopy.Client(config.email, config.password)
    if not arguments.i:
        interactive(Qz, directory, arguments.l, not arguments.a)
    else:
        handle_urls(arguments.i, Qz, directory, arguments.q)


if __name__ == "__main__":
    sys.exit(main())
