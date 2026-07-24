"""
Direct B2 access (via boto3, S3-compatible) for everything Anchor manages
outside of Genblaze's own asset/manifest sink:

  brand-kits/{brand_id}/reference/{filename}
  brand-kits/{brand_id}/centroid.json
  generations/{brand_id}/{generation_id}/metadata.json
  generations/{brand_id}/drift_log.jsonl

Genblaze writes generated assets + provenance manifests separately under
runs/... via its own ObjectStorageSink (see genblaze_pipeline.py). Anchor's
metadata.json cross-references that manifest so both trails stay linked.
"""
import json
from datetime import datetime, timezone

import boto3

from app.config import settings

_client = None


def get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.B2_ENDPOINT,
            aws_access_key_id=settings.B2_KEY_ID,
            aws_secret_access_key=settings.B2_APP_KEY,
        )
    return _client


def _put(key: str, body: bytes, content_type: str):
    get_client().put_object(
        Bucket=settings.B2_BUCKET, Key=key, Body=body, ContentType=content_type
    )


def _get(key: str) -> bytes:
    obj = get_client().get_object(Bucket=settings.B2_BUCKET, Key=key)
    return obj["Body"].read()


def _exists(key: str) -> bool:
    try:
        get_client().head_object(Bucket=settings.B2_BUCKET, Key=key)
        return True
    except Exception:
        return False


def _list(prefix: str) -> list[str]:
    paginator = get_client().get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=settings.B2_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def get_object_bytes(key: str) -> bytes:
    """Authenticated download for any object in the bucket, e.g. an asset
    Genblaze wrote whose public URL isn't directly fetchable (private bucket)."""
    return _get(key)


# ---------- reference kit ----------

def upload_reference_image(brand_id: str, filename: str, data: bytes, content_type: str) -> str:
    key = f"brand-kits/{brand_id}/reference/{filename}"
    _put(key, data, content_type)
    return key


def list_reference_images(brand_id: str) -> list[bytes]:
    keys = _list(f"brand-kits/{brand_id}/reference/")
    return [_get(k) for k in keys]


# ---------- centroid ----------

def save_centroid(brand_id: str, vector: list[float], num_images: int):
    key = f"brand-kits/{brand_id}/centroid.json"
    payload = {
        "brand_id": brand_id,
        "vector": vector,
        "num_reference_images": num_images,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _put(key, json.dumps(payload).encode(), "application/json")


def load_centroid(brand_id: str) -> dict | None:
    key = f"brand-kits/{brand_id}/centroid.json"
    if not _exists(key):
        return None
    return json.loads(_get(key))


# ---------- generations ----------

def save_generation_metadata(brand_id: str, generation_id: str, metadata: dict):
    key = f"generations/{brand_id}/{generation_id}/metadata.json"
    _put(key, json.dumps(metadata).encode(), "application/json")


def append_drift_log(brand_id: str, entry: dict):
    key = f"generations/{brand_id}/drift_log.jsonl"
    existing = _get(key) if _exists(key) else b""
    line = json.dumps(entry).encode() + b"\n"
    _put(key, existing + line, "application/jsonl")


def read_drift_log(brand_id: str) -> list[dict]:
    key = f"generations/{brand_id}/drift_log.jsonl"
    if not _exists(key):
        return []
    raw = _get(key).decode().strip().splitlines()
    return [json.loads(line) for line in raw if line]
