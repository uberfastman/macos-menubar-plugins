#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# to get homebrew and pyenv python working together, see:
# https://towardsdatascience.com/homebrew-and-pyenv-python-playing-pleasantly-in-partnership-3a342d86319b

# <bitbar.title>Message Notifier</bitbar.title>
# <bitbar.version>v1.0.0</bitbar.version>
# <bitbar.author>Wren J. R.</bitbar.author>
# <bitbar.author.github>uberfastman</bitbar.author.github>
# <bitbar.desc>Display unread messages from iMessages/SMS, Reddit, and Telegram in the macOS menubar!</bitbar.desc>
# <bitbar.image>https://github.com/uberfastman/macos-menubar-plugins/raw/develop/resources/images/message_notifier_icon.png</bitbar.image>
# <bitbar.dependencies>python3,opencv-python,pandas,pillow,praw,prawcore,pymediainfo,pync,python-dateutil,telethon,vobject</bitbar.dependencies>
# <bitbar.abouturl>https://github.com/uberfastman/macos-menubar-plugins</bitbar.abouturl>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>

# Some portions of the code used to retrieve Reddit messages was adapted from code originally written by /u/HeyItsShuga:
# https://github.com/matryer/bitbar-plugins/blob/master/Web/Reddit/redditnotify.30s.py

import base64
import calendar
import json
import logging
import os
import sqlite3
import sys
import textwrap
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from datetime import datetime
from importlib import util
from io import BytesIO
from pathlib import Path
from random import Random
from subprocess import call, run, DEVNULL, PIPE, STDOUT
from typing import Dict, Set, List, Tuple, Union
from urllib import parse
from uuid import UUID

import pandas as pd
import praw
import pyheif
import vobject
from PIL import Image, ExifTags, ImageFilter, ImageDraw, ImageFont
from cv2 import VideoCapture, imencode
from dateutil import tz
from pandas.errors import EmptyDataError
from prawcore.exceptions import ResponseException, RequestException
from pymediainfo import MediaInfo
from pync import Notifier
from telethon.sessions import StringSession
# noinspection PyProtectedMember
from telethon.sync import TelegramClient, Dialog, Message
from telethon.tl.types import User

sys.dont_write_bytecode = True

# suppress dependency library logs ror running
logging.getLogger("telethon.network.mtprotosender").setLevel(logging.ERROR)

# suppress dependency library logs ror debugging
logging.getLogger("telethon.extensions.messagepacker").setLevel(logging.WARN)
logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARN)
logging.getLogger("PIL.TiffImagePlugin").setLevel(logging.WARN)
logging.getLogger("prawcore").setLevel(logging.WARN)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARN)
logging.getLogger("asyncio").setLevel(logging.WARN)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ START SET CUSTOM LOCAL VARIABLES ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
MAX_LINE_CHARS = 50
MAX_GROUP_CHAT_SEARCH_RESULTS = 10  # The higher this number, the longer the app will take to run each time.
MAX_GROUP_CHAT_PARTICIPANT_DISPLAY = 5

THUMBNAIL_PIXEL_SIZE = 500

# uses macOS system font: https://developer.apple.com/fonts/
FONT_FOR_TEXT_PATH = Path("/Library/Fonts/SF-Compact.ttf")
FONT_FOR_TITLE = "Menlo"
FONT_ITALIC = "HelveticaNeue-Italic"
FONT_SIZE_FOR_TITLE = 10
FONT_SIZE_FOR_TIMESTAMP = 8

LOG_LEVEL = logging.WARN  # Logging levels: logging.INFO, logging.DEBUG, logging.WARN, logging.ERROR

PERSISTENT_DATA_COLUMNS = ["id", "type", "timestamp", "username", "sender"]

SUPPORTED_MESSAGE_TYPES = ["text", "reddit", "telegram"]
# SUPPORTED_MESSAGE_TYPES = ["text", "reddit"]
# SUPPORTED_MESSAGE_TYPES = ["text", "telegram"]
# SUPPORTED_MESSAGE_TYPES = ["reddit", "telegram"]
# SUPPORTED_MESSAGE_TYPES = ["text"]
# SUPPORTED_MESSAGE_TYPES = ["reddit"]
# SUPPORTED_MESSAGE_TYPES = ["telegram"]
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ END SET CUSTOM LOCAL VARIABLES ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# noinspection DuplicatedCode
logger = logging.getLogger(__name__)
logging.basicConfig(level=LOG_LEVEL)

# Unicode character "⠀" (U+2800) for blank lines
BLANK_CHAR = "⠀"

# reference: https://chrisyeh96.github.io/2020/03/28/terminal-colors.html
ANSI_BLACK = "\u001b[30m"
ANSI_RED = "\u001b[31m"
ANSI_GREEN = "\u001b[32m"
ANSI_YELLOW = "\u001b[33m"
ANSI_BLUE = "\u001b[34m"
ANSI_MAGENTA = "\u001b[35m"
ANSI_CYAN = "\u001b[36m"
ANSI_WHITE = "\u001b[37m"

ANSI_BLACK_BG = "\u001b[40m"
ANSI_RED_BG = "\u001b[41m"
ANSI_GREEN_BG = "\u001b[42m"
ANSI_YELLOW_BG = "\u001b[43m"
ANSI_BLUE_BG = "\u001b[44m"
ANSI_MAGENTA_BG = "\u001b[45m"
ANSI_CYAN_BG = "\u001b[46m"
ANSI_WHITE_BG = "\u001b[47m"

ANSI_OFF = "\u001b[0m"

HEX_ORANGE = "#e05415"
HEX_BLUE = "#7FC3D8"

CSS_TEAL = "teal"
CSS_GRAY = "gray"

# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • MENUBAR PLUGIN BASE CLASSES ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~


# noinspection PyShadowingNames
class Icons(object):

    def __init__(self, directory: Path, unread_count: int = 0):

        # check if macOS device is using a dark mode or light mode
        if call("defaults read -g AppleInterfaceStyle", shell=True, stdout=DEVNULL, stderr=STDOUT) == 0:
            macos_display_mode = "dark"
        else:
            macos_display_mode = "light"

        self.all_read_icon = encode_image(
            directory / "resources" / "images" / f"message_notifier_icon_{macos_display_mode}.png"
        )
        self.unread_icon = encode_image(
            directory / "resources" / "images" / f"message_notifier_icon_{macos_display_mode}.png", unread_count
        )


class BaseMessage(object):

    def __init__(self, df_row, max_line_characters, menubar_msg_display_str):
        self.id = df_row.id
        self.cid = df_row.cid
        self.title = df_row.title
        self.timestamp = convert_timestamp(df_row.timestamp)
        self.timestamp_str = format_timestamp(df_row.timestamp)
        self.sender = df_row.sender
        self.body = df_row.body.replace('\n', ' ').replace('\r', '').strip() if df_row.body else ""
        self.body_short = f"{self.body[:max_line_characters]}..."
        self.body_wrapped = textwrap.wrap(self.body, max_line_characters + 1, break_long_words=False)
        self.attachment = 0
        self.menubar_msg_display_str = menubar_msg_display_str

    def get_message_len(self) -> int:
        # return len(self.body.encode("ascii", "ignore"))
        return len(self.body.replace(BLANK_CHAR, ""))

    def __repr__(self):
        return str(vars(self))

    def __str__(self):
        return str(vars(self))


# noinspection DuplicatedCode
class BaseConversation(object):

    def __init__(self, message_obj: BaseMessage):
        self.id = message_obj.cid
        self.title = f"{ANSI_OFF}{message_obj.title}{ANSI_YELLOW}" if message_obj.title else ""
        self.most_recent_timestamp = message_obj.timestamp
        self.messages = [message_obj]
        self.participants = {message_obj.sender}
        self.is_group_conversation = False
        self.menubar_msg_display_str = message_obj.menubar_msg_display_str

    def add_message(self, message_obj) -> None:
        if message_obj.cid == self.id:
            self.most_recent_timestamp = (
                message_obj.timestamp
                if message_obj.timestamp > self.most_recent_timestamp
                else self.most_recent_timestamp
            )
            self.messages.append(message_obj)
            self.participants.add(message_obj.sender)
            if len(self.participants) > 1:
                self.is_group_conversation = True
                if not self.title:
                    self.title = f"{ANSI_OFF}Group Message{ANSI_YELLOW}"
        else:
            raise ValueError("Cannot add Message with mismatching id to Conversation!")

    def get_message_count(self) -> int:
        return len(self.messages)

    def get_participants_str(self) -> str:
        if self.is_group_conversation:
            return (
                f"{', '.join(participant for participant in self.participants)}"
                f"{', ...' if len(self.participants) == 1 else ''}"
            )
        else:
            return "".join(participant for participant in self.participants)

    def sort_messages(self, descending: bool = True) -> None:
        self.messages.sort(key=lambda x: x.timestamp, reverse=descending)

    def __repr__(self):
        return str(vars(self))

    def __str__(self):
        return str(vars(self))


# noinspection PyShadowingNames
class BaseOutput(ABC):

    @abstractmethod
    def __init__(self, credentials: Dict, project_root_dir: Path):
        self.credentials = credentials
        self.project_root_dir = project_root_dir
        self.unread_count = None

    @abstractmethod
    def _get_messages(self) -> None:
        pass

    def get_unread_count(self) -> int:
        return self.unread_count

    @abstractmethod
    def get_console_output(self) -> List[str]:
        pass


# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • MENUBAR PLUGIN BASE FUNCTIONS • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~


def create_deterministic_uuid(seed: str) -> str:
    random_num_gen_with_seed = Random()
    random_num_gen_with_seed.seed(seed)
    return str(UUID(int=random_num_gen_with_seed.getrandbits(128), version=4))


def convert_timestamp(timestamp: Union[str, float, datetime]) -> datetime:
    # iMessage/SMS message timestamp: datetime string
    # Reddit message timestamp: floating point UTC epoch
    # Telegram message timestamp: pandas datetime

    if isinstance(timestamp, float):
        timestamp = datetime.utcfromtimestamp(timestamp).strftime("%m-%d-%Y %H:%M:%S")

    if isinstance(timestamp, float) or isinstance(timestamp, datetime):
        utc_time_zone = tz.tzutc()
        local_time_zone = tz.tzlocal()
        timestamp = timestamp.replace(tzinfo=utc_time_zone)
        timestamp = timestamp.astimezone(local_time_zone)
        timestamp = timestamp.strftime("%m-%d-%Y %H:%M:%S")

    timestamp = datetime.strptime(str(timestamp), "%m-%d-%Y %H:%M:%S")

    return timestamp


# noinspection DuplicatedCode
def format_timestamp(timestamp: Union[str, float, datetime]) -> str:
    message_timestamp = convert_timestamp(timestamp)
    # reference for strftime formatting: https://strftime.org
    # message_timestamp_str = message_timestamp.strftime("%m-%d-%Y %I:%M:%S %p").lower()
    message_timestamp_str = message_timestamp.strftime("%b %-d, %Y - %-I:%M:%S %p").lower().capitalize()

    today = datetime.today()
    if today.date() == message_timestamp.date():
        if today.hour == message_timestamp.hour:
            if today.minute == message_timestamp.minute:
                if today.second == message_timestamp.second:
                    return message_timestamp_str
                else:
                    sec_delta = today.second - message_timestamp.second
                    return f"{message_timestamp_str} (Today - {sec_delta} second{'s' if sec_delta > 1 else ''} ago)"
            else:
                minute_delta = today.minute - message_timestamp.minute
                return f"{message_timestamp_str} (Today - {minute_delta} minute{'s' if minute_delta > 1 else ''} ago)"
        else:
            hour_delta = today.hour - message_timestamp.hour
            return f"{message_timestamp_str} (Today - {hour_delta} hour{'s' if hour_delta > 1 else ''} ago)"
    else:
        day_delta = (today.date() - message_timestamp.date()).days
        logger.debug(
            f"\n"
            f"Message time delivery info:\n"
            f"              Today: {today}\n"
            f"          Timestamp: {message_timestamp}\n"
            f"    Diff from today: {today - message_timestamp}\n"
            f"          Day delta: {day_delta}\n"
        )
        if day_delta == 1:
            weekday_str = "Yesterday"
        else:
            weekday_str = calendar.day_name[message_timestamp.weekday()]
        return f"{message_timestamp_str} ({weekday_str} - {day_delta} day{'s' if day_delta > 1 else ''} ago)"


def sanitize_url(url_str: str) -> str:
    url = parse.urlsplit(url_str)
    url = list(url)
    url[2] = parse.quote(url[2])
    return parse.urlunsplit(url)


# noinspection PyShadowingNames
def encode_image(image_file_path: Path, unread_count: int = 0) -> str:
    image_bytes = BytesIO()
    img = Image.open(image_file_path)

    # check if macOS device is using a retina screen
    if call("system_profiler SPDisplaysDataType | grep -i 'retina'", shell=True, stdout=DEVNULL, stderr=STDOUT) == 0:
        max_menubar_icon_height = 74
        menubar_icon_font_size = 54
    else:
        max_menubar_icon_height = 37
        menubar_icon_font_size = 27

    img_width, img_height = img.size

    if img_width > img_height:
        thumbnail_max = int((img_width * max_menubar_icon_height) / img_height)
    else:
        thumbnail_max = img_height

    img.thumbnail((thumbnail_max, thumbnail_max))

    img_width, img_height = img.size

    if unread_count > 0:
        unread_count_str = f"{unread_count}"

        font = ImageFont.truetype(str(FONT_FOR_TEXT_PATH), menubar_icon_font_size)
        ascent, descent = font.getmetrics()
        # offset_y = space above letters
        # ascent - offset_y = height of letters (not counting tails)
        # descent = space below letters (for tails)
        # noinspection PyUnresolvedReferences
        (width, baseline), (offset_x, offset_y) = font.font.getsize(unread_count_str)

        percent_height_shift = int(img_height * 0.06)
        x = int((img_width - width) / 2)
        y = int((img_height - ((ascent + offset_y + descent) - percent_height_shift)) / 2)
        position = (x, y)

        draw = ImageDraw.Draw(img)

        # macOS colors: https://developer.apple.com/design/human-interface-guidelines/macos/visual-design/color/
        # draw.text(position, value, (255, 69, 58, 255), font=font)
        # reddit colors: https://www.designpieces.com/palette/reddit-brand-colors-hex-and-rgb/
        draw.text(position, unread_count_str, (255, 69, 0, 255), font=font)

        img.save(image_bytes, format="PNG")

        # img.show()

        return base64.b64encode(image_bytes.getvalue()).decode("utf-8")

    else:
        img.save(image_bytes, format="PNG")

    return base64.b64encode(image_bytes.getvalue()).decode("utf-8")


def convert_image_to_bytes(output: BytesIO, image: Image, image_format: str, max_size: int = THUMBNAIL_PIXEL_SIZE,
                           optimize: bool = False, quality: int = 100,
                           conversion_attempts: int = 1) -> Tuple[BytesIO, str, bool]:

    image.thumbnail((max_size, max_size), Image.ANTIALIAS)
    image_format = image_format.upper()

    if image_format == "GIF":
        # image.save(output, save_all=True, format=image_format, optimize=optimize, quality=quality)
        image.save(output, format="PNG", optimize=optimize, quality=quality)
    elif image_format == "HEIC":
        image.save(output, format="JPEG", optimize=optimize, quality=25)
    else:
        image.save(output, format=image_format, optimize=optimize, quality=quality)

    img_data = output.getvalue()
    thumb_str = base64.b64encode(img_data).decode("utf-8")

    logger.debug(
        f"\n"
        f"Image conversion attempt {conversion_attempts} for {image_format}:\n"
        f"         Max size: {max_size}\n"
        f"          Quality: {quality}\n"
        f"    Thumb str len: {len(thumb_str)}\n"
    )

    if conversion_attempts <= 9:
        file_byte_size_cutoff = 10000
        if len(thumb_str) > file_byte_size_cutoff:
            output, thumb_str, attachment_has_image_thumbnail = convert_image_to_bytes(
                BytesIO(),
                image,
                image_format,
                max_size=max_size - 50,
                optimize=True,
                quality=quality - 10,
                conversion_attempts=conversion_attempts + 1
            )
        else:
            attachment_has_image_thumbnail = True
    else:
        thumb_str = None
        attachment_has_image_thumbnail = False

    return output, thumb_str, attachment_has_image_thumbnail


# noinspection DuplicatedCode
def encode_attachment(message_row) -> Tuple[Union[str, List], bool]:
    path_str = message_row.attchfile
    mime_type = message_row.attchtype
    attachment_has_image_thumbnail = False

    if path_str:
        path_str = str.replace(path_str, "~", str(Path.home()))

        try:
            if mime_type == "text/vcard":
                with open(path_str, "r") as vcf_file:
                    thumb_str = []
                    # noinspection PyUnresolvedReferences
                    vcard_objects = vobject.readComponents(vcf_file.read())
                    vcard = next(vcard_objects, None)
                    while vcard is not None:
                        thumb_str.append(f"{vcard.name}")
                        for vcard_component in vcard.getChildren():
                            component_name = vcard_component.name
                            component_value_list = str(vcard_component.valueRepr()).split("\n")

                            thumb_str.append(f"    {component_name}: {component_value_list[0]}")
                            for component_value in component_value_list[1:]:
                                thumb_str.append(f"    {' ' * len(component_name)}  {component_value}")
                            if vcard_component.params:
                                thumb_str.append(f"    params for {component_name}:")
                                for k in vcard_component.params.keys():
                                    thumb_str.append(f"        {k}: {vcard_component.params[k]}")

                        thumb_str.append(BLANK_CHAR)
                        vcard = next(vcard_objects, None)

                    thumb_str.pop()

                return thumb_str, attachment_has_image_thumbnail

            else:
                output = BytesIO()
                img = None
                img_format = None
                thumb_str = None

                # retrievable at /Applications/MediaInfo.app/Contents/Resources/libmediainfo.dylib
                mediainfo_dylib = str(Path(__file__).resolve().parent.parent / "resources" / "libmediainfo.dylib")
                attachment_media_file = MediaInfo.parse(
                    path_str,
                    library_file=mediainfo_dylib
                )
                attachment_is_video = False
                for track in attachment_media_file.tracks:
                    if track.track_type == "Video":
                        attachment_is_video = True

                if attachment_is_video:

                    video_file_icon_path = Path(
                        __file__
                    ).parent.parent / "resources" / "images" / "message_notifier_video_file_icon.png"

                    video_capture = VideoCapture(path_str)
                    success, image_frame = video_capture.read()
                    if success:

                        output = BytesIO(imencode(".png", image_frame)[1].tobytes())

                        frame_img = Image.open(output)
                        frame_img_width, frame_img_height = frame_img.size

                        watermark_img = Image.open(video_file_icon_path)
                        watermark_img.thumbnail((min(frame_img.size) // 2, min(frame_img.size) // 2), Image.ANTIALIAS)

                        watermark_img = watermark_img.convert("RGBA")
                        watermark_img = watermark_img.filter(ImageFilter.SMOOTH_MORE)
                        watermark_img_data = watermark_img.getdata()

                        transparent_watermark_img_data = []
                        for pixel in watermark_img_data:
                            # (0, 0, 0, 255) = black, (255, 255, 255, 255) = white
                            if pixel[0] == 0 and pixel[1] == 0 and pixel[2] == 0 and pixel[3] > 0:
                                transparent_watermark_img_data.append((pixel[0], pixel[1], pixel[2], 128))
                            else:
                                transparent_watermark_img_data.append((0, 0, 0, 0))

                        # noinspection PyTypeChecker
                        watermark_img.putdata(transparent_watermark_img_data)

                        watermark_img_width, watermark_img_height = watermark_img.size

                        x = int((frame_img_width - watermark_img_width) / 2)
                        y = int((frame_img_height - watermark_img_height) / 2)
                        position = (x, y)

                        img = Image.new("RGBA", frame_img.size, (0, 0, 0, 0))
                        img.paste(frame_img, (0, 0))
                        img.paste(watermark_img, position, mask=watermark_img)
                        img = img.convert("RGB")
                        img_format = "PNG"

                    else:
                        img = Image.open(video_file_icon_path)
                        img_format = "PNG"

                else:
                    if mime_type == "image/jpeg":
                        orientation = 0
                        for key in ExifTags.TAGS.keys():
                            if ExifTags.TAGS[key] == "Orientation":
                                orientation = key

                        img = Image.open(path_str)
                        if hasattr(img, "_getexif"):  # only present in JPEGs
                            try:
                                # noinspection PyProtectedMember
                                exif = img._getexif()
                                if exif:
                                    exif = dict(exif.items())

                                    if exif[orientation] == 3:
                                        img = img.rotate(180, expand=True)
                                    elif exif[orientation] == 6:
                                        img = img.rotate(270, expand=True)
                                    elif exif[orientation] == 8:
                                        img = img.rotate(90, expand=True)
                            except KeyError:
                                img = img

                            img_format = "JPEG"

                    elif mime_type == "image/gif":
                        # TODO: fix handling of GIFs
                        # img = Image.open(path_str)
                        # img_format = "GIF"
                        pass

                    elif mime_type == "image/png":
                        # pass
                        img = Image.open(path_str)
                        img_format = "PNG"

                    elif mime_type == "image/heic":
                        # pass
                        heif_file = pyheif.read(path_str)

                        img = Image.frombytes(
                            heif_file.mode,
                            heif_file.size,
                            heif_file.data,
                            "raw",
                            heif_file.mode,
                            heif_file.stride,
                        )
                        img_format = "HEIC"

                    else:
                        # TODO: handle more image MIME types
                        pass

                if img_format:
                    output, thumb_str, attachment_has_image_thumbnail = convert_image_to_bytes(output, img, img_format)

                return thumb_str, attachment_has_image_thumbnail

        except IOError as e:
            logger.error(f"Unable to create thumbnail for '{path_str}' with error {repr(e)}")


# noinspection DuplicatedCode
def send_macos_notification(unread: int, message_senders: Set[str], title: str, arguments) -> None:
    notification_group_id = "notifier"

    Notifier.notify(
        message=(
            f"Message{'s' if (len(message_senders) > 1 and unread > 1) else ''} from: {', '.join(message_senders)}"
        ),  # content of notification
        title=f"{title}: {str(unread)} unread message{'s' if unread > 1 else ''}",  # notification title
        group=notification_group_id,  # ID used to group notification with previous notifications
        **arguments
    )

    Notifier.remove(notification_group_id)


# noinspection PyShadowingNames,PyListCreation
def generate_output_read(local_dir: Path, message_type: str, display_string: str, username: str,
                         user: str = None) -> List[str]:

    recipient = user if user else username

    standard_output = []
    standard_output.append("---")
    standard_output.append(
        f"No unread {message_type.capitalize()} messages for {recipient}! (Go to messages ↗︎️) "
        f"| color={CSS_TEAL} {display_string}"
    )

    # create data directory if it does not exist
    data_dir = local_dir / "resources" / "data"
    if not data_dir.is_dir():
        os.makedirs(data_dir)

    # clear all processed message UUIDs once messages are read
    all_processed_messages_df = pd.read_csv(data_dir / "processed_messages.csv", index_col=0)
    all_other_processed_messages_df = all_processed_messages_df.loc[
        (all_processed_messages_df["type"] != message_type)
        | (all_processed_messages_df["username"] != username)
    ]
    all_other_processed_messages_df.to_csv(data_dir / "processed_messages.csv", header=PERSISTENT_DATA_COLUMNS)

    return standard_output


# noinspection PyUnresolvedReferences,PyShadowingNames,PyListCreation,DuplicatedCode
def generate_output_unread(local_dir: Path, message_type: str, display_string: str, unread: int,
                           conversations: Dict[str, BaseConversation], max_line_characters: int, arguments: Dict,
                           username: str, user: str = None, all_unread_message_senders: Set = None) -> List[str]:

    recipient = user if user else username

    standard_output = []
    standard_output.append("---")
    standard_output.append(
        f"Go to {message_type.capitalize()} messages for {recipient} ↗︎️ "
        f"| font={FONT_ITALIC} color={HEX_ORANGE} {display_string}"
    )

    unread_message_count = sum([conv.get_message_count() for conv in conversations.values()])
    standard_output.append(
        f"{ANSI_GREEN}Unread {message_type.capitalize()} messages for "
        f"{recipient}: {ANSI_RED}{unread_message_count}{ANSI_OFF} "
        f"| ansi=true {display_string}"
    )

    ordered_conversations = OrderedDict(
        [(conversation.id, conversation) for conversation in sorted(
            conversations.values(), key=lambda x: x.most_recent_timestamp, reverse=True)]
    )

    unread_messages = {}
    message_num = 1
    for cid, conversation in ordered_conversations.items():
        message_display_str = f"{ANSI_OFF} | ansi=true refresh=true "

        if conversation.title:
            standard_output.append(
                f"--{conversation.title}{message_display_str}{conversation.menubar_msg_display_str} "
                f"font={FONT_FOR_TITLE} size={FONT_SIZE_FOR_TITLE}"
            )

        standard_output.append(
            f"--{ANSI_YELLOW}{conversation.get_participants_str()}{message_display_str}"
            f"{conversation.menubar_msg_display_str}"
        )

        for message in conversation.messages:  # type: BaseMessage

            timestamp_display_str = (
                f"--{ANSI_CYAN}{message.timestamp_str}"
                f"{ANSI_GREEN}{message_display_str}{message.menubar_msg_display_str} "
                f"size={FONT_SIZE_FOR_TIMESTAMP}"
            )
            msg_sender_start_str = f"--{ANSI_RED}({message.sender}) {ANSI_GREEN}"
            msg_format_str = f"--{ANSI_GREEN}"

            if message.attachment == 1:
                if message.get_message_len() == 0:
                    msg_attachment_str = (
                        f"{ANSI_MAGENTA}"
                        f"(attachment{(' - ' + message.attachment_type) if message.attachment_type else ''}) "
                        f"{ANSI_GREEN}"
                    )
                else:
                    # TODO: handle messages that are longer than the max_line_chars with video attachments
                    msg_attachment_str = (
                        f"{message.body} {ANSI_MAGENTA}"
                        f"(attachment{f' - {message.attachment_type}' if message.attachment_type else ''}) {ANSI_GREEN}"
                    )

                if conversation.is_group_conversation:
                    standard_output.append(timestamp_display_str)
                    standard_output.append(
                        f"{msg_sender_start_str}{msg_attachment_str}"
                        f"{message_display_str}{message.menubar_msg_display_str}"
                    )
                else:
                    standard_output.append(timestamp_display_str)
                    standard_output.append(
                        f"{msg_format_str}{msg_attachment_str}{message_display_str}{message.menubar_msg_display_str}"
                    )
                if message.attachment_file:
                    if message.attachment_has_thumbnail:
                        standard_output.append(
                            f"----| image={message.attachment_file} {message.menubar_msg_display_str}"
                        )
                    else:
                        for line in message.attachment_file:
                            standard_output.append(
                                f"----{ANSI_OFF}{line}{message_display_str}{message.menubar_msg_display_str}"
                            )

            elif message.get_message_len() > max_line_characters:
                if conversation.is_group_conversation:
                    standard_output.append(timestamp_display_str)
                    standard_output.append(
                        f"{msg_sender_start_str}{message.body_short}"
                        f"{message_display_str}{message.menubar_msg_display_str}"
                    )
                else:
                    standard_output.append(timestamp_display_str)
                    standard_output.append(
                        f"{msg_format_str}{message.body_short}{message_display_str}{message.menubar_msg_display_str}"
                    )
                for line in message.body_wrapped:
                    standard_output.append(
                        f"----{ANSI_OFF}{line}{message_display_str}{message.menubar_msg_display_str}"
                    )

            elif message.get_message_len() == 0:
                standard_output.append(timestamp_display_str)
                standard_output.append(
                    f"--No message content"
                    f"| {message.menubar_msg_display_str} color={CSS_GRAY} font={FONT_ITALIC}"
                )

            else:
                if conversation.is_group_conversation:
                    standard_output.append(timestamp_display_str)
                    standard_output.append(
                        f"{msg_sender_start_str}{message.body}{message_display_str}{message.menubar_msg_display_str}"
                    )
                else:
                    standard_output.append(timestamp_display_str)
                    standard_output.append(
                        f"{msg_format_str}{message.body}{message_display_str}{message.menubar_msg_display_str}"
                    )

            if conversation.messages.index(message) != (len(conversation.messages) - 1):
                standard_output.append(f"--{BLANK_CHAR} | size=2")

            message_id = str(message.id).lower()
            message_uuid = create_deterministic_uuid(message_id)
            unread_messages[message_uuid] = [message_id, message_type, message.timestamp, username, message.sender]

        standard_output.append("-----")
        message_num += 1

    # create data directory if it does not exist
    data_dir = local_dir / "resources" / "data"
    if not data_dir.is_dir():
        os.makedirs(data_dir)

    processed_message_ids = set()
    processed_message_senders = set()
    all_processed_messages_df = pd.DataFrame(columns=PERSISTENT_DATA_COLUMNS)
    try:
        all_processed_messages_df = pd.read_csv(data_dir / "processed_messages.csv", index_col=0)
        processed_messages_df = all_processed_messages_df[all_processed_messages_df["type"] == message_type]
        uuids = processed_messages_df.index.tolist()
        processed_message_ids = set([str(message_id).lower() for message_id in uuids])
        processed_message_senders = set(processed_messages_df["sender"].to_list())

    except FileNotFoundError:
        logger.debug("File processed_messages.csv does not exist, and will be created.")
    except EmptyDataError:
        logger.debug("File processed_messages.csv is empty, and will be populated.")

    # if not message_ids.issubset(processed_messages):
    if not set(unread_messages.keys()).issubset(processed_message_ids):

        unread_messages_df = pd.DataFrame.from_dict(unread_messages, orient="index", columns=PERSISTENT_DATA_COLUMNS)
        all_processed_messages_df = all_processed_messages_df.append(unread_messages_df)
        all_processed_messages_df.drop_duplicates(inplace=True)
        all_processed_messages_df.rename_axis("uuid", inplace=True)
        # noinspection PyTypeChecker
        all_processed_messages_df.to_csv(data_dir / "processed_messages.csv", header=PERSISTENT_DATA_COLUMNS)

        send_macos_notification(
            unread,
            all_unread_message_senders if all_unread_message_senders else processed_message_senders,
            "Messages",
            arguments
        )

    return standard_output


# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ MENUBAR PLUGIN iMessage/SMS CLASSES • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~


class TextMessage(BaseMessage):

    def __init__(self, df_row, max_line_characters, menubar_msg_display_str):
        super().__init__(df_row, max_line_characters, menubar_msg_display_str)

        self.sender = df_row.sender if df_row.sender else (df_row.org if df_row.org else df_row.contact)

        self.rowid = df_row.rowid
        self.cguid = df_row.cguid
        self.groupid = df_row.groupid
        self.contact = df_row.contact
        self.number = df_row.number
        self.attachment = df_row.attachment
        self.attachment_type = df_row.attchtype
        try:
            self.attachment_file, self.attachment_has_thumbnail = encode_attachment(df_row)
        except TypeError:
            self.attachment_file = None
        self.org = df_row.org


class TextConversation(BaseConversation):

    def __init__(self, text_message_obj, sqlite_cursor, sqlite_query, max_conversation_search_results):
        super().__init__(text_message_obj)

        if "chat" in text_message_obj.cid:
            self.is_group_conversation = True
            sqlite_cursor.execute(sqlite_query, (text_message_obj.cid, max_conversation_search_results))
            group_chat_df = pd.DataFrame(
                sqlite_cursor.fetchall(), columns=["cid", "timestamp", "contact", "number", "sender", "org"]
            )
            for df_row in group_chat_df.itertuples():
                # noinspection PyUnresolvedReferences
                self.participants.add(
                    df_row.sender if df_row.sender else (df_row.org if df_row.org else df_row.contact))
            if not self.title:
                self.title = f"{ANSI_OFF}Group Message{ANSI_YELLOW}"


# noinspection PyShadowingNames,SqlSignature
class TextOutput(BaseOutput):

    def __init__(self, credentials: Dict, project_root_dir: Path):

        self.project_root_dir = project_root_dir
        self.message_type = "text"

        self.macos_username = credentials.get("username")
        self.macos_full_name = self._get_macos_full_name(self.macos_username)

        conn = sqlite3.connect(f"/Users/{self.macos_username}/Library/Messages/chat.db")
        self.cursor = conn.cursor()

        self.conversations = OrderedDict()
        self.unread_count = 0

    def _directory_size(self, directory_path: Path, total_size: int = 0) -> int:
        for child_path in directory_path.rglob("*"):
            if child_path.is_file():
                total_size += child_path.stat().st_size
            elif child_path.is_dir():
                total_size = self._directory_size(child_path / child_path.name, total_size)

        return total_size

    def _sqlite_query_attach_contact_db(self) -> str:

        contact_directory_root = Path(f"/Users/{self.macos_username}/Library/Application Support/AddressBook/Sources/")

        contact_directory_sizes = []
        for p in Path(contact_directory_root).rglob("*"):

            if len(p.name) == 36:
                try:
                    UUID(p.name, version=4)
                    contact_directory_sizes.append((p.name, self._directory_size(p.absolute())))
                except ValueError:
                    pass

        contact_db = str(
            contact_directory_root
            / sorted(contact_directory_sizes, key=lambda x: x[1], reverse=True)[0][0]
            / "AddressBook-v22.abcddb"
        )

        return f"ATTACH '{contact_db}' as adb"

    # noinspection SqlResolve
    @staticmethod
    def _sqlite_query_get_messages() -> str:
        return """
            SELECT 
                msg.guid as id, 
                cht.rowid as rowid, 
                cht.guid as cguid, 
                cht.chat_identifier as cid, 
                cht.group_id as grp, 
                cht.display_name as title, 
                strftime(
                    '%m-%d-%Y %H:%M:%S', 
                    datetime(date/1000000000 + strftime('%s', '2001-01-01'), 'unixepoch', 'localtime')
                ) as timestamp, 
                CASE 
                    WHEN instr(hdl.id, '@') > 0 
                    THEN hdl.id 
                    ELSE substr(hdl.id, -10) 
                END contact, 
                substr(
                    replace(replace(replace(replace(pnmbr.ZFULLNUMBER, '-', ''), ' ', ''), '(', ''), ')', ''), 
                    -10
                ) as phone, 
                replace(
                    CASE 
                        WHEN rcrd.ZLASTNAME IS NULL 
                        THEN rcrd.ZFIRSTNAME 
                        ELSE 
                            rcrd.ZFIRSTNAME 
                            || ' ' || 
                            CASE 
                                WHEN rcrd.ZMIDDLENAME IS NULL 
                                THEN '' 
                                ELSE rcrd.ZMIDDLENAME 
                            END 
                            || ' ' || 
                            rcrd.ZLASTNAME 
                    END, '  ', ' ') as sender, 
                rcrd.ZORGANIZATION as org, 
                msg.cache_has_attachments, 
                atc.mime_type, 
                atc.filename, 
                replace(replace(text, CHAR(10), ' '), CHAR(13), ' ') as message 
            FROM message msg 
            INNER JOIN handle hdl 
                ON hdl.ROWID = msg.handle_id 
            LEFT JOIN chat_message_join cmj 
                ON cmj.message_id = msg.rowid 
            LEFT JOIN chat cht 
                ON cht.rowid = cmj.chat_id 
            LEFT JOIN message_attachment_join maj 
                ON (maj.message_id = msg.rowid AND msg.cache_has_attachments = 1) 
            LEFT JOIN attachment atc 
                ON atc.rowid = maj.attachment_id 
            LEFT JOIN adb.ZABCDPHONENUMBER pnmbr 
                ON phone = contact 
            LEFT JOIN adb.ZABCDEMAILADDRESS eml 
                ON eml.ZADDRESSNORMALIZED = contact 
            LEFT JOIN adb.ZABCDRECORD as rcrd 
                ON (rcrd.Z_PK = pnmbr.ZOWNER OR rcrd.Z_PK = eml.ZOWNER) 
            WHERE is_read = 0 
                AND text != 'NULL' 
                AND is_from_me != 1 
            ORDER BY date
        """

    # noinspection SqlResolve
    @staticmethod
    def _sqlite_query_get_messages_recent() -> str:
        return """
            SELECT 
                msg.guid as id, 
                cht.rowid as rowid, 
                cht.guid as cguid, 
                cht.chat_identifier as cid, 
                cht.group_id as grp, 
                cht.display_name as title, 
                strftime(
                    '%m-%d-%Y %H:%M:%S', 
                    datetime(date/1000000000 + strftime('%s', '2001-01-01'), 'unixepoch', 'localtime')
                ) as timestamp, 
                CASE 
                    WHEN instr(hdl.id, '@') > 0 
                    THEN hdl.id 
                    ELSE substr(hdl.id, -10) 
                END contact, 
                substr(
                    replace(replace(replace(replace(pnmbr.ZFULLNUMBER, '-', ''), ' ', ''), '(', ''), ')', ''), 
                    -10
                ) as phone, 
                replace(
                    CASE 
                        WHEN rcrd.ZLASTNAME IS NULL 
                        THEN rcrd.ZFIRSTNAME 
                        ELSE 
                            rcrd.ZFIRSTNAME 
                            || ' ' || 
                            CASE 
                                WHEN rcrd.ZMIDDLENAME IS NULL 
                                THEN '' 
                                ELSE rcrd.ZMIDDLENAME 
                            END 
                            || ' ' || 
                            rcrd.ZLASTNAME 
                    END, '  ', ' ') as sender, 
                rcrd.ZORGANIZATION as org, 
                msg.cache_has_attachments, 
                atc.mime_type, 
                atc.filename, 
                replace(replace(text, CHAR(10), ' '), CHAR(13), ' ') as message 
            FROM message msg 
            INNER JOIN handle hdl 
                ON hdl.ROWID = msg.handle_id 
            LEFT JOIN chat_message_join cmj 
                ON cmj.message_id = msg.rowid 
            LEFT JOIN chat cht 
                ON cht.rowid = cmj.chat_id 
            LEFT JOIN message_attachment_join maj 
                ON (maj.message_id = msg.rowid AND msg.cache_has_attachments = 1) 
            LEFT JOIN attachment atc 
                ON atc.rowid = maj.attachment_id 
            LEFT JOIN adb.ZABCDPHONENUMBER pnmbr 
                ON phone = contact 
            LEFT JOIN adb.ZABCDEMAILADDRESS eml 
                ON eml.ZADDRESSNORMALIZED = contact 
            LEFT JOIN adb.ZABCDRECORD as rcrd 
                ON (rcrd.Z_PK = pnmbr.ZOWNER OR rcrd.Z_PK = eml.ZOWNER) 
            WHERE text != 'NULL' 
                AND is_from_me != 1 
            ORDER BY date 
            DESC 
            LIMIT 100 
        """

    # noinspection SqlResolve
    @staticmethod
    def _sqlite_query_get_messages_group_chat() -> str:
        return """
            SELECT 
                cht.chat_identifier as cid, 
                strftime(
                    '%m-%d-%Y %H:%M:%S', 
                    datetime(date/1000000000 + strftime('%s', '2001-01-01') ,'unixepoch','localtime')
                ) as timestamp, 
                CASE 
                    WHEN instr(hdl.id, '@') > 0 
                    THEN hdl.id 
                    ELSE substr(hdl.id, -10) 
                END contact, 
                substr(
                    replace(replace(replace(replace(pnmbr.ZFULLNUMBER, '-', ''), ' ', ''), '(', ''), ')', ''), 
                    -10
                ) as phone, 
                replace(
                    CASE 
                        WHEN rcrd.ZLASTNAME IS NULL 
                        THEN rcrd.ZFIRSTNAME 
                        ELSE    
                            rcrd.ZFIRSTNAME 
                            || ' ' || 
                            CASE 
                                WHEN rcrd.ZMIDDLENAME IS NULL 
                                THEN '' 
                                ELSE rcrd.ZMIDDLENAME 
                            END 
                            || ' ' || 
                            rcrd.ZLASTNAME 
                    END, '  ', ' ') as sender, 
                rcrd.ZORGANIZATION as org 
            FROM message msg 
            INNER JOIN handle hdl 
                ON hdl.ROWID = msg.handle_id 
            LEFT JOIN adb.ZABCDPHONENUMBER pnmbr 
                ON phone = contact 
            LEFT JOIN adb.ZABCDEMAILADDRESS eml 
                ON eml.ZADDRESSNORMALIZED = contact 
            LEFT JOIN adb.ZABCDRECORD as rcrd 
                ON (rcrd.Z_PK = pnmbr.ZOWNER OR rcrd.Z_PK = eml.ZOWNER) 
            LEFT JOIN chat_message_join cmj 
                ON cmj.message_id = msg.rowid 
            LEFT JOIN chat cht 
                ON cht.rowid = cmj.chat_id 
            WHERE cht.chat_identifier = ? 
            ORDER BY date 
            DESC 
            LIMIT ? 
        """

    @staticmethod
    def _get_macos_full_name(macos_username: str) -> str:

        output = run(["id", "-F", f"{macos_username}"], stdout=PIPE, stderr=PIPE, universal_newlines=True)
        exit_code = output.returncode
        standard_output = output.stdout

        if exit_code == 0:
            return standard_output.strip()
        else:
            return macos_username

    # noinspection PyTypeChecker,PyUnresolvedReferences
    def _get_messages(self) -> None:

        self.cursor.execute(self._sqlite_query_attach_contact_db())
        self.cursor.execute(self._sqlite_query_get_messages())

        unread_df = pd.DataFrame(
            self.cursor.fetchall(),
            columns=[
                "id", "rowid", "cguid", "cid", "groupid", "title", "timestamp", "contact", "number", "sender", "org",
                "attachment", "attchtype", "attchfile", "body"
            ]
        )
        logging.debug(f"\n{unread_df.to_string()}\n")
        self.unread_count = len(unread_df.index)

        # self.cursor.execute(self._sqlite_query_get_messages_recent())
        # recent_df = pd.DataFrame(
        #     self.cursor.fetchall(),
        #     columns=[
        #         "id", "rowid", "cguid", "cid", "groupid", "title", "timestamp", "contact", "number", "sender", "org",
        #         "attachment", "attchtype", "attchfile", "body"
        #     ]
        # )
        # recent_df = recent_df[["rowid", "cid"]]

        # display messages in reverse order they were received (newest to oldest, top to bottom)
        # unread_df.sort_values("timestamp", inplace=True, ascending=False)

        for row in unread_df.itertuples():

            if "chat" in row.cid:
                open_script = "open_text_messages.sh"
                script_params = ""
            else:
                open_script = "open_text_messages_to_conversation.sh"
                script_params = f"param1={row.cid}"

            deep_link_conversation = (
                f"bash={str(self.project_root_dir)}/resources/scripts/{open_script} {script_params} "
                f"terminal=false "
                f"tooltip='Open Messages to this conversation'"
            )

            text_message = TextMessage(
                row,
                MAX_LINE_CHARS,
                deep_link_conversation
            )
            if text_message.cid not in self.conversations.keys():
                self.conversations[text_message.cid] = TextConversation(
                    text_message,
                    self.cursor,
                    self._sqlite_query_get_messages_group_chat(),
                    MAX_GROUP_CHAT_SEARCH_RESULTS
                )
            else:
                self.conversations.get(text_message.cid).add_message(text_message)

        for conversation in self.conversations.values():  # type: TextConversation
            conversation.sort_messages(descending=False)

    def get_console_output(self) -> List[str]:

        self._get_messages()

        display_str = (
            f"bash={str(self.project_root_dir)}/resources/scripts/open_text_messages.sh "
            f"terminal=false "
            f"tooltip='Open Messages'"
        )

        standard_output = []
        if self.unread_count == 0:
            standard_output.extend(
                generate_output_read(
                    self.project_root_dir,
                    self.message_type,
                    display_str,
                    self.macos_username,
                    user=self.macos_full_name
                )
            )

        else:
            arg_dict = {
                "contentImage": self.project_root_dir / "resources" / "images" / "icon_text.png",
                "sound": "Glass",
            }

            standard_output.extend(
                generate_output_unread(
                    self.project_root_dir,
                    self.message_type,
                    display_str,
                    self.unread_count,
                    self.conversations,
                    MAX_LINE_CHARS,
                    arg_dict,
                    self.macos_username,
                    user=self.macos_full_name
                )
            )

        return standard_output


# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • MENUBAR PLUGIN REDDIT CLASSES • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~


# noinspection DuplicatedCode
class RedditMessage(BaseMessage):

    def __init__(self, df_row, max_line_characters, display_string):
        super().__init__(df_row, max_line_characters, display_string)

        self.recipient = df_row.recipient
        self.subreddit = df_row.subreddit
        self.comment = bool(df_row.comment)

        if self.comment:
            self.cid = self.id

        if df_row.context:
            self.context = df_row.context
        else:
            self.context = f"/message/messages/{df_row.id}"

        link_unread_message = sanitize_url(f"https://www.reddit.com{self.context}")
        self.menubar_msg_display_str = f"href={link_unread_message} tooltip={link_unread_message} "


class RedditConversation(BaseConversation):

    def __init__(self, reddit_message_obj):
        super().__init__(reddit_message_obj)
        if reddit_message_obj.comment:
            self.type_str = f"{ANSI_RED} (comment){ANSI_OFF}"
        else:
            self.type_str = f"{ANSI_RED} (message){ANSI_OFF}"

    def get_participants_str(self) -> str:
        if self.is_group_conversation:
            return (
                f"{', '.join(participant for participant in self.participants)}"
                f"{', ...' if len(self.participants) == 1 else ''}{self.type_str}"
            )
        else:
            return f"{''.join(participant for participant in self.participants)}{self.type_str}"


# noinspection PyShadowingNames,DuplicatedCode
class RedditOutput(BaseOutput):

    def __init__(self, credentials: Union[Dict, List], project_root_dir: Path):

        self.project_root_dir = project_root_dir
        self.message_type = "reddit"

        self.reddit_account_credentials_list = []
        if type(credentials) == dict:
            self.reddit_account_credentials_list.append(credentials)
        elif type(credentials) == list:
            self.reddit_account_credentials_list = credentials

        self.accounts_conversations = {}  # type: Dict[str, OrderedDict]
        self.unread_count = 0
        link_unread = "https://www.reddit.com/message/unread/"
        self.unread_display_str = f"href={link_unread} tooltip={link_unread} "
        self.all_unread_message_senders = set()

        self.standard_error = []

    def _get_messages(self) -> None:

        for reddit_account_credentials in self.reddit_account_credentials_list:

            try:
                reddit = praw.Reddit(
                    client_id=reddit_account_credentials.get("client_id"),
                    client_secret=reddit_account_credentials.get("client_secret"),
                    refresh_token=reddit_account_credentials.get("refresh_token"),
                    user_agent="Reddit Notifications for macOS menubar"
                )

                reddit_username = reddit.user.me().name

                unread_messages = list(reddit.inbox.unread(limit=None))
                # getting all messages instead of just unread
                # all_messages = reddit.inbox.all(limit=5)

                self.unread_count += len(unread_messages)
                self.all_unread_message_senders.update([message.author.name for message in unread_messages])

                unread_df = pd.DataFrame(
                    columns=[
                        "id", "cid", "title", "timestamp", "sender", "body", "recipient", "subreddit", "comment",
                        "context"
                    ]
                )

                for unread_message in unread_messages:
                    logger.debug(f"Unread message vars:\n{vars(unread_message)}\n")
                    unread_df.loc[len(unread_df)] = [
                        unread_message.id,
                        unread_message.parent_id,
                        unread_message.subject,
                        unread_message.created_utc,
                        # message.created,
                        unread_message.author.name if unread_message.author else unread_message.distinguished,
                        unread_message.body,
                        unread_message.dest,
                        unread_message.subreddit,
                        unread_message.was_comment,
                        unread_message.context
                    ]
                logger.debug(f"\n{unread_df.to_string()}\n")

                # display messages in reverse order they were received (newest to oldest, top to bottom)
                # unread_df.sort_values("timestamp", inplace=True, ascending=False)

                conversations = OrderedDict()
                for row in unread_df.itertuples():

                    # noinspection PyTypeChecker
                    unread_message = RedditMessage(row, MAX_LINE_CHARS, self.unread_display_str)
                    if unread_message.cid not in conversations.keys():
                        conversations[unread_message.cid] = RedditConversation(unread_message)
                    else:
                        conversations.get(unread_message.cid).add_message(unread_message)

                self.accounts_conversations[reddit_username] = conversations

            except (ResponseException, RequestException) as e:
                self.standard_error.extend([
                    "---",
                    "❗",
                    f"--{ANSI_RED}UNABLE TO RETRIEVE REDDIT ACCOUNT CONTENT WITH ERROR: {repr(e)}! | ansi=true"
                ])

    def get_console_output(self) -> List[str]:

        self._get_messages()

        reddit_link = "https://www.reddit.com/message/inbox/"

        standard_output = []
        for reddit_username, conversations in self.accounts_conversations.items():

            if len(conversations) == 0:
                standard_output.extend(
                    generate_output_read(
                        self.project_root_dir,
                        self.message_type,
                        f"href={reddit_link} tooltip={reddit_link}",
                        reddit_username
                    )
                )

            else:
                arg_dict = {
                    "contentImage": self.project_root_dir / "resources" / "images" / "icon_reddit.png",
                    "sound": "Glass"
                }

                standard_output.extend(
                    generate_output_unread(
                        self.project_root_dir,
                        self.message_type,
                        self.unread_display_str,
                        self.unread_count,
                        conversations,
                        MAX_LINE_CHARS,
                        arg_dict,
                        reddit_username,
                        all_unread_message_senders=self.all_unread_message_senders
                    )
                )

        if self.standard_error:
            standard_output.extend(self.standard_error)

        return standard_output


# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ MENUBAR PLUGIN TELEGRAM CLASSES • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~


# noinspection DuplicatedCode
class TelegramMessage(BaseMessage):

    def __init__(self, df_row, max_line_characters, display_string):
        super().__init__(df_row, max_line_characters, display_string)

        self.id = str(df_row.id)
        self.cid = str(df_row.cid)

        self.attachment = df_row.attachment
        self.attachment_type = df_row.attachment_type
        self.attachment_file = df_row.attachment_file
        self.attachment_has_thumbnail = df_row.attachment_has_thumbnail

        self.context = f"?{df_row.context}" if df_row.context else ""

        deep_link_unread_message = sanitize_url(f"tg://openmessage{self.context}")
        self.menubar_msg_display_str = f"href={deep_link_unread_message} tooltip={deep_link_unread_message} "


class TelegramConversation(BaseConversation):

    def __init__(self, telegram_message_obj):
        super().__init__(telegram_message_obj)

    def get_participants_str(self) -> str:
        if self.is_group_conversation:
            if len(self.participants) > MAX_GROUP_CHAT_PARTICIPANT_DISPLAY:
                participants = ', '.join(
                    participant for participant in list(self.participants)[:MAX_GROUP_CHAT_PARTICIPANT_DISPLAY]
                )
                return f"{participants}, ..."
            else:
                return f"{', '.join(participant for participant in self.participants)}"
        else:
            return f"{''.join(participant for participant in self.participants)}"


# noinspection PyTypeChecker,PyShadowingNames
class TelegramOutput(BaseOutput):

    def __init__(self, credentials: Dict, project_root_dir: Path):

        self.project_root_dir = project_root_dir
        self.message_type = "telegram"

        self.credentials = credentials
        self.telegram_username = None

        self.conversations = OrderedDict()
        self.unread_count = 0

        telegram_deep_link = "tg://"
        self.unread_display_str = f"href={telegram_deep_link} tooltip={telegram_deep_link} "

    def _get_messages(self) -> None:

        with TelegramClient(
                StringSession(self.credentials.get("session_string")),
                self.credentials.get("api_id"),
                self.credentials.get("api_hash")) as client:  # type: TelegramClient

            telegram_user = client.get_me()  # type: User
            self.telegram_username = telegram_user.username

            unread_df = pd.DataFrame(
                columns=[
                    "id", "cid", "title", "timestamp", "sender", "body", "attachment", "attachment_type",
                    "attachment_file", "attachment_has_thumbnail", "context"
                ]
            )

            for dialog in client.iter_dialogs():  # type: Dialog
                if not getattr(dialog.entity, "is_private", False) and dialog.unread_count > 0:
                    self.unread_count += dialog.unread_count

                    unread_count = dialog.unread_count
                    for message in client.iter_messages(dialog.entity):  # type: Message

                        sender = message.get_sender()  # type: User

                        sender_name = ""
                        if sender.first_name:
                            sender_name += f"{sender.first_name} "
                        if sender.last_name:
                            sender_name += f"{sender.last_name} "
                        if sender.username:
                            sender_name += f"({sender.username})"

                        sender_name = sender_name.strip()

                        media_exists = 0
                        media_type = None
                        media_thumb_str = None
                        media_has_thumbnail = False
                        if message.media:
                            media_bytes = BytesIO()
                            message.download_media(file=media_bytes)

                            img = Image.open(media_bytes)
                            # img.show()
                            output, media_thumb_str, media_has_thumbnail = convert_image_to_bytes(
                                BytesIO(), img, "JPEG"
                            )

                            media_exists = 1
                            media_type = "image/jpeg"

                        unread_df.loc[len(unread_df)] = [
                            message.id,
                            dialog.id,
                            dialog.name if dialog.is_channel else None,
                            message.date,
                            sender_name,
                            message.message,
                            media_exists,
                            media_type,
                            media_thumb_str,
                            media_has_thumbnail,
                            f"user_id={sender.id}&message_id={message.id}"
                        ]

                        unread_count -= 1
                        if unread_count == 0:
                            break

            logger.debug(f"\n{unread_df.to_string()}\n")

            # display messages in reverse order they were received (newest to oldest, top to bottom)
            # unread_df.sort_values("timestamp", inplace=True, ascending=False)

            for row in unread_df.itertuples():

                # noinspection PyTypeChecker
                unread_message = TelegramMessage(row, MAX_LINE_CHARS, self.unread_display_str)
                if unread_message.cid not in self.conversations.keys():
                    self.conversations[unread_message.cid] = TelegramConversation(unread_message)
                else:
                    self.conversations.get(unread_message.cid).add_message(unread_message)

            for conversation in self.conversations.values():  # type: TelegramConversation
                conversation.sort_messages(descending=False)

    def get_console_output(self) -> List[str]:

        self._get_messages()

        telegram_deep_link = "tg://"

        standard_output = []
        if len(self.conversations) == 0:
            standard_output.extend(
                generate_output_read(
                    self.project_root_dir,
                    self.message_type,
                    f"href={telegram_deep_link} tooltip={telegram_deep_link}",
                    self.telegram_username
                )
            )

        else:
            arg_dict = {
                "contentImage": self.project_root_dir / "resources" / "images" / "icon_telegram.png",
                "sound": "Glass",
            }

            standard_output.extend(
                generate_output_unread(
                    self.project_root_dir,
                    self.message_type,
                    self.unread_display_str,
                    self.unread_count,
                    self.conversations,
                    MAX_LINE_CHARS,
                    arg_dict,
                    self.telegram_username
                )
            )

        return standard_output


# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ MENUBAR PLUGIN MAIN • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~


if __name__ == "__main__":

    start = time.process_time()

    project_root = Path(__file__).parent.parent
    with open(project_root / "resources" / "credentials" / "private.json", "r") as credentials_json:
        credentials = json.load(credentials_json)

    unread_count = 0
    standard_output = []
    for message_account_type in SUPPORTED_MESSAGE_TYPES:  # type: str

        spec = util.spec_from_file_location("message_notifier", Path(__file__).parent / "message_notifier.1m.py")
        py_module = util.module_from_spec(spec)
        spec.loader.exec_module(py_module)

        MessageOutput = getattr(py_module, f"{message_account_type.capitalize()}Output")
        message_account_output = MessageOutput(credentials.get(message_account_type), project_root)  # type: BaseOutput

        standard_output.extend(message_account_output.get_console_output())
        unread_count += message_account_output.get_unread_count()

    standard_output.append("---")
    standard_output.append(F"Refresh | font={FONT_ITALIC} color={HEX_BLUE} refresh=true")
    standard_output.append("---")

    if unread_count > 0:
        unread_icon = Icons(project_root, unread_count).unread_icon
        print(f"| color={HEX_ORANGE} image={unread_icon}")
    else:
        all_read_icon = Icons(project_root).all_read_icon
        print(f"|image={all_read_icon} dropdown=false")

    for line in standard_output:
        print(line)

    logger.debug(f"Message Notifier completion time: {time.process_time() - start}")
