"""Basic Inconnu API."""

import io
import json
import logging
import os

import requests
from bson.objectid import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from google.cloud import pubsub_v1, storage
from PIL import Image
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO)


def verify_token(req: Request):
    """Validates the auth token."""
    token = req.headers.get("Authorization")
    if token != os.environ["API_TOKEN"]:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


app = FastAPI(dependencies=[Depends(verify_token)])


class FaceclaimRequest(BaseModel):
    """A request to process a faceclaim image."""

    user: int
    guild: int
    charid: str
    image_url: str


@app.post("/faceclaim/upload")
async def process_faceclaim(faceclaim: FaceclaimRequest):
    """Convert the given image URL to WebP and save to the bucket."""
    logger = logging.getLogger("faceclaim/upload")

    logger.info("Fetching %s", faceclaim.image_url)
    image = Image.open(io.BytesIO(requests.get(faceclaim.image_url, stream=True).raw.data))

    logger.debug("Converting to WebP")
    membuf = io.BytesIO()
    image.save(membuf, format="webp", quality=99)
    membuf.seek(0)

    bucket_name = os.environ["PCS_BUCKET"]
    key = f"{faceclaim.charid}/" + str(ObjectId()) + ".webp"

    bucket = _get_bucket(bucket_name)
    blob = bucket.blob(key)
    blob.content_type = "image/webp"
    blob.metadata = {
        "uploader": faceclaim.user,
        "guild": faceclaim.guild,
        "original": faceclaim.image_url,
    }

    logger.info("Uploading %s with metadata %s", key, str(blob.metadata))

    with blob.open("wb") as f:
        f.write(membuf.read())

    return f"https://{bucket_name}/{key}"


@app.delete("/faceclaim/delete/{charid}/all")
async def delete_character_faceclaims(charid: str):
    """Delete all of a character's faceclaims."""
    logging.getLogger("faceclaim/delete_all").info("Deleting all of %s's faceclaims", charid)
    _publish_message("delete-faceclaim-group", {"charid": charid})


@app.delete("/faceclaim/delete/{charid}/{image}")
async def delete_single_faceclaim(charid: str, image: str):
    """Delete a single faceclaim."""
    key = f"{charid}/{image}"
    logging.getLogger("faceclaim/delete_one").info("Deleting %s", key)
    _publish_message("delete-single-faceclaim", {"key": key})


def _publish_message(topic: str, data: dict[str, str]):
    """Publish a message to Pub/Sub."""
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path("inconnu-357402", topic)

    # Pub/Sub needs the message body as a byte str
    message = json.dumps(data).encode("utf-8")

    logging.getLogger("publish_message").debug("Publishing %s to %s", message, topic_path)
    publisher.publish(topic_path, message)


@app.post("/upload_log")
async def upload_log(log_file: UploadFile):
    """Upload a log file. Overwrites on name collision."""
    contents = await log_file.read()

    bucket = _get_bucket("inconnu-logs")
    blob = bucket.blob(log_file.filename)
    blob.content_type = "text/plain"

    logging.getLogger("upload_log").info("Uploading %s", log_file.filename)

    with blob.open("wb") as f:
        f.write(contents)


def _get_bucket(name: str):
    """Gets a bucket by a given name."""
    logging.getLogger("get_bucket").debug("Getting bucket %s", name)
    client = storage.Client()
    return client.get_bucket(name)
