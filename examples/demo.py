import os

import dotenv
from bw_sdk import Client, LoginData, NewItemLogin

dotenv.load_dotenv()

client = Client()
client.unlock(os.environ["BW_PASS"])

ls = client.get_items()
print(set([l.object for l in ls]))
for l in ls:
    if l.passwordHistory is None:
        continue
    print(l.passwordHistory)
