"""
Incident RAG Integration
Mengintegrasikan incident documents ke dalam sistem RAG yang sudah ada
"""

from pathlib import Path
from typing import List, Optional
from llama_index.core import Document, VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.tools import FunctionTool, QueryEngineTool, ToolMetadata
import chromadb

from app.config import Config
from app.llm.incident_loader import load_incident_documents


class IncidentRAG:
    """RAG system khusus untuk incident data"""

    def __init__(self):
        self.db_path = str(Config.dir / "storages" / "chroma_db")
        self.collection_name = "incident_rag"
        self.index = None
        self.query_engine = None
        self.documents = []

    def load_and_index(self, csv_path: Optional[Path] = None) -> bool:
        """
        Load incident CSV dan buat index

        Returns:
            bool: True jika berhasil
        """
        try:
            # Load documents
            self.documents = load_incident_documents(csv_path)

            if not self.documents:
                print("[WARNING] No incident documents to index")
                return False

            # Parse ke nodes dengan sentence splitter
            # (lebih baik untuk data incident yang struktural)
            # ✅ CHANGED: Smaller chunk size for more granular retrieval
            parser = SentenceSplitter(chunk_size=256, chunk_overlap=32)
            nodes = parser.get_nodes_from_documents(self.documents)

            print(
                f"[INFO] Created {len(nodes)} nodes from {len(self.documents)} incidents"
            )

            # Setup ChromaDB untuk incident collection
            chroma_client = chromadb.PersistentClient(path=self.db_path)

            # Cek apakah collection sudah ada
            existing_collections = chroma_client.list_collections()
            collection_exists = any(
                col.name == self.collection_name for col in existing_collections
            )

            if collection_exists:
                print(
                    f"[INFO] Loading existing incident collection: {self.collection_name}"
                )
                chroma_collection = chroma_client.get_collection(self.collection_name)
                vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
                storage_context = StorageContext.from_defaults(
                    vector_store=vector_store
                )
                self.index = VectorStoreIndex.from_vector_store(
                    vector_store, storage_context=storage_context
                )
            else:
                print(
                    f"[INFO] Creating new incident collection: {self.collection_name}"
                )
                chroma_collection = chroma_client.create_collection(
                    self.collection_name
                )
                vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
                storage_context = StorageContext.from_defaults(
                    vector_store=vector_store
                )
                self.index = VectorStoreIndex(
                    nodes=nodes, storage_context=storage_context, show_progress=True
                )

            # Setup query engine
            self._setup_query_engine(nodes)

            return True

        except Exception as e:
            print(f"[ERROR] Failed to load and index incidents: {e}")
            return False

    def _setup_query_engine(self, nodes):
        """Setup query engine dengan hybrid retrieval"""
        # Vector retriever - ✅ INCREASED top_k for better coverage
        vector_retriever = VectorIndexRetriever(index=self.index, similarity_top_k=8)

        # BM25 retriever untuk keyword matching - ✅ INCREASED top_k
        bm25_retriever = BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=8)

        # Gabungkan dengan hybrid
        from app.llm.rag import HybridRetriever

        hybrid_retriever = HybridRetriever(vector_retriever, bm25_retriever)

        # ✅ ADDED: Re-ranking for better relevance
        from llama_index.postprocessor.flag_embedding_reranker import (
            FlagEmbeddingReranker,
        )

        bge_rerank = FlagEmbeddingReranker(model="BAAI/bge-reranker-v2-m3", top_n=5)

        # Query engine - ✅ CHANGED: More permissive cutoff + reranking
        self.query_engine = RetrieverQueryEngine.from_args(
            retriever=hybrid_retriever,
            node_postprocessors=[
                SimilarityPostprocessor(similarity_cutoff=0.4),  # More permissive
                bge_rerank,  # Re-rank for better results
            ],
        )

    def query(self, question: str) -> str:
        """
        Query incident database

        Args:
            question: Pertanyaan tentang issue/solusi

        Returns:
            str: Jawaban dengan solusi dari incident history
        """
        if not self.query_engine:
            return "Error: Incident database not initialized"

        try:
            response = self.query_engine.query(question)
            return str(response)
        except Exception as e:
            print(f"[ERROR] Query failed: {e}")
            return f"Error querying incident database: {str(e)}"

    def get_tool(self) -> FunctionTool:
        """
        Get incident lookup tool untuk ReActAgent

        Returns:
            FunctionTool: Tool yang bisa digunakan oleh agent
        """

        def incident_lookup(issue_description: str) -> str:
            """
            Cari solusi dari incident history berdasarkan deskripsi masalah.

            Gunakan tool ini ketika user menanyakan:
            - Solusi untuk masalah teknis (commloss, sensor spike, etc.)
            - Root cause dari suatu issue
            - Action yang perlu diambil
            - Incident yang serupa

            Args:
                issue_description: Deskripsi masalah/issue

            Returns:
                Solusi berdasarkan incident history
            """
            return self.query(issue_description)

        return FunctionTool.from_defaults(
            fn=incident_lookup,
            name="incident_lookup",
            description=(
                "Search incident history for solutions to technical problems. "
                "Use this when user asks about: solving issues, commloss problems, "
                "sensor spikes, UPS failures, or any technical troubleshooting. "
                "Provides root cause analysis and corrective actions from past incidents."
            ),
        )


# Singleton instance
_incident_rag = None


def get_incident_rag() -> IncidentRAG:
    """Get or create IncidentRAG singleton"""
    global _incident_rag
    if _incident_rag is None:
        _incident_rag = IncidentRAG()
    return _incident_rag


def initialize_incident_rag(csv_path: Optional[Path] = None) -> bool:
    """
    Initialize incident RAG system

    Returns:
        bool: True jika berhasil diinisialisasi
    """
    rag = get_incident_rag()
    return rag.load_and_index(csv_path)


def query_incidents(issue_description: str) -> str:
    """
    Query incident database untuk mencari solusi.

    Fungsi ini di-export untuk digunakan oleh rag.py

    Args:
        issue_description: Deskripsi masalah/issue

    Returns:
        Solusi berdasarkan incident history
    """
    global _incident_rag

    # Initialize jika belum
    if _incident_rag is None:
        _incident_rag = IncidentRAG()
        success = _incident_rag.load_and_index()
        if not success:
            return "Error: Failed to initialize incident database"

    return _incident_rag.query(issue_description)


if __name__ == "__main__":
    # Test
    print("[TEST] Initializing Incident RAG...")
    success = initialize_incident_rag()
    if success:
        print("[TEST] Incident RAG initialized successfully!")
        rag = get_incident_rag()

        # Test query
        test_queries = [
            "UPS failure how to solve?",
            "sensor spike issue",
            "commloss problem",
        ]

        for query in test_queries:
            print(f"\n[TEST] Query: {query}")
            response = rag.query(query)
            print(f"[TEST] Response: {response[:200]}...")
    else:
        print("[TEST] Failed to initialize Incident RAG")
