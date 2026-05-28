#!/usr/bin/env python3
"""
Quick Test Script untuk RAG Improvements

Jalankan tanpa pytest:
    source .venv/bin/activate
    python tests/quick_test.py
"""

import sys

sys.path.insert(0, "/home/imaji/smart-ai/smart-ai-dev/agent-service")

print("=" * 70)
print("  QUICK TEST: RAG Improvements - Fase 1")
print("=" * 70)
print()

# Test 1: Import check
print("1. Testing imports...")
try:
    from app.llm.rag import query_engine, response_synthesizer, qa_system_prompt, agent

    print("   ✅ All imports successful")
except Exception as e:
    print(f"   ❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Similarity cutoff
print("\n2. Testing similarity cutoff...")
try:
    postprocessors = query_engine._node_postprocessors
    for p in postprocessors:
        if hasattr(p, "_similarity_cutoff"):
            cutoff = p._similarity_cutoff
            if cutoff == 0.4:
                print(f"   ✅ Similarity cutoff correctly set to 0.4")
            else:
                print(f"   ❌ Expected 0.4, got {cutoff}")
            break
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: Response mode
print("\n3. Testing response mode...")
try:
    mode = response_synthesizer._response_mode
    if mode == "refine":
        print(f"   ✅ Response mode is 'refine' (not compact)")
    else:
        print(f"   ❌ Expected 'refine', got '{mode}'")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 4: Reranking
print("\n4. Testing reranking...")
try:
    from llama_index.postprocessor.flag_embedding_reranker import FlagEmbeddingReranker

    rerankers = [p for p in postprocessors if isinstance(p, FlagEmbeddingReranker)]
    if rerankers:
        print(f"   ✅ Reranking enabled with BGE reranker")
        print(f"      Model: {rerankers[0].model_name}")
    else:
        print(f"   ❌ Reranker not found")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 5: Prompt improvements
print("\n5. Testing prompt improvements...")
prompt_checks = {
    "Source citation": "cite" in qa_system_prompt.lower()
    or "sumber" in qa_system_prompt.lower(),
    "Detailed instruction": "detailed" in qa_system_prompt.lower(),
    "Language instruction": "same language" in qa_system_prompt.lower(),
    "IDK instruction": "knowledge base" in qa_system_prompt.lower(),
}

all_passed = True
for check, passed in prompt_checks.items():
    if passed:
        print(f"   ✅ {check}: Present")
    else:
        print(f"   ❌ {check}: Missing")
        all_passed = False

# Test 6: Agent system prompt
print("\n6. Testing agent system prompt...")
try:
    agent_prompt = agent._system_prompt.lower()
    if "tool selection guide" in agent_prompt:
        print(f"   ✅ Tool selection guide present")
    else:
        print(f"   ❌ Tool selection guide missing")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 7: Incident RAG
print("\n7. Testing incident RAG...")
try:
    from app.llm.incident_rag import query_incidents, IncidentRAG

    print(f"   ✅ Incident RAG imports successful")

    # Check query function exists
    if callable(query_incidents):
        print(f"   ✅ query_incidents is callable")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("=" * 70)
print("  All basic checks completed!")
print("=" * 70)
print()
print("Note: For full integration tests, run:")
print("  python -m pytest tests/test_rag_improvements.py -v")
print()
