from app.llm.llm_client import analysis_point
from llama_index.llms.llama_cpp import LlamaCPP
from llama_index.core import (
    StorageContext,
    VectorStoreIndex,
    SimpleDirectoryReader,
    Settings,
    PromptTemplate,
    get_response_synthesizer,
)
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.postprocessor import (
    MetadataReplacementPostProcessor,
    SimilarityPostprocessor,
)
from llama_index.postprocessor.flag_embedding_reranker import FlagEmbeddingReranker
from llama_index.core.retrievers import VectorIndexRetriever, BaseRetriever
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.llms.openai_like import OpenAILike
from llama_index.core.tools import FunctionTool, QueryEngineTool, ToolMetadata
from llama_index.core.agent import ReActAgent  # Workflow version
import chromadb, requests, time, os
from app.modscan.diagnose import full_diagnostic_async_point, full_diagnostic, full_diagnostic_async
from pathlib import Path
from app.config import Config
from app.utils import get_tagname
from app.schemas import ModScanSchema
from app.llm.incident_rag import query_incidents

# --- Configuration ---
EMBED_NAME = "BAAI/bge-m3"
LLM_PATH = str(Config.dir / "storages" / "qwen2.5-3b-instruct-q4_k_m.gguf")
DB_PATH = str(Config.dir / "storages" / "chroma_db")
COLLECTION_NAME = "advanced_rag"


# --- Language Translation Helper ---
def translate_id_to_en(text: str, llm) -> str:
    """Translate Indonesian query to English for better retrieval"""
    translation_prompt = f"""<|im_start|>system
You are a translation assistant. Translate the following Indonesian text to English accurately. 
Only output the English translation, nothing else.<|im_end|>
<|im_start|>user
{text}<|im_end|>
<|im_start|>assistant
"""
    try:
        response = llm.complete(translation_prompt)
        translated = response.text.strip()
        print(f"[TRANSLATION] ID → EN: {text} → {translated}")
        return translated
    except Exception as e:
        print(f"[TRANSLATION ERROR] {e}, using original text")
        return text


def detect_language(text: str) -> str:
    """Simple language detection based on common Indonesian words"""
    indonesian_keywords = [
        "apa",
        "bagaimana",
        "mengapa",
        "kenapa",
        "dimana",
        "kapan",
        "siapa",
        "adalah",
        "yang",
        "untuk",
        "dari",
        "dengan",
        "pada",
        "ini",
        "itu",
        "saya",
        "kamu",
        "dia",
        "kami",
        "mereka",
        "bisa",
        "dapat",
        "akan",
        "sudah",
        "belum",
        "tidak",
        "ya",
        "atau",
        "dan",
        "jika",
        "kalau",
    ]

    text_lower = text.lower()
    indonesian_count = sum(
        1 for keyword in indonesian_keywords if keyword in text_lower
    )

    # If 2 or more Indonesian keywords found, assume Indonesian
    return "id" if indonesian_count >= 2 else "en"


# --- 1. Setup Models (LLM & Embedding) ---


def messages_to_prompt(messages):
    prompt = ""
    for message in messages:
        if message.role == "system":
            prompt += f"<|im_start|>system\n{message.content}<|im_end|>\n"
        elif message.role == "user":
            prompt += f"<|im_start|>user\n{message.content}<|im_end|>\n"
        elif message.role == "assistant":
            prompt += f"<|im_start|>assistant\n{message.content}<|im_end|>\n"

    # ensure we start with a system prompt, insert blank if needed
    if not prompt.startswith("<|im_start|>system"):
        prompt = "<|im_start|>system\n" + prompt

    # add final assistant prompt
    prompt = prompt + "<|im_start|>assistant\n"
    return prompt


def completion_to_prompt(completion):
    return f"<|im_start|>system\n<|im_end|>\n<|im_start|>user\n{completion}<|im_end|>\n<|im_start|>assistant\n"


# llm_model = LlamaCPP(
#     model_path=LLM_PATH,
#     temperature=0.1,
#     max_new_tokens=1024,
#     context_window=8192,
#     generate_kwargs={},
#     model_kwargs={"n_gpu_layers": 0, "verbose": False},
#     messages_to_prompt=messages_to_prompt,
#     completion_to_prompt=completion_to_prompt,
#     verbose=True,
# )
llm_model = OpenAILike(
    model="Qwen2.5-7B-Instruct-Q6_K.gguf",  # Nama model di server llama.cpp
    api_base="http://localhost:8080/v1",  # URL server llama.cpp-mu
    api_key="sk-no-key-required",  # Biasanya llama.cpp tidak butuh API key
    temperature=0.1,
    max_tokens=1024,
    messages_to_prompt=messages_to_prompt,
    completion_to_prompt=completion_to_prompt,
)

embed_model = HuggingFaceEmbedding(model_name=EMBED_NAME, device="cpu", normalize=True)

Settings.embed_model = embed_model
Settings.llm = llm_model
Settings.chunk_size = 512
Settings.chunk_overlap = 64

# --- 2. Database & Indexing ---

chroma_client = chromadb.PersistentClient(path=DB_PATH)
db_exists = Path(DB_PATH).exists() and any(Path(DB_PATH).iterdir())
input_dir = str(Config.dir / "storages" / "docs")

if db_exists:
    print("Loading existing vector database...")
    chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    vector_index = VectorStoreIndex.from_vector_store(
        vector_store, storage_context=storage_context
    )

    # Still need docs for BM25 since it's in-memory usually/needs rebuilding or separate persistence
    # optimized: try to see if we can skip full parse if just for BM25, but for safety lets reload
    documents = SimpleDirectoryReader(
        input_dir=input_dir, required_exts=[".md"], recursive=True
    ).load_data()
    splitter = MarkdownNodeParser()
    nodes = splitter.get_nodes_from_documents(documents)

else:
    print("Creating new vector database...")
    documents = SimpleDirectoryReader(
        input_dir=input_dir, required_exts=[".md"], recursive=True
    ).load_data()
    splitter = MarkdownNodeParser()
    nodes = splitter.get_nodes_from_documents(documents)

    chroma_collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    vector_index = VectorStoreIndex(
        nodes=nodes, storage_context=storage_context, show_progress=True
    )


# --- 3. Retrieval Components ---
# Using a reduced top_k to avoid flooding the context
vector_retriever = VectorIndexRetriever(index=vector_index, similarity_top_k=5)
# Re-index nodes for BM25 (will be fast if already in memory)
bm25_retriever = BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=5)


class HybridRetriever(BaseRetriever):
    def __init__(self, vector_retriever, bm25_retriever):
        self.vector_retriever = vector_retriever
        self.bm25_retriever = bm25_retriever
        super().__init__()

    def _retrieve(self, query_bundle):
        vector_nodes = self.vector_retriever.retrieve(query_bundle)
        bm25_nodes = self.bm25_retriever.retrieve(query_bundle)

        # Deduplicate by node ID
        all_nodes = {node.node_id: node for node in vector_nodes + bm25_nodes}
        return list(all_nodes.values())


hybrid_retriever = HybridRetriever(vector_retriever, bm25_retriever)
# bge_rerank = FlagEmbeddingReranker(model="BAAI/bge-reranker-v2-m3", top_n=3) # Rerank to top 3

# --- 4. Query Engine Setup ---

# ✅ IMPROVED: Better bilingual prompt with clear instructions
qa_system_prompt = (
    "You are an expert technical support assistant for SmartLink BMS system. "
    "You help users with technical questions, troubleshooting, and system usage.\n\n"
    "CRITICAL RULES:\n"
    "1. Answer in the SAME LANGUAGE as the user's question (Indonesian OR English)\n"
    "2. ALWAYS cite your sources at the end of the answer\n"
    "3. If unsure, say: 'Maaf, informasi ini tidak tersedia di knowledge base' (ID) or 'Sorry, this information is not available in the knowledge base' (EN)\n"
    "4. Be DETAILED and COMPLETE - do not oversimplify\n"
    "5. Include step-by-step instructions when applicable\n"
    "6. For troubleshooting: include root cause AND solution\n\n"
    "ANSWER FORMAT:\n"
    "[Your detailed answer here]\n\n"
    "Sumber/Source: [cite specific document section or incident ID]"
)

qa_prompt_tmpl_str = (
    "<|im_start|>system\n" + qa_system_prompt + "\n"
    "Context:\n{context_str}\n<|im_end|>\n"
    "<|im_start|>user\n{query_str}<|im_end|>\n"
    "<|im_start|>assistant\n"
)
qa_prompt_tmpl = PromptTemplate(qa_prompt_tmpl_str)

response_synthesizer = get_response_synthesizer(
    response_mode="refine",  # Refine for more detailed and accurate responses
    text_qa_template=qa_prompt_tmpl,
    streaming=True,
)

# Activate reranking for better result ranking
bge_rerank = FlagEmbeddingReranker(model="BAAI/bge-reranker-v2-m3", top_n=5)

query_engine = RetrieverQueryEngine.from_args(
    retriever=hybrid_retriever,
    node_postprocessors=[
        SimilarityPostprocessor(
            similarity_cutoff=0.4
        ),  # More lenient to include more context
        bge_rerank,  # Rerank to get best results
    ],
    response_synthesizer=response_synthesizer,
)

query_engine = RetrieverQueryEngine.from_args(
    retriever=hybrid_retriever,
    node_postprocessors=[
        SimilarityPostprocessor(similarity_cutoff=0.4),  # ✅ CHANGED: More permissive
        bge_rerank,  # ✅ ADDED: Re-rank for better relevance
    ],
    response_synthesizer=response_synthesizer,
)

# --- 5. Agent Setup ---


# Global variable to store last diagnostic output
_last_diagnostic_report = None
_query_language = "en"  # Track query language


def diagnose_point(point_name: str) -> str:
    """Diagnose a specific device/point in the system."""
    print("tag : ", point_name)
    payload = get_tagname(point_name)
    if not payload: 
        out = "TAGNAME is not found!"
    else: out = full_diagnostic(ModScanSchema.from_sl(payload))
    
    print(f"\n[SYSTEM] Running diagnostics for: {point_name}...")
    return out


async def diagnose_point_async(point_name: str) -> str:
    """Async version: Diagnose a specific device/point in the system."""
    print("tag : ", point_name)
    payload = get_tagname(point_name)
    if not payload: 
        out = "TAGNAME is not found!"
    else: 
        # Call async version directly without asyncio.run
        result = await full_diagnostic_async(ModScanSchema.from_sl(payload))
        # Convert result to string format (FullDiagnosticSchema has to_md_optimize method)
        generated = analysis_point(result.to_md_compact())
        out = result.to_md_optimize(generated)
    print(f"\n[SYSTEM] Running diagnostics for: {point_name}...")
    return out


diagnostic_tool = FunctionTool.from_defaults(fn=diagnose_point)


def incident_lookup(issue_description: str) -> str:
    """
    Search incident history for solutions to technical issues.

    Use this tool when the user asks about:
    - How to solve a specific technical problem
    - Similar past incidents
    - Solutions for BMS issues (commloss, sensor spike, etc.)
    - Root cause and corrective actions

    Args: issue_description: Description of the issue/problem

    Returns: Solution from historical incidents including root cause and action taken
    """
    print(f"[SYSTEM] Searching incident database for: {issue_description}")
    return query_incidents(issue_description)


incident_tool = FunctionTool.from_defaults(fn=incident_lookup)
memory = ChatMemoryBuffer.from_defaults(token_limit=40000)

rag_tool = QueryEngineTool(
    query_engine=query_engine,
    metadata=ToolMetadata(
        name="smartlink_manual",
        description=(
          "Provides information about SmartLink software features, manuals, how-to guides, and definitions. "
          "Use this for any general questions about the system, creating charts, users, etc. "
          "This tool can answer in both Indonesian and English based on the user's language."
        ),
    ),
)

# ✅ IMPROVED: Better system prompt for ReActAgent
agent = ReActAgent(
    llm=llm_model,
    tools=[rag_tool, diagnostic_tool, incident_tool],
    memory=memory,
    system_prompt=(
        "You are an expert technical support assistant for SmartLink BMS system. "
        "You help users solve technical problems and answer questions about the system.\n\n"
        "=== CRITICAL RULES ===\n"
        "1. Answer in the SAME LANGUAGE as the user's question (Indonesian OR English only)\n"
        "2. Be DETAILED and THOROUGH - do not give short answers\n"
        "3. ALWAYS cite your sources: [Manual: section X] or [Incident #ID]\n"
        "4. If information is insufficient, say so clearly\n"
        "5. For technical issues, always provide: root cause + solution + prevention\n\n"
        "=== TOOL SELECTION GUIDE ===\n"
        "1. smartlink_manual: Use for general questions about SmartLink features, manuals, how-to guides, definitions\n"
        "   Examples: 'What is SmartLink?', 'How to create a chart?', 'Apa itu SmartLink?'\n"
        "2. diagnose_point: Use ONLY when user asks to diagnose a SPECIFIC device/point\n"
        "   Examples: 'diagnose JK5-PDU-1', 'check point E1-MVP-01'\n"
        "   🔴 CRITICAL: When using diagnose_point, return the output EXACTLY as provided without any modification!\n"
        "3. incident_lookup: Use when user asks about technical problems, errors, troubleshooting, or solutions\n"
        "   Examples: 'UPS failure how to fix?', 'sensor spike issue', 'commloss problem', 'gimana solusi error?'\n\n"
        "=== RESPONSE FORMAT ===\n"
        "For general questions:\n"
        "[Detailed explanation with examples if applicable]\n"
        "Sumber/Source: [Manual: section X]\n\n"
        "For technical issues:\n"
        "**Problem**: [description]\n"
        "**Root Cause**: [cause from incident database]\n"
        "**Solution**: [step-by-step action taken]\n"
        "**Prevention**: [preventive measures]\n"
        "Sumber/Source: [Incident #ID]\n\n"
        "=== DIAGNOSTIC REPORT FORMAT ===\n"
        "When using diagnose_point tool, follow this EXACT format:\n\n"
        "## Diagnostic Report / Laporan Diagnostik\n"
        "```text\n"
        "[PASTE THE FULL REPORT HERE]\n"
        "```\n\n"
        "## Analysis / Analisis\n"
        "- **PING**: [status and explanation]\n"
        "- **TELNET**: [status and explanation]\n"
        "- **REGISTER**: [status if applicable]\n\n"
        "**Recommendation / Rekomendasi**: [specific actions to take]\n\n"
        "DO NOT SKIP THE CODE BLOCK.\n\n"
        "=== SPECIAL RULE FOR DIAGNOSTIC ===\n"
        "When using diagnose_point tool, you MUST output ONLY the diagnostic report "
        "provided by the tool. Do NOT add any additional commentary, explanation, "
        "or modify the report in any way. The output is already formatted and ready for the user."
    ),
    verbose=True,
)


import re

def extract_point_name(query: str) -> str:
    """Extract point name from diagnostic query patterns"""
    # Pattern: diagnose/check/test [point_name] or [point_name] after diagnose/check keywords
    patterns = [
        r'(?:diagnose|check|cek|test|diagnosis)\s+([\w\-\.]+)',
        r'(?:diagnose|check|cek|test|diagnosis)[\s:]+([\w\-\.]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query.lower())
        if match:
            return match.group(1)
    return None


def is_diagnostic_query(query: str) -> bool:
    """Check if query is asking for diagnostic"""
    diagnostic_keywords = ['diagnose', 'check', 'cek', 'test', 'diagnosis', 'periksa']
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in diagnostic_keywords)


async def query(question):
    tic = time.monotonic()
    global _last_diagnostic_report, _query_language
    _last_diagnostic_report = None  # Reset before each query

    # Detect language
    _query_language = detect_language(question)
    print(f"[DETECTED LANGUAGE] {_query_language.upper()}")

    print(f"\nQUERY: {question}")
    print("-" * 30)

    try:
        # Check if this is a diagnostic query - handle directly without agent
        if is_diagnostic_query(question):
            point_name = extract_point_name(question)
            if point_name:
                print(f"[DIRECT DIAGNOSTIC] Detected point name: {point_name}")
                # Directly call diagnose_point_async without going through agent
                # This returns the raw diagnostic output directly to user
                return await diagnose_point_async(point_name)

        # If Indonesian, translate query for better retrieval
        search_query = question
        if _query_language == "id":
            search_query = translate_id_to_en(question, llm_model)
            if search_query != question:
                print(f"TRANSLATED QUERY: {search_query}")

        # Create bilingual user message
        user_msg = question
        if _query_language == "id":
            user_msg = f"{question}\n[Note: Please answer in Indonesian / Tolong jawab dalam bahasa Indonesia]"

        response = await agent.run(user_msg=user_msg)
        return response.response.content

    except Exception as e:
        toc = time.monotonic()
        print(f"times: {toc - tic}")
        print("\n" + "=" * 30)
        raise ValueError(str(e))


if __name__ == "__main__":
    # Test queries in both languages
    print("=== Testing Multilingual RAG ===")
    print("You can ask questions in Indonesian or English")
    print("Examples:")
    print("  - Apa itu SmartLink?")
    print("  - What is SmartLink?")
    print("  - Bagaimana cara membuat chart?")
    print("  - How to create a chart?")
    print("=" * 50)

    payload = get_tagname("CRAH-2DH2.1-RETURN_AIR_TEMP")

    out = full_diagnostic(ModScanSchema.from_sl(payload))
    print(out)


    # while True:
    #   try:
    #     txt = str(input("> "))
    #     if txt.strip():
    #       import asyncio
    #
    #       asyncio.run(query(txt))
    #   except KeyboardInterrupt:
    #     print("\nExit ...")
    #     break
