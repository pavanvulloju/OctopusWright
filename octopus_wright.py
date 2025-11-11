# download_rendered_html_playwright.py
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

# Optional: Azure blob upload
try:
    from azure.storage.blob import BlobServiceClient
except Exception:
    BlobServiceClient = None

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

def get_env_url():
    # URL can be provided via env var TARGET_URL or fallback to a file 'target_url.txt'
    url = os.environ.get("TARGET_URL")
    if url:
        return url.strip()
    # fallback to file
    f = Path("target_url.txt")
    if f.exists():
        return f.read_text().strip()
    print("ERROR: No TARGET_URL env var or target_url.txt found.", file=sys.stderr)
    sys.exit(2)

def upload_to_blob(file_path: Path, container_name: str = "html-results"):
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        print("AZURE_STORAGE_CONNECTION_STRING not set — skipping blob upload.")
        return False
    if BlobServiceClient is None:
        print("azure-storage-blob not installed — cannot upload.", file=sys.stderr)
        return False

    blob_service = BlobServiceClient.from_connection_string(conn_str)
    try:
        container_client = blob_service.get_container_client(container_name)
        if not container_client.exists():
            print(f"Container '{container_name}' does not exist — creating.")
            container_client.create_container()
        blob_name = f"input/{file_path.name}"
        print(f"Uploading {file_path} to container '{container_name}' as blob '{blob_name}'...")
        with file_path.open("rb") as data:
            container_client.upload_blob(name=blob_name, data=data, overwrite=True)
        print("Upload complete.")
        return True
    except Exception as e:
        print("Blob upload failed:", e, file=sys.stderr)
        return False

def main():
    url = get_env_url()
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_name = url.replace("://", "_").replace("/", "_").replace("?", "_").replace("&", "_")
    filename = OUTPUT_DIR / f"{safe_name}_{timestamp}.html"

    print(f"Opening browser and rendering: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        # Wait extra 5 seconds as requested
        print("Waiting 5 seconds for JS to settle...")
        time.sleep(5)
        html = page.content()
        browser.close()

    filename.write_text(html, encoding="utf-8")
    print(f"Rendered HTML saved to: {filename}")

    # Optional: upload to Azure Blob if connection string present
    uploaded = upload_to_blob(filename)
    if uploaded:
        print("File uploaded to Azure Blob Storage.")
    else:
        print("File not uploaded to Azure Blob Storage (either not configured or failed).")

    # Exit 0 for success
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
