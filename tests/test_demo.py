from bw_sdk import Client


def test_run():
    client = Client()

    ad = client.get_item("fc9d9d9d-0027-46c9-8e43-abb000959d0f")

    print(ad)
