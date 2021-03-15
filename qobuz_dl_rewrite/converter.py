import logging
import os
import subprocess
from typing import Optional

from .exceptions import BadEncoderOption, ConversionError

logger = logging.getLogger(__name__)


class Converter:
    """Base class for audio codecs."""

    codec_name = None
    codec_lib = None
    container = None
    lossless = False
    cbr_options = None
    vbr_options = None
    default_ffmpeg_arg = ""

    def __init__(
        self,
        filename: str,
        ffmpeg_arg: Optional[str] = None,
        sampling_rate: Optional[int] = None,
        bit_depth: Optional[int] = None,
        copy_art: bool = False,
    ):
        """
        :param ffmpeg_arg: The codec ffmpeg argument (defaults to an "optimal value")
        :type ffmpeg_arg: Optional[str]
        :param sampling_rate: This value is ignored if a lossy codec is detected
        :type sampling_rate: Optional[int]
        :param bit_depth: This value is ignored if a lossy codec is detected
        :type bit_depth: Optional[int]
        :param copy_art: Embed the cover art (if found) into the encoded file
        :type copy_art: bool
        """
        logger.debug(locals())

        self.filename = filename
        self.final_fn = f"{os.path.splitext(filename)[0]}.{self.container}"
        self.sampling_rate = sampling_rate
        self.bit_depth = bit_depth
        self.copy_art = copy_art

        if ffmpeg_arg is None:
            logger.debug("No arguments provided. Codec defaults will be used")
            self.ffmpeg_arg = self.default_ffmpeg_arg
        else:
            self.ffmpeg_arg = ffmpeg_arg
            self._is_command_valid()

        logger.debug("Ffmpeg codec extra argument: %s", self.ffmpeg_arg)

    def convert(self, custom_fn: Optional[str] = None, remove_source: bool = False):
        """Convert the file.

        :param custom_fn: Custom output filename (defaults to the original
        name with a replaced container)
        :type custom_fn: Optional[str]
        :param remove_source: Remove the source after the conversion
        :type remove_source: bool
        """
        if custom_fn:
            self.final_fn = custom_fn

        self.command = self._gen_command()
        logger.debug("Generated conversion command: %s", self.command)

        process = subprocess.Popen(self.command)
        process.wait()
        if os.path.isfile(self.final_fn):
            if remove_source:
                logger.debug("Source removed: %s", self.filename)
                os.remove(self.filename)

            logger.debug("OK: %s -> %s", self.filename, self.final_fn)
        else:
            raise ConversionError("No file was returned from conversion")

    def _gen_command(self):
        command = [
            "ffmpeg",
            "-i",
            self.filename,
            "-loglevel",
            "warning",
            "-stats",  # progress
            "-c:a",
            self.codec_lib,
        ]
        if self.copy_art:
            command.extend(["-c:v", "copy"])

        if self.ffmpeg_arg:
            command.extend(self.ffmpeg_arg.split())

        if (self.sampling_rate and self.bit_depth) and self.lossless:
            # TODO: Add bit_depth support
            command.extend(["-ar", str(self.sampling_rate)])

        command.extend(["-y", self.final_fn])

        return command

    def _is_command_valid(self):
        if self.ffmpeg_arg is not None and self.lossless:
            logger.debug(
                "Lossless codecs don't support extra arguments; "
                "the extra argument will be ignored"
            )
            self.ffmpeg_arg = self.default_ffmpeg_arg
            return

        arg_value = self.ffmpeg_arg.split()[-1].strip().replace("k", "")

        try:
            arg_value = int(self.ffmpeg_arg.split()[-1].strip())
        except ValueError:
            raise BadEncoderOption(f"Invalid bitrate argument: {self.ffmpeg_arg}")

        logger.debug("Arg value provided: %d", arg_value)
        options = []

        if self.ffmpeg_arg.startswith("-b:a"):
            if self.cbr_options is None:
                raise BadEncoderOption("This codec doesn't support constant bitrate")

            options = self.cbr_options

        if self.ffmpeg_arg.startswith("-q:a"):
            if self.vbr_options is None:
                raise BadEncoderOption("This codec doesn't support variable bitrate")

            options = self.vbr_options

        if arg_value not in options:
            raise BadEncoderOption(
                f"VBR value is not in the codec range: {', '.join(options)}"
            )


class LAME(Converter):
    """
    Class for libmp3lame converter. See available options:
    https://trac.ffmpeg.org/wiki/Encode/MP3
    """

    codec_name = "lame"
    codec_lib = "libmp3lame"
    container = "mp3"
    lossless = False
    # Blatantly assume nobody will ever convert CBR at less than 96
    cbr_options = tuple(range(96, 321, 16))
    vbr_options = tuple(range(10))
    default_ffmpeg_arg = "-q:a 0"  # V0


class ALAC(Converter):
    " Class for ALAC converter. "
    codec_name = "alac"
    codec_lib = "alac"
    container = "m4a"
    lossless = True


class Vorbis(Converter):
    """
    Class for libvorbis converter. See available options:
    https://trac.ffmpeg.org/wiki/TheoraVorbisEncodingGuide
    """

    codec_name = "vorbis"
    codec_lib = "libvorbis"
    container = "ogg"
    lossless = False
    vbr_options = tuple(range(-1, 11))
    default_ffmpeg_arg = "-q:a 6"  # 160, aka the "high" quality profile from Spotify


class OPUS(Converter):
    """
    Class for libopus. Currently, this codec takes only `-b:a` as an argument
    but, unlike other codecs, it will convert to a variable bitrate.

    See more:
    http://ffmpeg.org/ffmpeg-codecs.html#libopus-1
    """

    codec_name = "opus"
    codec_lib = "libopus"
    container = "opus"
    lossless = False
    cbr_options = tuple(range(16, 513, 16))
    default_ffmpeg_arg = "-b:a 128k"  # Transparent


class AAC(Converter):
    """
    Class for libfdk_aac converter. See available options:
    https://trac.ffmpeg.org/wiki/Encode/AAC
    """

    codec_name = "aac"
    codec_lib = "libfdk_aac"
    container = "m4a"
    lossless = False
    cbr_options = tuple(range(16, 513, 16))
    # TODO: vbr_options
    default_ffmpeg_arg = "-b:a 256k"
