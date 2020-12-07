import os

import requests
from pathvalidate import sanitize_filename
from tqdm import tqdm

from qo_utils import metadata


def req_tqdm(url, fname, track_name):
    r = requests.get(url, allow_redirects=True, stream=True)
    total = int(r.headers.get("content-length", 0))
    with open(fname, "wb") as file, tqdm(
        total=total,
        unit="iB",
        unit_scale=True,
        unit_divisor=1024,
        desc=track_name,
        bar_format="{n_fmt}/{total_fmt} /// {desc}",
    ) as bar:
        for data in r.iter_content(chunk_size=1024):
            size = file.write(data)
            bar.update(size)


def mkDir(dirn):
    try:
        os.mkdir(dirn)
    except FileExistsError:
        print("Warning: folder already exists. Overwriting...")


def getDesc(u, mt):
    return "{}{} [{}/{}]".format(mt["title"],' (' + mt["version"] + ')' if mt["version"] is not None else '', u["bit_depth"], u["sampling_rate"])

def getBooklet(i, dirn):
     req_tqdm(i, dirn + "/booklet.pdf", "Downloading booklet")

def getCover(i, dirn):
    req_tqdm(i, dirn + "/cover.jpg", "Downloading cover art")


# Download and tag a file
def downloadItem(dirn, count, parse, meta, album, url, is_track, mp3):
    fname = (
        "{}/{:02}.mp3".format(dirn, count)
        if mp3
        else "{}/{:02}.flac".format(dirn, count)
    )
    func = metadata.tag_mp3 if mp3 else metadata.tag_flac
    desc = getDesc(parse, meta)
    req_tqdm(url, fname, desc)
    func(fname, dirn, meta, album, is_track)


# Iterate over IDs by type calling downloadItem
def iterateIDs(client, id, path, quality, album=False):
    count = 0

    if album:
        meta = client.get_album_meta(id)

        print("\nDownloading: {0} {1}\n".format(meta["title"], '(' + meta["version"] + ')' if meta["version"] is not None else ' '))
        dirT = (
            meta["artist"]["name"],
            meta["title"],
            ' ' + meta["version"] if meta["version"] is not None else '',
            meta["release_date_original"].split("-")[0],
        )
        sanitized_title = sanitize_filename("{} - {}{} [{}]".format(*dirT)) #aa-{}
        dirn = path + sanitized_title
        mkDir(dirn)
        getCover(meta["image"]["large"], dirn)
        if "goodies" in meta:
            getBooklet(meta["goodies"][0]["url"], dirn)
        for i in meta["tracks"]["items"]:
            parse = client.get_track_url(i["id"], quality)
            try:
                url = parse["url"]
            except KeyError:
                print("Track is not available for download")
                return
            if "sample" not in parse:
                is_mp3 = True if int(quality) == 5 else False
                downloadItem(dirn, count, parse, i, meta, url, False, is_mp3)
            else:
                print("Demo. Skipping")
            count = count + 1
    else:
        parse = client.get_track_url(id, quality)
        url = parse["url"]

        if "sample" not in parse:
            meta = client.get_track_meta(id)
            print("\nDownloading: {0} {1}\n".format(meta["title"], '(' + meta["version"] + ')' if meta["version"] is not None else ' '))
            dirT = (
                meta["album"]["artist"]["name"],
                meta["album"]["title"],
                ' ' + meta["album"]["version"] if meta["album"]["version"] is not None else '',
                meta["album"]["release_date_original"].split("-")[0],
            )
            sanitized_title = sanitize_filename("{} - {}{} [{}]".format(*dirT))
            dirn = path + sanitized_title
            mkDir(dirn)
            getCover(meta["album"]["image"]["large"], dirn)
            is_mp3 = True if int(quality) == 5 else False
            downloadItem(dirn, count, parse, meta, meta, url, True, is_mp3)
        else:
            print("Demo. Skipping")
    print("\nCompleted\n")
