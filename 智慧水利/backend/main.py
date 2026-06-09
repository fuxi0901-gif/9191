from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import sys, os, json, tempfile, asyncio, uuid, datetime
from jose import jwt as pyjwt
import bcrypt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.utils import extract_text_from_file, split_text_chunks, embed_texts, store_chunks_to_chromadb, search_knowledge_base
from backend.database import get_db, init_db, Conversation, Message, User

app = FastAPI(title="水利工程智能问答系统 API", version="2.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_preload():
    """启动时预加载 embedding 模型，消除首次请求的冷启动延迟（约2-3秒）"""
    from backend.utils import _get_embedding_model
    _get_embedding_model()
    try:
        init_db()
    except Exception as e:
        print(f"[WARN] 数据库初始化失败（MySQL 可能未启动）：{e}")


class LLMConfig(BaseModel):
    provider: str = ""       # deepseek / kimi / ollama / template
    api_key: str = ""
    api_base: str = ""
    model: str = ""


class QueryRequest(BaseModel):
    query: str
    top_k: int = 3
    llm_config: Optional[LLMConfig] = None
    conversation_id: Optional[int] = None


class ConversationCreateRequest(BaseModel):
    title: str = "新会话"


class ConversationUpdateRequest(BaseModel):
    title: str


class MessageCreateRequest(BaseModel):
    conversation_id: int
    role: str
    content: str


# ========== 认证相关 ==========

JWT_SECRET = os.getenv("JWT_SECRET", "water-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24  # 24 小时

security = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = pyjwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")


class UserRegisterRequest(BaseModel):
    username: str
    password: str
    dept: str = ""


class UserLoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_id: int


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    """上传文档，提取文本、分块、向量化并存入 ChromaDB"""
    try:
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            temp_path = tmp_file.name

        raw_text = extract_text_from_file(temp_path)
        if not raw_text:
            os.unlink(temp_path)
            raise HTTPException(status_code=400, detail="无法从文件中提取文本。")

        chunks = split_text_chunks(raw_text)
        embeddings = embed_texts(chunks)

        metadata = {
            "filename": file.filename,
            "source": temp_path,
            "domain": "general",
        }
        stored_count = store_chunks_to_chromadb(chunks, embeddings, metadata)

        os.unlink(temp_path)

        return {
            "message": "文档上传并处理成功",
            "chunks_processed": len(chunks),
            "chunks_stored": stored_count,
            "filename": file.filename,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传处理失败: {str(e)}")


@app.post("/query/")
async def query_knowledge_base(request: QueryRequest, db: Session = Depends(get_db)):
    """查询知识库，并行生成 RAG 增强回答 + 纯 LLM 回答"""
    try:
        # 获取对话历史（最近 10 轮）
        history_str = ""
        if request.conversation_id:
            history_msgs = db.query(Message).filter(
                Message.conversation_id == request.conversation_id
            ).order_by(Message.created_at.desc()).limit(20).all()
            if history_msgs:
                lines = []
                for m in reversed(history_msgs):
                    role_label = "用户" if m.role == "user" else "助手"
                    lines.append(f"{role_label}：{m.content}")
                history_str = "\n".join(lines)

        # 保存用户消息
        if request.conversation_id:
            user_msg = Message(
                conversation_id=request.conversation_id,
                role="user",
                content=request.query,
            )
            db.add(user_msg)
            db.commit()

        from rag_system.main import process_query
        llm_cfg = request.llm_config.model_dump() if request.llm_config else None
        result = process_query(request.query, request.top_k,
                               llm_config=llm_cfg, history=history_str)

        # 保存 AI 回答
        if request.conversation_id:
            ai_content_parts = []
            if result.get("rag_answer"):
                ai_content_parts.append(f"【知识库增强回答】\n{result['rag_answer']}")
            if result.get("llm_answer"):
                ai_content_parts.append(f"【AI 独立回答】\n{result['llm_answer']}")
            ai_content = "\n\n".join(ai_content_parts) if ai_content_parts else "未获取到回答"
            ai_msg = Message(
                conversation_id=request.conversation_id,
                role="assistant",
                content=ai_content,
            )
            db.add(ai_msg)
            db.commit()

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.post("/query/stream")
async def query_stream(request: QueryRequest, db: Session = Depends(get_db)):
    """流式查询（SSE）：先检索知识库，再流式输出回答"""
    from rag_system.main import _deduplicate_contexts, RELEVANCE_THRESHOLD
    from rag_system.utils import generate_answer_stream, generate_pure_llm_answer_stream

    llm_cfg = request.llm_config.model_dump() if request.llm_config else None

    # 获取对话历史
    history_str = ""
    if request.conversation_id:
        history_msgs = db.query(Message).filter(
            Message.conversation_id == request.conversation_id
        ).order_by(Message.created_at.desc()).limit(20).all()
        if history_msgs:
            lines = []
            for m in reversed(history_msgs):
                role_label = "用户" if m.role == "user" else "助手"
                lines.append(f"{role_label}：{m.content}")
            history_str = "\n".join(lines)

    # 保存用户消息
    if request.conversation_id:
        user_msg = Message(
            conversation_id=request.conversation_id,
            role="user",
            content=request.query,
        )
        db.add(user_msg)
        db.commit()

    async def event_generator():
        import queue, threading

        # Step 1: 检索知识库（先跑完，立即返回 meta）
        raw_contexts, distances, metadatas = search_knowledge_base(request.query, request.top_k)

        context_infos = []
        for ctx, dist, meta in zip(raw_contexts, distances, metadatas):
            if ctx and ctx.strip():
                context_infos.append({
                    "text": ctx.strip(),
                    "filename": (meta or {}).get("filename", "未知文档"),
                    "distance": dist,
                })

        context_infos = _deduplicate_contexts(context_infos, max_results=2)
        relevant = bool(context_infos and context_infos[0]["distance"] < RELEVANCE_THRESHOLD)

        context_str = "\n\n".join(
            f"【来源 {i + 1} · {info['filename']}】\n{info['text']}"
            for i, info in enumerate(context_infos)
        ) if context_infos else ""

        sources = [
            {
                "filename": info["filename"],
                "excerpt": info["text"][:300] + ("..." if len(info["text"]) > 300 else ""),
                "distance": round(info["distance"], 4),
            }
            for info in context_infos
        ] if relevant else []

        # 立即发送元信息
        yield f"data: {json.dumps({'type': 'meta', 'relevant': relevant, 'contexts': sources}, ensure_ascii=False)}\n\n"

        # Step 2: 并行流式生成 RAG + LLM 回答
        token_queue = queue.Queue()
        streamed_rag_text = []
        streamed_llm_text = []

        def _run_rag_stream():
            """线程 A: RAG 增强回答"""
            nonlocal streamed_rag_text
            token_queue.put(('rag_start', ''))
            try:
                for token in generate_answer_stream(context_str, request.query, llm_cfg, history=history_str):
                    streamed_rag_text.append(token)
                    token_queue.put(('rag_token', token))
            except Exception as e:
                token_queue.put(('rag_token', f'[RAG生成失败: {str(e)[:100]}]'))
            token_queue.put(('rag_end', ''))

        def _run_llm_stream():
            """线程 B: 纯 LLM 回答"""
            nonlocal streamed_llm_text
            token_queue.put(('llm_start', ''))
            try:
                for token in generate_pure_llm_answer_stream(request.query, llm_cfg, history=history_str):
                    streamed_llm_text.append(token)
                    token_queue.put(('llm_token', token))
            except Exception as e:
                token_queue.put(('llm_token', f'[LLM生成失败: {str(e)[:100]}]'))
            token_queue.put(('done', ''))

        if relevant:
            # 两条流并行启动
            threading.Thread(target=_run_rag_stream, daemon=True).start()
            threading.Thread(target=_run_llm_stream, daemon=True).start()

            rag_ended, llm_ended = False, False
            while not (rag_ended and llm_ended):
                try:
                    evt_type, evt_data = token_queue.get(timeout=0.1)
                    if evt_type == 'rag_end':
                        rag_ended = True
                    elif evt_type == 'done':
                        llm_ended = True
                    yield f"data: {json.dumps({'type': evt_type, 'data': evt_data}, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    await asyncio.sleep(0.02)
        else:
            # 不相关 → 仅 LLM 流（同样用线程避免 queue 阻塞）
            threading.Thread(target=_run_llm_stream, daemon=True).start()
            while True:
                try:
                    evt_type, evt_data = token_queue.get(timeout=0.1)
                    if evt_type == 'done':
                        break
                    yield f"data: {json.dumps({'type': evt_type, 'data': evt_data}, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    await asyncio.sleep(0.02)
            yield f"data: {json.dumps({'type': 'done', 'data': ''}, ensure_ascii=False)}\n\n"

        # 保存 AI 回答到数据库
        if request.conversation_id:
            try:
                rag_text = ''.join(streamed_rag_text).strip()
                llm_text = ''.join(streamed_llm_text).strip()
                parts = []
                if rag_text:
                    parts.append(f"【知识库增强回答】\n{rag_text}")
                if llm_text:
                    parts.append(f"【AI 独立回答】\n{llm_text}")
                ai_content = "\n\n".join(parts) if parts else "未获取到回答"
                ai_msg = Message(
                    conversation_id=request.conversation_id,
                    role="assistant",
                    content=ai_content,
                )
                db.add(ai_msg)
                db.commit()
            except Exception:
                pass  # 保存失败不影响流式响应

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/status/")
def system_status():
    """返回系统状态，包括 LLM 配置信息"""
    from backend.config import settings
    provider = settings.LLM_PROVIDER.lower()
    llm_available = False
    if provider == "deepseek" and settings.DEEPSEEK_API_KEY:
        llm_available = True
    elif provider == "kimi" and settings.KIMI_API_KEY:
        llm_available = True
    elif provider == "ollama":
        try:
            import requests
            r = requests.get(f"{settings.OLLAMA_API_BASE}/api/tags", timeout=3)
            llm_available = r.status_code == 200
        except Exception:
            pass

    return {
        "status": "ok",
        "message": "水利工程智能问答系统 API 运行中",
        "llm_provider": provider if llm_available else "template",
        "llm_available": llm_available,
    }


@app.post("/test-llm/")
def test_llm_connection(config: LLMConfig):
    """测试 LLM 连接是否正常"""
    from rag_system.llm_client import _call_openai_compatible, _call_ollama
    provider = config.provider.lower()
    try:
        if provider == "deepseek" and config.api_key:
            _call_openai_compatible(config.api_base or "https://api.deepseek.com", config.api_key, config.model or "deepseek-chat", "你好，请回复'连接成功'", timeout=15)
            return {"success": True, "message": "DeepSeek 连接成功"}
        elif provider == "kimi" and config.api_key:
            _call_openai_compatible(config.api_base or "https://api.moonshot.cn", config.api_key, config.model or "moonshot-v1-8k", "你好，请回复'连接成功'", timeout=15)
            return {"success": True, "message": "Kimi 连接成功"}
        elif provider == "ollama":
            _call_ollama(config.api_base or "http://localhost:11434", config.model or "qwen2:7b", "你好", timeout=10)
            return {"success": True, "message": "Ollama 连接成功"}
        else:
            return {"success": False, "message": "请填写有效的 API Key"}
    except Exception as e:
        return {"success": False, "message": str(e)[:200]}


# ========== 监测数据 API ==========

@app.get("/monitoring/")
def get_monitoring_data(data_type: str = "water_level", limit: int = 30):
    """获取监测数据。无真实数据时返回 7 天模拟数据"""
    now = datetime.datetime.utcnow()
    points = []

    if data_type == "water_level":
        base = 328.0
        unit = "m"
        for i in range(limit):
            t = now - datetime.timedelta(days=limit - 1 - i)
            val = base + 1.5 * (0.5 - (i % 12) / 24.0) + (i * 0.01)
            val += (hash(str(i)) % 100 - 50) / 100.0
            points.append({"timestamp": t.isoformat(), "value": round(val, 2), "unit": unit})
    elif data_type == "rainfall":
        unit = "mm"
        import random
        rng = random.Random(42)
        for i in range(limit):
            t = now - datetime.timedelta(days=limit - 1 - i)
            val = max(0, rng.gauss(8, 15))
            points.append({"timestamp": t.isoformat(), "value": round(val, 1), "unit": unit})
    elif data_type == "flow_rate":
        base = 120.0
        unit = "m³/s"
        import random
        rng = random.Random(99)
        for i in range(limit):
            t = now - datetime.timedelta(days=limit - 1 - i)
            val = base + rng.gauss(0, 15)
            points.append({"timestamp": t.isoformat(), "value": round(val, 1), "unit": unit})
    else:
        return {"error": "不支持的数据类型", "data_type": data_type}

    latest = points[-1]["value"] if points else 0
    return {
        "data_type": data_type,
        "unit": points[0]["unit"] if points else "",
        "latest_value": latest,
        "points": points,
        "count": len(points),
    }


# ========== 用户认证 API ==========

@app.post("/register/", status_code=201)
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """用户注册"""
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        dept=req.dept,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "user_id": user.id,
    }


@app.post("/login/")
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "user_id": user.id,
    }


@app.get("/users/me/")
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "dept": current_user.dept,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }


# ========== 对话管理 API ==========

@app.get("/conversations/")
def list_conversations(db: Session = Depends(get_db)):
    """获取对话列表，按更新时间倒序"""
    conversations = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    return [
        {
            "id": c.id,
            "session_id": c.session_id,
            "title": c.title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "message_count": db.query(func.count(Message.id)).filter(
                Message.conversation_id == c.id
            ).scalar() or 0,
        }
        for c in conversations
    ]


@app.post("/conversations/")
def create_conversation(req: ConversationCreateRequest, db: Session = Depends(get_db)):
    """创建新对话"""
    conv = Conversation(
        session_id=uuid.uuid4().hex,
        title=req.title,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {
        "id": conv.id,
        "session_id": conv.session_id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }


@app.get("/conversations/{conv_id}")
def get_conversation(conv_id: int, db: Session = Depends(get_db)):
    """获取单个对话及其所有消息"""
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    messages = db.query(Message).filter(
        Message.conversation_id == conv_id
    ).order_by(Message.created_at.asc()).all()
    return {
        "id": conv.id,
        "session_id": conv.session_id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@app.put("/conversations/{conv_id}")
def update_conversation(conv_id: int, req: ConversationUpdateRequest, db: Session = Depends(get_db)):
    """重命名对话"""
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    conv.title = req.title
    conv.updated_at = datetime.datetime.utcnow()
    db.commit()
    return {"id": conv.id, "title": conv.title, "updated_at": conv.updated_at.isoformat()}


@app.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: int, db: Session = Depends(get_db)):
    """删除对话及其所有消息"""
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    db.query(Message).filter(Message.conversation_id == conv_id).delete()
    db.delete(conv)
    db.commit()
    return {"message": "对话已删除"}


@app.post("/messages/")
def add_message(req: MessageCreateRequest, db: Session = Depends(get_db)):
    """向对话追加一条消息"""
    conv = db.query(Conversation).filter(Conversation.id == req.conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    msg = Message(
        conversation_id=req.conversation_id,
        role=req.role,
        content=req.content,
    )
    db.add(msg)
    conv.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(msg)
    return {
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


@app.get("/")
def health_check():
    return {"status": "ok", "message": "水利工程智能问答系统 API 运行中"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080, reload=True)
