# 智慧水利人机交互系统

基于人工智能技术的智慧水利人机交互系统，融合知识库检索增强（RAG）、多供应商大语言模型调用、语音交互和实时监测数据可视化，提升水利工程的智能化管理水平。

## 项目概览

- **技术栈**: Vue3 + ElementPlus + Vite (前端), FastAPI (后端), ChromaDB (向量数据库), SQLAlchemy + MySQL/SQLite (业务数据库)
- **核心功能**: 文档上传入库、RAG 智能问答、多 LLM 切换、流式 SSE 输出、语音输入/播报、KPI 仪表盘
- **LLM 支持**: Ollama (本地) / DeepSeek / Kimi / 离线模板
- **当前阶段**: 端到端 RAG 管线已打通，双路并行回答（RAG 增强 + 纯 LLM），流式 SSE 可用，语音交互可用

---

## 快速开始

### 环境要求

| 依赖 | 最低版本 | 说明 |
|------|----------|------|
| Python | 3.10+ | 推荐 3.11+ |
| Node.js | 16+ | 推荐 18+ |
| npm | 8+ | 随 Node.js 安装 |
| Chrome / Edge | 最新版 | 语音功能需要 Web Speech API |

### 1. 后端启动

```bash
# 在项目根目录下执行

# 创建虚拟环境（首次）
py -3 -m venv venv

# 安装 Python 依赖
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# 启动后端服务
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8080
```

后端运行在 http://127.0.0.1:8080 ，API 文档 http://127.0.0.1:8080/docs

验证后端是否启动成功：

```bash
curl http://127.0.0.1:8080/
# 返回 {"status":"ok","message":"水利工程智能问答系统 API 运行中"}
```

### 2. 前端启动

```bash
cd frontend

# 安装前端依赖（首次）
npm install

# 启动开发服务器
npm run dev
```

浏览器访问 http://localhost:3000

前端通过 Vite 代理将 `/api` 请求转发到后端 `http://127.0.0.1:8080`。

### 3. 配置 LLM 模型

打开页面后，在聊天输入框上方的模型选择栏中：

| 模型 | 说明 | 需要配置 |
|------|------|----------|
| Ollama (本地) | 默认首选，需本地安装 Ollama | `ollama pull qwen2:7b` |
| DeepSeek | 国内大模型 API，推荐 | [获取 API Key](https://platform.deepseek.com) |
| Kimi (Moonshot) | 国内大模型 API | [获取 API Key](https://platform.moonshot.cn) |
| 离线模板 | 无需外部服务，返回检索片段 | 无需配置 |

点击模型栏右侧的「API Key」按钮进入设置弹窗：
1. 选择供应商
2. 填入 API Key（Ollama 和离线模式无需 Key）
3. 点击「测试连接」验证
4. 点击「保存」

每个模型的 API Key 独立存储，切换模型不会串。

**也可以直接编辑 `.env` 文件配置（后端全局默认）：**

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-key-here
```

### 4. 上传知识文档

在右侧面板拖拽上传 PDF / DOCX / TXT 水利规范文档。系统自动完成：

```
文本提取 → 分块 (500字/块, 50字重叠) → 向量化 → ChromaDB 入库
```

项目自带测试文档 `test_water_doc.txt` 和 `data/water_spec.txt` 可用于快速验证。

上传后即可在左侧聊天区提问。系统检索知识库后并行生成两路回答：
- **知识库增强回答**：基于检索到的规范文档，引用具体条款
- **AI 独立回答**：纯 LLM 基于自身知识回答，供对比参考

---

## 核心功能

### 智能问答（RAG + LLM 双路并行）

- 用户提问后，系统先从 ChromaDB 检索相关知识片段
- 若知识库内容与问题相关（余弦距离 < 0.65），并行生成两路回答：
  - **RAG 增强回答**：结合检索到的规范文档条款
  - **纯 LLM 回答**：不依赖知识库，供对比参考
- 若知识库无相关内容，仅输出纯 LLM 回答
- 支持**普通模式**和**流式 SSE 模式**，通过界面开关切换

### 流式输出 (SSE)

- 后端 `/query/stream` 端点通过 Server-Sent Events 流式推送
- 先返回检索元信息（匹配状态、引用来源），再逐 token 推送回答内容
- 前端实时渲染，无需等待完整回答

### 多 LLM 供应商切换

- 聊天界面顶部有模型选择栏，一键切换
- 每个模型的 API Key 独立存储于 localStorage
- 实时显示当前模型是否有有效配置
- LLM 调用失败自动回退离线模板

### 语音交互

- **语音输入**：基于浏览器 Web Speech API，点击麦克风按钮说话，实时转写显示，点击「完成」发送
- **语音播报**：点击 AI 回答下方的喇叭按钮，TTS 朗读回答内容

### 文档管理

- 支持 PDF / DOCX / TXT 格式，单文件限 20MB
- 使用 `sentence-transformers` 生成 384 维向量，ChromaDB 持久化存储
- 检索结果经 n-gram Jaccard 去重和子串包含检测，最多保留 2 条

---

## 项目结构

```
├── README.md
├── requirements.txt                  # Python 依赖
├── .env                              # 环境变量（LLM API Key 等）
├── .gitignore
├── test_water_doc.txt                # 测试用文档
├── frontend/                         # 前端 (Vue3 + ElementPlus + Vite)
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js                # 开发代理 /api → :8080
│   └── src/
│       ├── main.js                   # 入口：挂载 ElementPlus + Router
│       ├── App.vue                   # 根布局（顶栏 + router-view）
│       ├── router/index.js           # 路由（Hash 模式）
│       ├── api/index.js              # Axios API 层 + fetch SSE
│       └── components/
│           ├── Dashboard.vue         # 仪表盘主页（KPI 卡片 + 聊天 + 上传面板）
│           ├── ChatInterface.vue     # 聊天界面（消息列表 + 模型栏 + 语音 + 流式切换）
│           ├── SettingsDialog.vue    # LLM 设置弹窗（API Key 管理 + 连接测试）
│           └── FileUpload.vue        # 文档拖拽上传
├── backend/                          # 后端 (FastAPI)
│   ├── __init__.py
│   ├── main.py                       # API 路由（含 Pydantic 模型定义）
│   ├── utils.py                      # 文本提取、分块、向量化、ChromaDB 操作
│   ├── config.py                     # 全系统配置（含 Redis/Milvus 预留）
│   ├── database.py                   # SQLAlchemy ORM（User/Conversation/Message/KnowledgeDocument）
│   └── .env                          # 数据库连接配置
├── rag_system/                       # RAG 核心模块
│   ├── __init__.py
│   ├── main.py                       # process_query() 检索→去重→并行生成双路回答
│   ├── utils.py                      # Prompt 构建 + generate_answer() 封装
│   └── llm_client.py                 # 多供应商 LLM 客户端（流式 + 非流式）
├── data/                             # 示例/测试文档
└── chroma_db/                        # ChromaDB 持久化数据（运行时生成）
```

---

## 后端 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| GET | `/status/` | 系统状态（LLM 供应商及可用性） |
| POST | `/upload/` | 上传文档（multipart/form-data） |
| POST | `/query/` | 知识库问答 `{query, top_k, ?llm_config}`，返回双路回答 |
| POST | `/query/stream` | 流式问答（SSE），先返检索元信息再逐 token 推送 |
| POST | `/test-llm/` | 测试 LLM 连接 `{provider, api_key, api_base, model}` |

### `/query/` 响应结构

```json
{
  "query": "大坝安全监测有哪些要求？",
  "relevant": true,
  "contexts": [
    {
      "filename": "水利规范.pdf",
      "excerpt": "大坝安全监测应符合 DL/T 5144-2015...",
      "distance": 0.234
    }
  ],
  "rag_answer": "【结论】...",
  "llm_answer": "【结论】..."
}
```

### `/query/stream` SSE 事件类型

| event.type | 说明 |
|------------|------|
| `meta` | 检索元信息：`{relevant, contexts}` |
| `rag_start` | RAG 增强回答开始 |
| `rag_token` | RAG 回答 token |
| `rag_end` | RAG 回答结束 |
| `llm_start` | 纯 LLM 回答开始 |
| `llm_token` | LLM 回答 token |
| `done` | 全部完成 |

---

## 架构说明

### RAG 查询流程

```
用户提问 → ChromaDB 向量检索 → 结果去重(Jaccard) → 相关性判断
                                                          ↓
                              相关 → 并行生成（RAG 增强回答 + 纯 LLM 回答）→ 返回
                              不相关 → 仅生成纯 LLM 回答 → 返回
```

- **检索**: `sentence-transformers` 生成 384 维向量，ChromaDB 余弦相似度检索
- **去重**: 基于 n-gram Jaccard 相似度和子串包含检测，最多保留 2 条去重结果
- **相关性阈值**: 余弦距离 < 0.65 视为匹配知识库
- **生成**: 优先使用用户选择的 LLM，API 调用失败自动回退离线模板
- **Prompt**: 三段式结构（结论 → 依据 → 建议），统一回答格式

### 数据库

- **ChromaDB**: 向量数据库，存储文档 Embedding，持久化于 `chroma_db/`，使用余弦相似度
- **业务数据库**: SQLAlchemy ORM，连接 MySQL (`127.0.0.1:3306/hydrau_db`)，配置在 `backend/.env` 中
- **数据模型**: User / Conversation / Message / KnowledgeDocument（ORM 模型已定义，API 接口待对接）

### 嵌入模型

- 默认使用 `paraphrase-multilingual-MiniLM-L12-v2`（多语言，384 维）
- 首次使用自动从 Hugging Face 下载（约 120MB），国内已配置 `hf-mirror.com` 镜像
- 下载失败自动回退 dummy embedding（全零向量），系统仍可运行但检索质量下降
- 模型在服务启动时预加载，消除首次请求冷启动延迟

### LLM 调用链

```
用户配置(localStorage) > .env 全局配置 > 离线模板回退
```

- DeepSeek / Kimi：OpenAI 兼容 API（`/v1/chat/completions`）
- Ollama：Ollama 原生 API（`/api/generate`）
- 离线模板：按三段式格式组织检索到的文档片段

---

## 配置说明

### 全局 .env（项目根目录）

```bash
# Hugging Face 镜像（国内用户必须设置）
HF_ENDPOINT=https://hf-mirror.com

# 默认 LLM 供应商（界面切换会覆盖此设置）
LLM_PROVIDER=deepseek

# DeepSeek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_MODEL=deepseek-chat

# Kimi
KIMI_API_KEY=sk-xxx
KIMI_MODEL=moonshot-v1-8k

# Ollama
OLLAMA_API_BASE=http://localhost:11434
OLLAMA_MODEL=qwen2:7b
```

### 数据库 .env（`backend/.env`）

```bash
# MySQL 业务数据库
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DB=hydrau_db

# Redis（配置预留，当前未激活）
REDIS_HOST=127.0.0.1
REDIS_PORT=6379

# Milvus（配置预留，当前使用 ChromaDB）
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
```

---

## 常见问题

### 1. 虚拟环境 Python 找不到

```
No Python at 'C:\Users\xxx\...\python.exe'
```

虚拟环境记录了创建时的 Python 路径，更换用户或移动目录后会失效。删除 `venv` 目录重新创建：

```bash
Remove-Item -Recurse -Force venv
py -3 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Embedding 模型下载失败

日志出现 `Error while downloading from https://...`：

- 模型下载需要访问 HuggingFace CDN，国内网络可能超时
- 系统会自动回退 dummy embedding，问答和检索功能不受影响
- 如需完整向量检索，可尝试手动下载模型放入 HF 缓存目录

### 3. LLM 返回离线模板回答

回答中包含「点击右上角设置按钮，配置 API Key」的提示，说明未配置有效的 API Key：

- 检查 `.env` 中 API Key 是否填写
- 或在页面 UI 中通过「API Key」按钮配置并保存（配置存储在浏览器 localStorage）
- 使用「测试连接」按钮验证 Key 是否有效

### 4. Ollama 连接失败

- 确保本地已安装 Ollama 并拉取模型：`ollama pull qwen2:7b`
- 确认 Ollama 服务正在运行，默认地址为 `http://localhost:11434`
- 可在设置弹窗中修改 Ollama 地址和模型名称

### 5. 端口被占用

```bash
# 查看占用 8080 端口的进程
netstat -ano | findstr :8080
# 查看占用 3000 端口的进程
netstat -ano | findstr :3000
```

---

## 开发计划

- [x] 系统架构搭建、后端基础框架
- [x] 真实 RAG 管线、文档上传与向量入库
- [x] 前端界面、多 LLM 支持与切换
- [x] 语音交互（输入 + 播报）
- [x] 流式 SSE 输出
- [x] 双路并行回答（RAG 增强 + 纯 LLM）
- [x] 数据库 ORM 模型定义（User/Conversation/Message/KnowledgeDocument）
- [x] 对话历史 API 对接与多轮对话
- [x] 用户管理与认证（JWT + bcrypt）
- [x] 监测数据可视化增强（ECharts 动态图表）
- [x] 容器化部署（Docker + docker-compose）
