# RAG Improvements Test Suite - Fase 1

Test suite untuk memverifikasi implementasi Fase 1 improvements pada RAG system.

## 📁 Test Files

### 1. `quick_test.py` (Recommended)
Test cepat tanpa pytest - langsung cek konfigurasi:

```bash
cd /home/imaji/smart-ai/smart-ai-dev/agent-service
source .venv/bin/activate
python tests/quick_test.py
```

Output akan menunjukkan ✅ untuk setiap test yang pass.

### 2. `run_rag_tests.py`
Test runner dengan format yang lebih detail:

```bash
source .venv/bin/activate
python tests/run_rag_tests.py
```

### 3. `test_rag_improvements.py`
Full pytest suite untuk automated testing:

```bash
# Install pytest jika belum
pip install pytest

# Run tests
python -m pytest tests/test_rag_improvements.py -v

# Run specific test class
python -m pytest tests/test_rag_improvements.py::TestRetrievalConfiguration -v
```

## 🧪 Apa yang Di-Test?

### Retrieval Configuration
- ✅ Similarity cutoff: 0.6 → **0.4**
- ✅ Response mode: compact → **refine**
- ✅ Top k: 5 → **8**
- ✅ Re-ranking: disabled → **enabled** (BGE reranker)

### Prompt Engineering
- ✅ Source citation instruction added
- ✅ Detailed/complete instructions added
- ✅ Language instruction improved
- ✅ "I don't know" instruction added
- ✅ Agent tool selection guide added

### Incident RAG
- ✅ Chunk size: 512 → **256**
- ✅ Similarity cutoff: 0.5 → **0.4**
- ✅ Re-ranking enabled
- ✅ Query function exports

## 📊 Expected Test Results

```
✅ All tests passed! RAG improvements are correctly implemented.
```

Jika ada test yang fail, akan ditampilkan detail error.

## 🔧 Troubleshooting

### Import Error
```
❌ Import failed: No module named 'llama_index'
```
**Solusi:** Pastikan virtual environment aktif dan dependencies terinstall
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Attribute Error
LSP errors tentang attributes (seperti `_similarity_cutoff`, `_response_mode`) adalah **false positive** - karena LSP tidak mengenal llama-index packages di virtual environment. Tests tetap akan berjalan normal saat dijalankan.

## 🎯 Setelah Test Pass

Jika semua test pass, Anda bisa:
1. Restart RAG service untuk apply changes
2. Test dengan query aktual
3. Monitor improvement dalam respons chatbot

## 📝 Catatan

- Tests menggunakan private attributes (e.g., `_similarity_cutoff`) untuk verifikasi
- Ini bukan best practice untuk production, tapi OK untuk testing
- Real-world testing tetap diperlukan untuk validasi akhir
