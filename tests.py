"""Simple unit test."""

import logging
import os
import re
import time
import unittest
import warnings

import requests
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from google.cloud import storage

from main import app

load_dotenv()
logging.disable(logging.INFO)

client = TestClient(app)
AUTH_HEADER = {"Authorization": os.environ["API_TOKEN"]}


def _upload_image(charid: str, url: str):
    """Upload an image and return the response."""
    payload = {
        "guild": 987654321,
        "user": 123456789,
        "charid": charid,
        "image_url": url,
    }
    return client.post("/faceclaim/upload", headers=AUTH_HEADER, json=payload)


class TestAPI(unittest.TestCase):
    """Test the API endpoints."""

    TEST_ID = "__test"
    BUCKET = "pcs.inconnu.app"
    TEST_IMAGE = "https://tilt-assets.s3-us-west-1.amazonaws.com/Nadea-FC0.webp"

    def setUp(self):
        """Ignore unclosed socket warning."""
        warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)

    def test_no_auth(self):
        """Test that a route will fail with no auth header."""
        response = client.delete(f"/faceclaim/delete/{TestAPI.TEST_ID}/all")
        self.assertEqual(response.status_code, 401)

    def test_bad_auth(self):
        """Test that a bad auth header results in a 401."""
        bad = {"Authorization": "fake"}
        response = client.delete(
            f"/faceclaim/delete/{TestAPI.TEST_ID}/42342436ae2.webp", headers=bad
        )
        self.assertTrue(response.status_code, 401)

    def test_faceclaim(self):
        """Test the /faceclaim/upload route."""
        response = _upload_image(TestAPI.TEST_ID, TestAPI.TEST_IMAGE)
        self.assertEqual(response.status_code, 200)

        url = response.json()
        self.assertTrue(isinstance(url, str))
        self.assertTrue(TestAPI.BUCKET in url)
        self.assertTrue(url.endswith(".webp"))
        self.assertTrue(url.startswith("https://pcs.inconnu.app"))
        self.assertTrue(TestAPI.TEST_ID in url)

        # Check that the file actually exists
        self.assertEqual(requests.head(url).status_code, 200)

    def test_upload_log(self):
        """Test the /upload_log route."""
        with open("main.py", "rb") as test_file:
            payload = {"log_file": test_file}
            response = client.post("/upload_log", headers=AUTH_HEADER, files=payload)

            self.assertEqual(response.status_code, 200)

            # Check that the file exists
            storage_client = storage.Client()
            bucket = storage_client.get_bucket("inconnu-logs")
            blob = bucket.blob(test_file.name)

            self.assertTrue(blob.exists())
            blob.delete()
            self.assertFalse(blob.exists())

    def test_single_delete(self):
        """Test the /faceclaim/delete/charid/key route."""
        response = _upload_image(TestAPI.TEST_ID, TestAPI.TEST_IMAGE)
        self.assertEqual(response.status_code, 200)

        url = response.json()
        match = re.search(r"(__test/[A-F0-9a-f]+\.webp)$", url)
        key = match.group(1)

        response = client.delete(f"/faceclaim/delete/{key}", headers=AUTH_HEADER)
        self.assertEqual(response.status_code, 200)

        successful = True
        for _ in range(10):
            if requests.head(url).status_code == 200:
                time.sleep(6)
            else:
                successful = True
                break

        self.assertTrue(successful)

    def test_multi_delete(self):
        """Test the /faceclaim/delete/charid/all endpoint."""
        for _ in range(3):
            response = _upload_image(TestAPI.TEST_ID, TestAPI.TEST_IMAGE)
            self.assertEqual(response.status_code, 200)

        response = client.delete(f"/faceclaim/delete/{TestAPI.TEST_ID}/all", headers=AUTH_HEADER)
        self.assertTrue(response.status_code, 200)

        storage_client = storage.Client()
        bucket = storage_client.get_bucket(TestAPI.BUCKET)

        successful = False
        for _ in range(10):
            blobs = list(bucket.list_blobs(prefix=TestAPI.TEST_ID))
            if not blobs:
                successful = True
                break
            time.sleep(6)

        self.assertTrue(successful)

    @classmethod
    def tearDownClass(cls):
        """Delete the test objects."""
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(TestAPI.BUCKET)
        blobs = bucket.list_blobs(prefix=TestAPI.TEST_ID)

        for blob in blobs:
            blob.delete()
