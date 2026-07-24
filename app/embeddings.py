"""
Embeds images with CLIP and scores drift as cosine similarity against a
brand's stored centroid vector.

torch/open_clip are imported lazily (inside functions, not at module load)
so the FastAPI process can start and open its port almost instantly. On
platforms like Cloud Run, the health check has a limited startup window;
importing these heavy libraries at module level can blow past it. The
actual model only loads on the first real embed_image() call.
"""
import io

_model = None
_preprocess = None
_device = None


def _load_model():
    global _model, _preprocess, _device
    if _model is None:
        import torch
        import open_clip

        _device = "cuda" if torch.cuda.is_available() else "cpu"
        _model, _, _preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="openai"
        )
        _model.to(_device).eval()
    return _model, _preprocess


def embed_image(image_bytes: bytes) -> list[float]:
    import torch
    from PIL import Image

    model, preprocess = _load_model()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = preprocess(img).unsqueeze(0).to(_device)
    with torch.no_grad():
        features = model.encode_image(tensor)
        features /= features.norm(dim=-1, keepdim=True)
    return features.squeeze(0).cpu().tolist()


def compute_centroid(embeddings: list[list[float]]) -> list[float]:
    import numpy as np

    arr = np.array(embeddings)
    centroid = arr.mean(axis=0)
    centroid /= np.linalg.norm(centroid)
    return centroid.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    import numpy as np

    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
