import os
from typing import List, Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config import settings

# --- 模型缓存（模块级单例，避免重复加载） ---
_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("[INFO] Loading embedding model (first time may download ~120MB)...")
            _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
            print("[INFO] Embedding model loaded successfully.")
        except Exception as e:
            print(f"[WARN] Cannot load embedding model: {e}")
            print("[WARN] Using dummy embeddings. Model download may have failed due to network.")
            print("[WARN] Tips: pip install -U huggingface_hub && huggingface-cli download sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            return None
    return _embedding_model


# --- ChromaDB 客户端缓存 ---
_chroma_client = None
_chroma_collection = None


def _get_chroma_collection():
    global _chroma_client, _chroma_collection
    if _chroma_client is None:
        import chromadb
        if settings.CHROMA_CLIENT_MODE == "http":
            _chroma_client = chromadb.HttpClient(
                host=settings.CHROMA_HTTP_HOST,
                port=settings.CHROMA_HTTP_PORT,
                settings=chromadb.config.Settings(anonymized_telemetry=False)
            )
        else:
            _chroma_client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR,
                settings=chromadb.config.Settings(anonymized_telemetry=False)
            )
    if _chroma_collection is None:
        _chroma_collection = _chroma_client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
    return _chroma_collection


def extract_text_from_file(file_path: str) -> str:
    """从 PDF、DOCX、TXT 文件中提取纯文本"""
    text = ""
    try:
        if file_path.lower().endswith(".pdf"):
            import PyPDF2
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        elif file_path.lower().endswith(".docx"):
            import docx
            doc = docx.Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
        elif file_path.lower().endswith(".txt"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        else:
            print(f"[WARN] Unsupported file type: {file_path}")
            return ""
    except ImportError as e:
        print(f"[ERROR] Missing dependency for reading {file_path}: {e}")
        return ""
    except Exception as e:
        print(f"[ERROR] Failed to read {file_path}: {e}")
        return ""
    return text.strip()


def split_text_chunks(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    """将长文本按固定长度和重叠切分"""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
        if start >= len(text):
            break
    return chunks


def embed_text(text: str) -> List[float]:
    """将单个文本转换为向量"""
    model = _get_embedding_model()
    if model is None:
        return [0.0] * 384
    try:
        embedding = model.encode([text], convert_to_numpy=True)[0]
        return embedding.tolist()
    except Exception as e:
        print(f"[ERROR] Embedding failed: {e}. Using dummy embedding.")
        return [0.0] * 384


def embed_texts(texts: List[str]) -> List[List[float]]:
    """将多个文本批量转换为向量"""
    if not texts:
        return []
    model = _get_embedding_model()
    if model is None:
        return [[0.0] * 384 for _ in texts]
    try:
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    except Exception as e:
        print(f"[ERROR] Batch embedding failed: {e}. Using dummy embeddings.")
        return [[0.0] * 384 for _ in texts]


def store_chunks_to_chromadb(chunks: List[str], embeddings: List[List[float]], metadata: dict) -> int:
    """将文本块和向量存入 ChromaDB"""
    if not chunks:
        return 0
    collection = _get_chroma_collection()
    doc_id = metadata.get("filename", "unknown")
    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "filename": metadata.get("filename", ""),
            "chunk_index": i,
            "source": metadata.get("source", ""),
            "domain": metadata.get("domain", "general"),
        }
        for i in range(len(chunks))
    ]
    collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    print(f"[INFO] Stored {len(chunks)} chunks to ChromaDB (doc: {doc_id})")
    return len(chunks)


def search_knowledge_base(query: str, top_k: int = 3):
    """从 ChromaDB 查询最相关的文本片段，返回 (documents, distances, metadatas)"""
    try:
        collection = _get_chroma_collection()
        if collection.count() == 0:
            print("[WARN] ChromaDB collection is empty. No results.")
            return [], [], []
        query_embedding = embed_text(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"]
        )
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        return (
            documents if documents else [],
            distances if distances else [],
            metadatas if metadatas else []
        )
    except Exception as e:
        print(f"[ERROR] Knowledge base search failed: {e}")
        return [], [], []
