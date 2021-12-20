#!/Users/wrenjr/.pyenv/versions/3.10.0/bin/python3
# -*- coding: utf-8 -*-

# <bitbar.title>macOS iMessage/SMS Notifications</bitbar.title>
# <bitbar.version>v1.0.0</bitbar.version>
# <bitbar.author>Wren J. R.</bitbar.author>
# <bitbar.author.github>uberfastman</bitbar.author.github>
# <bitbar.desc>Display unread iMessage/SMS messages in the macOS menubar!</bitbar.desc>
# <bitbar.image>https://github.com/uberfastman/local-bitbar-plugins/raw/develop/plugins/images/menubar-text-messages.png</bitbar.image>
# <bitbar.dependencies>python3,pandas,pync</bitbar.dependencies>
# <bitbar.abouturl>https://github.com/uberfastman/local-bitbar-plugins</bitbar.abouturl>

import base64
import calendar
import json
import logging
import sys

from cv2 import VideoCapture, imwrite, imencode
import os
import sqlite3
import textwrap
import time
from collections import OrderedDict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib import parse

import pandas as pd
from PIL import Image, ExifTags, ImageFilter
from pandas.errors import EmptyDataError
from pymediainfo import MediaInfo
from pync import Notifier

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ START SET CUSTOM LOCAL VARIABLES ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
max_line_chars = 75
max_group_chat_search_results = 10  # The higher this number, the longer the app will take to run each time.
thumbnail_pixel_size = 500
timestamp_font_size = 8
log_level = logging.WARN  # Logging levels: logging.INFO, logging.DEBUG, logging.WARN, logging.ERROR
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ END SET CUSTOM LOCAL VARIABLES ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

logger = logging.getLogger(__name__)
logging.basicConfig(level=log_level)


class Icons(object):

    def __init__(self, directory, message_type):
        self.all_read_icon = encode_image(
            directory + "resources/images/" + message_type + "-notifier.png")
        self.unread_icon = encode_image(
            directory + "resources/images/" + message_type + "-notifier-unread.png")


def format_timestamp(timestamp):
    message_timestamp = datetime.strptime(timestamp, "%m-%d-%Y %H:%M:%S")
    message_timestamp_str = message_timestamp.strftime("%m-%d-%Y %I:%M:%S %p").lower()

    today = datetime.today()
    if today.date() == message_timestamp.date():
        if today.hour == message_timestamp.hour:
            if today.minute == message_timestamp.minute:
                if today.second == message_timestamp.second:
                    return message_timestamp_str
                else:
                    second_delta = today.second - message_timestamp.second
                    return message_timestamp_str + " (Today - {} second{} ago)".format(
                        second_delta, "s" if second_delta > 1 else "")
            else:
                minute_delta = today.minute - message_timestamp.minute
                return message_timestamp_str + " (Today - {} minute{} ago)".format(
                    minute_delta, "s" if minute_delta > 1 else "")
        else:
            hour_delta = today.hour - message_timestamp.hour
            return message_timestamp_str + " (Today - {} hour{} ago)".format(hour_delta, "s" if hour_delta > 1 else "")
    else:
        day_delta = (today.date() - message_timestamp.date()).days
        # print("today:", today)
        # print("message timestamp:", message_timestamp)
        # print(today - message_timestamp)
        # print("day delta:", day_delta)
        if day_delta == 1:
            weekday_str = "Yesterday"
        else:
            weekday_str = calendar.day_name[message_timestamp.weekday()]
        return message_timestamp_str + " ({} - {} day{} ago)".format(weekday_str, day_delta,
                                                                     "s" if day_delta > 1 else "")


def sanitize_url(url_str):
    url = parse.urlsplit(url_str)
    url = list(url)
    url[2] = parse.quote(url[2])
    return parse.urlunsplit(url)


def encode_image(path_str):
    if path_str:
        path_str = str.replace(path_str, "~", str(Path.home()))
        with open(path_str, "rb") as img:
            return base64.b64encode(img.read()).decode("utf-8")


def encode_attachment(message_row, max_line_characters):
    path_str = message_row.attchfile
    mime_type = message_row.attchtype
    attachment_has_image_thumbnail = False

    if path_str:
        path_str = str.replace(path_str, "~", str(Path.home()))

        try:
            if mime_type == "text/vcard":
                # TODO: how to better read vcf file? Tried PyVCF and vcfpy, but both just provide complex VCF metadata
                with open(path_str, "r") as vcf_file:
                    thumb_str = textwrap.wrap(vcf_file.read(), max_line_characters + 1, break_long_words=False)
                return thumb_str, attachment_has_image_thumbnail

            else:
                output = BytesIO()

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

                        frame_img_with_watermark = Image.new("RGBA", frame_img.size, (0, 0, 0, 0))
                        frame_img_with_watermark.paste(frame_img, (0, 0))
                        frame_img_with_watermark.paste(watermark_img, position, mask=watermark_img)
                        frame_img_with_watermark = frame_img_with_watermark.convert("RGB")

                        # frame_img_with_watermark.show()
                        output = BytesIO()
                        frame_img_with_watermark.save(output, format="PNG")

                    else:
                        img = Image.open(video_file_icon_path)
                        img.save(output, format="PNG")
                else:
                    img = Image.open(path_str)

                    if mime_type == "image/jpeg":
                        orientation = 0
                        for key in ExifTags.TAGS.keys():
                            if ExifTags.TAGS[key] == "Orientation":
                                orientation = key

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

                            img.thumbnail((thumbnail_pixel_size, thumbnail_pixel_size), Image.ANTIALIAS)
                            img.save(output, format="JPEG")

                    elif mime_type == "image/gif":
                        img.save(output, save_all=True, format="GIF")

                    elif mime_type == "image/png":
                        img.save(output, format="PNG")

                    else:
                        # TODO: handle more image MIME types
                        pass

                img_data = output.getvalue()

                thumb_str = base64.b64encode(img_data).decode("utf-8")
                attachment_has_image_thumbnail = True

                return thumb_str, attachment_has_image_thumbnail

        except IOError:
            logger.error("Unable to create thumbnail for '%s'" % path_str)


def send_macos_notification(unread, message_senders, title, arguments):
    notification_group_id = "notifier"

    Notifier.notify(
        message="Message" + ("s" if (len(message_senders) > 1 and unread > 1) else "") + " from: " +
                ", ".join(message_senders),  # content of notification
        title=title + ": " + str(unread) + " unread message" + (
            "s" if unread > 1 else ""),  # notification title
        group=notification_group_id,  # ID used to group notification with previous notifications
        **arguments
    )

    Notifier.remove(notification_group_id)


def generate_output_read(local_dir, message_type, display_string):
    all_read_icon = Icons(local_dir, message_type).all_read_icon
    print("|image=" + all_read_icon)
    print("---")
    print("No unread " + message_type + " messages! (Go to messages ↗︎️) | color=teal " + display_string)
    print("---")
    print("Refresh | font=HelveticaNeue-Italic color=#7FC3D8 refresh=true")

    # create data directory if it does not exist
    if not os.path.isdir(local_dir + "resources/data"):
        os.makedirs(local_dir + "resources/data")

    # open processed messages file using w+ mode to truncate the contents (clear all processed message UUIDs)
    file = open(
        local_dir + "resources/data/" + message_type + "_messages_processed.csv", "w+")
    file.close()


def generate_output_unread(local_dir, message_type, display_string, unread, conversations, max_line_characters,
                           arguments):
    unread_icon = Icons(local_dir, message_type).unread_icon
    print(str(unread) + " | color=#e05415 " + "image=" + unread_icon)
    print("---")
    print("Go to " + message_type + " messages ↗︎️ | font=HelveticaNeue-Italic color=#e05415 " + display_string)
    print("---")
    print("Refresh | font=HelveticaNeue-Italic color=#7FC3D8 refresh=true")
    print("---")

    message_ids = set()
    message_senders = set()
    message_num = 1
    for cid, conversation in conversations.items():
        message_display_str = u" \u001b[37m| ansi=true refresh=true "

        if conversation.title:
            print(
                conversation.title + message_display_str + conversation.menubar_msg_display_str + " font=Menlo size=10")

        print(u"\u001b[33m" + conversation.get_participants_str() + message_display_str +
              conversation.menubar_msg_display_str)

        for message in conversation.messages:

            timestamp_display_str = u"\u001b[36m" + message.timestamp + "\u001b[32m" + message_display_str + \
                                    message.menubar_msg_display_str + " size=" + str(timestamp_font_size)
            msg_sender_start_str = u"\u001b[31m(" + message.sender + ") \u001b[32m"
            msg_format_str = u"\u001b[32m"

            if message.attachment == 1:
                if message.get_message_len() == 0:
                    msg_attachment_str = u"\u001b[35m(attachment{}) \u001b[32m".format(
                        (" - " + message.attchtype) if message.attchtype else "")
                else:
                    # TODO: handle messages that are longer than the max_line_chars with video attachments
                    msg_attachment_str = u"{} \u001b[35m(attachment{}) \u001b[32m".format(
                        message.body, (" - " + message.attchtype) if message.attchtype else "")

                if conversation.is_group_conversation:
                    print(timestamp_display_str)
                    print(msg_sender_start_str + msg_attachment_str + message_display_str +
                          message.menubar_msg_display_str)
                else:
                    print(timestamp_display_str)
                    print(msg_format_str + msg_attachment_str + message_display_str + message.menubar_msg_display_str)
                if message.attchfile:
                    if message.attchhasthumb:
                        print("--| " + "image=" + message.attchfile + " " + message.menubar_msg_display_str)
                    else:
                        for line in message.attchfile:
                            print(u"--\u001b[37m\u001b[49m" + line + "|" + message.menubar_msg_display_str)

            elif message.get_message_len() > max_line_characters:
                if conversation.is_group_conversation:
                    print(timestamp_display_str)
                    print(msg_sender_start_str + message.body_short + message_display_str +
                          message.menubar_msg_display_str)
                else:
                    print(timestamp_display_str)
                    print(msg_format_str + message.body_short + message_display_str + message.menubar_msg_display_str)
                for line in message.body_wrapped:
                    print(u"--\u001b[37m\u001b[49m" + line + message_display_str + message.menubar_msg_display_str)

            else:
                if conversation.is_group_conversation:
                    print(timestamp_display_str)
                    print(msg_sender_start_str + message.body + message_display_str + message.menubar_msg_display_str)
                else:
                    print(timestamp_display_str)
                    print(msg_format_str + message.body + message_display_str + message.menubar_msg_display_str)

            if conversation.messages.index(message) != (len(conversation.messages) - 1):
                print("⠀" + "| size=2")  # Unicode character '⠀' (U+2800) for blank lines

            message_ids.add(str.lower(message.id))
            message_senders.add(message.sender)

        print("---")
        message_num += 1

    # create data directory if it does not exist
    if not os.path.isdir(local_dir + "resources/data"):
        os.makedirs(local_dir + "resources/data")

    processed_messages = set()
    try:
        processed_messages = set(
            pd.read_csv(
                local_dir + "resources/data/" + message_type +
                "_messages_processed.csv")["uuid"].tolist())
    except FileNotFoundError:
        logger.debug("File " + message_type + "_messages_processed.csv does not exist, and will be created.")
    except EmptyDataError:
        logger.debug(
            "File " + message_type +
            "_messages_processed.csv is empty, and will be populated with any current unread message UUIDs.")

    if not message_ids.issubset(processed_messages):
        message_ids_series = pd.Series(list(message_ids))
        message_ids_series.to_csv(
            local_dir + "resources/data/" + message_type + "_messages_processed.csv",
            header=["uuid"])

        send_macos_notification(unread, message_senders, "Messages", arguments)


class BaseMessage(object):

    def __init__(self, df_row, max_line_characters, menubar_msg_display_str):
        self.id = df_row.id
        self.cid = df_row.cid
        self.title = df_row.title
        self.timestamp = df_row.timestamp
        self.sender = df_row.sender
        self.body = df_row.body.replace('\n', ' ').replace('\r', '').strip()
        self.body_short = self.body[:max_line_characters] + "..."
        self.body_wrapped = textwrap.wrap(self.body, max_line_characters + 1, break_long_words=False)
        self.attachment = 0
        self.menubar_msg_display_str = menubar_msg_display_str

    def get_message_len(self):
        return len(self.body.encode("ascii", "ignore"))

    def __repr__(self):
        return str(vars(self))

    def __str__(self):
        return str(vars(self))


class BaseConversation(object):

    def __init__(self, message_obj):
        self.id = message_obj.cid
        self.title = "\u001b[39m" + message_obj.title + "\u001b[33m" if message_obj.title else ""
        self.messages = [message_obj]
        self.participants = {message_obj.sender}
        self.is_group_conversation = False
        self.menubar_msg_display_str = message_obj.menubar_msg_display_str

    def add_message(self, message_obj):
        if message_obj.cid == self.id:
            self.messages.append(message_obj)
            self.participants.add(message_obj.sender)
            if len(self.participants) > 1:
                self.is_group_conversation = True
                if not self.title:
                    self.title = "\u001b[39mGroup Message\u001b[33m"
        else:
            raise ValueError("Cannot add Message with mismatching id to Conversation!")

    def get_message_count(self):
        return len(self.messages)

    def get_participants_str(self):
        if self.is_group_conversation:
            return ", ".join(participant for participant in self.participants) + (
                ", ..." if len(self.participants) == 1 else "")
        else:
            return "".join(participant for participant in self.participants)

    def __repr__(self):
        return str(vars(self))

    def __str__(self):
        return str(vars(self))

# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • SQLITE DB QUERIES • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~


def get_sqlite_attach_db_query(username, contact_database_directory):

    sqlite_attach_query = f"""
        ATTACH '/Users/{username}/Library/Application Support/AddressBook/Sources/{contact_database_directory}/AddressBook-v22.abcddb' as adb
    """
    return sqlite_attach_query


# query for copy/paste to SQLite console
# noinspection SqlResolve
"""
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
    substr(replace(replace(replace(replace(pnmbr.ZFULLNUMBER, '-', ''), ' ', ''), '(', ''), ')', ''), -10) as phone, 
    replace(
        CASE 
            WHEN rcrd.ZLASTNAME IS NULL 
            THEN rcrd.ZFIRSTNAME 
            ELSE rcrd.ZFIRSTNAME || ' ' || 
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
sqlite_select_query = """
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
        substr(replace(replace(replace(replace(pnmbr.ZFULLNUMBER, '-', ''), ' ', ''), '(', ''), ')', ''), -10) as phone, 
        replace(
            CASE 
                WHEN rcrd.ZLASTNAME IS NULL 
                THEN rcrd.ZFIRSTNAME 
                ELSE rcrd.ZFIRSTNAME || ' ' || 
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

# sqlite_select_query = """
#     SELECT
#         rcrd.*,
#         msg.guid as id,
#         cht.rowid as rowid,
#         cht.guid as cguid,
#         cht.chat_identifier as cid,
#         cht.group_id as grp,
#         cht.display_name as title,
#         strftime(
#             '%m-%d-%Y %H:%M:%S',
#             datetime(date/1000000000 + strftime('%s', '2001-01-01') ,'unixepoch','localtime')
#         ) as timestamp,
#         CASE
#             WHEN instr(hdl.id, '@') > 0
#             THEN hdl.id
#             ELSE substr(hdl.id, -10)
#         END contact,
#         substr(replace(replace(replace(replace(pnmbr.ZFULLNUMBER, '-', ''), ' ', ''), '(', ''), ')', ''), -10) as phone,
#         replace(
#             CASE
#                 WHEN rcrd.ZLASTNAME IS NULL
#                 THEN rcrd.ZFIRSTNAME
#                 ELSE rcrd.ZFIRSTNAME
#                 || ' ' ||
#                 CASE
#                     WHEN rcrd.ZMIDDLENAME IS NULL
#                     THEN ''
#                     ELSE rcrd.ZMIDDLENAME
#                 END
#                 || ' ' ||
#                 rcrd.ZLASTNAME
#             END, '  ', ' ') as sender,
#         rcrd.ZORGANIZATION as org,
#         msg.cache_has_attachments,
#         atc.mime_type,
#         atc.filename,
#         replace(replace(text, CHAR(10), ' '), CHAR(13), ' ') as message
#     FROM message msg
#     INNER JOIN handle hdl
#         ON hdl.ROWID = msg.handle_id
#     LEFT JOIN chat_message_join cmj
#         ON msg.rowid = cmj.message_id
#     LEFT JOIN chat cht
#         ON cmj.chat_id = cht.rowid
#     LEFT JOIN message_attachment_join maj
#         ON (msg.rowid = maj.message_id AND msg.cache_has_attachments = 1)
#     LEFT JOIN attachment atc
#         ON maj.attachment_id = atc.rowid
#     LEFT JOIN adb.ZABCDPHONENUMBER pnmbr
#         ON contact = phone
#     LEFT JOIN adb.ZABCDEMAILADDRESS eml
#         ON contact = eml.ZADDRESSNORMALIZED
#     LEFT JOIN adb.ZABCDRECORD as rcrd
#         ON (pnmbr.ZOWNER = rcrd.Z_PK OR eml.ZOWNER = rcrd.Z_PK)
#     WHERE is_read = 0
#         AND text != 'NULL'
#         AND is_from_me != 1
#     ORDER BY date;
# """

# noinspection SqlResolve
sqlite_get_recent_query = "SELECT " \
                          "msg.guid as id, " \
                          "cht.rowid as rowid, " \
                          "cht.guid as cguid, " \
                          "cht.chat_identifier as cid, " \
                          "cht.group_id as grp, " \
                          "cht.display_name as title, " \
                          "strftime(" \
                            "'%m-%d-%Y %H:%M:%S', " \
                            "datetime(date/1000000000 + strftime('%s', '2001-01-01'), 'unixepoch', 'localtime')" \
                          ") as timestamp, " \
                          "CASE " \
                            "WHEN instr(hdl.id, '@') > 0 " \
                            "THEN hdl.id " \
                            "ELSE substr(hdl.id, -10) " \
                          "END contact, " \
                          "substr(" \
                            "replace(" \
                              "replace(" \
                                "replace(" \
                                  "replace(" \
                                    "pnmbr.ZFULLNUMBER, '-', ''), ' ', ''), '(', ''), ')', ''), -10" \
                          ") as phone, " \
                          "replace(" \
                            "CASE " \
                              "WHEN rcrd.ZLASTNAME IS NULL " \
                              "THEN rcrd.ZFIRSTNAME " \
                              "ELSE rcrd.ZFIRSTNAME " \
                                "|| ' ' || " \
                                "CASE " \
                                  "WHEN rcrd.ZMIDDLENAME IS NULL " \
                                  "THEN '' " \
                                  "ELSE rcrd.ZMIDDLENAME " \
                                "END " \
                                "|| ' ' || " \
                                "rcrd.ZLASTNAME " \
                            "END, '  ', ' ') as sender, " \
                          "rcrd.ZORGANIZATION as org, " \
                          "msg.cache_has_attachments, " \
                          "atc.mime_type, " \
                          "atc.filename, " \
                          "replace(replace(text, CHAR(10), ' '), CHAR(13), ' ') as message " \
                        "FROM message msg " \
                        "INNER JOIN handle hdl " \
                          "ON hdl.ROWID = msg.handle_id " \
                        "LEFT JOIN chat_message_join cmj " \
                          "ON cmj.message_id = msg.rowid " \
                        "LEFT JOIN chat cht " \
                          "ON cht.rowid = cmj.chat_id " \
                        "LEFT JOIN message_attachment_join maj " \
                          "ON (maj.message_id = msg.rowid AND msg.cache_has_attachments = 1) " \
                        "LEFT JOIN attachment atc " \
                          "ON atc.rowid = maj.attachment_id " \
                        "LEFT JOIN adb.ZABCDPHONENUMBER pnmbr " \
                          "ON phone = contact " \
                        "LEFT JOIN adb.ZABCDEMAILADDRESS eml " \
                          "ON eml.ZADDRESSNORMALIZED = contact " \
                        "LEFT JOIN adb.ZABCDRECORD as rcrd " \
                          "ON (rcrd.Z_PK = pnmbr.ZOWNER OR rcrd.Z_PK = eml.ZOWNER) " \
                        "WHERE text != 'NULL' " \
                        "ORDER BY date " \
                        "DESC " \
                        "LIMIT 100 "

# noinspection SqlResolve
sqlite_group_chat_query = "SELECT " \
                            "cht.chat_identifier as cid, " \
                            "strftime(" \
                              "'%m-%d-%Y %H:%M:%S', " \
                              "datetime(date/1000000000 + strftime('%s', '2001-01-01') ,'unixepoch','localtime')" \
                            ") as timestamp, " \
                            "CASE " \
                              "WHEN instr(hdl.id, '@') > 0 " \
                              "THEN hdl.id " \
                              "ELSE substr(hdl.id, -10) " \
                            "END contact, " \
                            "substr(" \
                              "replace(" \
                                "replace(" \
                                  "replace(" \
                                    "replace(" \
                                      "pnmbr.ZFULLNUMBER, '-', ''), ' ', ''), '(', ''), ')', ''), -10" \
                            ") as phone, " \
                            "replace(" \
                              "CASE " \
                                "WHEN rcrd.ZLASTNAME IS NULL " \
                                "THEN rcrd.ZFIRSTNAME " \
                                "ELSE rcrd.ZFIRSTNAME " \
                                  "|| ' ' || " \
                                  "CASE " \
                                    "WHEN rcrd.ZMIDDLENAME IS NULL " \
                                    "THEN '' " \
                                    "ELSE rcrd.ZMIDDLENAME " \
                                  "END " \
                                  "|| ' ' || " \
                                  "rcrd.ZLASTNAME " \
                              "END, '  ', ' ') as sender, " \
                            "rcrd.ZORGANIZATION as org " \
                          "FROM message msg " \
                          "INNER JOIN handle hdl " \
                            "ON hdl.ROWID = msg.handle_id " \
                          "LEFT JOIN adb.ZABCDPHONENUMBER pnmbr " \
                            "ON phone = contact " \
                          "LEFT JOIN adb.ZABCDEMAILADDRESS eml " \
                            "ON eml.ZADDRESSNORMALIZED = contact " \
                          "LEFT JOIN adb.ZABCDRECORD as rcrd " \
                            "ON (rcrd.Z_PK = pnmbr.ZOWNER OR rcrd.Z_PK = eml.ZOWNER) " \
                          "LEFT JOIN chat_message_join cmj " \
                            "ON cmj.message_id = msg.rowid " \
                          "LEFT JOIN chat cht " \
                            "ON cht.rowid = cmj.chat_id " \
                          "WHERE cht.chat_identifier = ? " \
                          "ORDER BY date " \
                          "DESC " \
                          "LIMIT ? "

# sqlite_query_order_by = "ORDER BY strftime('%m-%d-%Y %H:%M:%S', datetime(date/1000000000 + " \
#                         "strftime('%s', '2001-01-01') ,'unixepoch','localtime'))"

# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • START CUSTOM PLUGIN ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~


class TextMessage(BaseMessage):

    def __init__(self, df_row, max_line_characters, menubar_msg_display_str):
        super().__init__(df_row, max_line_characters, menubar_msg_display_str)

        self.timestamp = format_timestamp(df_row.timestamp)
        self.sender = df_row.sender if df_row.sender else (df_row.org if df_row.org else df_row.contact)

        self.rowid = df_row.rowid
        self.cguid = df_row.cguid
        self.groupid = df_row.groupid
        self.contact = df_row.contact
        self.number = df_row.number
        self.attachment = df_row.attachment
        self.attchtype = df_row.attchtype
        try:
            self.attchfile, self.attchhasthumb = encode_attachment(df_row, max_line_characters)
        except TypeError:
            self.attchfile = None
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
                self.participants.add(
                    df_row.sender if df_row.sender else (df_row.org if df_row.org else df_row.contact))
            if not self.title:
                self.title = "\u001b[39mGroup Message\u001b[33m"


start = time.process_time()

# Currently supported message services: text (iMessage/SMS on macOS), reddit
message_type_str = "text"
local_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/"

with open(local_directory + "resources/credentials/private-" + message_type_str + ".json", "r") as credentials_json:
    credentials = json.load(credentials_json)

macos_username = credentials.get("username")
contact_db_dir = credentials.get("contact_db_dir")

conn = sqlite3.connect("/Users/" + macos_username + "/Library/Messages/chat.db")
cursor = conn.cursor()
cursor.execute(get_sqlite_attach_db_query(macos_username, contact_db_dir))
cursor.execute(sqlite_select_query)

unread_df = pd.DataFrame(
    cursor.fetchall(),
    columns=["id", "rowid", "cguid", "cid", "groupid", "title", "timestamp", "contact", "number", "sender", "org",
             "attachment", "attchtype", "attchfile", "body"]
)
logging.debug(unread_df.to_string())
unread_count = len(unread_df.index)

cursor.execute(sqlite_get_recent_query)
recent_df = pd.DataFrame(
    cursor.fetchall(),
    columns=["id", "rowid", "cguid", "cid", "groupid", "title", "timestamp", "contact", "number", "sender", "org",
             "attachment", "attchtype", "attchfile", "body"]
)
recent_df = recent_df[["rowid", "cid"]]

chat_order_dict = OrderedDict()
chat_order = 1
for row in recent_df.itertuples():
    if row.cid not in chat_order_dict.keys():
        chat_order_dict[row.cid] = chat_order
        chat_order += 1

display_str = "bash=" + local_directory + "resources/scripts/open_text_messages.sh terminal=false "

conversations_dict = OrderedDict()
for row in unread_df.itertuples():
    text_message = TextMessage(
        row, max_line_chars, "bash=" + local_directory + "resources/scripts/open-messages-to-conversation.sh param1=" +
                             str(chat_order_dict.get(row.cid)) + " terminal=false ")
    if text_message.cid not in conversations_dict.keys():
        conversations_dict[text_message.cid] = TextConversation(
            text_message, cursor, sqlite_group_chat_query, max_group_chat_search_results)
    else:
        conversations_dict.get(text_message.cid).add_message(text_message)

if unread_count == 0:
    generate_output_read(local_directory, message_type_str, display_str)

else:
    arg_dict = {
        # "appIcon": local_dir + "notifier/" + message_type_str + "/images/MessagesAppIcon.png",
        # "activate": "com.apple.iChat",
        # "execute": "open -a Messages",
        # "sound": "Glass"
        "sender": "com.apple.iChat"
    }

    generate_output_unread(
        local_directory, message_type_str, display_str, unread_count, conversations_dict, max_line_chars, arg_dict)

logger.debug(time.process_time() - start)
