#embed_and_store.py
import json
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

COLLECTION_NAME = "landtrades_knowledge"

print("Loading embedding model...")
model = SentenceTransformer("BAAI/bge-base-en-v1.5")
print("Connecting to Qdrant Cloud...")
client = QdrantClient(
    url="https://e7e5537b-3817-477c-a313-012c7ebe6e9d.us-west-2-0.aws.cloud.qdrant.io:6333",
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.KFCt0UqJvRGplUZ9LcpCHZ3ZlGx-jsiOxKNnVkerhhk",
)

print("Loading chunks...")
with open("structured_chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

print(f"Total chunks: {len(chunks)}")

# Create collection
print("Creating collection...")

collection_name = COLLECTION_NAME

# Delete only if it exists
if client.collection_exists(collection_name):
    client.delete_collection(collection_name)

# Small delay helps on Windows (file lock issues)
import time
time.sleep(1)

# Create fresh collection
client.create_collection(
    collection_name=collection_name,
    vectors_config=VectorParams(
        size=768,
        distance=Distance.COSINE
    )
)

points = []

print("Generating embeddings...")

for i, chunk in enumerate(tqdm(chunks)):

    text = chunk["content"]

    embedding = model.encode(text).tolist()

    payload = {
        "title": chunk["title"],
        "section": chunk["section_title"],
        "page_type": chunk["page_type"],
        "url": chunk["url"],
        "content": chunk["content"]
    }

    points.append(
        PointStruct(
            id=i,
            vector=embedding,
            payload=payload
        )
    )

# Upload to Qdrant in batches (avoids timeout)
print("Uploading vectors to Qdrant Cloud (batching)...")

batch_size = 50
for i in range(0, len(points), batch_size):
    batch = points[i:i+batch_size]
    try:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=batch,
            wait=True
        )
        print(f"✅ Uploaded batch {i//batch_size + 1}/{(len(points)-1)//batch_size + 1} ({len(batch)} vectors)")
    except Exception as e:
        print(f"❌ Batch upload failed: {e}")
        print(f"   Retrying batch {i//batch_size + 1}...")
        try:
            import time
            time.sleep(2)
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=batch,
                wait=True
            )
            print(f"✅ Retry successful for batch {i//batch_size + 1}")
        except Exception as e2:
            print(f"❌ Retry failed: {e2}")

print("✅ Embedding pipeline completed.")
print(f"Stored {len(points)} vectors in Qdrant Cloud.")
