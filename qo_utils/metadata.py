import os

from mutagen.flac import FLAC
from mutagen.mp3 import EasyMP3
from pathvalidate import sanitize_filename

def tag_flac(file, path, d, album, istrack=True):
    audio = FLAC(file)
    try:
        d["version"]
    except KeyError:
        audio["TITLE"] = d["title"]
        dversion_exist = 0
    else:
        if d["version"] is None:
            audio["TITLE"] = d["title"]# TRACK TITLE
            dversion_exist = 0
        else:
            audio["TITLE"] = d["title"] + ' ' + '(' + d["version"] + ')'
            dversion_exist = 1
#   if d["version"] is None:
#        audio["TITLE"] = d["title"]# TRACK TITLE
#    else:
#        audio["TITLE"] = d["title"] + ' ' + '(' + d["version"] + ')'

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
        if dversion_exist == 0:
            audio["GENRE"] = ", ".join(d["album"]["genres_list"])  # GENRE
            audio["ALBUMARTIST"] = d["album"]["artist"]["name"]  # ALBUM ARTIST
            audio["TRACKTOTAL"] = str(d["album"]["tracks_count"])  # TRACK TOTAL
            audio["ALBUM"] = d["album"]["title"] # ALBUM TITLE
            audio["YEAR"] = d["album"]["release_date_original"].split("-")[0]
        else:
            audio["GENRE"] = ", ".join(d["album"]["genres_list"])  # GENRE
            audio["ALBUMARTIST"] = d["album"]["artist"]["name"]  # ALBUM ARTIST
            audio["TRACKTOTAL"] = str(d["album"]["tracks_count"])  # TRACK TOTAL
            audio["ALBUM"] = d["album"]["title"] + ' ' + '(' + d["album"]["version"] + ')'  # ALBUM TITLE
            audio["YEAR"] = d["album"]["release_date_original"].split("-")[0]
    else:
        if dversion_exist == 0:
            audio["GENRE"] = ", ".join(album["genres_list"])  # GENRE
            audio["ALBUMARTIST"] = album["artist"]["name"]  # ALBUM ARTIST
            audio["TRACKTOTAL"] = str(album["tracks_count"])  # TRACK TOTAL
            audio["ALBUM"] = album["title"]  # ALBUM TITLE
            audio["YEAR"] = album["release_date_original"].split("-")[0]  # YEAR
        else:
            audio["GENRE"] = ", ".join(album["genres_list"])  # GENRE
            audio["ALBUMARTIST"] = album["artist"]["name"]  # ALBUM ARTIST
            audio["TRACKTOTAL"] = str(album["tracks_count"])  # TRACK TOTAL
            audio["ALBUM"] = album["title"] + ' ' + '(' + album["version"] + ')'  # ALBUM TITLE
            audio["YEAR"] = album["release_date_original"].split("-")[0]  # YEAR

    audio.save()
    if  dversion_exist == 1:
        title = sanitize_filename(d["title"] + ' ' + '(' + d["version"] + ')')
    else:
        title = sanitize_filename(d["title"])
    try:
        os.rename(file, "{}/{:02}. {}.flac".format(path, d["track_number"], title))
    except FileExistsError:
        print("File already exists. Skipping...")


def tag_mp3(file, path, d, album, istrack=True): #needs to be fixed
    audio = EasyMP3(file)
    try:
         d["version"]
    except KeyError:
        audio["TITLE"] = d["title"]
        dversion_exist = 0
    else:
        if d["version"] is None:
            audio["TITLE"] = d["title"]# TRACK TITLE
            dversion_exist = 0
        else:
            audio["TITLE"] = d["title"] + ' ' + '(' + d["version"] + ')'
            dversion_exist = 1

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
        if dversion_exist == 1:
            audio["genre"] = ", ".join(d["album"]["genres_list"])  # GENRE
            audio["albumartist"] = d["album"]["artist"]["name"]  # ALBUM ARTIST
            audio["album"] = d["album"]["title"] + ' ' + '(' + d["album"]["version"] + ')'  # ALBUM TITLE
            audio["date"] = d["album"]["release_date_original"].split("-")[0]
        else:
            audio["genre"] = ", ".join(d["album"]["genres_list"])  # GENRE
            audio["albumartist"] = d["album"]["artist"]["name"]  # ALBUM ARTIST
            audio["album"] = d["album"]["title"]  # ALBUM TITLE
            audio["date"] = d["album"]["release_date_original"].split("-")[0]
    else:
        if album["version"] is not None:
            audio["GENRE"] = ", ".join(album["genres_list"])  # GENRE
            audio["albumartist"] = album["artist"]["name"]  # ALBUM ARTIST
            try:
                album["version"]
            except KeyError:
                audio["album"] = album["title"]
            else:
                audio["album"] = album["title"] + ' ' + '(' + album["version"] + ')'  # ALBUM TITLE
            audio["date"] = album["release_date_original"].split("-")[0]  # YEAR
        else:
            audio["GENRE"] = ", ".join(album["genres_list"])  # GENRE
            audio["albumartist"] = album["artist"]["name"]  # ALBUM ARTIST
            audio["album"] = album["title"]  # ALBUM TITLE
            audio["date"] = album["release_date_original"].split("-")[0]  # YEAR

    audio.save()
    if dversion_exist == 1:
        title = sanitize_filename(d["title"] + ' ' + '(' + d["version"] + ')')
    else:
        title = sanitize_filename(d["title"])
    try:
        os.rename(file, "{}/{:02}. {}.mp3".format(path, d["track_number"], title))
    except FileExistsError:
        print("File already exists. Skipping...")
