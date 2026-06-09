"""
RAG 查询主流程：检索 → 相关性判断 → 并行生成双路回答
"""
import sys, os
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils import search_knowledge_base
from rag_system.utils import generate_answer, generate_pure_llm_answer

# 余弦距离阈值：低于此值认为知识库内容与问题相关
RELEVANCE_THRESHOLD = 0.65


def _deduplicate_contexts(context_infos: list, max_results: int = 2) -> list:
    """去除重复/高度相似的文本块，保留最相关的唯一条目（带元数据）"""
    if not context_infos:
        return []

    result = []
    for info in context_infos:
        ctx = info["text"].strip()
        if not ctx:
            continue

        is_dup = False
        for existing in result:
            existing_text = existing["text"]
            shorter = ctx if len(ctx) < len(existing_text) else existing_text
            longer = existing_text if len(ctx) < len(existing_text) else ctx

            if len(shorter) < 20:
                continue

            if shorter in longer:
                is_dup = True
                break

            half = len(shorter) // 2
            if shorter[:half] in longer or shorter[half:] in longer:
                is_dup = True
                break

            if _jaccard_similarity(shorter, longer) > 0.75:
                is_dup = True
                break

        if not is_dup:
            result.append(info)

    return result[:max_results]


def _jaccard_similarity(text1: str, text2: str, n: int = 3) -> float:
    """基于 n-gram 的 Jaccard 相似度"""
    def ngrams(s, n):
        return {s[i:i + n] for i in range(len(s) - n + 1)}

    g1 = ngrams(text1, n)
    g2 = ngrams(text2, n)
    if not g1 or not g2:
        return 0.0
    intersection = len(g1 & g2)
    union = len(g1 | g2)
    return intersection / union if union > 0 else 0.0


def process_query(query: str, top_k: int = 3, llm_config: dict = None, history: str = "") -> dict:
    """
    RAG 查询主流程：
    1. 检索知识库 → 2. 判断相关性 → 3. 并行生成双路回答（RAG + 纯 LLM）
    """
    # Step 1: 检索知识库（带相似度分数和元数据）
    raw_contexts, distances, metadatas = search_knowledge_base(query, top_k)

    # Step 2: 构建带元数据的上下文列表
    context_infos = []
    for ctx, dist, meta in zip(raw_contexts, distances, metadatas):
        if ctx and ctx.strip():
            context_infos.append({
                "text": ctx.strip(),
                "filename": (meta or {}).get("filename", "未知文档"),
                "distance": dist,
            })

    # 去重
    context_infos = _deduplicate_contexts(context_infos, max_results=2)

    # 相关性判断
    relevant = bool(context_infos and context_infos[0]["distance"] < RELEVANCE_THRESHOLD)

    # 构建 LLM 用的上下文字符串
    context_str = "\n\n".join(
        f"【来源 {i + 1} · {info['filename']}】\n{info['text']}"
        for i, info in enumerate(context_infos)
    ) if context_infos else ""

    # 构建返回给前端的引用来源（精简文本 + 文档名）
    sources = [
        {
            "filename": info["filename"],
            "excerpt": info["text"][:300] + ("..." if len(info["text"]) > 300 else ""),
            "distance": round(info["distance"], 4),
        }
        for info in context_infos
    ] if relevant else []

    # Step 3: 并行生成回答
    if relevant:
        with ThreadPoolExecutor(max_workers=2) as executor:
            rag_future = executor.submit(generate_answer, context_str, query, llm_config, history)
            llm_future = executor.submit(generate_pure_llm_answer, query, llm_config, history)

            rag_answer = None
            llm_answer = None
            for future in as_completed([rag_future, llm_future]):
                try:
                    result = future.result(timeout=120)
                except Exception as e:
                    result = f"生成回答失败: {str(e)[:100]}"

                if future == rag_future:
                    rag_answer = result
                else:
                    llm_answer = result

        return {
            "query": query,
            "relevant": True,
            "contexts": sources,
            "rag_answer": rag_answer,
            "llm_answer": llm_answer,
        }
    else:
        llm_answer = generate_pure_llm_answer(query, llm_config, history)

        return {
            "query": query,
            "relevant": False,
            "contexts": [],
            "rag_answer": None,
            "llm_answer": llm_answer,
        }


def initialize_kb():
    """初始化知识库连接（首次调用时自动创建 ChromaDB 集合）"""
    from backend.utils import _get_chroma_collection
    _get_chroma_collection()
    return True
