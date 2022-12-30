"""Sends some files to __test without deleting them."""

import os

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from main import app

load_dotenv()


def main():
    """Upload the files, aborting if there's an error."""
    client = TestClient(app)
    auth_header = {"Authorization": os.environ["API_TOKEN"]}

    img_names = ["Nadea-FC0.webp", "nadea-mynonjo.webp", "Nadea-NK.webp", "Nadea-Prone.webp"]

    for img in map(lambda s: "https://tilt-assets.s3-us-west-1.amazonaws.com/" + s, img_names):
        payload = {
            "guild": 987654321,
            "user": 1234567890,
            "charid": "__test",
            "image_url": img,
        }
        response = client.post("/faceclaim/upload", headers=auth_header, json=payload)

        if response.status_code == 200:
            print(response.json())
        else:
            print(f"Error uploading {img} ({response.status_code})")
            return


if __name__ == "__main__":
    main()
