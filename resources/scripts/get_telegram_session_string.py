import json
from pathlib import Path

from telethon.sessions import StringSession
# noinspection PyProtectedMember
from telethon.sync import Dialog, Message
from telethon.sync import TelegramClient
from telethon.tl.types import User

credentials_path = Path(__file__).parent.parent.parent / "resources" / "credentials" / "private.json"

with open(credentials_path, "r") as credentials_json:
    credentials = json.load(credentials_json)

telegram_credentials = credentials.get("telegram")
api_id = telegram_credentials.get("api_id")
api_hash = telegram_credentials.get("api_hash")
session_string = telegram_credentials.get("session_string")

string_session = StringSession(session_string) if session_string else StringSession()
with TelegramClient(string_session, api_id, api_hash) as client:  # type: TelegramClient

    # noinspection PyUnresolvedReferences
    saved_session_string = client.session.save()
    print(f"Session String: {saved_session_string}")
    with open(credentials_path, "w") as credentials_json:
        credentials["telegram"]["session_string"] = saved_session_string
        json.dump(credentials, credentials_json, indent=2)

    # noinspection PyTypeChecker
    user = client.get_me()  # type: User
    print(f"User: {user.username}")
    print(user.stringify())

    for dialog in client.iter_dialogs():  # type: Dialog

        print(dialog.is_user)
        print(dialog.is_group)
        print(dialog.is_channel)
        print(dialog.unread_count)
        if not getattr(dialog.entity, "is_private", False) and dialog.unread_count > 0:
            unread_count = dialog.unread_count
            for msg in client.iter_messages(dialog.entity):  # type: Message
                print(msg.message)
                print("-----")
                unread_count -= 1
                if unread_count == 0:
                    break
        print("-" * 100)
