# extract_and_structure_updated.py
import json
import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://landtrades.in"
DOMAIN = urlparse(BASE_URL).netloc
OUTPUT_FILE = "knowledge_base_clean.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LandTradesKnowledgeCrawler/4.0)"
}

SEED_URLS = [
    BASE_URL,
    "https://landtrades.in/apartments-in-mangalore.php",
    "https://landtrades.in/commercial-projects-in-mangalore.php",
    "https://landtrades.in/current-openings.php",
    "https://landtrades.in/mangalore-builders-news.php",
    "https://landtrades.in/blog.php",
    "https://landtrades.in/magazine.php",
    "https://landtrades.in/contact-mangalore-builders.php",
    "https://landtrades.in/corporate-profile-land-trades.php",
    "https://landtrades.in/best-residential-areas-for-families-in-mangalore.php",
    "https://landtrades.in/builders-in-mangalore.php",
    "https://landtrades.in/social-responsibility.php",
]

# These ongoing project pages are now maintained manually in
# landtrades_projects_structured_updated.json, so skip them here.
SKIP_PROJECT_URLS = {
    "https://landtrades.in/expertise-enclave-apartment-in-mangalore.php",
    "https://landtrades.in/durga-mahal-apartment-in-mannaguda-road-kudroli.php",
    "https://landtrades.in/altitude-residential-project-bendoorwell.php",
    "https://landtrades.in/laxmi-govind-apartment-in-kadri-mangalore.php",
    "https://landtrades.in/krishna-kuteera-apartment-in-mangalore.php",
    "https://landtrades.in/mahalaxmi-residential-apartment-mangalore.php",
    "https://landtrades.in/sky-villa-apartments-mangalore.php",
    "https://landtrades.in/pristine-flats-mangalore.php",
    "https://landtrades.in/shivabagh-residential-apartment-mangalore.php",
    "https://landtrades.in/altura-residential-bendoorwell-mangalore.php",
    "https://landtrades.in/vikram-commercial-complex-kodialbail-mangalore.php",
    "https://landtrades.in/synergy-commercial-project-mangalore.php",
}

SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".pdf", ".zip", ".rar", ".mp4", ".mp3", ".avi", ".mov", ".wmv"
)

visited = set()
queued = set()
queue = deque()
clean_pages = []


def normalize_space(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    path = re.sub(r"/{2,}", "/", path)
    if path != "/" and not path.endswith(".php"):
        path = path.rstrip("/")
    bad_params = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term",
        "utm_content", "fbclid", "gclid"
    }
    query_pairs = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k not in bad_params
    ]
    query = urlencode(query_pairs, doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def is_valid_internal_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.netloc != DOMAIN:
            return False
        lower = url.lower()
        if any(lower.endswith(ext) for ext in SKIP_EXTENSIONS):
            return False
        if parsed.path and "." in parsed.path.split("/")[-1]:
            if not parsed.path.lower().endswith(".php"):
                return False
        return True
    except Exception:
        return False


def should_skip_url(url: str) -> bool:
    return canonicalize_url(url) in SKIP_PROJECT_URLS


def enqueue(url: str):
    url = canonicalize_url(url)
    if not is_valid_internal_url(url):
        return
    if should_skip_url(url):
        return
    if url not in visited and url not in queued:
        queue.append(url)
        queued.add(url)


def remove_noise(soup: BeautifulSoup) -> BeautifulSoup:
    for tag in soup(["script", "style", "noscript", "iframe", "form"]):
        tag.decompose()

    noise_patterns = [
        "menu", "navbar", "footer", "sidebar", "breadcrumb",
        "popup", "modal", "subscribe", "newsletter", "social",
        "search", "offcanvas", "mobile-menu"
    ]

    for tag in list(soup.find_all(True)):
        try:
            class_str = " ".join(tag.get("class", [])).lower()
            id_str = (tag.get("id") or "").lower()
            if any(p in class_str for p in noise_patterns):
                tag.decompose()
                continue
            if any(p in id_str for p in noise_patterns):
                tag.decompose()
                continue
        except Exception:
            continue
    return soup


def fetch(url: str):
    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        if res.status_code == 200 and "text/html" in res.headers.get("Content-Type", ""):
            return res
    except Exception as exc:
        print("Fetch error:", url, exc)
    return None


def extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return normalize_space(soup.title.string)
    h1 = soup.find("h1")
    if h1:
        return normalize_space(h1.get_text(" ", strip=True))
    return ""


def choose_main_container(soup: BeautifulSoup):
    selectors = [
        "main", "article", '[role="main"]', ".blog-details", ".blog-content",
        ".post-content", ".entry-content", ".news-content", ".career-content",
        ".content", ".container",
    ]
    for sel in selectors:
        node = soup.select_one(sel)
        if node and len(node.get_text(" ", strip=True).split()) > 80:
            return node

    best = None
    best_words = 0
    for node in soup.find_all(["main", "article", "section", "div"]):
        words = len(node.get_text(" ", strip=True).split())
        if words > best_words:
            best_words = words
            best = node
    return best


def is_company_profile_page(url: str) -> bool:
    u = (url or "").lower()
    return any(x in u for x in [
        "builders-in-mangalore.php",
        "corporate-profile-land-trades.php",
        "social-responsibility.php",
        "csr.php",
    ])


def extract_company_page_content(soup: BeautifulSoup) -> str:
    blocks = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        txt = normalize_space(tag.get_text(" ", strip=True))
        if not txt or len(txt) < 3:
            continue
        low = txt.lower()
        if low in {"search", "projects", "menu", "read more", "brochure", "quote", "explore", "enquire now"}:
            continue
        blocks.append(txt)

    seen = set()
    final = []
    for block in blocks:
        key = block.lower()
        if key not in seen:
            seen.add(key)
            final.append(block)
    return normalize_space(" ".join(final))


def extract_main_content(soup: BeautifulSoup, page_url: str = "") -> str:
    if is_company_profile_page(page_url):
        text = extract_company_page_content(soup)
        if text:
            return text

    main = choose_main_container(soup)
    if not main:
        return ""

    for li in main.find_all("li"):
        li.insert_before("\n• ")

    return normalize_space(main.get_text(" ", strip=True))


def extract_tables(soup: BeautifulSoup) -> list:
    tables = []
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            row = [normalize_space(c.get_text(" ", strip=True)) for c in cells]
            row = [x for x in row if x]
            if row:
                rows.append(row)
        if rows:
            tables.append(rows)
    return tables


def extract_images(soup: BeautifulSoup, page_url: str) -> list:
    images = []
    seen = set()
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src:
            continue
        full = urljoin(page_url, src)
        alt = normalize_space(img.get("alt", ""))
        full = canonicalize_url(full) if full.startswith("http") else full
        key = (full, alt)
        if key in seen:
            continue
        seen.add(key)
        images.append({"url": full, "alt": alt})
    return images


def extract_links(soup: BeautifulSoup, current_url: str) -> dict:
    internal = set()
    external = []
    seen_external = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = normalize_space(a.get_text(" ", strip=True))
        if not href or href.startswith(("javascript:", "mailto:", "tel:")):
            continue

        full = canonicalize_url(urljoin(current_url, href))
        parsed = urlparse(full)

        if any(full.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
            continue

        if parsed.netloc == DOMAIN:
            if is_valid_internal_url(full) and not should_skip_url(full):
                internal.add(full)
        else:
            key = (full, text)
            if key not in seen_external:
                seen_external.add(key)
                external.append({"url": full, "text": text})

    return {"internal": sorted(internal), "external": external}


def process_page(url: str):
    if should_skip_url(url):
        print("Skipping manual project page:", url)
        return None

    res = fetch(url)
    if not res:
        return None

    soup = BeautifulSoup(res.text, "html.parser")
    raw_links = extract_links(soup, url)

    soup = remove_noise(soup)

    return {
        "url": url,
        "title": extract_title(soup),
        "content": extract_main_content(soup, url),
        "tables": extract_tables(soup),
        "images": extract_images(soup, url),
        "internal_links": raw_links["internal"],
        "external_links": raw_links["external"],
    }


def crawl(max_pages: int = 1000, delay_sec: float = 0.4):
    for seed in SEED_URLS:
        enqueue(seed)

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        queued.discard(url)

        if url in visited:
            continue

        print("Crawling:", url)
        visited.add(url)

        page_data = process_page(url)
        if page_data:
            clean_pages.append(page_data)
            for link in page_data.get("internal_links", []):
                enqueue(link)

        time.sleep(delay_sec)


def save_output():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(clean_pages, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(clean_pages)} pages to {OUTPUT_FILE}")


if __name__ == "__main__":
    crawl()
    save_output()
