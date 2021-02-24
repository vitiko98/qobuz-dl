import os
import logging

from mutagen.flac import FLAC, Picture
import mutagen.id3 as id3
from mutagen.id3 import ID3NoHeaderError

logger = logging.getLogger(__name__)


# unicode symbols
COPYRIGHT, PHON_COPYRIGHT = '\u2117', '\u00a9'


def get_title(track_dict):
    title = track_dict["title"]
    version = track_dict.get("version")
    if version:
        title = f"{title} ({version})"
    # for classical works
    if track_dict.get("work"):
        title = "{}: {}".format(track_dict["work"], title)

    return title


def _format_copyright(s: str) -> str:
    s = s.replace('(P)', PHON_COPYRIGHT)
    s = s.replace('(C)', COPYRIGHT)
    return s


# Use KeyError catching instead of dict.get to avoid empty tags
def tag_flac(filename, root_dir, final_name, d, album,
             istrack=True, em_image=False):
    """
    Tag a FLAC file

    :param str filename: FLAC file path
    :param str root_dir: Root dir used to get the cover art
    :param str final_name: Final name of the FLAC file (complete path)
    :param dict d: Track dictionary from Qobuz_client
    :param dict album: Album dictionary from Qobuz_client
    :param bool istrack
    :param bool em_image: Embed cover art into file
    """
    print('in tag_flac d:')
    # print(json.dumps(d.keys(), indent=2))
    # print(d.keys())
    print('album:')
    # print(album.keys())
    # print(json.dumps(album.keys(), indent=2))
    print(f'{filename=}')
    print(f'{istrack=}')
    audio = FLAC(filename)

    audio["TITLE"] = get_title(d)

    audio["TRACKNUMBER"] = str(d["track_number"])  # TRACK NUMBER

    if "Disc " in final_name:
        audio["DISCNUMBER"] = str(d["media_number"])

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

    try:
        audio["LABEL"] = album["label"]["name"]
    except KeyError:
        pass

    if istrack:
        audio["GENRE"] = ", ".join(d["album"]["genres_list"])  # GENRE
        audio["ALBUMARTIST"] = d["album"]["artist"]["name"]    # ALBUM ARTIST
        audio["TRACKTOTAL"] = str(d["album"]["tracks_count"])  # TRACK TOTAL
        audio["ALBUM"] = d["album"]["title"]                   # ALBUM TITLE
        audio["DATE"] = d["album"]["release_date_original"]
        audio["COPYRIGHT"] = _format_copyright(d["copyright"])
    else:
        audio["GENRE"] = ", ".join(album["genres_list"])  # GENRE
        audio["ALBUMARTIST"] = album["artist"]["name"]    # ALBUM ARTIST
        audio["TRACKTOTAL"] = str(album["tracks_count"])  # TRACK TOTAL
        audio["ALBUM"] = album["title"]                   # ALBUM TITLE
        audio["DATE"] = album["release_date_original"]
        audio["COPYRIGHT"] = _format_copyright(album["copyright"])

    if em_image:
        emb_image = os.path.join(root_dir, "cover.jpg")
        multi_emb_image = os.path.join(
            os.path.abspath(os.path.join(root_dir, os.pardir)), "cover.jpg"
        )
        if os.path.isfile(emb_image):
            cover_image = emb_image
        else:
            cover_image = multi_emb_image

        try:
            image = Picture()
            image.type = 3
            image.mime = "image/jpeg"
            image.desc = "cover"
            with open(cover_image, "rb") as img:
                image.data = img.read()
            audio.add_picture(image)
        except Exception as e:
            logger.error(f"Error embedding image: {e}", exc_info=True)

    audio.save()
    os.rename(filename, final_name)


def tag_mp3(filename, root_dir, final_name, d, album,
            istrack=True, em_image=False):
    """
    Tag an mp3 file

    :param str filename: mp3 temporary file path
    :param str root_dir: Root dir used to get the cover art
    :param str final_name: Final name of the mp3 file (complete path)
    :param dict d: Track dictionary from Qobuz_client
    :param bool istrack
    :param bool em_image: Embed cover art into file
    """

    id3_legend = {
        "album": id3.TALB,
        "albumartist": id3.TPE2,
        "artist": id3.TPE1,
        "comment": id3.COMM,
        "composer": id3.TCOM,
        "copyright": id3.TCOP,
        "date": id3.TDAT,
        "genre": id3.TCON,
        "isrc": id3.TSRC,
        "label": id3.TPUB,
        "performer": id3.TOPE,
        "title": id3.TIT2,
        "year": id3.TYER
    }
    try:
        audio = id3.ID3(filename)
    except ID3NoHeaderError:
        audio = id3.ID3()

    # temporarily holds metadata
    tags = dict()
    tags['title'] = get_title(d)
    try:
        tags['label'] = album["label"]["name"]
    except KeyError:
        pass

    try:
        tags['artist'] = d["performer"]["name"]
    except KeyError:
        if istrack:
            tags['artist'] = d["album"]["artist"]["name"]
        else:
            tags['artist'] = album["artist"]["name"]

    if istrack:
        tags["genre"] = ", ".join(d["album"]["genres_list"])
        tags["albumartist"] = d["album"]["artist"]["name"]
        tags["album"] = d["album"]["title"]
        tags["date"] = d["album"]["release_date_original"]
        tags["copyright"] = _format_copyright(d["copyright"])
        tracktotal = str(d["album"]["tracks_count"])
    else:
        tags["genre"] = ", ".join(album["genres_list"])
        tags["albumartist"] = album["artist"]["name"]
        tags["album"] = album["title"]
        tags["date"] = album["release_date_original"]
        tags["copyright"] = _format_copyright(album["copyright"])
        tracktotal = str(album["tracks_count"])

    tags['year'] = tags['date'][:4]

    audio['TRCK'] = id3.TRCK(encoding=3,
                             text=f'{d["track_number"]}/{tracktotal}')
    audio['TPOS'] = id3.TPOS(encoding=3,
                             text=str(d["media_number"]))

    def lookup_and_set_tags(tag_name, value):
        id3tag = id3_legend[tag_name]
        audio[id3tag.__name__] = id3tag(encoding=3, text=value)

    # write metadata in `tags` to file
    for k, v in tags.items():
        lookup_and_set_tags(k, v)

    if em_image:
        emb_image = os.path.join(root_dir, "cover.jpg")
        multi_emb_image = os.path.join(
            os.path.abspath(os.path.join(root_dir, os.pardir)), "cover.jpg"
        )
        if os.path.isfile(emb_image):
            cover_image = emb_image
        else:
            cover_image = multi_emb_image

        with open(cover_image, 'rb') as cover:
            audio.add(id3.APIC(3, 'image/jpeg', 3, '', cover.read()))

    audio.save(filename, 'v2_version=3')
    os.rename(filename, final_name)
