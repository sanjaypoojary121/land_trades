import json
import os
import re
import uuid
from datetime import UTC, datetime
from typing import Iterable

INPUT_FILE = "knowledge_base_clean.json"
MANUAL_PROJECTS_FILE = "landtrades_projects_structured_updated.json"
DUMMY_FILE = "dummy_real_estate.json"
OUTPUT_FILE = "structured_chunks.json"

NOISE_PHRASES = [
    "Previous Next",
    "Price Brochure EMI Calculator",
    "Your perfect space awaits",
    "Download Profile",
    "Request a quote",
    "Enquire Now",
    "Call Enquire Share",
    "Search Now",
    "Apply Now",
    "Read More",
    "Follow Us",
    "Like Us",
    "Latest Posts",
]

CONTACT_FIELD_PATTERNS = {
    "Phone Numbers": re.compile(r"(?:\+?\d[\d\s\-()]{7,}\d)"),
    "Emails": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
}

MANUAL_SKIP_URL_KEYWORDS = {
    "expertise-enclave-apartment-in-mangalore.php",
    "durga-mahal-apartment-in-mannaguda-road-kudroli.php",
    "altitude-residential-project-bendoorwell.php",
    "laxmi-govind-apartment-in-kadri-mangalore.php",
    "krishna-kuteera-apartment-in-mangalore.php",
    "mahalaxmi-residential-apartment-mangalore.php",
    "sky-villa-apartments-mangalore.php",
    "pristine-flats-mangalore.php",
    "shivabagh-residential-apartment-mangalore.php",
    "altura-residential-bendoorwell-mangalore.php",
    "vikram-commercial-complex-kodialbail-mangalore.php",
    "synergy-commercial-project-mangalore.php",
}

CAREER_TITLES = [
    "Interior Designer",
    "Architect",
    "Marketing Executive",
    "Graphic Designer",
    "Sales Executive",
    "Civil Engineer",
    "Site Engineer",
    "Accounts Executive",
    "Receptionist",
    "HR Executive",
    "Admin Executive",
    "Project Manager",
]

COMPANY_CUES = [
    "about us",
    "corporate profile",
    "why land trades",
    "our vision",
    "our mission",
    "chairman",
    "founder",
    "milestones",
    "awards",
    "certifications",
    "social responsibility",
    "environmental policy",
]


def load_json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def clean_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text).replace("\xa0", " ")
    text = text.replace("•", " • ")
    text = re.sub(r"\s+", " ", text)
    for phrase in NOISE_PHRASES:
        text = text.replace(phrase, " ")
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" |-•")


def slugify(text: str) -> str:
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"\s+", "-", text).strip("-")
    return text


def word_count(text: str) -> int:
    return len(clean_text(text).split())


def sentence_count(text: str) -> int:
    text = clean_text(text)
    if not text:
        return 0
    parts = re.split(r"(?<=[.!?])\s+", text)
    return len([p for p in parts if clean_text(p)])


def is_manual_project_url(url: str) -> bool:
    u = (url or "").lower()
    return any(key in u for key in MANUAL_SKIP_URL_KEYWORDS)


def detect_page_type(url: str, title: str, content: str = "") -> str:
    u = (url or "").lower()
    t = (title or "").lower()
    c = (content or "").lower()

    if "contact-mangalore-builders" in u or "contact us" in t:
        return "contact"
    if "current-openings" in u or "career" in t or "roles & responsibilities" in c:
        return "careers"
    if "mangalore-builders-news" in u or "latest events" in t or "latest events" in c:
        return "news"
    if "blog.php" in u or "magazine.php" in u:
        return "blog_index"
    if any(k in u for k in [
        "best-", "top-", "why-", "how-", "mistakes-", "guide", "investment", "luxury",
        "home-loan", "nri", "rera", "buying", "homeownership", "renting", "reits", "property",
    ]):
        return "blog"
    if "corporate-profile" in u or "builders-in-mangalore.php" in u or any(cue in t for cue in COMPANY_CUES):
        return "company"
    if "social-responsibility" in u or "csr.php" in u:
        return "csr"
    if "apartments-in-mangalore.php" in u or "commercial-projects-in-mangalore.php" in u:
        return "listing"
    if any(x in u for x in ["apartment-in-", "residential-project", "commercial-project", "villa", "flats-mangalore", "commercial-complex"]):
        return "project"
    if "emi-calculator" in u:
        return "calculator"
    return "general"


def build_chunk(page_type: str, title: str, section_title: str, content: str, url: str, confidence: float = 0.99, source_file: str = "") -> dict:
    chunk = {
        "id": str(uuid.uuid4()),
        "page_type": page_type,
        "title": clean_text(title),
        "section_title": clean_text(section_title),
        "content": clean_text(content),
        "url": clean_text(url),
        "confidence_score": confidence,
        "last_updated": datetime.now(UTC).isoformat(),
    }
    if source_file:
        chunk["source_file"] = source_file
    return chunk


def split_sentences(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [clean_text(s) for s in sentences if clean_text(s)]


def normalize_section_title(title: str, fallback: str = "Details") -> str:
    title = clean_text(title)
    if not title:
        return fallback
    if len(title) > 90:
        title = title[:90].rsplit(" ", 1)[0].strip()
    return title or fallback


def split_by_numbered_points(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    parts = re.split(r"(?=(?:^|\s)\d+\.\s+)", text)
    out = [clean_text(p) for p in parts if word_count(p) >= 10]
    return out


def chunk_by_sentences(text: str, min_words: int = 80, max_words: int = 220) -> list[str]:
    sentences = split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for sent in sentences:
        wc = word_count(sent)
        if current and current_words + wc > max_words:
            chunks.append(clean_text(" ".join(current)))
            current = [sent]
            current_words = wc
        else:
            current.append(sent)
            current_words += wc

    if current:
        chunks.append(clean_text(" ".join(current)))

    merged: list[str] = []
    for chunk in chunks:
        if merged and word_count(chunk) < min_words and word_count(merged[-1]) + word_count(chunk) <= max_words + 40:
            merged[-1] = clean_text(merged[-1] + " " + chunk)
        else:
            merged.append(chunk)
    return [c for c in merged if word_count(c) >= 20]


def extract_contact_sections(content: str) -> list[tuple[str, str]]:
    sections = []
    text = clean_text(content)
    if not text:
        return sections

    for label, pattern in CONTACT_FIELD_PATTERNS.items():
        matches = [clean_text(m) for m in pattern.findall(text) if clean_text(m)]
        matches = list(dict.fromkeys(matches))
        if matches:
            sections.append((label, " | ".join(matches)))

    addr_match = re.search(r"(?:office address|address|corporate office)\s*[:\-]?\s*(.{20,260})", text, flags=re.IGNORECASE)
    if addr_match:
        sections.append(("Address", clean_text(addr_match.group(1))))

    return sections


def split_blog_article(title: str, text: str) -> list[tuple[str, str]]:
    text = clean_text(text)
    if not text:
        return []

    numbered = split_by_numbered_points(text)
    sections: list[tuple[str, str]] = []

    if len(numbered) >= 3:
        intro_bits = []
        if not re.match(r"^\d+\.\s+", numbered[0]):
            intro_bits.append(numbered.pop(0))
        if intro_bits:
            sections.append(("Article Overview", " ".join(intro_bits)))

        for part in numbered:
            m = re.match(r"^(\d+\.\s+[^.?!:]{3,110})", part)
            sec_title = normalize_section_title(m.group(1) if m else title, "Article")
            sections.append((sec_title, part))
    else:
        if word_count(text) <= 260:
            sections.append(("Article", text))
        else:
            for idx, part in enumerate(chunk_by_sentences(text, 110, 220), start=1):
                sec_title = "Article Overview" if idx == 1 else f"Article Part {idx}"
                sections.append((sec_title, part))

    return merge_small_sections(sections, min_words=45, max_words=260)


def split_news_page(title: str, text: str) -> list[tuple[str, str]]:
    text = clean_text(text)
    if not text:
        return []

    event_starts = re.split(
        r"(?=(?:Land Trades|Mangaluru:|Mangalore:|Childhood Cancer|Property Show|CRISIL|Foundation stone|inauguration|launch|award))",
        text,
        flags=re.IGNORECASE,
    )
    parts = [clean_text(p) for p in event_starts if word_count(p) >= 20]
    if len(parts) <= 1:
        parts = chunk_by_sentences(text, 100, 220)

    sections = []
    for idx, part in enumerate(parts, start=1):
        first = clean_text(" ".join(part.split()[:12]))
        sec_title = normalize_section_title(first, f"News Item {idx}")
        sections.append((sec_title, part))
    return merge_small_sections(sections, min_words=45, max_words=260)


def split_careers_page(text: str) -> list[tuple[str, str]]:
    text = clean_text(text)
    if not text:
        return []

    pattern = r"(?=(?:" + "|".join(re.escape(t) for t in CAREER_TITLES) + r"))"
    parts = re.split(pattern, text, flags=re.IGNORECASE)
    sections: list[tuple[str, str]] = []
    current_title = "Career Opportunities"

    i = 0
    while i < len(parts):
        part = clean_text(parts[i])
        if not part:
            i += 1
            continue
        matched = next((t for t in CAREER_TITLES if part.lower().startswith(t.lower())), None)
        if matched:
            body = clean_text(part[len(matched):])
            if i + 1 < len(parts):
                body = clean_text(body + " " + parts[i + 1])
                i += 1
            body = body or matched
            sections.append((matched, body))
        else:
            sections.append((current_title, part))
        i += 1

    if not sections:
        sections = [("Career Opportunities", text)]

    return merge_small_sections(sections, min_words=35, max_words=260)


def split_company_or_general(title: str, text: str, max_words: int = 260) -> list[tuple[str, str]]:
    text = clean_text(text)
    if not text:
        return []

    marker_pattern = re.compile(
        r"(?=(?:About Us|Corporate Profile|Our Vision|Our Mission|Chairman(?:'s)? Message|Founder(?:'s)? Message|Milestones|Awards(?: & Certifications)?|Certifications|Testimonials|Contact|Address|Environmental Policy|Social Responsibility))",
        flags=re.IGNORECASE,
    )
    raw_parts = [clean_text(p) for p in marker_pattern.split(text) if clean_text(p)]

    if len(raw_parts) >= 2:
        sections = []
        for idx, part in enumerate(raw_parts, start=1):
            first_words = " ".join(part.split()[:10])
            sec_title = normalize_section_title(first_words, f"Section {idx}")
            sections.append((sec_title, part))
        return merge_small_sections(sections, min_words=50, max_words=max_words)

    if word_count(text) <= max_words:
        return [("Overview", text)]

    parts = chunk_by_sentences(text, 110, max_words)
    sections = []
    for idx, part in enumerate(parts, start=1):
        sections.append((("Overview" if idx == 1 else f"Details Part {idx}"), part))
    return merge_small_sections(sections, min_words=50, max_words=max_words)


def split_listing_page(title: str, text: str) -> list[tuple[str, str]]:
    text = clean_text(text)
    if not text:
        return []
    if word_count(text) <= 240:
        return [("Listing Overview", text)]
    parts = chunk_by_sentences(text, 110, 230)
    return merge_small_sections([("Listing Overview" if i == 0 else f"Listing Details Part {i+1}", p) for i, p in enumerate(parts)], min_words=55, max_words=260)


def merge_small_sections(sections: list[tuple[str, str]], min_words: int = 40, max_words: int = 260) -> list[tuple[str, str]]:
    merged: list[tuple[str, str]] = []
    for sec_title, body in sections:
        sec_title = normalize_section_title(sec_title)
        body = clean_text(body)
        if not body:
            continue
        if merged and word_count(body) < min_words:
            prev_title, prev_body = merged[-1]
            if word_count(prev_body) + word_count(body) <= max_words + 30:
                merged[-1] = (prev_title, clean_text(prev_body + " " + body))
                continue
        merged.append((sec_title, body))
    return merged


def flatten_table(table: list) -> str:
    rows = []
    for row in table or []:
        if not isinstance(row, list):
            continue
        cells = [clean_text(c) for c in row if clean_text(c)]
        if cells:
            rows.append(" ; ".join(cells))
    return clean_text(" | ".join(rows))


def is_low_value_chunk(section_title: str, content: str, page_type: str) -> bool:
    section_title = clean_text(section_title).lower()
    content = clean_text(content)
    c = content.lower()

    if not content:
        return True
    if content.startswith("http://") or content.startswith("https://"):
        return True
    if word_count(content) < 8:
        return True
    if page_type != "contact" and word_count(content) < 18 and sentence_count(content) < 2 and "•" not in content:
        return True
    if len(set(re.findall(r"[a-zA-Z]+", c))) <= 3 and word_count(content) < 20:
        return True

    bad_exact = {
        "brochure", "emi calculator", "download profile", "manual data source",
        "external reference", "image description", "source"
    }
    if section_title in bad_exact:
        return True

    bad_content_phrases = [
        "request a quote", "enquire now", "call enquire share", "search now",
        "download profile", "previous next", "read more", "click here",
    ]
    if any(p in c for p in bad_content_phrases) and word_count(content) < 35:
        return True

    return False


def dedupe_and_merge_chunks(chunks: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str, str], dict] = {}
    order: list[tuple[str, str, str, str]] = []

    for chunk in chunks:
        key = (
            chunk["page_type"],
            chunk["title"].lower(),
            chunk["url"].lower(),
            chunk["section_title"].lower(),
        )
        content = clean_text(chunk["content"])
        if key not in grouped:
            new_chunk = dict(chunk)
            new_chunk["content"] = content
            grouped[key] = new_chunk
            order.append(key)
            continue

        prev = grouped[key]
        prev_content = clean_text(prev["content"])
        if content.lower() == prev_content.lower():
            continue
        if content.lower() in prev_content.lower():
            continue
        if prev_content.lower() in content.lower():
            prev["content"] = content
            continue
        if word_count(prev_content) + word_count(content) <= 360:
            prev["content"] = clean_text(prev_content + " " + content)

    final_chunks: list[dict] = []
    seen_content = set()
    for key in order:
        chunk = grouped[key]
        norm_content = re.sub(r"\W+", " ", chunk["content"].lower()).strip()
        dup_key = (chunk["title"].lower(), chunk["url"].lower(), norm_content)
        if dup_key in seen_content:
            continue
        seen_content.add(dup_key)
        final_chunks.append(chunk)
    return final_chunks


def add_kb_chunks(chunks: list[dict], pages: list[dict]) -> None:
    for page in pages:
        url = clean_text(page.get("url", ""))
        title = clean_text(page.get("title", ""))
        content = clean_text(page.get("content", ""))
        tables = page.get("tables", []) or []

        if is_manual_project_url(url):
            continue

        page_type = detect_page_type(url, title, content)

        if page_type == "calculator":
            continue
        if not content and not tables:
            continue

        sections: list[tuple[str, str]] = []
        if page_type == "blog":
            sections.extend(split_blog_article(title, content))
        elif page_type == "news":
            sections.extend(split_news_page(title, content))
        elif page_type == "careers":
            sections.extend(split_careers_page(content))
        elif page_type in {"company", "csr", "general", "project"}:
            sections.extend(split_company_or_general(title, content))
        elif page_type == "listing":
            sections.extend(split_listing_page(title, content))
        elif page_type == "contact":
            sections.append(("Contact Details", content))
            sections.extend(extract_contact_sections(content))
        elif page_type == "blog_index":
            sections.extend(split_listing_page(title, content))
        else:
            sections.extend(split_company_or_general(title, content))

        for sec_title, sec_body in sections:
            if is_low_value_chunk(sec_title, sec_body, page_type):
                continue
            chunks.append(build_chunk(page_type, title, sec_title, sec_body, url, confidence=0.99, source_file=INPUT_FILE))

        for idx, table in enumerate(tables, start=1):
            flat = flatten_table(table)
            if flat and not is_low_value_chunk(f"Table {idx}", flat, page_type):
                chunks.append(build_chunk(page_type, title, f"Table {idx}", flat, url, confidence=0.95, source_file=INPUT_FILE))


def list_to_text(items: Iterable) -> str:
    parts = []
    for item in items or []:
        text = clean_text(item)
        if text:
            parts.append(text)
    return " • ".join(dict.fromkeys(parts))


def split_manual_faqs(value) -> list[str]:
    if isinstance(value, list):
        if len(value) == 1:
            text = clean_text(value[0])
        else:
            return [clean_text(v) for v in value if clean_text(v)]
    else:
        text = clean_text(value)

    if not text:
        return []

    parts = re.split(r"(?=(?:^|\s)\d+\.\s+)", text)
    parts = [clean_text(p) for p in parts if word_count(p) >= 6]
    return parts or [text]


def add_manual_project_chunks(chunks: list[dict], manual_data: dict) -> None:
    if not manual_data:
        return

    project_names = sorted({clean_text(v.get("project_name", k)) for k, v in manual_data.items() if isinstance(v, dict)}, key=len, reverse=True)

    for project_name in project_names:
        base = manual_data.get(project_name, {}) or {}
        info = manual_data.get(f"{project_name} info", {}) or {}
        specs = manual_data.get(f"{project_name} Specifications", {}) or {}
        url = clean_text(base.get("url") or info.get("url") or specs.get("url") or f"manual://{slugify(project_name)}")

        overview_bits = []
        highlights = base.get("High lights", []) or base.get("Highlights", []) or []
        if highlights:
            text = list_to_text(highlights)
            chunks.append(build_chunk("project", project_name, "Highlights", text, url, confidence=1.0, source_file=MANUAL_PROJECTS_FILE))
            overview_bits.append(text)

        floor_plans = base.get("Floor Plans", []) or base.get("Floor plans", []) or []
        if floor_plans:
            text = list_to_text(floor_plans)
            chunks.append(build_chunk("project", project_name, "Floor Plans", text, url, confidence=1.0, source_file=MANUAL_PROJECTS_FILE))

        amenities = base.get("amenities_specifications", []) or base.get("Amenities", []) or []
        if amenities:
            text = list_to_text(amenities)
            chunks.append(build_chunk("project", project_name, "Amenities & Features", text, url, confidence=1.0, source_file=MANUAL_PROJECTS_FILE))
            overview_bits.append(text)

        connectivity = info.get("Connectivity", []) or []
        if connectivity:
            text = list_to_text(connectivity)
            chunks.append(build_chunk("project", project_name, "Connectivity", text, url, confidence=1.0, source_file=MANUAL_PROJECTS_FILE))
            overview_bits.append(text)

        faqs = split_manual_faqs(info.get("FAQ'S", []) or info.get("FAQs", []) or info.get("FAQ", []))
        for idx, faq in enumerate(faqs, start=1):
            if faq:
                sec_title = "FAQ" if len(faqs) == 1 else f"FAQ {idx}"
                chunks.append(build_chunk("project", project_name, sec_title, faq, url, confidence=1.0, source_file=MANUAL_PROJECTS_FILE))

        spec_parts = []
        for key, value in specs.items():
            if clean_text(key).lower() in {"project_name", "url", "source", "source_file"}:
                continue
            if isinstance(value, list):
                text = list_to_text(value)
            elif isinstance(value, dict):
                text = " | ".join(f"{clean_text(k)}: {clean_text(v)}" for k, v in value.items() if clean_text(v))
            else:
                text = clean_text(value)
            if text:
                spec_parts.append(f"{clean_text(key)}: {text}")
                chunks.append(build_chunk("project", project_name, f"Specifications - {clean_text(key)}", text, url, confidence=1.0, source_file=MANUAL_PROJECTS_FILE))

        if overview_bits:
            overview = " | ".join(overview_bits[:3])
            chunks.append(build_chunk("project", project_name, "Project Overview", overview, url, confidence=1.0, source_file=MANUAL_PROJECTS_FILE))

        if spec_parts:
            summary = " | ".join(spec_parts[:4])
            chunks.append(build_chunk("project", project_name, "Specifications Summary", summary, url, confidence=1.0, source_file=MANUAL_PROJECTS_FILE))


def add_dummy_chunks(chunks: list[dict], dummy_data: dict) -> None:
    if not dummy_data:
        return

    for project_name, payload in dummy_data.items():
        if not isinstance(payload, dict):
            continue

        title = clean_text(payload.get("name") or project_name)
        url = clean_text(payload.get("url") or f"dummy://{slugify(title)}")

        overview_fields = [
            ("Type", payload.get("type")),
            ("Category", payload.get("category")),
            ("Location", payload.get("location")),
            ("Micro Location", payload.get("micro_location")),
            ("Facing", payload.get("facing")),
            ("Project Status", payload.get("project_status")),
            ("Launch Year", payload.get("launch_year")),
            ("Possession Year", payload.get("possession_year")),
            ("Developer", payload.get("developer")),
            ("RERA ID", payload.get("rera_id")),
            ("Project Area", payload.get("project_area")),
            ("Floors", payload.get("floors")),
            ("Total Units", payload.get("total_units")),
            ("Starting Price", payload.get("starting_price")),
        ]

        overview = " | ".join(
            f"{k}: {clean_text(v)}"
            for k, v in overview_fields
            if clean_text(v)
        )

        if overview:
            chunks.append(
                build_chunk(
                    "project",
                    title,
                    "Project Overview",
                    overview,
                    url,
                    confidence=1.0,
                    source_file=DUMMY_FILE,
                )
            )

        field_map = {
            "Unit Types": payload.get("unit_types"),
            "Amenities": payload.get("amenities"),
            "Specifications": payload.get("specifications"),
            "Connectivity": payload.get("connectivity"),
            "Floor Plans": payload.get("floor_plans"),
            "Gallery Tags": payload.get("gallery_tags"),
            "Investment Profile": payload.get("investment_profile"),
            "Loan Details": payload.get("loan_details"),
            "Bank Interest": payload.get("bank_interest"),
            "EMI Scenarios": payload.get("emi_scenarios"),
            "Year Wise Loan Status": payload.get("year-wise_loan_status") or payload.get("year_wise_loan_status"),
            "Loan Summary": payload.get("loan_summary"),
            "ROI Details": payload.get("roi_details"),
            "ROI 5 Year Table": payload.get("roi_5_year_table"),
            "Booking Process": payload.get("booking_process"),
            "FAQs": payload.get("faqs"),
        }

        for section_title, value in field_map.items():
            if isinstance(value, list):
                text = list_to_text(value)
            else:
                text = clean_text(value)

            if text:
                chunks.append(
                    build_chunk(
                        "project",
                        title,
                        section_title,
                        text,
                        url,
                        confidence=1.0,
                        source_file=DUMMY_FILE,
                    )
                )
def main() -> None:
    pages = load_json(INPUT_FILE)
    if pages is None:
        raise FileNotFoundError(f"{INPUT_FILE} not found")

    chunks: list[dict] = []
    add_kb_chunks(chunks, pages)
    add_manual_project_chunks(chunks, load_json(MANUAL_PROJECTS_FILE) or {})
    add_dummy_chunks(chunks, load_json(DUMMY_FILE) or {})

    chunks = [c for c in chunks if not is_low_value_chunk(c["section_title"], c["content"], c["page_type"])]
    chunks = dedupe_and_merge_chunks(chunks)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(chunks)} chunks to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
