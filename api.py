#api.py
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uuid

from rag_pipeline import generate_answer

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str
    session_id: str | None = None


@app.post("/query")
async def query_bot(request: QueryRequest):
    session_id = request.session_id or str(uuid.uuid4())

    result = generate_answer(request.query, session_id=session_id)

    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "images": result.get("images", []),
        "session_id": session_id,
    }