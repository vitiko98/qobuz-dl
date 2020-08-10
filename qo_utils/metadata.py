from mutagen.flac import FLAC
from pathvalidate import sanitize_filename
import os


def iterateTag(file, path, d, album, istrack=True):
    audio = FLAC(file)

    audio['TITLE'] = d['title']  # TRACK TITLE
    audio['TRACKNUMBER'] = str(d['track_number'])  # TRACK NUMBER
    try:
        audio['COMPOSER'] = d['composer']['name']  # COMPOSER
    except KeyError:
        pass

    try:
        audio['ARTIST'] = d['performer']['name']  # TRACK ARTIST
    except KeyError:
        if istrack:
            audio['ARTIST'] = d['album']['artist']['name']  # TRACK ARTIST
        else:
            audio['ARTIST'] = album['artist']['name']

    if istrack:
        audio['GENRE'] = ', '.join(d['album']['genres_list'])  # GENRE
        audio['ALBUMARTIST'] = d['album']['artist']['name']  # ALBUM ARTIST
        audio['TRACKTOTAL'] = str(d['album']['tracks_count'])  # TRACK TOTAL
        audio['ALBUM'] = d['album']['title']  # ALBUM TITLE
        audio['YEAR'] = d['album']['release_date_original'].split('-')[0]  # YEAR
    else:
        audio['GENRE'] = ', '.join(album['genres_list'])  # GENRE
        audio['ALBUMARTIST'] = album['artist']['name']  # ALBUM ARTIST
        audio['TRACKTOTAL'] = str(album['tracks_count'])  # TRACK TOTAL
        audio['ALBUM'] = album['title']  # ALBUM TITLE
        audio['YEAR'] = album['release_date_original'].split('-')[0]  # YEAR

    audio.save()
    title = sanitize_filename(d['title'])
    os.rename(file, '{}/{:02}. {}.flac'.format(path, d['track_number'], title))
