#!/usr/local/opt/python/libexec/bin/python
# -*- coding: utf-8 -*-

# Adapted fomr code originally written by /u/HeyItsShuga found here:
# https://github.com/matryer/bitbar-plugins/blob/master/Web/Reddit/redditnotify.30s.py

# <bitbar.title>Reddit Notifications</bitbar.title>
# <bitbar.version>v1.0.0</bitbar.version>
# <bitbar.author>Wren J. R.</bitbar.author>
# <bitbar.author.github>uberfastman</bitbar.author.github>
# <bitbar.desc>Display unread reddit messages in the macOS menubar!</bitbar.desc>
# <bitbar.image>http://www.hosted-somewhere/pluginimage</bitbar.image>
# <bitbar.dependencies>python3,praw</bitbar.dependencies>
# <bitbar.abouturl>http://url-to-about.com/</bitbar.abouturl>

import json
import logging
import os
import sys
import time
from collections import OrderedDict
from datetime import datetime

import pandas as pd
import praw
from dateutil import tz
from prawcore.exceptions import ResponseException, RequestException

import notifier.utils as utils
from notifier.base import BaseMessage, BaseConversation

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ START SET CUSTOM LOCAL VARIABLES ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
max_line_chars = 50
log_level = logging.WARN  # Logging levels: logging.INFO, logging.DEBUG, logging.WARN, logging.ERROR


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ END SET CUSTOM LOCAL VARIABLES ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class RedditMessage(BaseMessage):

    def __init__(self, df_row, max_line_characters, bitbar_msg_display_str):
        super().__init__(df_row, max_line_characters, bitbar_msg_display_str)

        self.timestamp = datetime.utcfromtimestamp(df_row.timestamp).strftime("%m-%d-%Y %H:%M:%S")
        utc_time_zone = tz.tzutc()
        local_time_zone = tz.tzlocal()

        self.timestamp = datetime.strptime(self.timestamp, "%m-%d-%Y %H:%M:%S")
        self.timestamp = self.timestamp.replace(tzinfo=utc_time_zone)
        self.timestamp = self.timestamp.astimezone(local_time_zone)
        self.timestamp = self.timestamp.strftime("%m-%d-%Y %H:%M:%S")

        self.timestamp = utils.format_timestamp(str(self.timestamp))

        self.recipient = df_row.recipient
        self.subreddit = df_row.subreddit
        self.comment = bool(df_row.comment)

        if self.comment:
            self.cid = self.id

        if df_row.context:
            self.context = df_row.context
        else:
            self.context = "/message/unread/"

        self.bitbar_msg_display_str = "href=" + utils.sanitize_url("https://www.reddit.com" + self.context)


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


logger = logging.getLogger(__name__)
logging.basicConfig(level=log_level)

start = time.process_time()

# Currently supported message services: text (iMessage/SMS on macOS), reddit, slack
message_type_str = "reddit"
local_dir = os.path.dirname(os.path.abspath(__file__)) + "/"

with open(local_dir + "notifier/reddit/private.json", "r") as credentials_json:
    credentials = json.load(credentials_json)
reddit = praw.Reddit(client_id=credentials.get("client_id"),
                     client_secret=credentials.get("client_secret"),
                     refresh_token=credentials.get("refresh_token"),
                     user_agent="Reddit Notifications for BitBar")

unread = reddit.inbox.unread(limit=None)
# getting all messages instead of just unread
# unread = reddit.inbox.all(limit=5)

unread_df = pd.DataFrame(
    columns=["id", "cid", "title", "timestamp", "sender", "body", "recipient", "subreddit", "comment", "context"]
)

try:
    for message in unread:
        # print(vars(message))
        unread_df.loc[len(unread_df)] = [
            message.id,
            message.parent_id,
            message.subject,
            message.created_utc,
            # message.created,
            message.author.name if message.author else message.distinguished,
            message.body,
            message.dest,
            message.subreddit,
            message.was_comment,
            message.context
        ]
    logger.debug(unread_df.to_string())
except (ResponseException, RequestException) as e:
    print("❗")
    print("---")
    print("UNABLE TO RETRIEVE REDDIT CONTENT!")
    sys.exit(str(e))

unread_count = len(unread_df.index)
bitbar_unread_display_str = "href=https://www.reddit.com/message/unread/ "

conversations = OrderedDict()
for row in unread_df.itertuples():

    message = RedditMessage(row, max_line_chars, bitbar_unread_display_str)
    if message.cid not in conversations.keys():
        conversations[message.cid] = RedditConversation(message)
    else:
        conversations.get(message.cid).add_message(message)

if unread_count == 0:
    utils.generate_output_read(local_dir, message_type_str, "href=https://www.reddit.com/message/inbox/")

else:
    arg_dict = {
        "appIcon": local_dir + "notifier/" + message_type_str + "/images/reddit-icon.png",
        "open": "https://www.reddit.com/message/inbox/",
        "sound": "Glass"
    }

    utils.generate_output_unread(
        local_dir, message_type_str, bitbar_unread_display_str, unread_count, conversations, max_line_chars, arg_dict)

logger.debug(time.process_time() - start)
