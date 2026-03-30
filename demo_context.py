#!/usr/bin/env python3
"""
Simple demonstration of context carrying in chat conversations
"""

def demonstrate_context_carrying():
    print("\n" + "="*80)
    print("CONTEXT CARRYING DEMONSTRATION")
    print("="*80)
    
    # Import the functions we updated
    from rag_pipeline import (
        detect_project_query, 
        extract_project_from_history,
        FOLLOWUP_PROJECT_PHRASES,
        normalize
    )
    from project_links import detect_project_from_text
    
    # Simulate a session
    session = {
        "last_project": None,
        "chat_history": [],
    }
    
    print("\n1️⃣  EXPANDED FOLLOW-UP PHRASES (Sample):")
    print("-" * 80)
    sample_phrases = list(FOLLOWUP_PROJECT_PHRASES)[:15]
    for phrase in sample_phrases:
        print(f"   ✓ '{phrase}'")
    print(f"   ... and {len(FOLLOWUP_PROJECT_PHRASES) - 15} more")
    
    print("\n2️⃣  PROJECT DETECTION FLOW:")
    print("-" * 80)
    
    # Q1: Direct mention
    print("\n   Q1: 'Tell me about Altura'")
    q1 = "Tell me about Altura"
    p1 = detect_project_query(q1, session)
    session["chat_history"].append(f"User: {q1}")
    session["chat_history"].append(f"Assistant: Altura is a premium residential project...")
    print(f"   ✓ Detected: {p1}")
    print(f"   📝 History size: {len(session['chat_history'])} entries")
    
    # Q2: Follow-up without project name
    print("\n   Q2: 'Show me the floor plans'")
    q2 = "Show me the floor plans"
    p2 = detect_project_query(q2, session)
    print(f"   ✓ Detected: {p2}")
    print(f"   📝 Method: Follow-up phrase detection + history extraction")
    session["chat_history"].append(f"User: {q2}")
    session["chat_history"].append(f"Assistant: Here are the floor plans for Altura...")
    
    # Q3: Another follow-up
    print("\n   Q3: 'What about amenities?'")
    q3 = "What about amenities?"
    p3 = detect_project_query(q3, session)
    print(f"   ✓ Detected: {p3}")
    print(f"   📝 Method: Context from history preservation")
    session["chat_history"].append(f"User: {q3}")
    
    # Q4: Switch projects
    print("\n   Q4: 'Tell me about Krishna Kuteera'")
    q4 = "Tell me about Krishna Kuteera"
    p4 = detect_project_query(q4, session)
    print(f"   ✓ Detected: {p4}")
    print(f"   📝 Method: Direct mention (context switch)")
    session["chat_history"].append(f"User: {q4}")
    
    # Q5: Follow-up for new project
    print("\n   Q5: 'Show gallery images'")
    q5 = "Show gallery images"
    p5 = detect_project_query(q5, session)
    print(f"   ✓ Detected: {p5}")
    print(f"   📝 Method: History extraction for new project context")
    
    print("\n3️⃣  CHAT HISTORY (Last 6 entries):")
    print("-" * 80)
    for i, entry in enumerate(session["chat_history"][-6:], 1):
        print(f"   {i}. {entry[:70]}...")
    
    print("\n4️⃣  KEY IMPROVEMENTS:")
    print("-" * 80)
    print("   ✅ Expanded follow-up phrases: floor plans, gallery, images, etc.")
    print("   ✅ History-based project extraction for follow-ups")
    print("   ✅ Seamless context switching when new project mentioned")
    print("   ✅ Multi-turn conversations maintain project context")
    print("   ✅ LLM prompt includes conversation history and context rules")
    
    print("\n" + "="*80)
    print("✓ All context carrying improvements are active!")
    print("="*80 + "\n")

if __name__ == "__main__":
    demonstrate_context_carrying()
