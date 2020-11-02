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
        r"https?://(?:w{0,3}|play|open)\.qobuz\.com/(?:(?"
        ":album|track)/|[a-z]{2}-[a-z]{2}/album/-?\w+(?:-\w+)"
        "*-?/|user/library/favorites/)(\w+)",
        url,
    ).group(1)


def searchSelected(Qz, path, albums, ids, types, quality):
    q = ["5", "6", "7", "27"]
    quality = q[quality[1]]
    for alb, id_, type_ in zip(albums, ids, types):
        for al in alb:
            downloader.iterateIDs(
                Qz, id_[al[1]], path, quality, True if type_[al[1]] else False
            )


def fromUrl(Qz, path, link, quality):
    id = get_id(link)
    downloader.iterateIDs(
        Qz, id, path, str(quality), False if "/track/" in link else True
    )


def interactive(Qz, path, limit, tracks=True):
    while True:
        Albums, Types, IDs = [], [], []
        try:
            while True:
                query = input("\nEnter your search: [Ctrl + c to quit]\n- ")
                print("Searching...")
                start = Search(Qz, query, limit)
                start.getResults(tracks)
                Types.append(start.Types)
                IDs.append(start.IDs)

                title = (
                    "Select [space] the item(s) you want to download "
                    "(one or more)\nPress Ctrl + c to quit\n"
                )
                Selected = pick(
                    start.Total, title, multiselect=True, min_selection_count=1
                )
                Albums.append(Selected)

                y_n = pick(
                    ["Yes", "No"],
                    "Items were added to queue to be downloaded. Keep searching?",
                )
                if y_n[0][0] == "N":
                    break

            desc = (
                "Select [intro] the quality (the quality will be automat"
                "ically\ndowngraded if the selected is not found)"
            )
            Qualits = ["320", "Lossless", "Hi-res =< 96kHz", "Hi-Res > 96 kHz"]
            quality = pick(Qualits, desc)
            searchSelected(Qz, path, Albums, IDs, Types, quality)
        except KeyboardInterrupt:
            sys.exit("\nBye")


def main():
    arguments = getArgs()
    directory = musicDir(arguments.d) + "/"
    Qz = qopy.Client(config.email, config.password)
    if not arguments.i:
        interactive(Qz, directory, arguments.l, not arguments.a)
    else:
        fromUrl(Qz, directory, arguments.i, arguments.q)


if __name__ == "__main__":
    sys.exit(main())
