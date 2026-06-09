import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量（使用 __file__ 定位，避免依赖 CWD）
_env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=_env_path)

# Hugging Face 镜像（国内网络访问加速）
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')

class Settings:
    # --- 项目基础配置 ---
    PROJECT_NAME: str = "水利工程智能问答系统"
    API_V1_STR: str = "/api/v1"

    # --- 数据库配置 ---
    # MySQL: 格式为 mysql+pymysql://用户:密码@主机:端口/数据库名
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "password")
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT: str = os.getenv("MYSQL_PORT", "3306")
    MYSQL_DB: str = os.getenv("MYSQL_DB", "hydrau_db")
    
    SQLALCHEMY_DATABASE_URI: str = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
    )

    # Redis配置
    REDIS_HOST: str = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))

    # --- 嵌入模型配置 ---
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

    # --- 向量数据库配置 (Milvus) ---
    MILVUS_HOST: str = os.getenv("MILVUS_HOST", "127.0.0.1")
    MILVUS_PORT: str = os.getenv("MILVUS_PORT", "19530")
    MILVUS_COLLECTION_NAME: str = os.getenv("MILVUS_COLLECTION", "hydrau_knowledge")

    # --- 文件存储与路径配置 ---
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "uploaded_files")

    # --- ChromaDB 向量数据库配置 ---
    CHROMA_CLIENT_MODE: str = os.getenv("CHROMA_CLIENT_MODE", "persistent")  # "persistent" 或 "http"
    CHROMA_HTTP_HOST: str = os.getenv("CHROMA_HTTP_HOST", "127.0.0.1")
    CHROMA_HTTP_PORT: int = int(os.getenv("CHROMA_HTTP_PORT", "8000"))
    CHROMA_PERSIST_DIR: str = os.path.join(BASE_DIR, "chroma_db")
    CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION", "hydrau_knowledge")

    # --- 大语言模型配置（多供应商）---
    # 优先级: deepseek > kimi > ollama > none(模板回退)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek")

    # DeepSeek
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_BASE: str = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # Kimi (Moonshot)
    KIMI_API_KEY: str = os.getenv("KIMI_API_KEY", "")
    KIMI_API_BASE: str = os.getenv("KIMI_API_BASE", "https://api.moonshot.cn")
    KIMI_MODEL: str = os.getenv("KIMI_MODEL", "moonshot-v1-8k")

    # Ollama (本地部署)
    OLLAMA_API_BASE: str = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2:7b")

    # 确保上传目录存在
    os.makedirs(UPLOAD_DIR, exist_ok=True)

settings = Settings()