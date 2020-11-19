# qobuz-dl
Seach and download Lossless and Hi-Res music from [Qobuz](https://www.qobuz.com/)

![Demostration](demo.gif)
> This is a GIF from the first release. After the first release, some new features like **queue** and **MP3** support were added.

## Features

* Download FLAC and MP3 files from Qobuz
* Search and download music directly from your terminal with interactive mode
* Queue support
* URL input mode with download support for albums, tracks, artists, playlists and labels

## Getting started

> Note: `qobuz-dl` requires Python >3.6

> Note 2: You'll need an **active subscription**

#### Install requirements with pip
##### Linux / MAC OS
```
pip3 install -r requirements.txt --user
```
##### Windows 10
```
pip3 install windows-curses
pip3 install -r requirements.txt
```
#### Add your credentials to `config.py`
```python
email = "your@email.com"
password = "your_password"
```
#### Run qobuz-dl
##### Linux / MAC OS
```
python3 main.py
```
##### Windows 10
```
python.exe main.py
```
## Usage
```
usage: python3 main.py [-h] [-a] [-i] [-q int] [-l int] [-d PATH]

optional arguments:
  -h, --help          show this help message and exit
  -a                  enable albums-only search
  -i album/track/artist/label/playlist URL  run qobuz-dl on URL input mode (download by url)
  -q int              quality (5, 6, 7, 27) (default: 6) [320, LOSSLESS, 24B <96KHZ, 24B >96KHZ]
  -l int              limit of search results by type (default: 10)
  -d PATH             custom directory for downloads (default: 'Qobuz Downloads')
```
## A note about Qo-DL
`qobuz-dl` is inspired in the discontinued Qo-DL-Reborn. This program uses two modules from Qo-DL: `qopy` and `spoofer`, both written by Sorrow446 and DashLt.
## Disclaimer
This tool was written for educational purposes. I will not be responsible if you use this program in bad faith.
Also, you are accepting this: https://static.qobuz.com/apps/api/QobuzAPI-TermsofUse.pdf
