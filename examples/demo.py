from __future__ import annotations

import os

import bw_sdk
import bw_sdk.model
import dotenv
from bw_sdk import Client, SecretStr

dotenv.load_dotenv()

client = Client()
client.unlock(SecretStr(os.environ["BW_PASS"]))

print(client.get_fingerprint())

o = client.get_items()

print(len(o))
i = bw_sdk.model.NewItemLogin(name="flaf", org_id=bw_sdk.model.OrgID("dsa"))

d = i.model_dump_json(indent=3, by_alias=True)

print(d)

print(bw_sdk.model.NewItemLogin.model_validate_json(d))
