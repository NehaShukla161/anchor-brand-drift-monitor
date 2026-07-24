"""
Embeds images with CLIP and scores drift as cosine similarity against a
brand's stored centroid vector.
"""
import io

import numpy as np
import open_clip
import torch
from PIL import Image

_model = None
_preprocess = None
_device = "cuda" if torch.cuda.is_available() else "cpu"


def _load_model():
    global _model, _preprocess
    if _model is None:
        _model, _, _preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="openai"
        )
        _model.to(_device).eval()
    return _model, _preprocess


@torch.no_grad()
def embed_image(image_bytes: bytes) -> list[float]:
    model, preprocess = _load_model()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = preprocess(img).unsqueeze(0).to(_device)
    features = model.encode_image(tensor)
    features /= features.norm(dim=-1, keepdim=True)
    return features.squeeze(0).cpu().tolist()


def compute_centroid(embeddings: list[list[float]]) -> list[float]:
    arr = np.array(embeddings)
    centroid = arr.mean(axis=0)
    centroid /= np.linalg.norm(centroid)
    return centroid.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
