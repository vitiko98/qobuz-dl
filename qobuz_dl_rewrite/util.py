import requests
from tqdm import tqdm


def safe_get(d: dict, *keys, default=None):
    """A replacement for chained `get()` statements on dicts:
    >>> d = {'foo': {'bar': 'baz'}}
    >>> _safe_get(d, 'baz')
    None
    >>> _safe_get(d, 'foo', 'bar')
    'baz'
    """
    curr = d
    res = default
    for key in keys:
        res = curr.get(key, default)
        if res == default or not hasattr(res, "__getitem__"):
            return res
        else:
            curr = res
    return res


def quality_id(bit_depth: int, sampling_rate: int):
    """Return a quality id in (5, 6, 7, 27) from bit depth and
    sampling rate. If None is provided, mp3/lossy is assumed.

    :param bit_depth: bit depth of track
    :type bit_depth: int
    :param sampling_rate: sampling rate in kHz
    :type sampling_rate: int
    """
    if bit_depth or sampling_rate is None:  # is lossy
        return 5
    if bit_depth == 16:
        return 6
    elif bit_depth == 24:
        if sampling_rate <= 96:
            return 7
        else:
            return 27


def tqdm_download(url: str, filepath: str):
    """Downloads a file with a progress bar.

    :param url: url to direct download
    :type url: str
    :param filepath: file to write
    :type filepath: str
    """
    # Fixme: add the conditional to the progress_bar bool
    r = requests.get(url, allow_redirects=True, stream=True)
    total = int(r.headers.get("content-length", 0))
    with open(filepath, "wb") as file, tqdm(
        total=total, unit="iB", unit_scale=True, unit_divisor=1024
    ) as bar:
        for data in r.iter_content(chunk_size=1024):
            size = file.write(data)
            bar.update(size)
