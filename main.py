from qo_utils.search import Search
from qo_utils import downloader
import argparse
import re
import os
import sys
import json
import qopy


def getArgs():
    parser = argparse.ArgumentParser(prog='python3 main.py')
    parser.add_argument("-a", action="store_true",
                        help="enable albums-only search")
    parser.add_argument("-i", action="store_true",
                        help="run Qo-Dl-curses on URL input mode")
    parser.add_argument("-q", metavar="int", default=6,
                        help="FLAC quality (6, 7, 27) (default: 6)")
    parser.add_argument("-l", metavar="int", default=10,
                        help="limit of search results by type (default: 10)")
    parser.add_argument("-d", metavar="PATH", default='Qobuz Downloads',
                        help="custom directory for downloads")
    return parser.parse_args()


def getSession():
    print('Logging...')
    with open('config.json') as f:
        config = json.load(f)
    return qopy.Client(config['email'], config['password'])


def musicDir(dir):
    fix = os.path.normpath(dir)
    if not os.path.isdir(fix):
        os.mkdir(fix)
    return fix


def get_id(url):
    return re.match(r'https?://(?:w{0,3}|play|open)\.qobuz\.com/(?:(?'
                    ':album|track)/|[a-z]{2}-[a-z]{2}/album/-?\w+(?:-\w+)'
                    '*-?/|user/library/favorites/)(\w+)', url).group(1)


def searchSelected(Qz, path, start):
    q = ['6', '7', '27']
    quality = q[start.quality[1]]
    for i in start.Selected:
        if start.Types[i[1]]:
            downloader.iterateIDs(Qz, start.IDs[i[1]], path, quality, True)
        else:
            downloader.iterateIDs(Qz, start.IDs[i[1]], path, quality, False)


def fromUrl(Qz, path, link, quality):
    if '/track/' in link:
        id = get_id(link)
        downloader.iterateIDs(Qz, id, path, quality, False)
    else:
        id = get_id(link)
        downloader.iterateIDs(Qz, id, path, quality, True)


def interactive(Qz, path, limit, tracks=True):
    while True:
        try:
            query = input("\nEnter your search: [Ctrl + c to quit]\n- ")
            print('Searching...')
            start = Search(Qz, query, limit)
            start.getResults(tracks)
            start.pickResults()
            searchSelected(Qz, path, start)
        except KeyboardInterrupt:
            sys.exit('\nBye')


def inputMode(Qz, path, quality):
    while True:
        try:
            link = input("\nAlbum/track URL: [Ctrl + c to quit]\n- ")
            fromUrl(Qz, path, link, quality)
        except KeyboardInterrupt:
            sys.exit('\nBye')


def main():
    arguments = getArgs()
    directory = musicDir(arguments.d) + '/'
    Qz = getSession()
    if not arguments.i:
        if arguments.a:
            interactive(Qz, directory, arguments.l, False)
        else:
            interactive(Qz, directory, arguments.l, True)
    else:
        inputMode(Qz, directory, arguments.q)


if __name__ == "__main__":
    sys.exit(main())
