"""
统一 LLM 客户端 — 支持 DeepSeek / Kimi / Ollama / 离线模板
支持流式和非流式两种调用方式
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config import settings


def _call_openai_compatible(api_base: str, api_key: str, model: str, prompt: str, timeout: int = 90) -> str:
    """调用 OpenAI 兼容 API（DeepSeek、Kimi 等）"""
    import requests
    url = f"{api_base}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位资深的水利工程专家。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 1024
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code == 200:
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    else:
        raise RuntimeError(f"API error {resp.status_code}: {resp.text[:200]}")


def _call_openai_compatible_stream(api_base: str, api_key: str, model: str, prompt: str, timeout: int = 90):
    """流式调用 OpenAI 兼容 API，逐 token yield"""
    import requests
    url = f"{api_base}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位资深的水利工程专家。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
        "stream": True
    }
    resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"API error {resp.status_code}: {resp.text[:200]}")

    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data_str = line[6:]
        if data_str.strip() == "[DONE]":
            break
        try:
            obj = json.loads(data_str)
            delta = obj.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield content
        except (json.JSONDecodeError, KeyError, IndexError):
            continue


def _call_ollama(api_base: str, model: str, prompt: str, timeout: int = 90) -> str:
    """调用本地 Ollama API"""
    import requests
    resp = requests.post(
        f"{api_base}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=timeout
    )
    if resp.status_code == 200:
        return resp.json().get("response", "").strip()
    else:
        raise RuntimeError(f"Ollama error {resp.status_code}")


def _call_ollama_stream(api_base: str, model: str, prompt: str, timeout: int = 90):
    """流式调用 Ollama API"""
    import requests
    resp = requests.post(
        f"{api_base}/api/generate",
        json={"model": model, "prompt": prompt, "stream": True},
        stream=True,
        timeout=timeout
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Ollama error {resp.status_code}")

    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        try:
            obj = json.loads(line)
            token = obj.get("response", "")
            if token:
                yield token
            if obj.get("done", False):
                break
        except json.JSONDecodeError:
            continue


def _template_fallback(context: str, query: str) -> str:
    """离线模板回退 — 按结论+依据+建议三段式组织"""
    if context:
        return (
            f"【结论】\n"
            f"知识库中已检索到与「{query}」相关的水利规范内容，请查看下方引用来源获取完整条款。\n\n"
            f"【依据】\n"
            f"匹配内容来自已上传的水利规范文档，具体条款详见「查看引用来源」面板。\n\n"
            f"【建议】\n"
            f"1. 点击下方「查看引用来源」查看完整规范原文；\n"
            f"2. 配置 DeepSeek 或 Kimi API Key 后，AI 将自动提取关键结论、规范依据和建议措施；\n"
            f"3. 如需精准分析，建议上传完整的水利规范 PDF/DOCX 文档。"
        )
    else:
        return (
            f"【结论】\n"
            f"知识库中暂无与「{query}」相关的内容。\n\n"
            f"【建议】\n"
            f"1. 请先上传相关水利规范文档（PDF/DOCX/TXT）；\n"
            f"2. 或尝试使用更具体的水利工程术语重新提问。"
        )


def _resolve_config(llm_config: dict = None) -> tuple:
    """解析 LLM 配置：前端传入 > .env，返回 (provider, api_key, api_base, model)"""
    provider = ""
    api_key = ""
    api_base = ""
    model = ""

    if llm_config and llm_config.get("provider") and llm_config.get("api_key"):
        provider = llm_config["provider"].lower()
        api_key = llm_config["api_key"]
        api_base = llm_config.get("api_base", "")
        model = llm_config.get("model", "")

    if not provider:
        provider = settings.LLM_PROVIDER.lower()

    if provider == "deepseek":
        api_key = api_key or settings.DEEPSEEK_API_KEY
        api_base = api_base or settings.DEEPSEEK_API_BASE
        model = model or settings.DEEPSEEK_MODEL
    elif provider == "kimi":
        api_key = api_key or settings.KIMI_API_KEY
        api_base = api_base or settings.KIMI_API_BASE
        model = model or settings.KIMI_MODEL
    elif provider == "ollama":
        api_base = api_base or settings.OLLAMA_API_BASE
        model = model or settings.OLLAMA_MODEL

    return provider, api_key, api_base, model


def generate_with_llm(prompt: str, context: str = "", query: str = "", llm_config: dict = None) -> str:
    """按优先级尝试 LLM 供应商，返回完整的回答字符串"""
    provider, api_key, api_base, model = _resolve_config(llm_config)

    # DeepSeek
    if provider == "deepseek" and api_key and api_key != "your_deepseek_api_key_here":
        try:
            return _call_openai_compatible(api_base, api_key, model, prompt)
        except Exception as e:
            print(f"[WARN] DeepSeek failed: {e}")

    # Kimi
    if provider == "kimi" and api_key and api_key != "your_kimi_api_key_here":
        try:
            return _call_openai_compatible(api_base, api_key, model, prompt)
        except Exception as e:
            print(f"[WARN] Kimi failed: {e}")

    # Ollama
    if provider == "ollama":
        try:
            return _call_ollama(api_base, model, prompt)
        except Exception as e:
            print(f"[WARN] Ollama failed: {e}")

    # 回退
    print(f"[INFO] No LLM available, using template fallback.")
    return _template_fallback(context, query)


def generate_with_llm_stream(prompt: str, context: str = "", query: str = "", llm_config: dict = None):
    """流式 LLM 调用，逐 token yield。失败时 yield 完整回退文本。"""
    provider, api_key, api_base, model = _resolve_config(llm_config)

    # DeepSeek
    if provider == "deepseek" and api_key and api_key != "your_deepseek_api_key_here":
        try:
            yield from _call_openai_compatible_stream(api_base, api_key, model, prompt)
            return
        except Exception as e:
            print(f"[WARN] DeepSeek stream failed: {e}")

    # Kimi
    if provider == "kimi" and api_key and api_key != "your_kimi_api_key_here":
        try:
            yield from _call_openai_compatible_stream(api_base, api_key, model, prompt)
            return
        except Exception as e:
            print(f"[WARN] Kimi stream failed: {e}")

    # Ollama
    if provider == "ollama":
        try:
            yield from _call_ollama_stream(api_base, model, prompt)
            return
        except Exception as e:
            print(f"[WARN] Ollama stream failed: {e}")

    # 回退
    print(f"[INFO] No LLM available, using template fallback.")
    yield _template_fallback(context, query)
