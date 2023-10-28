from __future__ import annotations

import os

import dotenv

import bw_sdk
import bw_sdk.model
from bw_sdk import Client, SecretStr

dotenv.load_dotenv()

client = Client()
client.unlock(SecretStr(os.environ["BW_PASS"]))

client.sync()

print(client.get_fingerprint())

o = client.get_item_identities()

print(o)


i = bw_sdk.model.NewItemLogin(name="flaf", org_id=bw_sdk.model.OrgID("dsa"))

d = i.model_dump_json(indent=3, by_alias=True)

print(d)

print(bw_sdk.model.NewItemLogin.model_validate_json(d))

print()
i = client.get_item_login(bw_sdk.model.ItemID("bd61eeb2-368c-4f71-bcfd-abf900d17e62"))
print()
print(i.login.uris)
