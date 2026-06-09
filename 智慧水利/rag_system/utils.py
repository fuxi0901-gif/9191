def build_prompt(context: str, query: str, history: str = "") -> str:
    """构建 RAG 增强 prompt，强制三段式结构"""
    history_section = ""
    if history:
        history_section = f"【历史对话】\n{history}\n\n"
    return f"""你是水利工程专家。请严格按以下格式回答，每段必须独立标注标题：

【结论】
（用1-2句话直接回答用户问题的核心结论）

【依据】
（引用参考知识中的具体规范条款编号和内容，如"根据 DL/T 5144-2015 第6.3.2条……"）

【建议】
（基于规范给出可操作的建议措施，2-3条）

{history_section}【参考知识】
{context if context else "（知识库中暂无相关内容）"}

【用户问题】{query}

请按上述格式回答："""


def build_prompt_pure(query: str, history: str = "") -> str:
    """构建纯 LLM prompt，水利专家身份回答"""
    history_section = ""
    if history:
        history_section = f"【历史对话】\n{history}\n\n"
    return f"""你是水利工程专家。请严格按以下格式回答：

【结论】
（1-2句话直接回答核心结论）

【依据】
（基于你的专业知识说明判断依据）

【建议】
（给出2-3条可操作的建议措施）

{history_section}【用户问题】{query}

请按上述格式回答："""


def generate_answer(context: str, query: str, llm_config: dict = None, history: str = "") -> str:
    """调用 LLM 生成 RAG 增强回答"""
    from rag_system.llm_client import generate_with_llm
    prompt = build_prompt(context, query, history)
    return generate_with_llm(prompt, context, query, llm_config)


def generate_pure_llm_answer(query: str, llm_config: dict = None, history: str = "") -> str:
    """调用 LLM 生成纯模型回答（不依赖知识库）"""
    from rag_system.llm_client import generate_with_llm
    prompt = build_prompt_pure(query, history)
    return generate_with_llm(prompt, "", query, llm_config)


def generate_answer_stream(context: str, query: str, llm_config: dict = None, history: str = ""):
    """流式生成 RAG 增强回答"""
    from rag_system.llm_client import generate_with_llm_stream
    prompt = build_prompt(context, query, history)
    yield from generate_with_llm_stream(prompt, context, query, llm_config)


def generate_pure_llm_answer_stream(query: str, llm_config: dict = None, history: str = ""):
    """流式生成纯 LLM 回答"""
    from rag_system.llm_client import generate_with_llm_stream
    prompt = build_prompt_pure(query, history)
    yield from generate_with_llm_stream(prompt, "", query, llm_config)
