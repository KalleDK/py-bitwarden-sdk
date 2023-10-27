import os

import dotenv
from bw_sdk import Client, SecretStr

dotenv.load_dotenv()

client = Client()
client.unlock(SecretStr(os.environ["BW_PASS"]))

print(client.get_fingerprint())
