import re

_PROJECT_ALIAS_CACHE: dict[str, str] | None = None


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _load_project_aliases_from_structured_chunks() -> dict[str, str]:
    """
    Build alias -> canonical project name mapping from `structured_chunks.json`.

    Source of truth:
    - Any chunk with `page_type == "project"` contributes its `title` as a project name.
    """
    import json  # local import keeps module import light

    alias_map: dict[str, str] = {}

    try:
        with open("structured_chunks.json", "r", encoding="utf-8") as f:
            chunks = json.load(f)
    except Exception:
        return alias_map

    titles: set[str] = set()
    if isinstance(chunks, list):
        for ch in chunks:
            if not isinstance(ch, dict):
                continue
            if clean_text(ch.get("page_type", "")) != "project":
                continue
            t = (ch.get("title") or "").strip()
            if t:
                titles.add(t)

    for canonical in titles:
        variants = {canonical}

        # Safe normalization variant
        norm = normalize(canonical)
        if norm:
            variants.add(norm)

        # If titles contain "Land Trades <Project>", also allow "<Project>"
        if canonical.lower().startswith("land trades "):
            variants.add(canonical[11:].strip())

        for v in variants:
            v_norm = normalize(v)
            if v_norm:
                alias_map[v_norm] = canonical

    return alias_map


def build_project_aliases() -> dict[str, str]:
    global _PROJECT_ALIAS_CACHE
    if _PROJECT_ALIAS_CACHE is None:
        _PROJECT_ALIAS_CACHE = _load_project_aliases_from_structured_chunks()
    return _PROJECT_ALIAS_CACHE


PROJECT_ALIASES = build_project_aliases()

PROJECT_KEYWORDS = {
    "amenities", "facility", "facilities", "floor plan", "floorplan",
    "layout", "unit", "units", "bhk", "apartment", "apartments",
    "flat", "flats", "villa", "project", "configuration", "location",
    "price", "pricing", "cost", "details", "specification",
    "specifications", "address", "site", "property", "possession",
    "roi", "investment", "invest", "rental", "appreciation", "approvals",
    "legal approvals", "compare", "comparison",
}

COMPANY_KEYWORDS = {
    "company", "builder", "builders", "developer", "developers",
    "office", "head office", "corporate office", "contact details",
    "company address", "office address", "phone number", "email address",
    "customer care", "contact us",
}

CONTACT_ONLY_KEYWORDS = {
    "contact", "phone", "email", "office", "address", "customer care", "whatsapp",
}

PROJECT_FOLLOWUP_KEYWORDS = {
    "this project", "that project", "this apartment", "that apartment",
    "this property", "that property", "its amenities", "its location",
    "its price", "its address", "its details", "its floor plan",
    "its layout", "its configuration", "its specifications",
}

INFO_INTENT_KEYWORDS = {
    "buy", "buying", "purchase", "invest", "investment", "roi",
    "rental", "appreciation", "benefits", "process", "documentation",
    "loan", "finance", "approvals", "compare", "best", "suitable",
}


def contains_phrase(query: str, phrases: set[str]) -> bool:
    return any(p in query for p in phrases)


def detect_project_name(query: str) -> str | None:
    q = normalize(query)
    matches: list[tuple[int, str]] = []

    for alias, canonical_name in PROJECT_ALIASES.items():
        if not alias:
            continue
        pattern = rf"(^|\s){re.escape(alias)}(\s|$)"
        if re.search(pattern, q):
            matches.append((len(alias), canonical_name))

    if not matches:
        return None

    matches.sort(reverse=True)
    return matches[0][1]


def is_project_query(query: str, detected_project: str | None = None) -> bool:
    q = normalize(query)
    if detected_project:
        return True
    if contains_phrase(q, PROJECT_FOLLOWUP_KEYWORDS):
        return True
    if contains_phrase(q, PROJECT_KEYWORDS):
        return True
    if contains_phrase(q, INFO_INTENT_KEYWORDS):
        return True
    return False


def is_company_query(query: str, detected_project: str | None = None) -> bool:
    q = normalize(query)

    if detected_project:
        return False

    if contains_phrase(q, COMPANY_KEYWORDS):
        return True

    if contains_phrase(q, CONTACT_ONLY_KEYWORDS) and not contains_phrase(q, INFO_INTENT_KEYWORDS):
        return True

    return False


def detect_intent(query: str) -> str:
    q = normalize(query)
    detected_project = detect_project_name(q)

    if detected_project:
        return "project"

    if is_project_query(q):
        return "project"

    if is_company_query(q, detected_project=None):
        return "company"

    return "rag"

