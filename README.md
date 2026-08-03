# Anchor

Brand drift monitor for generative media. Upload a handful of reference
images once, and Anchor builds your brand's visual "centroid" in Backblaze
B2. Every asset you generate afterward — through Genblaze, across any
provider — gets scored against that centroid in real time, with a full
drift history you can track over time.

Built for the [Backblaze Generative Media Hackathon](https://backblaze-generative-media.devpost.com/).

## How it uses B2 and Genblaze

- **Genblaze** orchestrates image generation across providers (GMICloud, 
  OpenAI, and more via `PROVIDERS` in `app/genblaze_pipeline.py`) through a
  single `Pipeline` call shape, and writes every asset + provenance
  manifest into the B2 bucket automatically via `ObjectStorageSink`.
- **Backblaze B2** stores three things beyond what Genblaze writes:
  reference brand images, the computed brand centroid, and an append-only
  drift log (`generations/{brand_id}/drift_log.jsonl`) that powers the
  trend view. See `app/storage.py` for the exact key layout.

## Setup

1. **Create a B2 application key**
   [secure.backblaze.com/app_keys.htm](https://secure.backblaze.com/app_keys.htm)
   — needs read/write access to bucket.

2. **Copy the env template and fill in credentials**
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   - `B2_KEY_ID`, `B2_APP_KEY` — from step 1
   - `B2_BUCKET` — already set to `BrandBucket2916`
   - `B2_REGION` — check your bucket's endpoint in the B2 console
     (e.g. `s3.us-west-004.backblazeb2.com` → region is `us-west-004`)
   - At least one provider key (`GMI_API_KEY` and/or `OPENAI_API_KEY`) so
     Genblaze has something to generate with

3. **Install dependencies**
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Run the API**
   ```bash
   uvicorn app.main:app --reload
   ```
   Visit `http://localhost:8000/docs` for interactive API docs.

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/brand-kits/{brand_id}/reference` | POST | Upload 3+ reference images, builds the brand centroid |
| `/brand-kits/{brand_id}/centroid` | GET | View the stored centroid metadata |
| `/brand-kits/{brand_id}/generate` | POST | Generate an asset via Genblaze, score it against the centroid |
| `/brand-kits/{brand_id}/drift-history` | GET | Full drift log + flagged count, for the trend chart |

**Example: onboard a brand**
```bash
curl -X POST http://localhost:8000/brand-kits/acme/reference \
  -F "files=@ref1.jpg" -F "files=@ref2.jpg" -F "files=@ref3.jpg"
```

**Example: generate and score**
```bash
curl -X POST http://localhost:8000/brand-kits/acme/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "a product photo on a clean studio background", "provider": "gmicloud"}'
```

## Project structure

```
app/
  config.py              # env / settings
  storage.py             # B2 reads/writes for kits, centroid, drift log
  embeddings.py          # CLIP embedding + cosine similarity scoring
  genblaze_pipeline.py   # Genblaze Pipeline wrapper, multi-provider
  main.py                # FastAPI endpoints
requirements.txt
.env.example
```

## Providers configured

Add or remove entries in `PROVIDERS` inside `app/genblaze_pipeline.py`.
Ships with GMICloud and OpenAI image adapters; any Genblaze image provider
(Google Imagen, NVIDIA NIM, Replicate, Decart) can be added the same way.
