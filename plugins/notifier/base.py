#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import textwrap


class BaseMessage(object):

    def __init__(self, df_row, max_line_characters, bitbar_msg_display_str):
        self.id = df_row.id
        self.cid = df_row.cid
        self.title = df_row.title
        self.timestamp = df_row.timestamp
        self.sender = df_row.sender
        self.body = df_row.body.replace('\n', ' ').replace('\r', '').strip()
        self.body_short = self.body[:max_line_characters] + "..."
        self.body_wrapped = textwrap.wrap(self.body, max_line_characters + 1, break_long_words=False)
        self.bitbar_msg_display_str = bitbar_msg_display_str

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
        self.bitbar_msg_display_str = message_obj.bitbar_msg_display_str

    def add_message(self, message_obj):
        if message_obj.cid == self.id:
            self.messages.append(message_obj)
            self.participants.add(message_obj.sender)
            if len(self.participants) > 1:
                self.is_group_conversation = True
                if not self.title:
                    self.title = "\u001b[39mGroup BaseMessage\u001b[33m"
        else:
            raise ValueError("Cannot add BaseMessage with mismatching id to BaseConversation!")

    def get_message_count(self):
        return len(self.messages)

    def get_participants_str(self):
        if self.is_group_conversation:
            return ", ".join(participant for participant in self.participants) + (", ..." if len(self.participants) == 1 else "")
        else:
            return "".join(participant for participant in self.participants)

    def __repr__(self):
        return str(vars(self))

    def __str__(self):
        return str(vars(self))
