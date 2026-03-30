
import json
import re
import time
import hashlib
from pathlib import Path
from urllib.parse import urlparse

import requests

INPUT_JSON = "project_image_sources_with_categories.json"
OUTPUT_JSON = "project_images.json"
IMAGE_ROOT = Path("real-estate-ai/public/project_images")

REQUEST_TIMEOUT = 25
SLEEP_BETWEEN_DOWNLOADS = 0.15


def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "item"


def guess_extension(url: str) -> str:
    path = urlparse(url).path
    ext = Path(path).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".jfif"}:
        return ext
    return ".jpg"


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def file_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def download_file(url: str, dest_path: Path) -> bool:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, stream=True)
        response.raise_for_status()

        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return True
    except Exception as e:
        print(f"[ERROR] Failed to download: {url}")
        print(f"        {e}")
        return False


def build_project_filename(index: int, item_type: str, category: str, label: str, url: str) -> str:
    ext = guess_extension(url)
    return f"{index:03d}-{slugify(item_type)}-{slugify(category)}-{slugify(label)}{ext}"


def build_general_filename(index: int, bucket: str, label: str, url: str) -> str:
    ext = guess_extension(url)
    return f"{index:03d}-{slugify(bucket)}-{slugify(label)}{ext}"


def normalize_project_items(project_items: list[dict], project_name: str):
    out = []
    for item in project_items:
        out.append({
            "url": item["url"],
            "label": item.get("label", f"{project_name} image"),
            "type": item.get("type", "other"),
            "category": item.get("category", item.get("type", "other")),
            "tags": item.get("tags", []),
        })
    return out


def normalize_general_items(items: list[dict], default_type: str):
    out = []
    for item in items:
        out.append({
            "url": item["url"],
            "label": item.get("label", default_type.title()),
            "type": item.get("type", default_type),
            "category": item.get("category", default_type.title()),
            "tags": item.get("tags", []),
        })
    return out


def dedupe_by_source(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for item in items:
        key = item.get("url", "").strip()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def main():
    if not Path(INPUT_JSON).exists():
        raise FileNotFoundError(f"{INPUT_JSON} not found")

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        source_data = json.load(f)

    ensure_dir(IMAGE_ROOT)

    final_mapping = {
        "projects": {},
        "general": {}
    }

    seen_hashes = {}
    source_url_to_local = {}
    failed_downloads = []

    projects = source_data.get("projects", {})
    for project_name, items in projects.items():
        print(f"\n[INFO] Project: {project_name}")
        project_slug = slugify(project_name)
        project_dir = IMAGE_ROOT / project_slug
        ensure_dir(project_dir)

        normalized_items = dedupe_by_source(normalize_project_items(items, project_name))
        final_mapping["projects"][project_name] = []

        for idx, item in enumerate(normalized_items, start=1):
            url = item["url"]
            label = item["label"]
            item_type = item["type"]
            category = item["category"]
            tags = item.get("tags", [])

            if url in source_url_to_local:
                local_url = source_url_to_local[url]
                final_mapping["projects"][project_name].append({
                    "label": label,
                    "url": local_url,
                    "source_url": url,
                    "type": item_type,
                    "category": category,
                    "tags": tags,
                })
                print(f"[SKIP] Reused existing local asset for {url}")
                continue

            filename = build_project_filename(idx, item_type, category, label, url)
            local_path = project_dir / filename

            ok = download_file(url, local_path)
            time.sleep(SLEEP_BETWEEN_DOWNLOADS)

            if not ok:
                failed_downloads.append(url)
                continue

            try:
                sha1 = file_sha1(local_path)
                if sha1 in seen_hashes:
                    print(f"[INFO] Duplicate content found, removing local copy: {local_path.name}")
                    local_path.unlink(missing_ok=True)
                    local_url = seen_hashes[sha1]
                else:
                    local_url = f"/project_images/{project_slug}/{filename}"
                    seen_hashes[sha1] = local_url
            except Exception as e:
                print(f"[WARN] Could not hash file: {local_path.name} -> {e}")
                local_url = f"/project_images/{project_slug}/{filename}"

            source_url_to_local[url] = local_url

            final_mapping["projects"][project_name].append({
                "label": label,
                "url": local_url,
                "source_url": url,
                "type": item_type,
                "category": category,
                "tags": tags,
            })

            print(f"[OK] {local_url}")

    general = source_data.get("general", {})
    for bucket, items in general.items():
        print(f"\n[INFO] General bucket: {bucket}")
        bucket_slug = slugify(bucket)
        bucket_dir = IMAGE_ROOT / "_general" / bucket_slug
        ensure_dir(bucket_dir)

        default_type = slugify(bucket).replace("-", "_")
        normalized_items = dedupe_by_source(normalize_general_items(items, default_type))
        final_mapping["general"][bucket] = []

        for idx, item in enumerate(normalized_items, start=1):
            url = item["url"]
            label = item["label"]
            item_type = item["type"]
            category = item["category"]
            tags = item.get("tags", [])

            if url in source_url_to_local:
                local_url = source_url_to_local[url]
                final_mapping["general"][bucket].append({
                    "label": label,
                    "url": local_url,
                    "source_url": url,
                    "type": item_type,
                    "category": category,
                    "tags": tags,
                })
                print(f"[SKIP] Reused existing local asset for {url}")
                continue

            filename = build_general_filename(idx, bucket, label, url)
            local_path = bucket_dir / filename

            ok = download_file(url, local_path)
            time.sleep(SLEEP_BETWEEN_DOWNLOADS)

            if not ok:
                failed_downloads.append(url)
                continue

            try:
                sha1 = file_sha1(local_path)
                if sha1 in seen_hashes:
                    print(f"[INFO] Duplicate content found, removing local copy: {local_path.name}")
                    local_path.unlink(missing_ok=True)
                    local_url = seen_hashes[sha1]
                else:
                    local_url = f"/project_images/_general/{bucket_slug}/{filename}"
                    seen_hashes[sha1] = local_url
            except Exception as e:
                print(f"[WARN] Could not hash file: {local_path.name} -> {e}")
                local_url = f"/project_images/_general/{bucket_slug}/{filename}"

            source_url_to_local[url] = local_url

            final_mapping["general"][bucket].append({
                "label": label,
                "url": local_url,
                "source_url": url,
                "type": item_type,
                "category": category,
                "tags": tags,
            })

            print(f"[OK] {local_url}")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(final_mapping, f, indent=2, ensure_ascii=False)

    print(f"\n[DONE] Created {OUTPUT_JSON}")
    print(f"[DONE] Images saved under: {IMAGE_ROOT}")

    if failed_downloads:
        with open("failed_image_downloads.txt", "w", encoding="utf-8") as f:
            for url in failed_downloads:
                f.write(url + "\n")
        print(f"[WARN] Some downloads failed. See failed_image_downloads.txt")


if __name__ == "__main__":
    main()