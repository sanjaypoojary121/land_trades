#rag_pipeline.py
import json
import os
import re
from collections import defaultdict
from typing import Any

from groq import Groq

from intent_router import detect_intent
from project_links import (
    detect_project_from_text,
    get_project_link_info,
    is_floor_plan_query,
    is_project_link_query,
)
from retriever import retrieve, rerank

# Initialize Groq client with API key
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise EnvironmentError("❌ GROQ_API_KEY environment variable not set!")
if not api_key.startswith("gsk_"):
    print("⚠️  Warning: API key doesn't start with 'gsk_', may be invalid")

client = Groq(api_key=api_key)
print(f"[OK] Groq client initialized (key ending: ...{api_key[-6:]})")

sessions = defaultdict(lambda: {
    "last_project": None,
    "last_company_topic": None,
    "awaiting_image_project": False,
    "pending_image_type": None,
    "pending_image_category": None,
    "pending_image_query": None,
    "chat_history": [],
})

with open("company_info.json", "r", encoding="utf-8") as f:
    company_info = json.load(f)

with open("project_images.json", "r", encoding="utf-8") as f:
    project_images_db = json.load(f)


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    return text



def normalize(text: str) -> str:
    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text



def _img_norm(text: str) -> str:
    return normalize(text)


FOLLOWUP_PROJECT_PHRASES = {
    # Project-specific references
    "this project", "that project", "this apartment", "that apartment",
    "this property", "that property", "its amenities", "its location",
    "its address", "its price", "its details", "its floor plan",
    "its layout", "its configuration", "its specifications", "its possession",
    "its unit types", "its approvals", "its legal approvals",
    # Multi-word follow-up queries only
    "tell me more about it", "tell me more", "more about it",
    "give me more details", "more details", "explain more",
    "how can i book apartment in thisproject", "how can i book apartment in this project",
    "do you provide loan", "loan", "its loan", "its booking", "its address",
    # Floor plan and gallery queries
    "floor plan", "floor plans", "show floor plan", "show floor plans",
    "gallery", "gallery images", "show images", "show gallery",
    "interior", "interior images", "interior photos",
    # Project-specific follow-ups only
    "show photos", "images for", "price for", "cost of", "booking for",
    "availability of", "connectivity of", "amenities of", "specifications of",
}



def extract_project_from_history(history: list) -> str | None:
    """
    Extract the last mentioned project from chat history.
    Searches backwards through history to find project mentions.
    """
    if not history:
        return None
    
    # Search through history in reverse order (most recent first)
    for line in reversed(history):
        # Look for both User and Assistant lines
        if "User:" in line or "Assistant:" in line:
            # Extract the message part
            msg = line.split(":", 1)[1].strip() if ":" in line else line.strip()
            detected = detect_project_from_text(msg)
            if detected:
                return detected
    
    return None


def detect_project_query(query: str, session: dict):
    linked_project = detect_project_from_text(query)
    if linked_project:
        session["last_project"] = linked_project
        return linked_project

    q = normalize(query)
    
    # STRICT follow-up detection: Only use last_project for specific project-related follow-ups
    # Exclude generic phrases to avoid mistaking company queries as project follow-ups
    STRICT_FOLLOWUP_PHRASES = {
        "this project", "that project", "this apartment", "that apartment",
        "this property", "that property", "its amenities", "its location",
        "its address", "its price", "its details", "its floor plan",
        "its layout", "its configuration", "its specifications",
        "floor plan", "floor plans", "show floor plan", "show floor plans",
        "gallery", "gallery images", "show gallery", "interior images",
        "amenities of", "specifications of", "of this", "of that",
    }
    
    # Only apply follow-up if query contains strict project-related phrases AND has a last_project
    if session["last_project"] and any(phrase in q for phrase in STRICT_FOLLOWUP_PHRASES):
        return session["last_project"]
    
    # If no project detected in current query but it's a project-specific follow-up,
    # try to extract from history (only for project-specific keywords)
    project_specific_keywords = {
        "floor plan", "gallery", "images", "interior",
        "amenities", "specifications", "connectivity", "possession",
        "unit types", "bhk", "configuration", "booking",
    }
    
    is_strict_followup = any(keyword in q for keyword in project_specific_keywords)
    
    if is_strict_followup:
        # Try to get project from history
        project_from_history = extract_project_from_history(session.get("chat_history", []))
        if project_from_history:
            return project_from_history
    
    return None



def detect_only_keyword(query: str) -> bool:
    """Detect if user wants ONLY specific information, not boilerplate"""
    q = normalize(query)
    only_patterns = [
        "only ",
        "just ",
        "show me just ",
        "give me just ",
        "i want only ",
        "provide only ",
    ]
    return any(q.startswith(p) or f" {p}" in f" {q}" for p in only_patterns)


def detect_comparison_query(query: str) -> bool:
    """Detect if user is comparing projects or asking which is best"""
    q = normalize(query)
    comparison_patterns = [
        "which is best",
        "which project is best",
        "which one is best",
        "compare",
        "vs",
        "versus",
        "better",
        "best",
        "most",
        "between",
        "among these",
        "among which",
    ]
    return any(p in q for p in comparison_patterns)


def extract_multiple_projects_from_query(query: str) -> list:
    """Extract all project names mentioned in a query"""
    from project_links import detect_project_from_text
    
    q_lower = query.lower()
    projects = []
    
    # Common project names
    project_keywords = [
        "altura", "altitude", "pristine", "shivabagh", "laxmi govind",
        "krishna kuteera", "mahalaxmi", "bmk sky villa", "expertise enclave",
        "durga mahal", "vikram", "synergy", "land trades project 1",
        "land trades project 2", "land trades project 3", "esha", "olivé",
        "atria", "arjun", "aryan", "akshar enclave"
    ]
    
    for proj in project_keywords:
        if proj in q_lower:
            # Normalize the name
            parts = proj.split()
            first_letter = (parts[0][0].upper() + parts[0][1:]) if parts else ""
            normalized = " ".join([first_letter] + [p.capitalize() for p in parts[1:]])
            if normalized not in projects:
                projects.append(normalized)
    
    return projects


def rewrite_comparison_query(query: str, projects: list) -> str:
    """Rewrite a comparison query to emphasize comparison and recommendation"""
    if not projects:
        return query
    
    projects_str = ", ".join(projects)
    return f"Compare these projects: {projects_str}. Which one is best? Provide specific reasoning for your recommendation based on location, amenities, investment potential, and connectivity."


def rewrite_query_with_project(query: str, session: dict):
    project = detect_project_query(query, session)
    q = normalize(query)

    if not project:
        return query

    # More flexible project query detection
    # Check if it's a general project request (includes project name + general keywords)
    project_norm = normalize(project)
    
    # Phrases that indicate a general project overview request
    general_keywords = {"tell", "about", "inform", "explain", "describe", "overview", "project"}
    
    # Check if query contains project name + at least one general keyword
    has_project_name = project_norm in q
    has_general_keyword = any(keyword in q for keyword in general_keywords)
    
    simple_project_queries = {
        normalize(project),
        f"{normalize(project)} project",
        f"about {normalize(project)}",
        f"tell me about {normalize(project)}",
        f"tell me {normalize(project)}",
        f"{normalize(project)} details",
        f"details of {normalize(project)}",
    }

    # broad project overview - if exact match or project name + general keyword
    if q in simple_project_queries or (has_project_name and has_general_keyword):
        return (
            f"Give a complete overview of {project} project including "
            f"project type, location, unit types, amenities, specifications, "
            f"approvals, connectivity, investment details, and loan information."
        )

    # conversational follow-up
    if session.get("last_project") == project and q in {
        "tell me more about it",
        "tell me more",
        "more about it",
        "more",
        "explain more",
        "give more details",
        "more details",
    }:
        return (
            f"Give more details about {project} project including "
            f"location, configuration, amenities, specifications, approvals, "
            f"connectivity, and any extra available project details."
            f"Use the Amenities and Specifications sections for {project} and list all available items clearly."
        )

    if "amenities" in q or "facility" in q or "facilities" in q:
        return (
            f"What are the amenities of {project}? "
            f"Use the Amenities and Specifications sections for {project} and list all available items clearly."
        )

    if "specification" in q or "specifications" in q:
        return (
            f"What are the specifications of {project}? "
            f"Use the Specifications and Amenities sections for {project} and list all available items clearly."
        )

    if "location" in q or "address" in q or "connectivity" in q:
        return f"What is the location, address, and connectivity of {project}?"

    if "floor plan" in q or "layout" in q or "3d plan" in q or "ground floor" in q or "basement floor" in q:
        return f"What floor plans are available for {project}?"

    if "price" in q or "cost" in q or "pricing" in q:
        return f"What is the price or starting price of {project}?"

    if "configuration" in q or "bhk" in q or "unit" in q or "units" in q:
        return f"What are the unit types and configurations of {project}?"

    if "possession" in q:
        return f"What is the possession date and current status of {project}?"

    if "approval" in q or "legal" in q or "rera" in q:
        return f"What are the legal approvals and RERA details of {project}?"

    if "book" in q or "booking" in q:
        return f"How can someone book an apartment in {project}?"

    if "loan" in q or "finance" in q or "financing" in q or "bank" in q or "emi" in q:
        return f"What are the loan and financing options available for {project}? Include any bank partnerships or EMI details if available."

    if "invest" in q or "investment" in q or "roi" in q or "rental" in q:
        return f"What are the investment-related advantages of {project}? Include ROI, rental yield, growth rate, and investment potential."

    return (
        f"Give a complete overview of {project} project including "
        f"location, unit types, amenities, specifications, approvals, "
        f"connectivity, and notable features."
    )



def detect_company_query(query: str):
    q = normalize(query)

    if any(x in q for x in [
        "company address", "office address", "head office", "corporate office",
        "office location", "company location", "address of land trades",
        "location of land trades", "where is land trades",
    ]):
        return "address"

    if any(x in q for x in [
        "phone number", "contact number", "call company", "office phone",
        "contact details", "contact of land trades", "phone of land trades",
    ]):
        return "phone"

    if any(x in q for x in [
        "email address", "company email", "office email", "email of land trades",
    ]):
        return "email"

    if any(x in q for x in [
        "full address with contact details", "full address and contact details",
        "full address with contact", "contact details with address",
    ]):
        return "full_contact"

    if "land trades" in q or "company" in q or "office" in q:
        if "address" in q or "location" in q:
            return "address"
        if "phone" in q or "contact" in q or "call" in q:
            return "phone"
        if "email" in q or "mail" in q:
            return "email"

    return None



def detect_company_followup(query: str):
    q = normalize(query)
    short_followups = {
        "address", "adress", "full address", "location", "office address",
        "office location", "phone", "contact", "contact details", "email", "mail",
    }
    return q if q in short_followups else None



def format_company_answer(field: str, session: dict):
    session["last_company_topic"] = field

    if field == "address":
        return {
            "answer": f"The office address of Land Trades is:\n\n{company_info['address']}",
            "sources": [{"title": "Contact", "url": company_info["website"]}],
            "images": [],
        }

    if field == "phone":
        phones = "\n".join(company_info["phone"])
        return {
            "answer": f"You can contact Land Trades at:\n\n{phones}",
            "sources": [{"title": "Contact", "url": company_info["website"]}],
            "images": [],
        }

    if field == "email":
        emails = "\n".join(company_info["email"])
        return {
            "answer": f"The email addresses of Land Trades are:\n\n{emails}",
            "sources": [{"title": "Contact", "url": company_info["website"]}],
            "images": [],
        }

    if field == "full_contact":
        phones = "\n".join(company_info["phone"])
        emails = ", ".join(company_info["email"])
        return {
            "answer": f"{company_info['address']}\n\n{phones}\nEmail: {emails}",
            "sources": [{"title": "Contact", "url": company_info["website"]}],
            "images": [],
        }

    return {
        "answer": "I couldn't find the company details right now.",
        "sources": [],
        "images": [],
    }



def format_project_link_answer(project_name: str):
    info = get_project_link_info(project_name)
    if not info:
        return {
            "answer": "I could not find a direct project link right now.",
            "sources": [],
            "images": [],
        }

    if info["kind"] == "dedicated":
        answer = f"You can view the official page for {info['name']} here:\n\n[Open {info['name']} project page]({info['url']})"
    elif info["kind"] == "commercial_listing":
        answer = f"{info['name']} appears in the commercial projects listing.\n\n[Open commercial projects listing]({info['url']})"
    elif info["kind"] == "residential_listing":
        answer = f"{info['name']} appears in the residential projects listing.\n\n[Open residential projects listing]({info['url']})"
    else:
        answer = f"[Open project link]({info['url']})"

    return {
        "answer": answer,
        "sources": [{"title": info["name"], "url": info["url"]}],
        "images": [],
    }



def is_gallery_query(text: str) -> bool:
    q = _img_norm(text)

    if is_floor_plan_query(q) or is_interior_query(q):
        return False

    patterns = [
        r"\bgallery\b",
        r"\bgallery image\b",
        r"\bgallery images\b",
        r"\bgallery photo\b",
        r"\bgallery photos\b",
        r"\bsite images\b",
        r"\bsite photos\b",
        r"\bproject images\b",
        r"\bproject photos\b",
        r"\bshow gallery\b",
        r"\bshow images\b",
        r"\bshow photos\b",
        r"\bshow pictures\b",
        r"\bgive me images\b",
        r"\bgive me image\b",
        r"\bgive me few images\b",
        r"\bgive me some images\b",
        r"\bgive me photos\b",
        r"\bimages\b",
        r"\bimage\b",
        r"\bphotos\b",
        r"\bphoto\b",
        r"\bpictures\b",
        r"\bpicture\b",
    ]
    return any(re.search(p, q) for p in patterns)


def is_interior_query(text: str) -> bool:
    q = _img_norm(text)
    patterns = [
        r"\binterior\b",
        r"\binteriors\b",
        r"\binterior image\b",
        r"\binterior images\b",
        r"\binterior photo\b",
        r"\binterior photos\b",
        r"\binterior picture\b",
        r"\binterior pictures\b",
        r"\binside image\b",
        r"\binside images\b",
        r"\binside view\b",
        r"\binside views\b",
        r"\bshow interior\b",
        r"\bshow interiors\b",
        r"\bindoor images\b",
    ]
    return any(re.search(p, q) for p in patterns)


def resolve_image_type(query: str) -> str | None:
    if is_floor_plan_query(query):
        return "floor_plan"
    if is_interior_query(query):
        return "interior"
    if is_gallery_query(query):
        return "gallery"
    return None


def get_project_image_items(project_name: str | None) -> list[dict]:
    if not project_name:
        return []
    return project_images_db.get("projects", {}).get(project_name, [])



def detect_category_from_raw_query(query: str) -> str | None:
    q = _img_norm(query)
    patterns = [
        "ground floor plan", "ground floor", "basement floor plan", "basement",
        "1st floor plan", "first floor plan", "first floor",
        "2nd floor plan", "second floor plan", "second floor",
        "3rd floor plan", "third floor plan", "third floor",
        "4th floor plan", "fourth floor plan", "fourth floor",
        "typical floor plan", "typical unit plan", "terrace floor plan", "terrace plan",
        "parking terrace floor plan", "master plan", "combined and duplex floor plan",
        "duplex lower floor plan", "combined floor plan", "amenities floor plan",
        "upper ground floor plan", "lower ground floor plan", "club house floor plan",
        "floor image", "floor images", "plan image", "plan images",
    ]
    for pattern in patterns:
        if pattern in q:
            return pattern
    return None


def detect_requested_category(query: str, items: list[dict], image_type: str | None = None) -> str | None:
    q = _img_norm(query)

    categories = []
    for item in items:
        if image_type and item.get("type") != image_type:
            continue
        cat = item.get("category")
        if cat and cat not in categories:
            categories.append(cat)

    categories.sort(key=lambda x: len(_img_norm(x)), reverse=True)
    for cat in categories:
        if _img_norm(cat) in q:
            return cat

    for item in items:
        if image_type and item.get("type") != image_type:
            continue
        label = item.get("label", "")
        if label and _img_norm(label) in q:
            return item.get("category") or label

    return None


def dedupe_image_sources(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for item in items:
        key = item.get("source_url") or item.get("url")
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out

def get_general_interior_items() -> list[dict]:
    return project_images_db.get("projects", {}).get("Interiors", [])

def filter_project_images(project_name: str, image_type: str | None = None, category: str | None = None) -> list[dict]:
    items = get_project_image_items(project_name)
    results = []
    wanted_type = _img_norm(image_type) if image_type else None
    wanted_category = _img_norm(category) if category else None

    for item in items:
        item_type = _img_norm(item.get("type", ""))
        item_category = _img_norm(item.get("category", ""))
        item_label = _img_norm(item.get("label", ""))

        if wanted_type and item_type != wanted_type:
            continue
        if wanted_category and wanted_category not in item_category and wanted_category not in item_label:
            continue

        results.append(item)

    return dedupe_image_sources(results)

def format_images_answer_from_items(items: list[dict], answer: str):
    if not items:
        return {
            "answer": "I couldn’t find stored images right now.",
            "sources": [],
            "images": [],
        }

    images = []
    sources = []
    for item in items:
        images.append({
            "label": item.get("label", "Image"),
            "url": item.get("url", ""),
            "source_url": item.get("source_url", ""),
            "type": item.get("type", ""),
            "category": item.get("category", ""),
        })
        source_url = item.get("source_url") or item.get("url")
        if source_url:
            sources.append({"title": item.get("label", "Image"), "url": source_url})

    return {
        "answer": answer,
        "sources": sources,
        "images": images,
    }

def format_general_interior_images_answer():
    items = dedupe_image_sources(get_general_interior_items())
    if not items:
        return {
            "answer": "I couldn’t find stored interior images right now.",
            "sources": [],
            "images": [],
        }

    return format_images_answer_from_items(
        items,
        "Here are some interior images:"
    )

def format_project_images_answer(project_name: str, image_type: str = "gallery", category: str | None = None):
    items = filter_project_images(project_name, image_type=image_type, category=category)

    if not items:
        if image_type == "interior":
            general_items = dedupe_image_sources(get_general_interior_items())
            if general_items:
                return format_images_answer_from_items(
                    general_items,
                    f"I couldn’t find project-specific interior images for {project_name}, but here are some general interior images:"
                )

        if category:
            answer = f"I couldn’t find stored {category} images for {project_name} yet."
        else:
            label = {"floor_plan": "floor plan", "gallery": "gallery", "interior": "interior"}.get(image_type, "image")
            answer = f"I couldn’t find stored {label} images for {project_name} yet."

        return {"answer": answer, "sources": [], "images": []}

    if image_type == "floor_plan":
        answer = f"Here are the {category} images for {project_name}:" if category else f"Here are the floor plan images for {project_name}:"
    elif image_type == "interior":
        answer = f"Here are the interior images for {project_name}:"
    else:
        answer = f"Here are the gallery images for {project_name}:"

    return format_images_answer_from_items(items, answer)



def build_context(docs: list[dict]) -> str:
    blocks = []
    for d in docs:
        content = d.get('content', '')

        if any(x in content.lower() for x in ["not specified", "no specific details"]):
            continue

        blocks.append(
            f"""Title: {d.get('title', '')}
Section: {d.get('section_title', d.get('section', ''))}
Page Type: {d.get('page_type', '')}

Content:
{content}

Source:
{d.get('url', '')}"""
        )
    return "\n\n".join(blocks)



def clean_sources(docs: list[dict]):
    seen = set()
    sources = []
    for d in docs:
        url = d.get("url", "")
        title = d.get("title", "Source")
        if url and url not in seen:
            seen.add(url)
            sources.append({"title": title, "url": url})
    return sources



def append_project_link_to_answer(answer: str, project_name: str | None):
    info = get_project_link_info(project_name) if project_name else None
    if not info or info["url"] in answer:
        return answer

    if info["kind"] == "dedicated":
        suffix = f"\n\nProject page: [Open {info['name']} project page]({info['url']})"
    elif info["kind"] == "commercial_listing":
        suffix = f"\n\nProject listing page: [Open commercial projects listing]({info['url']})"
    elif info["kind"] == "residential_listing":
        suffix = f"\n\nProject listing page: [Open residential projects listing]({info['url']})"
    else:
        suffix = f"\n\nProject link: [Open project page]({info['url']})"

    return answer + suffix



def is_explicit_contact_request(query: str) -> bool:
    q = normalize(query)
    terms = [
        "phone", "contact", "contact number", "call me", "email",
        "office address", "address", "customer care", "whatsapp", "reach land trades",
    ]
    return any(term in q for term in terms)



def is_sales_or_purchase_intent(query: str) -> bool:
    q = normalize(query)
    terms = [
        "book", "booking", "buy", "purchase", "invest", "investment",
        "available", "availability", "price quote", "how to buy", "how to book",
        "roi", "rental income", "appreciation", "loan", "finance",
        "documentation", "approval", "approvals",
    ]
    return any(term in q for term in terms)



def infer_answer_style(query: str) -> str:
    q = normalize(query)
    if any(w in q for w in ["compare", "best", "which", "suitable"]):
        return "comparison"
    if any(w in q for w in ["process", "steps", "documentation", "loan", "finance"]):
        return "process"
    return "normal"



def plan_retrieval_queries(user_query: str, project_name: str | None = None) -> dict[str, Any]:
    q = clean_text(user_query)
    q_norm = normalize(q)

    expanded_queries = [q]
    must_have_terms: list[str] = []
    intent = "general"
    needs_comparison = False
    explicit_contact_request = is_explicit_contact_request(q)

    if project_name:
        must_have_terms.append(project_name)

    if any(w in q_norm for w in ["compare", "best", "which", "suitable"]):
        intent = "comparison"
        needs_comparison = True
        expanded_queries.append(q + " amenities location approvals legal approvals")
        expanded_queries.append("Land Trades residential projects amenities location approvals comparison")
    elif any(w in q_norm for w in ["invest", "investment", "roi", "rental", "appreciation"]):
        intent = "investment_assessment"
        if project_name:
            expanded_queries.append(f"{project_name} investment potential rental income appreciation location approvals")
        expanded_queries.append(q + " investment potential rental income appreciation legal approvals")
        expanded_queries.append(q + " blog investment mangalore property guidance")
    elif any(w in q_norm for w in ["buy", "buying", "purchase", "documentation", "loan", "finance", "approval", "approvals"]):
        intent = "buying_process"
        expanded_queries.append(q + " buying process documentation approvals financing")
        expanded_queries.append("Land Trades buying process documentation approvals financing blog")
    elif project_name:
        intent = "project_info"
        expanded_queries.append(f"{project_name} project details amenities location specifications")
    else:
        expanded_queries.append(q + " project details location amenities")

    deduped = []
    seen = set()
    for item in expanded_queries:
        item = clean_text(item)
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)

    return {
        "intent": intent,
        "answer_style": infer_answer_style(q),
        "must_have_terms": must_have_terms,
        "expanded_queries": deduped[:1],
        "explicit_contact_request": explicit_contact_request,
        "needs_comparison": needs_comparison,
    }



def generate_llm_answer(user_query, docs, session, project_name=None):
    context = build_context(docs)
    
    # Format conversation history with better clarity
    history_lines = session["chat_history"][-10:] if session["chat_history"] else []
    if history_lines:
        history_text = "**CONVERSATION HISTORY:**\n" + "\n".join(history_lines)
    else:
        history_text = "(This is the first question in our conversation)"
    
    # Build project context emphasis
    project_context = ""
    if project_name:
        project_context = f"\n\n**IMPORTANT: This conversation is about the {project_name} project. Keep this context in mind for your answer.**"
    
    # Determine focus based on query type
    q_norm = normalize(user_query)
    focus_instructions = ""
    suppress_boilerplate = detect_only_keyword(user_query)
    is_comparison = detect_comparison_query(user_query)
    is_loan_query = any(w in q_norm for w in ["loan", "finance", "financing", "bank", "emi", "interest rate"])
    
    if is_comparison:
        focus_instructions = "\n**ANSWER FOCUS**: This is a COMPARISON query. Provide a SPECIFIC recommendation with clear reasoning. DO NOT just list projects—recommend which one is BEST and explain why."
    elif is_loan_query:
        focus_instructions = "\n**ANSWER FOCUS**: This is a LOAN/FINANCE question. Prioritize exact loan information, bank partnerships, EMI details, and financing options. Provide SPECIFIC numbers if available."
    elif any(w in q_norm for w in ["roi", "return", "rental", "yield", "appreciation", "investment", "5 year", "growth"]):
        focus_instructions = "\n**ANSWER FOCUS**: This is an INVESTMENT/ROI question. Prioritize SPECIFIC ROI percentages, rental yields (%), growth rates (%), 5-year returns, and investment potential. Provide exact numbers from the knowledge base."
    elif any(w in q_norm for w in ["amenity", "amenities", "facility", "facilities", "feature"]):
        focus_instructions = "\n**ANSWER FOCUS**: This is an AMENITIES question. List and describe all amenities clearly from the knowledge base. Be specific and detailed."
    elif any(w in q_norm for w in ["specification", "specifications", "configuration", "bhk", "unit", "floor", "size"]):
        focus_instructions = "\n**ANSWER FOCUS**: This is a SPECIFICATIONS/LAYOUT question. Focus on unit types, exact configurations, sizes in SQFT, and detailed specifications."
    elif any(w in q_norm for w in ["location", "address", "connectivity", "near", "nearby", "distance"]):
        focus_instructions = "\n**ANSWER FOCUS**: This is a LOCATION/CONNECTIVITY question. Focus on EXACT location, full address, specific nearby landmarks, and exact distances."
    else:
        # ✅ FOR GENERAL PROJECT QUERIES: DO NOT include loan information - EVER
        focus_instructions = "\n**ANSWER FOCUS**: This is a GENERAL PROJECT query. Answer ONLY about project highlights, amenities, locations, connectivity, and specifications from the knowledge base. ABSOLUTELY DO NOT include any loan/financing/investment/banking information - NEVER add 'Loan Information' section or financing suggestions unless the user explicitly asks about loans. Structure your answer around the actual project details only."
    
    boilerplate_instruction = ""
    if suppress_boilerplate:
        boilerplate_instruction = "\n**CRITICAL**: User asked for ONLY specific information. DO NOT add generic suggestions like 'You can also ask for floor plans' or 'contact support'. Answer ONLY what was asked."
    
    # ✅ ALWAYS add this for general queries - NEVER add loan sections
    if not is_loan_query and not is_comparison and "loan" not in q_norm and "finance" not in q_norm and "invest" not in q_norm:
        boilerplate_instruction += "\n**NEVER ADD**: Do NOT include a 'Loan Information' section, financing options, or banking details. Only provide the project information that is in the knowledge base."
    

    prompt = f"""You are the Land Trades AI Assistant — a professional real estate consultant for Land Trades Builders & Developers, Mangalore.

CRITICAL RULES FOR ALL RESPONSES:
1. **ONLY use the KNOWLEDGE BASE provided.** Do NOT invent, fabricate, hallucinate, or generate any information.
2. **Answer ONLY the user's specific question.** Do NOT add extra content, sections, or suggestions.
3. **NEVER create a 'Loan Information' section for general project queries.** ONLY if user explicitly asks about loans/financing.
4. **For general queries, if some details are not available in the knowledge base, do NOT mention that they are missing.** Simply ignore those points and answer only with the relevant details that are available.
5. **Do NOT suggest options the user didn't ask for.**

{history_text}

**CURRENT QUESTION:**
{user_query}{project_context}{focus_instructions}{boilerplate_instruction}

**KNOWLEDGE BASE:**
{context}

**RULES:**

PROJECT CLASSIFICATION (Ongoing Projects):
    Residential Projects:
    - Expertise Enclave (Moneky Stand, Jeppu)
    - Durga Mahal (Mannaguda Road Kudroli)
    - Altitude (Bendoorwell, Mangalore)
    - Laxmi Govind (Alvares Road, Kadri, Mangalore)
    - Krishna Kuteera (Kadri Kambla Road, Mangalore)
    - Mahalaxmi (Alake, Mangaluru)
    - BMK Sky Villa (Vaslane, Mangalore)
    - Pristine (Chilimbi, Mangalore)
    - Shivabagh (Shivabagh, Kadri)
    - Altura (Bendoorwell, Mangalore)
    - Land Trades Project 1 (Bendoorwell, Mangalore)
    - Land Trades Project 3 (Near Coastal Belt, Mangalore)

    Commercial Projects:
    - Vikram (PVS Road, Kodialbail)
    - Synergy (Yeyyadi, Mangaluru)
    - Land Trades Project 2 (Hampankatta, Mangalore)

* while listing the projects include land trades project 1,2,3 also     
* Answer from knowledge base - never hallucinate
* For Yes/No questions, start with a short direct answer like "Yes" or "No".
* Use **bold** for project names, headings, and key numbers, and use bullet points instead of long paragraphs.
* Use standard Markdown lists with "-" when listing items.
* Put each list item on a separate line.
* When listing project names, include the location in brackets  
  – Example: **Altitude (Bendoorwell, Mangalore)**
* **CONTEXT PRESERVATION**: If this question is about a project mentioned earlier in our conversation, continue discussing that project unless the user asks about a different topic or different project.
* Provide clean, structured, and human-like explanations.
* For general queries, answer only with the details available in the extracted context and silently skip unavailable points.
* If the user asks for floor plans, galleries, or images about a project we discussed, remember which project it is.
* For investment, booking/loan queries, Answer from context first, then optionally suggest contacting support.
* Do not say, “Unfortunately, the provided context does not have the details.” Instead, answer using the available data in the context that is relevant to the user’s question.
* Do NOT add "data missing" unless directly required.
* Be conversational but professional.
* If the user asks about:
  Expertise Enclave, Durga Mahal, Altitude, Laxmi Govind, Krishna Kuteera, Mahalaxmi, BMK Sky Villa, Pristine, Shivabagh, Altura, Vikram, Synergy  
  → You may suggest:  
  "You can also ask for floor plans or gallery images [and project info]" (mention project info only if it is not already included in the response)
* **FOR COMPARISON QUERIES**: When comparing projects, provide a clear recommendation with specific reasoning for why one is better for the user's needs.
* **FOR "ONLY" QUERIES**: Comply strictly - NO boilerplate, NO suggestions, NO contact info
* **FOR GENERAL PROJECT QUERIES**: Do NOT add loan/financing info unless explicitly asked
* Never say "No specific details available", "not explicitly mentioned", or similar phrases for general queries. Just answer from the available data.

Answer:
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        error_msg = str(e)
        print(f"💥 DEBUG - Full Error: {error_msg}")
        if "403" in error_msg or "Access denied" in error_msg:
            return "❌ API Authentication Error: Your Groq API key is invalid or expired. Please set a valid GROQ_API_KEY environment variable."
        elif "404" in error_msg:
            return "❌ Model Error: The Groq model 'llama-3.3-70b-versatile' is not available. Please contact support or check API status at status.groq.com."
        elif "429" in error_msg or "rate limit" in error_msg.lower():
            return "⚠️  Rate Limited: Too many requests. Please wait a moment and try again."
        elif "connection" in error_msg.lower() or "timeout" in error_msg.lower() or "qdrant" in error_msg.lower():
            return "⚠️  Connection Error: Temporary service issue. Please try again in a moment."
        else:
            print(f"❌ LLM Error: {error_msg}")
            return f"❌ Error generating response: {error_msg[:80]}"


def retrieve_with_planner(original_query: str, project: str | None) -> tuple[list[dict], dict[str, Any]]:
    planner = plan_retrieval_queries(original_query, project)
    all_docs = []
    seen_ids = set()
    
    # ✅ FOR GENERAL PROJECT OVERVIEW QUERIES: Do targeted multi-section searches
    is_general_overview = (
        re.search(r"tell\s+(?:me\s+)?about.*project", original_query, re.IGNORECASE) or
        re.search(r"about.*project\s*$", original_query, re.IGNORECASE)
    )
    
    if is_general_overview and project:
        # Do THREE targeted searches to get highlights + amenities + connectivity
        targeted_searches = [
            f"{project} highlights features key points",
            f"{project} amenities facilities services",
            f"{project} connectivity location nearby distance",
        ]
        for search_query in targeted_searches:
            docs = retrieve(search_query, top_k=4)
            for doc in docs:
                doc_id = doc.get("id") or f"{doc.get('url', '')}|{doc.get('section_title', '')}|{hash(doc.get('content', ''))}"
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    all_docs.append(doc)
    else:
        # Standard retrieval for other queries
        for search_query in planner.get("expanded_queries", [original_query])[:1]:
            docs = retrieve(search_query, top_k=7)
            for doc in docs:
                doc_id = doc.get("id") or f"{doc.get('url', '')}|{doc.get('section_title', '')}|{hash(doc.get('content', ''))}"
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    all_docs.append(doc)

    final_docs = rerank(original_query, all_docs, top_k=6) if all_docs else []
    return final_docs, planner


def maybe_append_soft_contact_cta(answer: str, query: str, project: str | None) -> str:
    q = normalize(query)
    
    # Respect "only" keyword - don't add boilerplate
    if detect_only_keyword(query):
        return answer

    should_add = any(x in q for x in [
        "book", "booking", "buy", "purchase", "invest", "investment",
        "loan", "finance", "pricing", "price", "availability"
    ])

    if not should_add or is_explicit_contact_request(query):
        return answer

    suffix = (
        "\n\nIf you want, I can also share the Land Trades contact details for "
        "pricing, booking support, or loan assistance."
    )
    return answer + suffix

def clean_final_answer(answer: str) -> str:
    bad_phrases = [
        "not specified",
        "no specific details available",
        "information not available",
        "not available in the dataset",
        "no specific loan details available",
    ]

    lines = answer.split("\n")
    cleaned = []

    skip_next_empty_header = False

    for i, line in enumerate(lines):
        lower = line.lower().strip()

        # Remove bad lines
        if any(bp in lower for bp in bad_phrases):
            continue

        # Remove empty headers like "Amenities:" if no content after
        if line.strip().endswith(":"):
            # Check next line
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip().lower()
                if any(bp in next_line for bp in bad_phrases):
                    continue

        cleaned.append(line)

    return "\n".join(cleaned)

def generate_answer(query, session_id="default"):
    session = sessions[session_id]
    q_norm = normalize(query)

    company_field = detect_company_query(query)
    company_followup = detect_company_followup(query)

    explicit_company_query = any(x in q_norm for x in [
        "land trades", "company", "office", "head office", "corporate office",
    ])

    if company_followup and session["last_company_topic"]:
        if company_followup in {"address", "adress", "location", "office address", "office location"}:
            return format_company_answer("address", session)
        if company_followup in {"full address"}:
            return format_company_answer("full_contact", session)
        if company_followup in {"phone", "contact", "contact details"}:
            return format_company_answer("phone", session)
        if company_followup in {"email", "mail"}:
            return format_company_answer("email", session)

    if company_field and explicit_company_query:
        return format_company_answer(company_field, session)

    intent = detect_intent(query)
    project = detect_project_query(query, session)

    if session["awaiting_image_project"]:
        followup_project = detect_project_query(query, session) or detect_project_from_text(query)

        # allow generic interior fallback without forcing a project
        if not followup_project and (session.get("pending_image_type") == "interior"):
            session["awaiting_image_project"] = False
            session["pending_image_type"] = None
            session["pending_image_category"] = None
            session["pending_image_query"] = None
            return format_general_interior_images_answer()

        if followup_project:
            session["awaiting_image_project"] = False
            requested_type = session.get("pending_image_type") or "floor_plan"
            requested_category = session.get("pending_image_category")

            image_result = format_project_images_answer(
                project_name=followup_project,
                image_type=requested_type,
                category=requested_category,
            )

            session["pending_image_type"] = None
            session["pending_image_category"] = None
            session["pending_image_query"] = None

            if image_result["images"]:
                return image_result

            return {
                "answer": f"I couldn’t find stored {requested_type.replace('_', ' ')} images for {followup_project} yet.",
                "sources": [],
                "images": [],
            }

    if intent == "company" and not project and company_field:
        return format_company_answer(company_field, session)

    if is_project_link_query(query) and project:
        return format_project_link_answer(project)

    requested_image_type = resolve_image_type(query)

    # image / gallery / floor plan / interior queries should never go to LLM
    if requested_image_type:
        if project:
            category = detect_requested_category(
                query,
                get_project_image_items(project),
                image_type=requested_image_type
            )

            image_result = format_project_images_answer(
                project_name=project,
                image_type=requested_image_type,
                category=category
            )

            if image_result["images"]:
                return image_result

            if requested_image_type == "interior":
                general_result = format_general_interior_images_answer()
                if general_result["images"]:
                    return general_result

            return {
                "answer": f"I couldn’t find stored {requested_image_type.replace('_', ' ')} images for {project} yet.",
                "sources": [],
                "images": [],
            }

        # general interiors can be shown without asking project
        if requested_image_type == "interior":
            general_result = format_general_interior_images_answer()
            if general_result["images"]:
                return general_result

        session["awaiting_image_project"] = True
        session["pending_image_type"] = requested_image_type
        session["pending_image_category"] = detect_category_from_raw_query(query)
        session["pending_image_query"] = query

        prompt_label = {
            "floor_plan": "floor plan",
            "gallery": "gallery images",
            "interior": "interior images",
        }.get(requested_image_type, "images")

        return {
            "answer": f"Which project do you want the {prompt_label} for?",
            "sources": [],
            "images": [],
        }

    # Handle comparison queries specially
    is_comparison = detect_comparison_query(query)
    if is_comparison:
        mentioned_projects = extract_multiple_projects_from_query(query)
        if len(mentioned_projects) >= 2:
            rewritten_query = rewrite_comparison_query(query, mentioned_projects)
        else:
            rewritten_query = query
    else:
        rewritten_query = rewrite_query_with_project(query, session)
    
    docs, planner = retrieve_with_planner(rewritten_query, project)

    if not docs:
        if is_explicit_contact_request(query):
            return format_company_answer(company_field or "full_contact", session)

        if project:
            info = get_project_link_info(project)
            sources = []
            answer = f"I found the project name {project}, but I could not retrieve enough reliable details from the current data to answer that accurately."
            if info:
                answer += f"\n\nProject page:\n[Open {info['name']} project page]({info['url']})"
                sources.append({"title": info["name"], "url": info["url"]})
            return {"answer": answer, "sources": sources, "images": []}

        return {
            "answer": "I couldn’t find enough reliable information in the current Land Trades data to answer that accurately.",
            "sources": [],
            "images": [],
        }

    answer = generate_llm_answer(rewritten_query, docs, session, project)
    answer = clean_final_answer(answer)
    answer = maybe_append_soft_contact_cta(answer, query, project)

    if project:
        answer = append_project_link_to_answer(answer, project)

    session["chat_history"].append(f"User: {query}")
    session["chat_history"].append(f"Assistant: {answer}")

    sources = clean_sources(docs)
    info = get_project_link_info(project) if project else None
    if info:
        existing_urls = {s['url'] for s in sources}
        if info["url"] not in existing_urls:
            sources.append({"title": info["name"], "url": info["url"]})

    # Auto-add 2 gallery images when discussing a project
    images = []
    if project:
        gallery_items = filter_project_images(project, image_type="gallery")
        images = gallery_items[:2] if gallery_items else []

    return {
        "answer": answer,
        "sources": sources,
        "images": images,
        "debug": {
            "intent": intent,
            "planner_intent": planner.get("intent"),
            "project": project,
        },
    }


if __name__ == "__main__":
    while True:
        query = input("\nAsk about Land Trades: ").strip()
        if query.lower() in ["exit", "quit"]:
            break

        result = generate_answer(query)
        print("\nAnswer:\n")
        print(result["answer"])

        print("\nSources:\n")
        for s in result["sources"]:
            print(f"- {s['title']}")
            print(f"  {s['url']}")

        if result.get("images"):
            print("\nImages:\n")
            for img in result["images"]:
                print(f"- {img.get('label', 'Image')}")
                print(f"  {img.get('url', '')}")

