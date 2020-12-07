import os

from mutagen.flac import FLAC
from mutagen.mp3 import EasyMP3
from pathvalidate import sanitize_filename


def tag_flac(file, path, d, album, istrack=True):
    audio = FLAC(file)

    audio["TITLE"] = (
        "{} ({})".format(d["title"], d["version"]) if d["version"] else d["title"]
    )  # TRACK TITLE
    audio["TRACKNUMBER"] = str(d["track_number"])  # TRACK NUMBER
    try:
        audio["COMPOSER"] = d["composer"]["name"]  # COMPOSER
    except KeyError:
        pass

    try:
        audio["ARTIST"] = d["performer"]["name"]  # TRACK ARTIST
    except KeyError:
        if istrack:
            audio["ARTIST"] = d["album"]["artist"]["name"]  # TRACK ARTIST
        else:
            audio["ARTIST"] = album["artist"]["name"]

    if istrack:
        audio["GENRE"] = ", ".join(d["album"]["genres_list"])  # GENRE
        audio["ALBUMARTIST"] = d["album"]["artist"]["name"]  # ALBUM ARTIST
        audio["TRACKTOTAL"] = str(d["album"]["tracks_count"])  # TRACK TOTAL
        audio["ALBUM"] = d["album"]["title"]  # ALBUM TITLE
        audio["YEAR"] = d["album"]["release_date_original"].split("-")[0]
    else:
        audio["GENRE"] = ", ".join(album["genres_list"])  # GENRE
        audio["ALBUMARTIST"] = album["artist"]["name"]  # ALBUM ARTIST
        audio["TRACKTOTAL"] = str(album["tracks_count"])  # TRACK TOTAL
        audio["ALBUM"] = album["title"]  # ALBUM TITLE
        audio["YEAR"] = album["release_date_original"].split("-")[0]  # YEAR

    audio.save()
    title = sanitize_filename(d["title"])
    try:
        os.rename(file, "{}/{:02}. {}.flac".format(path, d["track_number"], title))
    except FileExistsError:
        print("File already exists. Skipping...")


def tag_mp3(file, path, d, album, istrack=True):
    audio = EasyMP3(file)

    audio["title"] = (
        "{} ({})".format(d["title"], d["version"]) if d["version"] else d["title"]
    )  # TRACK TITLE
    audio["tracknumber"] = str(d["track_number"])
    try:
        audio["composer"] = d["composer"]["name"]
    except KeyError:
        pass
    try:
        audio["artist"] = d["performer"]["name"]  # TRACK ARTIST
    except KeyError:
        if istrack:
            audio["artist"] = d["album"]["artist"]["name"]  # TRACK ARTIST
        else:
            audio["artist"] = album["artist"]["name"]

    if istrack:
        audio["genre"] = ", ".join(d["album"]["genres_list"])  # GENRE
        audio["albumartist"] = d["album"]["artist"]["name"]  # ALBUM ARTIST
        audio["album"] = d["album"]["title"]  # ALBUM TITLE
        audio["date"] = d["album"]["release_date_original"].split("-")[0]
    else:
        audio["GENRE"] = ", ".join(album["genres_list"])  # GENRE
        audio["albumartist"] = album["artist"]["name"]  # ALBUM ARTIST
        audio["album"] = album["title"]  # ALBUM TITLE
        audio["date"] = album["release_date_original"].split("-")[0]  # YEAR

    audio.save()
    title = sanitize_filename(d["title"])
    try:
        os.rename(file, "{}/{:02}. {}.mp3".format(path, d["track_number"], title))
    except FileExistsError:
        print("File already exists. Skipping...")
