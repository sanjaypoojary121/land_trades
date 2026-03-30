
import re


def _norm(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


RESIDENTIAL_LISTING_URL = "https://landtrades.in/apartments-in-mangalore.php"
COMMERCIAL_LISTING_URL = "https://landtrades.in/commercial-projects-in-mangalore.php"


# Dedicated / active pages
PROJECT_PAGE_URLS = {
    "Altitude": "https://landtrades.in/altitude-residential-project-bendoorwell.php",
    "Altura": "https://landtrades.in/altura-residential-bendoorwell-mangalore.php",
    "BMK Sky Villa": "https://landtrades.in/sky-villa-apartments-mangalore.php",
    "Expertise Enclave": "https://landtrades.in/expertise-enclave-apartment-in-mangalore.php",
    "Krishna Kuteera": "https://landtrades.in/krishna-kuteera-apartment-in-mangalore.php",
    "Laxmi Govind": "https://landtrades.in/laxmi-govind-apartment-in-kadri-mangalore.php",
    "Mahalaxmi": "https://landtrades.in/mahalaxmi-residential-apartment-mangalore.php",
    "Pristine": "https://landtrades.in/pristine-flats-mangalore.php",
    "Shivabagh": "https://landtrades.in/shivabagh-residential-apartment-mangalore.php",
    "Synergy": "https://landtrades.in/synergy-commercial-project-mangalore.php",
    "Vikram": "https://landtrades.in/vikram-commercial-complex-kodialbail-mangalore.php",
    "Durga Mahal": "https://landtrades.in/durga-mahal-apartment-in-mannaguda-road-kudroli.php",
}

# Completed / listing-only commercial projects
COMMERCIAL_LISTING_ONLY = {
    "Indus": COMMERCIAL_LISTING_URL,
    "Anantessh": COMMERCIAL_LISTING_URL,
    "Milestone 25": COMMERCIAL_LISTING_URL,
    "Parin": COMMERCIAL_LISTING_URL,
    "Aadheesh": COMMERCIAL_LISTING_URL,
    "Land Trades Project 2": COMMERCIAL_LISTING_URL,
}

# Completed / listing-only residential projects
RESIDENTIAL_LISTING_ONLY = {
    "Adira": RESIDENTIAL_LISTING_URL,
    "Kamath Gardens": RESIDENTIAL_LISTING_URL,
    "Nakshatra": RESIDENTIAL_LISTING_URL,
    "Habitat One54": RESIDENTIAL_LISTING_URL,
    "Emerald Bay": RESIDENTIAL_LISTING_URL,
    "Solitaire": RESIDENTIAL_LISTING_URL,
    "Insignia": RESIDENTIAL_LISTING_URL,
    "Lenhil Ferns": RESIDENTIAL_LISTING_URL,
    "Melody": RESIDENTIAL_LISTING_URL,
    "Sanskriti": RESIDENTIAL_LISTING_URL,
    "Aashna": RESIDENTIAL_LISTING_URL,
    "Atlantis": RESIDENTIAL_LISTING_URL,
    "Roopali": RESIDENTIAL_LISTING_URL,
    "Vasundhara": RESIDENTIAL_LISTING_URL,
    "Aquarius": RESIDENTIAL_LISTING_URL,
    "Maurishka Palace": RESIDENTIAL_LISTING_URL,
    "Sai Prem": RESIDENTIAL_LISTING_URL,
    "Rehoboth": RESIDENTIAL_LISTING_URL,
    "Brookside": RESIDENTIAL_LISTING_URL,
    "Adonia": RESIDENTIAL_LISTING_URL,
    "Hillside Ferns": RESIDENTIAL_LISTING_URL,
    "Minerva": RESIDENTIAL_LISTING_URL,
    "Ourania": RESIDENTIAL_LISTING_URL,
    "Sai Grandeur": RESIDENTIAL_LISTING_URL,
    "Serene": RESIDENTIAL_LISTING_URL,
    "Danube": RESIDENTIAL_LISTING_URL,
    "Pushkar": RESIDENTIAL_LISTING_URL,
    "Aria": RESIDENTIAL_LISTING_URL,
    "Mercara Heights": RESIDENTIAL_LISTING_URL,
    "Olive": RESIDENTIAL_LISTING_URL,
    "Orion": RESIDENTIAL_LISTING_URL,
    "Aadhee": RESIDENTIAL_LISTING_URL,
    "Vijaya": RESIDENTIAL_LISTING_URL,
    "Esha": RESIDENTIAL_LISTING_URL,
    "Hathill Crest": RESIDENTIAL_LISTING_URL,
    "Astoria": RESIDENTIAL_LISTING_URL,
    "Land Trades Project 1": RESIDENTIAL_LISTING_URL,
    "Land Trades Project 3": RESIDENTIAL_LISTING_URL,
}

# Extra aliases for matching user input
PROJECT_ALIASES = {
    # Active / dedicated
    "bmk sky villa": "BMK Sky Villa",
    "sky villa": "BMK Sky Villa",
    "skyvilla": "BMK Sky Villa",
    "shivabagh": "Shivabagh",
    "shivbagh": "Shivabagh",
    "laxmi govind": "Laxmi Govind",
    "krishna kuteera": "Krishna Kuteera",
    "mahalaxmi": "Mahalaxmi",
    "expertise enclave": "Expertise Enclave",
    "expertise": "Expertise Enclave",
    "synergy": "Synergy",
    "vikram": "Vikram",
    "pristine": "Pristine",
    "altitude": "Altitude",
    "altura": "Altura",
    "durga mahal": "Durga Mahal",

    # Completed / aliases
    "milestone25": "Milestone 25",
    "milestone 25": "Milestone 25",
    "habitat": "Habitat One54",
    "habitat one54": "Habitat One54",
    "emerald": "Emerald Bay",
    "emerald bay": "Emerald Bay",
    "lenhil": "Lenhil Ferns",
    "lenhil ferns": "Lenhil Ferns",
    "kamath": "Kamath Gardens",
    "kamath gardens": "Kamath Gardens",
    "sai grandeur": "Sai Grandeur",
    "maurishka": "Maurishka Palace",
    "maurishka palace": "Maurishka Palace",
    "solitaire apartment": "Solitaire",
    "solitaire project": "Solitaire",
    "indus project": "Indus",
    "parin project": "Parin",
    "aadheesh project": "Aadheesh",
    "adhira": "Adira",
    "adira": "Adira",
    "esha": "Esha",
    "aadhee": "Aadhee",
    "hathill": "Hathill Crest",
    "crest": "Hathill Crest",
    # Land Trades Projects 1-4
    "land trades project 1": "Land Trades Project 1",
    "land trades 1": "Land Trades Project 1",
    "project 1": "Land Trades Project 1",
    "land trades project 2": "Land Trades Project 2",
    "land trades 2": "Land Trades Project 2",
    "project 2": "Land Trades Project 2",
    "land trades project 3": "Land Trades Project 3",
    "land trades 3": "Land Trades Project 3",
}

_ALL_PROJECTS = {}
_ALL_PROJECTS.update(PROJECT_PAGE_URLS)
_ALL_PROJECTS.update(COMMERCIAL_LISTING_ONLY)
_ALL_PROJECTS.update(RESIDENTIAL_LISTING_ONLY)

_NORM_TO_CANONICAL = {}
for name in _ALL_PROJECTS:
    _NORM_TO_CANONICAL[_norm(name)] = name
for alias, canonical in PROJECT_ALIASES.items():
    _NORM_TO_CANONICAL[_norm(alias)] = canonical


def detect_project_from_text(text: str) -> str | None:
    q = _norm(text)
    matches = []

    for alias_norm, canonical in _NORM_TO_CANONICAL.items():
        pattern = rf"(^|\s){re.escape(alias_norm)}(\s|$)"
        if re.search(pattern, q):
            matches.append((len(alias_norm), canonical))

    if not matches:
        return None

    matches.sort(reverse=True)
    return matches[0][1]


def get_project_link_info(project_name: str | None) -> dict | None:
    if not project_name:
        return None

    canonical = _NORM_TO_CANONICAL.get(_norm(project_name), project_name)
    url = _ALL_PROJECTS.get(canonical)

    if not url:
        return None

    if canonical in PROJECT_PAGE_URLS:
        return {"name": canonical, "url": url, "kind": "dedicated"}
    if canonical in COMMERCIAL_LISTING_ONLY:
        return {"name": canonical, "url": url, "kind": "commercial_listing"}
    if canonical in RESIDENTIAL_LISTING_ONLY:
        return {"name": canonical, "url": url, "kind": "residential_listing"}

    return {"name": canonical, "url": url, "kind": "unknown"}


def is_floor_plan_query(text: str) -> bool:
    q = _norm(text)
    patterns = [
        r"\bfloor plan\b",
        r"\bfloor plans\b",
        r"\bfloor image\b",
        r"\bfloor images\b",
        r"\bplan image\b",
        r"\bplan images\b",
        r"\blayout\b",
        r"\blayout image\b",
        r"\blayout images\b",
        r"\b3d plan\b",
        r"\b3d floor plan\b",
        r"\bmaster plan\b",
        r"\btypical floor plan\b",
        r"\bterrace floor plan\b",
        r"\bground floor plan\b",
        r"\bbasement floor plan\b",
    ]
    return any(re.search(p, q) for p in patterns)


def is_project_link_query(text: str) -> bool:
    q = _norm(text)
    terms = [
        "project link",
        "project page",
        "direct link",
        "official link",
        "website link",
        "show project page",
        "open project page",
        "give me the link",
    ]
    return any(term in q for term in terms)