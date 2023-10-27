from bw_sdk import Client


def test_run():
    client = Client()
    client.get_status()
