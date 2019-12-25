#!/usr/local/bin/python3
# # -*- coding: utf-8 -*-

# <bitbar.title>macOS iMessage/SMS Notifications</bitbar.title>
# <bitbar.version>v1.0.0</bitbar.version>
# <bitbar.author>Wren J. R.</bitbar.author>
# <bitbar.author.github>uberfastman</bitbar.author.github>
# <bitbar.desc>Display unread iMessage/SMS messages in the macOS menubar!</bitbar.desc>
# <bitbar.image>https://github.com/uberfastman/local-bitbar-plugins/raw/develop/plugins/notifier/text/images/bitbar-text-messages.png</bitbar.image>
# <bitbar.dependencies>python3,pandas,pync</bitbar.dependencies>
# <bitbar.abouturl>https://github.com/uberfastman/local-bitbar-plugins</bitbar.abouturl>

import json
import logging
import os
import sqlite3
import time
from collections import OrderedDict

import pandas as pd

import notifier.utils as utils
from notifier.base import BaseMessage, BaseConversation
from notifier.text import queries

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ START SET CUSTOM LOCAL VARIABLES ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
max_line_chars = 75
max_group_chat_search_results = 10  # The higher this number, the longer the app will take to run each time.
log_level = logging.WARN  # Logging levels: logging.INFO, logging.DEBUG, logging.WARN, logging.ERROR
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ END SET CUSTOM LOCAL VARIABLES ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class TextMessage(BaseMessage):

    def __init__(self, df_row, max_line_characters, bitbar_msg_display_str):
        super().__init__(df_row, max_line_characters, bitbar_msg_display_str)

        self.timestamp = utils.format_timestamp(df_row.timestamp)
        self.sender = df_row.sender if df_row.sender else (df_row.org if df_row.org else df_row.contact)

        self.rowid = df_row.rowid
        self.cguid = df_row.cguid
        self.groupid = df_row.groupid
        self.contact = df_row.contact
        self.number = df_row.number
        self.attachment = df_row.attachment
        self.attchtype = df_row.attchtype
        try:
            self.attchfile, self.attchhasthumb = utils.encode_attachment(df_row, max_line_characters)
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


logger = logging.getLogger(__name__)
logging.basicConfig(level=log_level)

start = time.process_time()

# Currently supported message services: text (iMessage/SMS on macOS), reddit, slack
message_type_str = "text"
local_dir = os.path.dirname(os.path.abspath(__file__)) + "/"

with open(local_dir + "notifier/" + message_type_str + "/private.json", "r") as credentials_json:
    credentials = json.load(credentials_json)

username = credentials.get("username")
contact_db_dir = credentials.get("contact_db_dir")

conn = sqlite3.connect("/Users/" + username + "/Library/Messages/chat.db")
cursor = conn.cursor()
cursor.execute(queries.get_sqlite_attach_db_query(username, contact_db_dir))
cursor.execute(queries.sqlite_select_query)

unread_df = pd.DataFrame(
    cursor.fetchall(),
    columns=["id", "rowid", "cguid", "cid", "groupid", "title", "timestamp", "contact", "number", "sender", "org",
             "attachment", "attchtype", "attchfile", "body"]
)
logging.debug(unread_df.to_string())
unread_count = len(unread_df.index)

cursor.execute(queries.sqlite_get_recent_query)
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

bitbar_display_str = "bash=" + local_dir + "notifier/text/scripts/open-messages.sh terminal=false "

conversations = OrderedDict()
for row in unread_df.itertuples():
    message = TextMessage(
        row, max_line_chars, "bash=" + local_dir + "notifier/text/scripts/open-messages-to-conversation.sh param1=" +
                             str(chat_order_dict.get(row.cid)) + " terminal=false ")
    if message.cid not in conversations.keys():
        conversations[message.cid] = TextConversation(
            message, cursor, queries.sqlite_group_chat_query, max_group_chat_search_results)
    else:
        conversations.get(message.cid).add_message(message)

if unread_count == 0:
    utils.generate_output_read(local_dir, message_type_str, bitbar_display_str)

else:
    arg_dict = {
        # "appIcon": local_dir + "notifier/" + message_type_str + "/images/MessagesAppIcon.png",
        # "activate": "com.apple.iChat",
        # "execute": "open -a Messages",
        # "sound": "Glass"
        "sender": "com.apple.iChat"
    }

    utils.generate_output_unread(
        local_dir, message_type_str, bitbar_display_str, unread_count, conversations, max_line_chars, arg_dict)

logger.debug(time.process_time() - start)
