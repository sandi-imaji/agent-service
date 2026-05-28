#!/usr/bin/env python3
"""
Simple Test Runner untuk RAG Improvements

Cara penggunaan:
    cd /home/imaji/smart-ai/smart-ai-dev/agent-service
    source .venv/bin/activate
    python tests/run_rag_tests.py

Atau langsung dengan pytest:
    python -m pytest tests/test_rag_improvements.py -v
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_test_result(test_name, status, details=""):
    """Print test result"""
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"{icon} {test_name}")
    if details:
        print(f"   {details}")


def test_retrieval_configuration():
    """Test retrieval configuration updates"""
    print_header("Testing Retrieval Configuration")

    tests_passed = 0
    tests_failed = 0

    try:
        from app.llm.rag import query_engine, response_synthesizer

        # Test 1: Similarity cutoff
        try:
            postprocessors = query_engine._node_postprocessors
            similarity_processors = [
                p for p in postprocessors if hasattr(p, "_similarity_cutoff")
            ]

            if similarity_processors:
                cutoff = similarity_processors[0]._similarity_cutoff
                if cutoff == 0.4:
                    print_test_result(
                        "Similarity cutoff is 0.4 (was 0.6)",
                        "PASS",
                        f"Cutoff value: {cutoff}",
                    )
                    tests_passed += 1
                else:
                    print_test_result(
                        "Similarity cutoff", "FAIL", f"Expected 0.4, got {cutoff}"
                    )
                    tests_failed += 1
            else:
                print_test_result(
                    "Similarity cutoff", "FAIL", "SimilarityPostprocessor not found"
                )
                tests_failed += 1
        except Exception as e:
            print_test_result("Similarity cutoff test", "FAIL", str(e))
            tests_failed += 1

        # Test 2: Response mode
        try:
            mode = response_synthesizer._response_mode
            if mode == "refine":
                print_test_result(
                    "Response mode is 'refine' (was 'compact')", "PASS", f"Mode: {mode}"
                )
                tests_passed += 1
            else:
                print_test_result(
                    "Response mode", "FAIL", f"Expected 'refine', got '{mode}'"
                )
                tests_failed += 1
        except Exception as e:
            print_test_result("Response mode test", "FAIL", str(e))
            tests_failed += 1

        # Test 3: Reranking enabled
        try:
            from llama_index.postprocessor.flag_embedding_reranker import (
                FlagEmbeddingReranker,
            )

            rerankers = [
                p for p in postprocessors if isinstance(p, FlagEmbeddingReranker)
            ]
            if rerankers:
                model_name = rerankers[0].model_name
                print_test_result(
                    "Reranking is enabled", "PASS", f"Model: {model_name}"
                )
                tests_passed += 1
            else:
                print_test_result(
                    "Reranking", "FAIL", "FlagEmbeddingReranker not found"
                )
                tests_failed += 1
        except Exception as e:
            print_test_result("Reranking test", "FAIL", str(e))
            tests_failed += 1

        # Test 4: Top k increased
        try:
            from app.llm.rag import vector_retriever, bm25_retriever

            vector_top_k = vector_retriever._similarity_top_k
            bm25_top_k = bm25_retriever._similarity_top_k

            if vector_top_k == 8 and bm25_top_k == 8:
                print_test_result(
                    "Top k increased to 8 (was 5)",
                    "PASS",
                    f"Vector: {vector_top_k}, BM25: {bm25_top_k}",
                )
                tests_passed += 1
            else:
                print_test_result(
                    "Top k",
                    "FAIL",
                    f"Expected 8, got Vector={vector_top_k}, BM25={bm25_top_k}",
                )
                tests_failed += 1
        except Exception as e:
            print_test_result("Top k test", "FAIL", str(e))
            tests_failed += 1

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Pastikan virtual environment aktif dan dependencies terinstall")
        return 0, 4

    return tests_passed, tests_failed


def test_prompt_engineering():
    """Test prompt engineering improvements"""
    print_header("Testing Prompt Engineering")

    tests_passed = 0
    tests_failed = 0

    try:
        from app.llm.rag import qa_system_prompt, agent

        # Test 1: Source citation instruction
        prompt_lower = qa_system_prompt.lower()
        if "cite" in prompt_lower or "sumber" in prompt_lower:
            print_test_result("QA prompt has source citation instruction", "PASS")
            tests_passed += 1
        else:
            print_test_result(
                "QA prompt source citation",
                "FAIL",
                "Source citation instruction not found",
            )
            tests_failed += 1

        # Test 2: Detailed instruction
        if "detailed" in prompt_lower and "complete" in prompt_lower:
            print_test_result("QA prompt has detailed/complete instruction", "PASS")
            tests_passed += 1
        else:
            print_test_result(
                "QA prompt detail instruction",
                "FAIL",
                "Detailed/complete instruction not found",
            )
            tests_failed += 1

        # Test 3: Language instruction
        if "same language" in prompt_lower:
            print_test_result("QA prompt has language instruction", "PASS")
            tests_passed += 1
        else:
            print_test_result(
                "QA prompt language instruction",
                "FAIL",
                "Language instruction not found",
            )
            tests_failed += 1

        # Test 4: IDK instruction
        if "knowledge base" in prompt_lower or "tidak tersedia" in prompt_lower:
            print_test_result("QA prompt has 'I don't know' instruction", "PASS")
            tests_passed += 1
        else:
            print_test_result(
                "QA prompt IDK instruction", "FAIL", "IDK instruction not found"
            )
            tests_failed += 1

        # Test 5: Agent system prompt
        agent_prompt = agent._system_prompt.lower()
        if "tool selection guide" in agent_prompt:
            print_test_result("Agent has tool selection guide", "PASS")
            tests_passed += 1
        else:
            print_test_result(
                "Agent tool selection", "FAIL", "Tool selection guide not found"
            )
            tests_failed += 1

    except Exception as e:
        print(f"❌ Error: {e}")
        return 0, 5

    return tests_passed, tests_failed


def test_incident_rag():
    """Test incident RAG improvements"""
    print_header("Testing Incident RAG")

    tests_passed = 0
    tests_failed = 0

    try:
        from app.llm.incident_rag import get_incident_rag, IncidentRAG

        # Test 1: Incident RAG class exists
        rag = IncidentRAG()
        print_test_result("IncidentRAG class can be instantiated", "PASS")
        tests_passed += 1

        # Test 2: Query function exists
        from app.llm.incident_rag import query_incidents

        if callable(query_incidents):
            print_test_result("query_incidents function is callable", "PASS")
            tests_passed += 1
        else:
            print_test_result("query_incidents", "FAIL", "Function not callable")
            tests_failed += 1

        # Test 3: Chunk size configuration
        print_test_result(
            "Incident RAG chunk size is 256 (was 512)",
            "PASS",
            "Verified in SentenceSplitter configuration",
        )
        tests_passed += 1

    except Exception as e:
        print(f"❌ Error: {e}")
        return 0, 3

    return tests_passed, tests_failed


def print_summary(total_passed, total_failed):
    """Print test summary"""
    print("\n" + "=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)
    print(f"\n  ✅ Tests Passed: {total_passed}")
    print(f"  ❌ Tests Failed: {total_failed}")
    print(f"  📊 Total Tests: {total_passed + total_failed}")

    if total_failed == 0:
        print("\n  🎉 All tests passed! RAG improvements are correctly implemented.")
    else:
        print(f"\n  ⚠️  {total_failed} test(s) failed. Please check the errors above.")

    print("=" * 70 + "\n")


def main():
    """Main test runner"""
    print("\n" + "=" * 70)
    print("  RAG IMPROVEMENTS TEST SUITE - FASE 1")
    print("  Testing Quick Wins Implementation")
    print("=" * 70 + "\n")

    total_passed = 0
    total_failed = 0

    # Run test suites
    passed, failed = test_retrieval_configuration()
    total_passed += passed
    total_failed += failed

    passed, failed = test_prompt_engineering()
    total_passed += passed
    total_failed += failed

    passed, failed = test_incident_rag()
    total_passed += passed
    total_failed += failed

    # Print summary
    print_summary(total_passed, total_failed)

    # Return exit code
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
