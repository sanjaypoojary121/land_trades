import json
import re
from typing import Any, Dict, List

from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

COLLECTION_NAME = "landtrades_knowledge"
TOP_K_DEFAULT = 7
VECTOR_LIMIT = 15
BM25_LIMIT = 15

print("Loading embedding model...")
embed_model = SentenceTransformer("BAAI/bge-base-en-v1.5")

print("Loading reranker model...")
reranker = CrossEncoder("BAAI/bge-reranker-base")

print("Connecting to Qdrant Cloud...")
client = QdrantClient(
    url="https://e7e5537b-3817-477c-a313-012c7ebe6e9d.us-west-2-0.aws.cloud.qdrant.io:6333",
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.KFCt0UqJvRGplUZ9LcpCHZ3ZlGx-jsiOxKNnVkerhhk",
)

print("Loading chunks for BM25...")
with open("structured_chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

STOPWORDS = {
    "what", "is", "are", "the", "of", "in", "for", "a", "an", "to", "me",
    "tell", "about", "show", "list", "all", "give", "project", "projects",
    "land", "trades", "please", "its", "it", "this", "that", "can", "i",
    "do", "should", "would", "be", "my", "there", "any", "on", "from",
}

CONTACT_WORDS = {
    "phone", "contact", "email", "office", "address", "call", "mobile",
    "customer care", "reach", "whatsapp",
}

INVESTMENT_WORDS = {
    "invest", "investment", "roi", "return", "rental", "appreciation",
    "capital gain", "yield", "good investment",
}

COMPARISON_WORDS = {
    "compare", "best", "which", "suitable", "recommend", "better",
}

BUYING_WORDS = {
    "buy", "buying", "purchase", "booking", "book", "loan", "finance",
    "documentation", "approval", "approvals", "legal", "rera",
}

NOISY_PAGE_TYPES = {"image", "external_link"}

KNOWN_PROJECTS = [
    "expertise enclave",
    "durga mahal",
    "altitude",
    "laxmi govind",
    "krishna kuteera",
    "mahalaxmi",
    "bmk sky villa",
    "pristine",
    "shivabagh",
    "altura",
    "vikram",
    "synergy",
    "Land Trades Project 1",
    "Land Trades Project 2",
    "Land Trades Project 3",
]

# ✅ KEY SECTIONS FOR STRUCTURED RETRIEVAL
KEY_SECTIONS = {
    "highlights": ["highlights", "highlights and features", "key highlights"],
    "amenities": ["amenities", "facilities", "features"],
    "connectivity": ["connectivity", "nearby", "proximity", "distance"],
    "specifications": ["specifications", "specification", "specs", "technical"],
    "floor_plans": ["floor plan", "layout", "floor plans", "layouts"],
    "pricing": ["pricing", "price", "cost", "investment"],
    "legal": ["approvals", "rera", "legal", "registration"],
}

def detect_project_name_from_query(query: str) -> str:
    q = normalize_text(query)
    for name in KNOWN_PROJECTS:
        if name in q:
            return name
    return ""

def detect_section_from_query(query: str) -> str:
    """Extract desired section (highlights, amenities, etc.) from query"""
    q = normalize_text(query)
    for section_key, keywords in KEY_SECTIONS.items():
        for keyword in keywords:
            if keyword in q:
                return section_key
    return ""

def is_loan_query(query: str) -> bool:
    """Check if the query is explicitly asking about loans/financing"""
    q = normalize_text(query)
    loan_keywords = ["loan", "finance", "financing", "bank", "emi", "interest", "credit"]
    return any(kw in q for kw in loan_keywords)

def is_loan_section(chunk: Dict[str, Any]) -> bool:
    """Check if chunk is about loan/financing information"""
    section = normalize_text(chunk.get("section_title", chunk.get("section", "")))
    content = normalize_text(chunk.get("content", ""))
    
    loan_keywords = ["loan", "finance", "financing", "bank", "emi", "interest", "credit"]
    return any(kw in section or kw in content for kw in loan_keywords)

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = str(text).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text



def normalize_text(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text



def tokenize(text: str) -> List[str]:
    return normalize_text(text).split()



def build_search_text(chunk: Dict[str, Any]) -> str:
    title = chunk.get("title", "")
    section = chunk.get("section_title", chunk.get("section", ""))
    page_type = chunk.get("page_type", "")
    content = chunk.get("content", "")
    return f"{title} {section} {page_type} {content}".strip()



def extract_salient_terms(query: str) -> List[str]:
    return [t for t in tokenize(query) if t not in STOPWORDS and len(t) > 2]



def detect_query_mode(query: str) -> str:
    q = normalize_text(query)

    if any(w in q for w in CONTACT_WORDS):
        return "contact"
    if any(w in q for w in COMPARISON_WORDS):
        return "comparison"
    if any(w in q for w in INVESTMENT_WORDS):
        return "investment"
    if any(w in q for w in BUYING_WORDS):
        return "buying"
    return "general"



def normalize_query(query: str) -> str:
    q = clean_text(query)
    replacements = {
        "floor plans": "floor plan",
        "layouts": "layout",
        "facilities": "amenities facilities",
        "apartments": "apartment",
        "flats": "flat apartment",
        "villas": "villa",
        "builders": "builder",
        "adress": "address",
    }
    for old, new in replacements.items():
        q = q.replace(old, new)
    return q



def expand_query(query: str, mode: str) -> str:
    q = normalize_query(query)
    
    # ✅ EXTRACT PROJECT + SECTION FOR TARGETED RETRIEVAL
    project_name = detect_project_name_from_query(query)
    section_name = detect_section_from_query(query)

    # If we have project + section, create highly specific search
    if project_name and section_name:
        # Add the actual section keywords to boost retrieval
        for keywords in KEY_SECTIONS.values():
            for keyword in keywords:
                if section_name in keyword.lower():
                    q = f"{project_name} {keyword} {q}"
                    break

    # ✅ DETECT GENERAL PROJECT OVERVIEW QUERIES
    is_general_project_overview = (
        re.search(r"tell\s+(?:me\s+)?about.*project", q, re.IGNORECASE) or
        re.search(r"about.*project\s*$", q, re.IGNORECASE) or
        (project_name and (q.endswith("project") or "project" in q and len(q.split()) < 6))
    )
    
    if is_general_project_overview and project_name:
        # ✅ FOR GENERAL PROJECT OVERVIEW: Include all key sections equally
        return f"{project_name} highlights amenities connectivity features specifications location"

    if re.fullmatch(r"(tell me about|about)?\s*(the\s+)?[a-z0-9\s]+ project", q) or q.endswith(" details"):
        return q + " overview project details amenities specifications location status unit type floors approvals"

    if "amenities" in q:
        return q + " amenities facilities features"

    if "specification" in q or "specifications" in q:
        return q + " specifications specs technical details"
    
    additions: List[str] = []

    if "floor plan" in q or "layout" in q:
        additions += [
            "floor plan",
            "layout",
            "basement ground floor first floor typical floor plan unit plan terrace plan",
        ]

    if mode == "investment":
        additions += [
            "investment potential",
            "rental income",
            "appreciation",
            "location advantages",
            "rera approvals",
        ]
    elif mode == "buying":
        additions += [
            "buying process",
            "documentation",
            "legal approvals",
            "bank approval",
            "rera",
            "financing",
        ]
    elif mode == "comparison":
        additions += [
            "amenities",
            "location",
            "approvals",
            "project details",
            "comparison",
        ]
    elif mode == "general":
        additions += ["project details", "location", "amenities", "highlights"]

    if "location" in q or "address" in q:
        additions += ["connectivity", "near airport road mangalore"]

    if additions:
        q = q + " " + " ".join(additions)

    return q.strip()


DOCUMENTS = [build_search_text(c) for c in chunks]
TOKENIZED_CORPUS = [tokenize(doc) for doc in DOCUMENTS]
bm25 = BM25Okapi(TOKENIZED_CORPUS)



def looks_contact_heavy(chunk: Dict[str, Any]) -> bool:
    text = build_search_text(chunk).lower()
    phone_hits = len(re.findall(r"\+?\d[\d\s\-()]{8,}", text))
    email_hits = len(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text))
    keywords = sum(1 for w in ["contact us", "phone", "email", "office address"] if w in text)
    return phone_hits > 0 or email_hits > 0 or keywords >= 2



def metadata_penalty(chunk: Dict[str, Any], query_mode: str, query: str = "") -> float:
    penalty = 0.0
    page_type = chunk.get("page_type", "")
    content_len = len((chunk.get("content", "") or "").split())

    if page_type in NOISY_PAGE_TYPES:
        penalty += 0.45

    if query_mode != "contact" and looks_contact_heavy(chunk):
        penalty += 0.40

    if page_type == "general" and content_len > 250:
        penalty += 0.18

    # ✅ ADD THIS BLOCK (project filtering)
    project_name = detect_project_name_from_query(query)
    if project_name:
        searchable = build_search_text(chunk).lower()
        if project_name not in searchable:
            penalty += 0.60

    return penalty



def heuristic_boost(query: str, chunk: Dict[str, Any]) -> float:
    terms = extract_salient_terms(query)
    if not terms:
        return 0.0

    title = normalize_text(chunk.get("title", ""))
    section = normalize_text(chunk.get("section_title", chunk.get("section", "")))
    content = normalize_text(chunk.get("content", ""))
    url = normalize_text(chunk.get("url", ""))

    boost = 0.0
    
    # ✅ EXTRACT PROJECT + SECTION FROM QUERY
    project_name = detect_project_name_from_query(query)
    section_name = detect_section_from_query(query)
    
    # ✅ DETECT GENERAL PROJECT OVERVIEW QUERY
    is_general_overview = (
        re.search(r"tell\s+(?:me\s+)?about.*project", query, re.IGNORECASE) or
        re.search(r"about.*project\s*$", query, re.IGNORECASE) or
        (project_name and query.lower().endswith("project"))
    )
    
    # ✅ FOR GENERAL PROJECT OVERVIEW: Boost key sections
    if is_general_overview and project_name:
        project_norm = normalize_text(project_name)
        if project_norm in title:
            # Boost highlights, amenities, connectivity sections - HIGHEST PRIORITY
            if "highlight" in section or "feature" in section:
                boost += 2.50  # ✅ HIGHEST priority for highlights
            elif "amenit" in section or "facilit" in section:
                boost += 2.40  # ✅ HIGHEST priority for amenities
            elif "connectiv" in section or "proximat" in section or "nearby" in section:
                boost += 2.30  # ✅ HIGHEST priority for connectivity
            elif "specification" in section or "spec" in section:
                boost += 1.80
            elif "location" in section or "address" in section:
                boost += 1.70
            elif "faq" in section or "overview" in section:
                boost += 0.80  # Lower priority for FAQ/overview
            else:
                # Penalize loan/contact sections for general queries
                if is_loan_section(chunk):
                    boost -= 2.00  # Strong penalty for loan sections
    
    # ✅ PROJECT+SECTION MATCHING - HIGHEST PRIORITY (when specific section asked)
    elif project_name and section_name:
        project_norm = normalize_text(project_name)
        
        # If chunk title matches project
        if project_norm in title or project_norm in section:
            boost += 0.50
            
            # If section also matches what user asked for
            for keywords in KEY_SECTIONS.values():
                for keyword in keywords:
                    if section_name in keyword.lower():
                        if keyword in section:
                            boost += 1.50  # MASSIVE boost for exact section match
                        break
    
    for term in terms:
        if term in title:
            boost += 0.30
        if term in section:
            boost += 0.22
        if term in url:
            boost += 0.20
        if term in content:
            boost += 0.06

    q = normalize_text(query)
    if "amenities" in q:
        if "amenit" in section:
            boost += 1.20
        if "amenit" in content:
            boost += 0.55
        if "specification" in section:
            boost += 0.70
    
    # ✅ HIGHLIGHTS SECTION BOOST
    if "highlights" in q:
        if "highlight" in section:
            boost += 1.20
        if "highlight" in content:
            boost += 0.55
        if "overview" in section:
            boost += 0.70
            
    # ✅ CONNECTIVITY SECTION BOOST
    if "connectivity" in q or "nearby" in q or "distance" in q:
        if "connectivity" in section or "nearby" in section or "distance" in section:
            boost += 1.20
        if "connectivity" in content or "nearby" in content:
            boost += 0.55
            
    if "tell me about" in q or q.endswith("project") or "project details" in q:
        if "overview" in section or "project snapshot" in section or "full content" in section or "highlights" in section:
            boost += 0.55

    if "specification" in q or "specifications" in q:
        if "specification" in section:
            boost += 1.20
        if "specification" in content:
            boost += 0.55
        if "amenit" in section:
            boost += 0.70
    if ("floor plan" in q or "layout" in q) and ("floor plan" in section or "layout" in section or "floor plan" in content):
        boost += 0.38
    if ("location" in q or "address" in q or "connectivity" in q) and (
        "location" in section or "connectivity" in section or "address" in content
    ):
        boost += 0.30
    if chunk.get("page_type", "") == "project":
        boost += 0.20
    elif chunk.get("page_type", "") in {"listing", "blog", "careers"}:
        boost += 0.05
    
    return boost

    return boost



def should_keep_chunk(chunk: Dict[str, Any], query_mode: str) -> bool:
    content = clean_text(chunk.get("content", ""))
    if not content:
        return False
    if query_mode != "contact" and chunk.get("page_type") in NOISY_PAGE_TYPES:
        return False
    return True

def vector_search(query: str, limit: int = VECTOR_LIMIT) -> List[Dict[str, Any]]:
    query_vector = embed_model.encode(query).tolist()

    try:
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
        ).points

        # Convert to expected format
        docs: List[Dict[str, Any]] = []
        for point in results:
            payload = point.payload or {}
            docs.append({
                "id": payload.get("id", ""),
                "title": payload.get("title", ""),
                "section_title": payload.get("section_title", payload.get("section", "")),
                "page_type": payload.get("page_type", ""),
                "content": payload.get("content", ""),
                "url": payload.get("url", ""),
                "_vector_score": float(point.score) if hasattr(point, "score") and point.score is not None else 0.0,
                "source_type": "vector",
            })
        return docs

    except Exception as e:
        print(f"❌ Vector search error: {e}")
        return []   # Safe fallback



def bm25_search(query: str, limit: int = BM25_LIMIT) -> List[Dict[str, Any]]:
    scores = bm25.get_scores(tokenize(query))
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:limit]

    docs: List[Dict[str, Any]] = []
    for idx in ranked_indices:
        c = chunks[idx]
        docs.append({
            "id": c.get("id", ""),
            "title": c.get("title", ""),
            "section_title": c.get("section_title", c.get("section", "")),
            "page_type": c.get("page_type", ""),
            "content": c.get("content", ""),
            "url": c.get("url", ""),
            "_bm25_score": float(scores[idx]),
            "source_type": "bm25",
        })
    return docs



def merge_results(vector_docs: List[Dict[str, Any]], bm25_docs: List[Dict[str, Any]], query_mode: str) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}

    for d in vector_docs + bm25_docs:
        doc_id = d.get("id") or f"{d.get('url', '')}|{d.get('section_title', '')}|{hash(d.get('content', ''))}"
        if doc_id not in merged:
            merged[doc_id] = d
        else:
            merged[doc_id]["_vector_score"] = max(merged[doc_id].get("_vector_score", 0.0), d.get("_vector_score", 0.0))
            merged[doc_id]["_bm25_score"] = max(merged[doc_id].get("_bm25_score", 0.0), d.get("_bm25_score", 0.0))

    results = [d for d in merged.values() if should_keep_chunk(d, query_mode)]
    return results



def rerank(query: str, docs: List[Dict[str, Any]], top_k: int = TOP_K_DEFAULT) -> List[Dict[str, Any]]:
    if not docs:
        return []

    mode = detect_query_mode(query)
    pairs = []
    for d in docs:
        section = d.get("section_title", d.get("section", ""))
        text = f"""Title: {d.get('title', '')}
Section: {section}
Page Type: {d.get('page_type', '')}

Content:
{d.get('content', '')}

Source:
{d.get('url', '')}"""
        pairs.append((query, text))

    rerank_scores = reranker.predict(pairs)

    rescored: List[Dict[str, Any]] = []
    for score, doc in zip(rerank_scores, docs):
        boost = heuristic_boost(query, doc)
        penalty = metadata_penalty(doc, mode, query)
        final_score = float(score) + boost - penalty
        doc["_rerank_score"] = float(score)
        doc["_heuristic_boost"] = boost
        doc["_penalty"] = penalty
        doc["_final_score"] = final_score
        rescored.append(doc)

    rescored.sort(key=lambda x: x["_final_score"], reverse=True)

    seen = set()
    deduped = []
    for doc in rescored:
        key = (doc.get("url", ""), doc.get("section_title", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(doc)
        if len(deduped) >= top_k:
            break

    return deduped



def is_retrieval_good_enough(query: str, docs: List[Dict[str, Any]]) -> bool:
    if not docs:
        return False

    top = docs[0]
    score = top.get("_final_score", -999)
    mode = detect_query_mode(query)

    if mode in {"investment", "comparison", "buying"}:
        return score >= 0.20
    return score >= 0.10


def prioritize_project_section_matches(query: str, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    ✅ Reorder results to prioritize chunks from queried project + section
    This ensures that when user asks "What are amenities of Altura?",
    we return the "Altura" + "Amenities" chunk first
    """
    project_name = detect_project_name_from_query(query)
    section_name = detect_section_from_query(query)
    
    if not project_name and not section_name:
        return docs
    
    project_norm = normalize_text(project_name) if project_name else ""
    section_keywords = []
    if section_name:
        for keywords in KEY_SECTIONS.values():
            for keyword in keywords:
                if section_name in keyword.lower():
                    section_keywords = keywords
                    break
    
    # Sort docs: prioritize project+section matches
    def score_priority(doc: Dict[str, Any]) -> tuple:
        title_norm = normalize_text(doc.get("title", ""))
        section_norm = normalize_text(doc.get("section_title", doc.get("section", "")))
        
        # Priority 1: Exact project + exact section match (score: 0)
        if project_name and section_keywords:
            if project_norm in title_norm:
                for kw in section_keywords:
                    if kw in section_norm:
                        return (0, doc.get("_final_score", 0))
        
        # Priority 2: Exact project match (score: 1)
        if project_name and project_norm in title_norm:
            return (1, doc.get("_final_score", 0))
        
        # Priority 3: Section match only (score: 2)
        if section_keywords:
            for kw in section_keywords:
                if kw in section_norm:
                    return (2, doc.get("_final_score", 0))
        
        # Priority 4: General match (score: 3)
        return (3, doc.get("_final_score", 0))
    
    docs_sorted = sorted(docs, key=score_priority)
    return docs_sorted



def retrieve(query: str, top_k: int = TOP_K_DEFAULT) -> List[Dict[str, Any]]:
    mode = detect_query_mode(query)
    expanded_query = expand_query(query, mode)

    vector_docs = vector_search(expanded_query, limit=VECTOR_LIMIT)
    bm25_docs = bm25_search(expanded_query, limit=BM25_LIMIT)

    merged_docs = merge_results(vector_docs, bm25_docs, mode)
    final_docs = rerank(query, merged_docs, top_k=top_k)
    
    # ✅ PRIORITIZE PROJECT+SECTION MATCHES BEFORE FINAL SELECTION
    final_docs = prioritize_project_section_matches(query, final_docs)
    
    # ✅ FILTER OUT LOAN SECTIONS FOR NON-LOAN QUERIES
    if not is_loan_query(query):
        final_docs = [doc for doc in final_docs if not is_loan_section(doc)]

    if not is_retrieval_good_enough(query, final_docs):
        return []

    return final_docs
