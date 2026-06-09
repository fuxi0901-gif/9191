"""
RAG 主流程测试
覆盖：空知识库、相关性判断、双路回答生成
"""
import pytest
from unittest.mock import patch, MagicMock

from rag_system.main import process_query, _deduplicate_contexts


# ---------- 空知识库 ----------

def test_process_query_empty_kb_returns_not_relevant():
    """知识库为空时，relevant=False，只返回 llm_answer"""
    with patch("rag_system.main.search_knowledge_base", return_value=([], [], [])):
        with patch("rag_system.main.generate_pure_llm_answer", return_value="纯 LLM 回答（无文档支持）"):
            result = process_query("混凝土入仓温度")

    assert result["query"] == "混凝土入仓温度"
    assert result["relevant"] is False
    assert result["contexts"] == []
    assert result["rag_answer"] is None
    assert "纯 LLM" in result["llm_answer"]


# ---------- 相关路径 ----------

def test_process_query_relevant_runs_both_paths():
    """知识库命中时，应并行生成 rag_answer + llm_answer"""
    mock_contexts = ["混凝土入仓温度应控制在 5~28 度"]
    mock_distances = [0.2]  # 小于阈值 0.65
    mock_metas = [{"filename": "规范.txt"}]

    with patch("rag_system.main.search_knowledge_base", return_value=(mock_contexts, mock_distances, mock_metas)):
        with patch("rag_system.main.generate_answer", return_value="RAG 增强回答"):
            with patch("rag_system.main.generate_pure_llm_answer", return_value="纯 LLM 回答"):
                result = process_query("混凝土入仓温度控制要求")

    assert result["relevant"] is True
    assert result["rag_answer"] == "RAG 增强回答"
    assert result["llm_answer"] == "纯 LLM 回答"
    assert len(result["contexts"]) == 1
    assert result["contexts"][0]["filename"] == "规范.txt"


def test_process_query_relevance_threshold():
    """distance >= 0.65 时应判定为不相关"""
    mock_contexts = ["不太相关的内容"]
    mock_distances = [0.7]  # 超过阈值
    mock_metas = [{"filename": "无关.txt"}]

    with patch("rag_system.main.search_knowledge_base", return_value=(mock_contexts, mock_distances, mock_metas)):
        with patch("rag_system.main.generate_pure_llm_answer", return_value="LLM 兜底") as m:
            result = process_query("无关问题")

    assert result["relevant"] is False
    assert result["contexts"] == []
    assert m.called


# ---------- 去重边界 ----------

def test_deduplicate_max_two():
    """去重后应最多保留 2 条
    注意：实际实现中相似度高的会被去重，最终可能少于 max_results。
    使用差异较大的内容验证 max_results 上限生效。"""
    import random
    random.seed(42)
    # 用完全独立的随机字符序列构造 N 个不同文本（无 n-gram 重叠）
    chars = "天地玄黄宇宙洪荒日月盈昃辰宿列张寒来暑往秋收冬藏"
    infos = [
        {"text": f"独立条款 {i}：{''.join(random.sample(chars, 20))}",
         "filename": "a.pdf", "distance": 0.1}
        for i in range(10)
    ]
    out = _deduplicate_contexts(infos, max_results=2)
    assert len(out) <= 2  # 严格不超过 max_results 上限


# ---------- 生成函数异常处理 ----------

def test_process_query_handles_rag_failure():
    """RAG 生成失败不应阻塞 LLM 路径"""
    with patch("rag_system.main.search_knowledge_base", return_value=(["内容"], [0.2], [{"filename": "f.txt"}])):
        with patch("rag_system.main.generate_answer", side_effect=Exception("RAG 失败")):
            with patch("rag_system.main.generate_pure_llm_answer", return_value="LLM OK"):
                result = process_query("测试问题")

    assert result["relevant"] is True
    # RAG 失败时仍应返回错误占位符
    assert "失败" in result["rag_answer"] or "RAG" in result["rag_answer"]
    assert result["llm_answer"] == "LLM OK"
