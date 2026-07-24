"""
Thin wrapper around Genblaze so the rest of the app can say
`generate_image(prompt, provider="gmicloud")` without touching Pipeline
internals. Every call goes through the same B2-backed storage sink, so
assets and provenance manifests always land in the bucket automatically.

Add more providers by extending PROVIDERS below — each entry maps a name
you pass from the API to a (ProviderClass, default_model) pair.
"""
import requests
from urllib.parse import urlparse
from genblaze_core import Modality, ObjectStorageSink, KeyStrategy, Pipeline
from genblaze_s3 import S3StorageBackend

from app import storage
from app.config import settings

_storage = None

# Register providers here. Use at least 2 so the demo shows genuine
# multi-provider orchestration through the same pipeline call shape.
PROVIDERS = {}

try:
    from genblaze_gmicloud import GMICloudImageProvider

    PROVIDERS["gmicloud"] = (GMICloudImageProvider, "seedream-5.0-lite")
except ImportError:
    pass

try:
    from genblaze_openai import DalleProvider

    PROVIDERS["openai"] = (DalleProvider, "dall-e-3")
except ImportError:
    pass


def _get_storage():
    global _storage
    if _storage is None:
        _storage = ObjectStorageSink(
            S3StorageBackend.for_backblaze(settings.B2_BUCKET),
            key_strategy=KeyStrategy.HIERARCHICAL,
        )
    return _storage


def generate_image(prompt: str, provider: str, brand_id: str, model: str | None = None):
    """
    Runs one generation step through Genblaze, storing the asset + provenance
    manifest in B2. Returns the asset bytes (for embedding), the durable B2
    URL, and the manifest reference.
    """
    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown or unconfigured provider '{provider}'. "
            f"Available: {list(PROVIDERS.keys())}"
        )
    provider_cls, default_model = PROVIDERS[provider]

    result = (
        Pipeline(f"anchor-{brand_id}")
        .step(
            provider_cls(),
            model=model or default_model,
            prompt=prompt,
            modality=Modality.IMAGE,
        )
        .run(sink=_get_storage(), timeout=300)
    )

    step_result = result.run.steps[0]
    if not step_result.assets:
        raise RuntimeError(
            f"Genblaze step produced no assets. "
            f"status={getattr(step_result, 'status', 'unknown')} "
            f"error={getattr(step_result, 'error', None)}"
        )
    asset = step_result.assets[0]

    # asset.url is a plain S3-style URL, but the bucket is private, so an
    # unauthenticated GET returns 401. Fetch it via our authenticated boto3
    # client instead. URL shape: https://s3.<region>.backblazeb2.com/<bucket>/<key>
    key = urlparse(asset.url).path.lstrip("/").split("/", 1)[1]
    image_bytes = storage.get_object_bytes(key)

    return {
        "image_bytes": image_bytes,
        "asset_url": asset.url,
        "asset_key": key,
        "sha256": asset.sha256,
        "manifest_uri": result.manifest.manifest_uri,
        "canonical_hash": result.manifest.canonical_hash,
        "provider": provider,
        "model": model or default_model,
    }
