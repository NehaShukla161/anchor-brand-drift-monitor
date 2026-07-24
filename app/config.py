import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    B2_KEY_ID = os.environ["B2_KEY_ID"]
    B2_APP_KEY = os.environ["B2_APP_KEY"]
    B2_BUCKET = os.environ.get("B2_BUCKET", "BrandBucket2916")
    # B2 S3-compatible region — check your bucket's "Endpoint" field in the
    # B2 console (e.g. s3.ca-east-006.backblazeb2.com -> region ca-east-006).
    # Region is tied to your Backblaze account and can't be changed after
    # account creation, so this must match wherever your account actually is.
    B2_REGION = os.environ.get("B2_REGION", "ca-east-006")
    B2_ENDPOINT = os.environ.get(
        "B2_ENDPOINT", f"https://s3.{B2_REGION}.backblazeb2.com"
    )
    DRIFT_THRESHOLD = float(os.environ.get("DRIFT_THRESHOLD", "0.75"))


settings = Settings()
