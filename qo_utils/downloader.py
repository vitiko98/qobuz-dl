import os
import requests
from qo_utils import metadata
from tqdm import tqdm


def req_tqdm(url, fname, track_name):
    r = requests.get(url, allow_redirects=True, stream=True)
    total = int(r.headers.get('content-length', 0))
    with open(fname, 'wb') as file, tqdm(
        total=total,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
        desc=track_name,
        bar_format='{n_fmt}/{total_fmt} /// {desc}',
    ) as bar:
        for data in r.iter_content(chunk_size=1024):
            size = file.write(data)
            bar.update(size)


def mkDir(dirn):
    try:
        os.mkdir(dirn)
    except FileExistsError:
        print('Warning: folder already exists. Overwriting...')


def getDesc(u, mt):
    return '{} [{}/{}]'.format(mt['title'], u['bit_depth'], u['sampling_rate'])


def getCover(i, dirn):
    req_tqdm(i, dirn + '/cover.jpg', 'Downloading cover art')


# Download and tag a file
def downloadItem(dirn, count, parse, meta, album, url, is_track):
    fname = '{}/{:02}.flac'.format(dirn, count)
    desc = getDesc(parse, meta)
    req_tqdm(url, fname, desc)
    metadata.iterateTag(fname, dirn, meta, album, is_track)


# Iterate over IDs by type calling downloadItem
def iterateIDs(client, id, path, quality, album=False):
    count = 0

    if album:
        meta = client.get_album_meta(id)
        print('\nDownloading: {}\n'.format(meta['title']))
        dirT = (meta['artist']['name'],
                meta['title'],
                meta['release_date_original'].split('-')[0])
        dirn = path + '{} - {} [{}]'.format(*dirT)
        mkDir(dirn)
        getCover(meta['image']['large'], dirn)
        for i in meta['tracks']['items']:
            parse = client.get_track_url(i['id'], quality)
            url = parse['url']

            if 'sample' not in parse and '.mp3' not in parse:
                downloadItem(dirn, count, parse, i, meta, url, False)
            else:
                print('Demo or MP3. Skipping')

            count = count + 1
    else:
        parse = client.get_track_url(id, quality)
        url = parse['url']

        if 'sample' not in parse and '.mp3' not in parse:
            meta = client.get_track_meta(id)
            print('\nDownloading: {}\n'.format(meta['title']))
            dirT = (meta['album']['artist']['name'],
                    meta['title'],
                    meta['album']['release_date_original'].split('-')[0])
            dirn = path + '{} - {} [{}]'.format(*dirT)
            mkDir(dirn)
            getCover(meta['album']['image']['large'], dirn)
            downloadItem(dirn, count, parse, meta, meta, url, True)
        else:
            print('Demo or MP3. Skipping')

    print('\nCompleted\n')
