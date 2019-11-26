#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import base64
import calendar
import logging
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib import parse

import pandas as pd
from PIL import Image, ExifTags
from pandas.errors import EmptyDataError
from pync import Notifier

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~ START SET CUSTOM LOCAL VARIABLES ~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
thumbnail_pixel_size = 500
timestamp_font_size = 8
log_level = logging.WARN  # Logging levels: logging.INFO, logging.DEBUG, logging.WARN, logging.ERROR
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~ END SET CUSTOM LOCAL VARIABLES ~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

logger = logging.getLogger(__name__)
logging.basicConfig(level=log_level)


class Icons(object):

    def __init__(self, local_dir, message_type_str):
        self.all_read_icon = encode_image(
            local_dir + "notifier/" + message_type_str + "/images/" + message_type_str + "-notifier.png")
        self.unread_icon = encode_image(
            local_dir + "notifier/" + message_type_str + "/images/" + message_type_str + "-notifier-unread.png")


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


def encode_image_thumbnail(path_str, mime_type):
    if path_str:
        path_str = str.replace(path_str, "~", str(Path.home()))

        try:
            img = Image.open(path_str)
            output = BytesIO()

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
                    except KeyError as ke:
                        logger.error("Unable to rotate image due to KeyError: {}".format(ke))

                    img.thumbnail((thumbnail_pixel_size, thumbnail_pixel_size), Image.ANTIALIAS)
                    img.save(output, format="JPEG")

            elif mime_type == "image/gif":
                img.save(output, save_all=True, format="GIF")

            img_data = output.getvalue()

            thumb_str = base64.b64encode(img_data).decode("utf-8")
            return thumb_str

        except IOError:
            logger.error("Unable to create thumbnail for '%s'" % path_str)


def send_macos_notification(unread_count, message_senders, title, arg_dict):
    notification_group_id = "notifier"

    Notifier.notify(
        message="Message" + ("s" if (len(message_senders) > 1 and unread_count > 1) else "") + " from: " +
                ", ".join(message_senders),  # content of notification
        title=title + ": " + str(unread_count) + " unread message" + (
            "s" if unread_count > 1 else ""),  # notification title
        group=notification_group_id,  # ID used to group notification with previous notifications
        **arg_dict
    )

    Notifier.remove(notification_group_id)


def generate_output_read(local_dir, message_type_str, bitbar_display_str):
    all_read_icon = Icons(local_dir, message_type_str).all_read_icon
    print("|image=" + all_read_icon)
    print("---")
    print("No unread " + message_type_str + " messages! (Go to messages ↗︎️) | color=teal " + bitbar_display_str)
    print("---")
    print("Refresh | font=HelveticaNeue-Italic color=#7FC3D8 refresh=true")

    # open processed messages file using w+ mode to truncate the contents (clear all processed message UUIDs)
    file = open(
        local_dir + "notifier/" + message_type_str + "/data/" + message_type_str + "_messages_processed.csv", "w+")
    file.close()


def generate_output_unread(local_dir, message_type_str, bitbar_display_str, unread_count, conversations, max_line_chars,
                           arg_dict):
    unread_icon = Icons(local_dir, message_type_str).unread_icon
    print(str(unread_count) + " | color=#e05415 " + "image=" + unread_icon)
    print("---")
    print("Go to " + message_type_str + " messages ↗︎️ | font=HelveticaNeue-Italic color=#e05415 " + bitbar_display_str)
    print("---")
    print("Refresh | font=HelveticaNeue-Italic color=#7FC3D8 refresh=true")
    print("---")

    message_ids = set()
    message_senders = set()
    message_num = 1
    for cid, conversation in conversations.items():
        message_display_str = u" \u001b[37m| ansi=true refresh=true "

        if conversation.title:
            print(conversation.title + message_display_str + conversation.bitbar_msg_display_str + " font=Menlo size=10")

        print(u"\u001b[33m" + conversation.get_participants_str() + message_display_str +
              conversation.bitbar_msg_display_str)

        for message in conversation.messages:

            timestamp_display_str = u"\u001b[36m" + message.timestamp + "\u001b[32m" + message_display_str + \
                                    message.bitbar_msg_display_str + " size=" + str(timestamp_font_size)
            msg_sender_start_str = u"\u001b[31m(" + message.sender + ") \u001b[32m"
            msg_format_str = u"\u001b[32m"

            if message.get_message_len() == 0 and message.attachment == 1:

                msg_attachment_str = u"\u001b[35m(attachment) \u001b[32m"
                if conversation.is_group_conversation:
                    print(timestamp_display_str)
                    print(msg_sender_start_str + msg_attachment_str + message_display_str +
                          message.bitbar_msg_display_str)
                else:
                    print(timestamp_display_str)
                    print(msg_format_str + msg_attachment_str + message_display_str + message.bitbar_msg_display_str)
                if message.attchfile:
                    print("--| " + "image=" + message.attchfile + " " + message.bitbar_msg_display_str)

            elif message.get_message_len() > max_line_chars:
                if conversation.is_group_conversation:
                    print(timestamp_display_str)
                    print(msg_sender_start_str + message.body_short + message_display_str +
                          message.bitbar_msg_display_str)
                else:
                    print(timestamp_display_str)
                    print(msg_format_str + message.body_short + message_display_str + message.bitbar_msg_display_str)
                for line in message.body_wrapped:
                    print(u"--\u001b[37m\u001b[49m" + line + message_display_str + message.bitbar_msg_display_str)

            else:
                if conversation.is_group_conversation:
                    print(timestamp_display_str)
                    print(msg_sender_start_str + message.body + message_display_str + message.bitbar_msg_display_str)
                else:
                    print(timestamp_display_str)
                    print(msg_format_str + message.body + message_display_str + message.bitbar_msg_display_str)

            if conversation.messages.index(message) != (len(conversation.messages) - 1):
                print("⠀" + "| size=2")  # Unicode character '⠀' (U+2800) for blank lines

            message_ids.add(str.lower(message.id))
            message_senders.add(message.sender)

        print("---")
        message_num += 1

    # create data directory if it does not exist
    if not os.path.isdir(local_dir + "notifier/" + message_type_str + "/data"):
        os.makedirs(local_dir + "notifier/" + message_type_str + "/data")

    processed_messages = set()
    try:
        processed_messages = set(
            pd.read_csv(
                local_dir + "notifier/" + message_type_str + "/data/" + message_type_str +
                "_messages_processed.csv")["uuid"].tolist())
    except FileNotFoundError:
        logger.debug("File " + message_type_str + "_messages_processed.csv does not exist, and will be created.")
    except EmptyDataError:
        logger.debug(
            "File " + message_type_str +
            "_messages_processed.csv is empty, and will be populated with any current unread message UUIDs.")

    if not message_ids.issubset(processed_messages):
        message_ids_series = pd.Series(list(message_ids))
        message_ids_series.to_csv(
            local_dir + "notifier/" + message_type_str + "/data/" + message_type_str + "_messages_processed.csv",
            header=["uuid"])

        send_macos_notification(unread_count, message_senders, "Messages", arg_dict)
