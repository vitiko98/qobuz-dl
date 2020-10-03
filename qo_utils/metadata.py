from mutagen.flac import FLAC, Picture
from mutagen.mp3 import EasyMP3
import mutagen.id3 as id3
from pathvalidate import sanitize_filename
import os
from PIL import Image


def tag_flac(file, path, d, album, type, *arg):
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
        if type=="track" or type=="playlist":
            audio['ARTIST'] = d['album']['artist']['name']  # TRACK ARTIST
        else:
            audio['ARTIST'] = album['artist']['name']

    if type=="track" or type=="playlist":
        try:
            audio['GENRE'] = ', '.join(d['album']['genres_list'])  # GENRE
        except:
            audio['GENRE'] = ""
        audio['ALBUMARTIST'] = d['album']['artist']['name']  # ALBUM ARTIST
        audio['TRACKTOTAL'] = str(d['album']['tracks_count'])  # TRACK TOTAL
        audio['ALBUM'] = d['album']['title']  # ALBUM TITLE
        audio['YEAR'] = d['album']['release_date_original'].split('-')[0]

    else:
        audio['GENRE'] = ', '.join(album['genres_list'])  # GENRE
        audio['ALBUMARTIST'] = album['artist']['name']  # ALBUM ARTIST
        audio['TRACKTOTAL'] = str(album['tracks_count'])  # TRACK TOTAL
        audio['ALBUM'] = album['title']  # ALBUM TITLE
        audio['YEAR'] = album['release_date_original'].split('-')[0]  # YEAR

    data = open('{}/cover.jpg'.format(path),'rb').read()

    img = Picture()
    img.type = id3.PictureType.COVER_FRONT
    mime = 'image/jpeg'
    img.desc = 'front cover'
    img.data = data
    audio.add_picture(img)

    dataimg = Image.open('{}/cover.jpg'.format(path))
    dataimg.resize((32,32))
    dataimg.save('{}/cover.png'.format(path))

    data = open('{}/cover.png'.format(path),'rb').read()

    img = Picture()
    img.type = id3.PictureType.FILE_ICON
    mime = 'image/jpeg'
    img.desc = 'icon'
    img.data = data
    audio.add_picture(img)


    audio.save()
    title = sanitize_filename(d['title'])
    if type=="playlist":
        os.rename(file, '{}/{:02}. {}.flac'.format(path, arg[0]+1, title))
    else:
        os.rename(file, '{}/{:02}. {}.flac'.format(path, d['track_number'], title))
    os.remove('{}/cover.png'.format(path))
    os.remove('{}/cover.jpg'.format(path))


def tag_mp3(file, path, d, album, type, *arg):
    audio = EasyMP3(file)

    audio['title'] = d['title']
    audio['tracknumber'] = str(d['track_number'])
    try:
        audio['composer'] = d['composer']['name']
    except KeyError:
        pass
    try:
        audio['artist'] = d['performer']['name']  # TRACK ARTIST
    except KeyError:
        if type=="track" or type=="playlist":
            audio['artist'] = d['album']['artist']['name']  # TRACK ARTIST
        else:
            audio['artist'] = album['artist']['name']

    if type=="track" or type=="playlist":
        audio['genre'] = ', '.join(d['album']['genres_list'])  # GENRE
        audio['albumartist'] = d['album']['artist']['name']  # ALBUM ARTIST
        audio['album'] = d['album']['title']  # ALBUM TITLE
        audio['date'] = d['album']['release_date_original'].split('-')[0]
    else:
        audio['GENRE'] = ', '.join(album['genres_list'])  # GENRE
        audio['albumartist'] = album['artist']['name']  # ALBUM ARTIST
        audio['album'] = album['title']  # ALBUM TITLE
        audio['date'] = album['release_date_original'].split('-')[0]  # YEAR

    audio.save()
    title = sanitize_filename(d['title'])
    os.rename(file, '{}/{:02}. {}.mp3'.format(path, d['track_number'], title))
    os.remove('{}/cover.png'.format(path))
    os.remove('{}/cover.jpg'.format(path))