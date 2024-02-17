from __future__ import annotations

import os

import dotenv

from bw_sdk import Client, SecretStr

dotenv.load_dotenv()

client = Client()
client.unlock(SecretStr(os.environ["BW_PASS"]))

client.sync()

print(client.get_fingerprint())

print(client.get_item_securenotes("BBS", exact=True))
