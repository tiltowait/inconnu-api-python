"""Test the live deployment."""

import os
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

auth_header = {"Authorization": os.environ["API_TOKEN"]}
url = "https://api.inconnu.app/faceclaim/upload"
payload = {
    "guild": 987654321,
    "user": 123456789,
    "charid": "__test",
    "image_url": "https://pcs.inconnu.app/62242d51ae0016646378a6be/63ab89f23b77500001f0bb68.webp",
}

start = datetime.now()
print(start)
r = requests.post(url, headers=auth_header, json=payload)
end = datetime.now()

if r.ok:
    print("SUCCESS! ", r.json())
else:
    print(f"FAILURE! Received {r.status_code}")

print("Completed in", end - start)
