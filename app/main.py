import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel

from app import storage, embeddings, genblaze_pipeline
from app.config import settings

app = FastAPI(title="Anchor", description="Brand drift monitor for generative media")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- onboarding: build the brand centroid ----------

@app.post("/brand-kits/{brand_id}/reference")
async def upload_reference_kit(brand_id: str, files: list[UploadFile] = File(...)):
    if len(files) < 3:
        raise HTTPException(400, "Upload at least 3 reference images for a stable centroid.")

    vectors = []
    for f in files:
        data = await f.read()
        storage.upload_reference_image(brand_id, f.filename, data, f.content_type)
        vectors.append(embeddings.embed_image(data))

    centroid = embeddings.compute_centroid(vectors)
    storage.save_centroid(brand_id, centroid, num_images=len(files))

    return {
        "brand_id": brand_id,
        "reference_images_stored": len(files),
        "centroid_saved": True,
    }


@app.get("/brand-kits/{brand_id}/centroid")
def get_centroid(brand_id: str):
    centroid = storage.load_centroid(brand_id)
    if centroid is None:
        raise HTTPException(404, "No brand kit found for this brand_id. Upload reference images first.")
    return centroid


# ---------- generation + drift scoring ----------

class GenerateRequest(BaseModel):
    prompt: str
    provider: str = "gmicloud"
    model: str | None = None


@app.post("/brand-kits/{brand_id}/generate")
def generate_and_score(brand_id: str, req: GenerateRequest):
    centroid = storage.load_centroid(brand_id)
    if centroid is None:
        raise HTTPException(404, "No brand kit found. Upload reference images before generating.")

    result = genblaze_pipeline.generate_image(
        prompt=req.prompt, provider=req.provider, brand_id=brand_id, model=req.model
    )

    generation_embedding = embeddings.embed_image(result["image_bytes"])
    drift_score = embeddings.cosine_similarity(generation_embedding, centroid["vector"])
    flagged = drift_score < settings.DRIFT_THRESHOLD

    generation_id = str(uuid.uuid4())
    metadata = {
        "generation_id": generation_id,
        "brand_id": brand_id,
        "prompt": req.prompt,
        "provider": result["provider"],
        "model": result["model"],
        "asset_url": result["asset_url"],
        "asset_key": result["asset_key"],
        "manifest_uri": result["manifest_uri"],
        "canonical_hash": result["canonical_hash"],
        "drift_score": drift_score,
        "flagged": flagged,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    storage.save_generation_metadata(brand_id, generation_id, metadata)
    storage.append_drift_log(brand_id, metadata)

    return metadata


@app.get("/brand-kits/{brand_id}/drift-history")
def drift_history(brand_id: str):
    log = storage.read_drift_log(brand_id)
    return {
        "brand_id": brand_id,
        "count": len(log),
        "flagged_count": sum(1 for e in log if e.get("flagged")),
        "entries": log,
    }


@app.get("/assets/{key:path}")
def get_asset(key: str):
    """Streams an image out of the private B2 bucket, authenticated
    server-side, so the frontend can display it with a plain <img src=...>."""
    try:
        data = storage.get_object_bytes(key)
    except Exception:
        raise HTTPException(404, "Asset not found")
    return Response(content=data, media_type="image/jpeg")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def dashboard():
    """Serves the Anchor dashboard so judges can use the app from one URL."""
    return FileResponse("frontend/index.html")
