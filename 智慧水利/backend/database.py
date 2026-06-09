from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Date, Index, Float
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config import settings
import datetime

# 尝试 MySQL，不可用时回退 SQLite
try:
    engine = create_engine(
        settings.SQLALCHEMY_DATABASE_URI,
        pool_pre_ping=True,
        echo=False
    )
    engine.connect().close()
    print("[INFO] MySQL 数据库连接成功")
except Exception as e:
    print(f"[WARN] MySQL 连接失败 ({e})，回退 SQLite")
    sqlite_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "water_rag.db")
    engine = create_engine(
        f"sqlite:///{sqlite_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI 依赖注入：每个请求获取独立数据库会话，结束后自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="engineer")
    dept = Column(String(100))
    created_at = Column(DateTime, default=datetime.datetime.now)

    conversations = relationship("Conversation", back_populates="owner")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String(64), nullable=False, index=True)
    title = Column(String(100), default="新会话")
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    role = Column(String(10))
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.now)

    conversation = relationship("Conversation", back_populates="messages")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500))
    file_type = Column(String(20))
    title = Column(String(255))
    content = Column(Text)
    source = Column(String(255))
    upload_user_id = Column(Integer)
    status = Column(String(20), default="active")
    domain = Column(String(50), default="general")
    version = Column(String(20))
    effective_date = Column(Date)
    created_at = Column(DateTime, default=datetime.datetime.now)

    __table_args__ = (
        Index("idx_version_domain", "version", "domain"),
        Index("idx_status", "status"),
    )


def init_db():
    Base.metadata.create_all(bind=engine)


class SensorData(Base):
    """传感器监测数据（预留模型，供 Phase 3 可视化使用）"""
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(50))
    data_type = Column(String(20))
    value = Column(Float)
    unit = Column(String(10))
    recorded_at = Column(DateTime, default=datetime.datetime.now)
