import json

# Load structured chunks
with open('structured_chunks.json', 'r', encoding='utf-8') as f:
    chunks = json.load(f)

# Find Project 1 chunks
project1_chunks = [c for c in chunks if 'Land Trades Project 1' in c.get('title', '')]

print(f"Total chunks in knowledge base: {len(chunks)}")
print(f"Chunks for 'Land Trades Project 1': {len(project1_chunks)}\n")

if project1_chunks:
    print("=" * 80)
    print("PROJECT 1 INFORMATION IN KNOWLEDGE BASE:")
    print("=" * 80)
    for i, chunk in enumerate(project1_chunks[:10], 1):
        title = chunk.get('title', 'No Title')
        section = chunk.get('section_title', 'No Section')
        content_len = len(chunk.get('content', ''))
        url = chunk.get('url', 'No URL')
        content_preview = chunk.get('content', '')[:100]
        
        print(f"\n{i}. Title: {title}")
        print(f"   Section: {section}")
        print(f"   URL: {url}")
        print(f"   Content Length: {content_len} characters")
        print(f"   Preview: {content_preview}...")
else:
    print("❌ NO CHUNKS FOUND FOR PROJECT 1!")
    print("\nSample titles in database:")
    titles = set(c.get('title', '') for c in chunks[:50])
    for title in list(titles)[:10]:
        print(f"  - {title}")
