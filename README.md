# Land Trades Real Estate AI Assistant

A full-stack RAG (Retrieval Augmented Generation) chatbot for Land Trades real estate projects in Mangalore, powered by LLM and vector search.

---

## 🏗️ System Architecture

```
Data Pipeline → Vector DB → Retrieval → LLM → API → Frontend
```

---

## 📊 Complete Data Flow

### 1. **Data Extraction** 
**File:** `scrape_perfect.py`
- Scrapes project details from **landtrades.in**
- Extracts: amenities, specifications, location, RERA approval, booking info, etc.
- Output: `landtrades_projects_extracted.json`

### 2. **Data Cleanup & Correction**
**Manual Step:** Edit output from extraction
- Fix inconsistencies and missing data
- Add project details manually if needed
- Output: `landtrades_projects_structured_updated.json`

### 3. **Image Source Preparation**
**File:** `project_image_sources_with_categories.json` (manual preparation)
- Lists floor plans, gallery images, etc. with URLs
- Categorized by project and image type
- Input for next step

### 4. **Image Download** 
**File:** `download_project_images.py`
- Downloads images from URLs in `project_image_sources_with_categories.json`
- Organizes into folders: `real-estate-ai/public/project_images/{project_name}/`
- Output: `project_images.json` (image metadata)
- **Note:** Images are auto-displayed (2 gallery images) in chat

### 5. **Data Chunking** 
**File:** `final_structure_and_chunk.py`
- Combines:
  - Project data from `landtrades_projects_structured_updated.json`
  - Company info from `knowledge_base_clean.json`(extracted through extract_and_structure_updated.py)
  - Dummy real estate Q&A from `dummy_real_estate.json`
- Chunks large content into small, searchable pieces
- Removes noise and irrelevant sections
- Output: `structured_chunks.json` (523 chunks)

### 6. **Embedding & Vector Storage**
**File:** `embed_and_store.py`
- Generates embeddings using: `BAAI/bge-base-en-v1.5`
- Stores vectors in **Qdrant Cloud**
- Uses batch uploads (50 vectors per batch, avoids timeout)
- Output: 523 vectors in Qdrant

---

## 🔍 Query Processing Pipeline

### 7. **Retrieval** 
**File:** `retriever.py`
- **Hybrid Search:** Vector + BM25 ranking
- Expands queries (e.g., "amenities" → "amenities facilities features")
- Boosts project-specific sections
- Reranks using CrossEncoder (`BAAI/bge-reranker-base`)
- Returns top 6 most relevant chunks

### 8. **RAG Pipeline** 
**File:** `rag_pipeline.py`
- Detects project name from user query
- Carries context across multi-turn conversations
- Handles special queries: loans, floor plans, images
- Routes to appropriate response generator
- Key features:
  - **Project Detection:** Auto-detects project from query
  - **Context Carrying:** Remembers project across turns
  - **Query Types:** General, Loan, Investment, Amenities, Specifications
  - **Image Integration:** Retrieves and displays project images
  - **Follow-up Support:** Understands "show floor plans" in context

### 9. **LLM Answer Generation**
**File:** `rag_pipeline.py` → Groq API
- Model: `llama-3.3-70b-versatile`
- Generates answers using only provided context
- No hallucination of data from other projects
- Includes: amenities, specs, investment ROI, loan details, connectivity

### 10. **API Server**
**File:** `api.py` (FastAPI)
- **Endpoint:** `POST /query`
- Input: `{query, session_id}`
- Output: `{answer, sources, images, session_id}`
- Session persistence (defaultdict)
- CORS enabled

### 11. **Frontend**
**Folder:** `real-estate-ai/`
- **Framework:** React + Vite + TailwindCSS
- **Features:**
  - Chat interface with markdown support
  - Voice input (Web Speech API)
  - Image modal with zoom/drag
  - 2 auto-displayed gallery images + View More button
  - 4-image limit with collapsible gallery
  - Right-side project images (Altitude, Sky Villa, Mahalaxmi)
  - Expanded text window for better readability
- **State:** localStorage for session persistence

---

## ⚙️ Setup & Running

### Prerequisites
```bash
Python 3.11+
Node.js 18+
```

### 1. Install Python Dependencies
```bash
cd cursor_01
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt
```

### 2. Set Groq API Key
```bash
$env:GROQ_API_KEY="Your_Groq_API_Key"
```

### 3. Run Backend (FastAPI)
```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```
- API runs on: `http://localhost:8000`
- Vector DB: Connected to Qdrant Cloud (no Docker needed)

### 4. Run Frontend (React)
```bash
cd real-estate-ai
npm install
npm run dev
```
- Frontend runs on: `http://localhost:5173`

---

## 📁 Key Files Reference

| File | Purpose |
|------|---------|
| `scrape_perfect.py` | Extract project data from website |
| `download_project_images.py` | Download images for projects |
| `final_structure_and_chunk.py` | Split data into searchable chunks |
| `embed_and_store.py` | Generate embeddings and store in Qdrant |
| `retriever.py` | Hybrid search (vector + BM25 + rerank) |
| `rag_pipeline.py` | Query processing, context, LLM calls |
| `api.py` | FastAPI REST endpoint |
| `project_links.py` | Project name detection and mapping |
| `intent_router.py` | Query intent classification |
| `structured_chunks.json` | Final knowledge base (523 chunks) |

---

## 🔗 Data Flow (Visual)

```
landtrades.in
    ↓
scrape_perfect.py
    ↓
landtrades_projects_extracted.json
    ↓ (manual cleanup)
landtrades_projects_structured_updated.json
    ↓ ← project_image_sources_with_categories.json
    ↓
final_structure_and_chunk.py
    ↓
structured_chunks.json (523 chunks)
    ↓
embed_and_store.py
    ↓
Qdrant Cloud (523 vectors)
    ↓
retriever.py (hybrid search)
    ↓
rag_pipeline.py (Groq LLM)
    ↓
api.py (FastAPI)
    ↓
Frontend (React + Vite)
```

---

## 💾 Vector Database

**Cloud Provider:** Qdrant AWS
- **URL:** `https://e7e5537b-3817-477c-a313-012c7ebe6e9d.us-west-2-0.aws.cloud.qdrant.io:6333`
- **Collection:** `landtrades_knowledge` (523 vectors)
- **Embedding Model:** BAAI/bge-base-en-v1.5 (768 dimensions)
- **Distance Metric:** Cosine similarity

---

## 🎯 Query Examples

1. **General Info**
   ```
   "Tell me about Altura project"
   ```
   → Full project overview with amenities, specs, investment details

2. **Specific Details**
   ```
   "What are the loan options for Altitude?"
   ```
   → Extracting loan/bank/EMI information

3. **Images**
   ```
   "Show floor plans of Altitude"
   ```
   → Retrieves and displays floor plan images with zoom/drag

4. **Context Carrying**
   ```
   "Tell me about Altura"
   "Show floor plans"  ← Remembers Altura from previous message
   ```
   → Answers refer to previously mentioned project

---

## 🚀 Optimization Features

✅ **Fast Retrieval**
- Hybrid search (vector + BM25)
- Cross-encoder reranking
- Batch processing for uploads

✅ **Context Preservation**
- Multi-turn conversation memory
- Project context across turns
- Session persistence

✅ **Smart Chunking**
- Project-specific sections
- Noise removal
- Semantic boundaries

✅ **Image Integration**
- Auto-display 2 gallery images
- Collapsible gallery (max 4)
- Zoom/drag image viewer

---

## 📝 Configuration

### Environment Variables
```bash
GROQ_API_KEY=your_groq_api_key
```

### Qdrant Cloud Credentials (in code)
- URL: `https://e7e5537b-3817-477c-a313-012c7ebe6e9d.us-west-2-0.aws.cloud.qdrant.io:6333`
- API Key: Embedded in `retriever.py` and `embed_and_store.py`

---

## 📤 Re-Embedding Data (If Updated)

If you modify project data and want to re-embed:

```bash
# Update your project data
# Edit: landtrades_projects_structured_updated.json

# Run chunking
python final_structure_and_chunk.py

# Re-embed and upload to Qdrant
python embed_and_store.py
```

---

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| Groq API 403 Error | Set valid GROQ_API_KEY environment variable |
| Qdrant Connection Failed | Check cloud credentials in retriever.py |
| Images not displaying | Ensure download_project_images.py was run |
| Slow responses | Already optimized (batch processing, caching) |
| Project not recognized | Check project name in project_links.py |

---

## 📚 Tech Stack

**Backend:**
- FastAPI (REST API)
- Groq LLM (llama-3.3-70b)
- Qdrant (Vector Database)
- SentenceTransformers (Embeddings & Reranking)
- BM25 (Keyword Search)

**Frontend:**
- React 18 + Vite
- TailwindCSS
- React Markdown
- Web Speech API (Voice)

**Data Processing:**
- BeautifulSoup (Web Scraping)
- Requests (HTTP)
- Pandas (Data manipulation)

---

## 📄 License

Internal - Land Trades AI Project

---

**Created:** March 2026
**Last Updated:** March 30, 2026
