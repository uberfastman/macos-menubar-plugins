#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

# Adapted from code originally written by /u/HeyItsShuga found here:
# https://github.com/matryer/bitbar-plugins/blob/master/Web/Reddit/redditnotify.30s.py

# <bitbar.title>Reddit Notifications</bitbar.title>
# <bitbar.version>v1.0.0</bitbar.version>
# <bitbar.author>Wren J. R.</bitbar.author>
# <bitbar.author.github>uberfastman</bitbar.author.github>
# <bitbar.desc>Display unread reddit messages in the macOS menubar!</bitbar.desc>
# <bitbar.image>https://github.com/uberfastman/local-bitbar-plugins/raw/develop/plugins/images/menubar-reddit-messages.png</bitbar.image>
# <bitbar.dependencies>python3,praw,pync</bitbar.dependencies>
# <bitbar.abouturl>https://github.com/uberfastman/local-bitbar-plugins</bitbar.abouturl>

import base64
import calendar
import json
import logging
import os
import sys
import textwrap
import time
from collections import OrderedDict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib import parse

import pandas as pd
import praw
from PIL import Image, ExifTags
from dateutil import tz
from pandas.errors import EmptyDataError
from prawcore.exceptions import ResponseException, RequestException
from pymediainfo import MediaInfo
from pync import Notifier

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ START SET CUSTOM LOCAL VARIABLES ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
max_line_chars = 50
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

                attachment_media_file = MediaInfo.parse(
                    path_str,
                    library_file=Path(__file__).resolve().parent.parent.joinpath("resources", "libmediainfo.0.dylib")
                )
                attachment_is_video = False
                for track in attachment_media_file.tracks:
                    if track.track_type == "Video":
                        attachment_is_video = True

                if attachment_is_video:
                    # TODO: extract first frame of video for thumbnail instead of placeholder image
                    video_file_icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                        os.path.abspath(__file__)))), "resources", "images", "text-video-file.png")
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
    print(local_dir)
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
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • START CUSTOM PLUGIN ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~
# ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~ • ~


class RedditMessage(BaseMessage):

    def __init__(self, df_row, max_line_characters, display_string):
        super().__init__(df_row, max_line_characters, display_string)

        self.timestamp = datetime.utcfromtimestamp(df_row.timestamp).strftime("%m-%d-%Y %H:%M:%S")
        utc_time_zone = tz.tzutc()
        local_time_zone = tz.tzlocal()

        self.timestamp = datetime.strptime(self.timestamp, "%m-%d-%Y %H:%M:%S")
        self.timestamp = self.timestamp.replace(tzinfo=utc_time_zone)
        self.timestamp = self.timestamp.astimezone(local_time_zone)
        self.timestamp = self.timestamp.strftime("%m-%d-%Y %H:%M:%S")

        self.timestamp = format_timestamp(str(self.timestamp))

        self.recipient = df_row.recipient
        self.subreddit = df_row.subreddit
        self.comment = bool(df_row.comment)

        if self.comment:
            self.cid = self.id

        if df_row.context:
            self.context = df_row.context
        else:
            self.context = "/message/messages/" + df_row.id

        self.menubar_msg_display_str = "href=" + sanitize_url("https://www.reddit.com" + self.context)


class RedditConversation(BaseConversation):

    def __init__(self, reddit_message_obj):
        super().__init__(reddit_message_obj)
        if reddit_message_obj.comment:
            self.type_str = "\u001b[31m (comment)\u001b[39m"
        else:
            self.type_str = "\u001b[31m (message)\u001b[39m"

    def get_participants_str(self):
        if self.is_group_conversation:
            return ", ".join(participant for participant in self.participants) + (
                ", ..." if len(self.participants) == 1 else "") + self.type_str
        else:
            return "".join(participant for participant in self.participants) + self.type_str


start = time.process_time()

# Currently supported message services: text (iMessage/SMS on macOS), reddit, slack
message_type_str = "reddit"
local_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/"

with open(local_directory + "resources/credentials/private-" + message_type_str + ".json", "r") as credentials_json:
    credentials = json.load(credentials_json)

reddit = praw.Reddit(client_id=credentials.get("client_id"),
                     client_secret=credentials.get("client_secret"),
                     refresh_token=credentials.get("refresh_token"),
                     user_agent="Reddit Notifications for macOS menubar")

unread_messages = reddit.inbox.unread(limit=None)
# getting all messages instead of just unread
# unread = reddit.inbox.all(limit=5)

unread_df = pd.DataFrame(
    columns=["id", "cid", "title", "timestamp", "sender", "body", "recipient", "subreddit", "comment", "context"]
)

try:
    for unread_message in unread_messages:
        # print(vars(message))
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
    logger.debug(unread_df.to_string())
except (ResponseException, RequestException) as e:
    print("❗")
    print("---")
    print("UNABLE TO RETRIEVE REDDIT CONTENT!")
    sys.exit(str(e))

unread_count = len(unread_df.index)
unread_display_str = "href=https://www.reddit.com/message/unread/ "

conversations_dict = OrderedDict()
for row in unread_df.itertuples():

    unread_message = RedditMessage(row, max_line_chars, unread_display_str)
    if unread_message.cid not in conversations_dict.keys():
        conversations_dict[unread_message.cid] = RedditConversation(unread_message)
    else:
        conversations_dict.get(unread_message.cid).add_message(unread_message)

if unread_count == 0:
    generate_output_read(local_directory, message_type_str, "href=https://www.reddit.com/message/inbox/")

else:
    arg_dict = {
        "appIcon": local_directory + "resources/images/reddit-icon.png",
        "open": "https://www.reddit.com/message/inbox/",
        "sound": "Glass"
    }

    generate_output_unread(
        local_directory, message_type_str, unread_display_str, unread_count, conversations_dict, max_line_chars,
        arg_dict)

logger.debug(time.process_time() - start)
