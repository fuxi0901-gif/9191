"""
FastAPI 接口集成测试
覆盖：健康检查、注册/登录、Token 验证、监测数据、对话接口鉴权
"""
import pytest
from fastapi.testclient import TestClient

# 注意：导入时即触发后端初始化，MySQL 不可用会自动回退 SQLite
from backend.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ---------- 公开端点 ----------

def test_health_check(client):
    """根路径应返回 200 + status ok"""
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"


def test_system_status(client):
    """状态端点应返回 LLM 配置信息"""
    r = client.get("/status/")
    assert r.status_code == 200
    body = r.json()
    assert "llm_provider" in body
    assert "llm_available" in body


# ---------- 用户认证 ----------

def test_register_login_flow(client):
    """完整流程：注册 → 登录 → 获取自己信息"""
    import time
    suffix = str(int(time.time() * 1000))[-8:]
    username = f"testuser_{suffix}"
    password = "testpass123"

    # 1. 注册（接口声明 status_code=201）
    r = client.post("/register/", json={"username": username, "password": password})
    assert r.status_code in (200, 201), r.text
    body = r.json()
    token = body.get("access_token")
    assert token is not None and len(token) > 10

    # 2. 登录（独立）
    r = client.post("/login/", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    assert "access_token" in r.json()

    # 3. 用 token 访问 /users/me/
    r = client.get("/users/me/", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["username"] == username


def test_register_duplicate_username(client):
    """重复注册应失败（业务层使用 HTTPException 400 或 status=error）"""
    import time
    username = f"dup_{int(time.time() * 1000)}"
    client.post("/register/", json={"username": username, "password": "123456"})
    r = client.post("/register/", json={"username": username, "password": "123456"})
    # 业务层会返回 400 或 200(带 status=error)，只要不成功即可
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        body = r.json()
        assert body.get("status") == "error" or "已存在" in body.get("detail", "")


def test_login_wrong_password(client):
    """错误密码应返回 401 或登录失败"""
    import time
    username = f"wp_{int(time.time() * 1000)}"
    client.post("/register/", json={"username": username, "password": "right_pwd"})
    r = client.post("/login/", json={"username": username, "password": "wrong_pwd"})
    # 业务层可能返回 401 或 200(带 status=error)
    assert r.status_code in (200, 401, 400)
    if r.status_code == 200:
        assert r.json().get("status") == "error"


# ---------- 鉴权保护 ----------

def test_get_users_me_no_token(client):
    """不带 token 访问受保护端点应 401 或 403"""
    r = client.get("/users/me/")
    assert r.status_code in (401, 403)


def test_get_users_me_invalid_token(client):
    """伪造 token 应被拒"""
    r = client.get("/users/me/", headers={"Authorization": "Bearer fake.invalid.token"})
    assert r.status_code in (401, 403)


# ---------- 监测数据 ----------

def test_monitoring_water_level(client):
    """水位数据应返回最新值 + 时间点数组"""
    r = client.get("/monitoring/?data_type=water_level")
    assert r.status_code == 200
    body = r.json()
    assert "latest_value" in body
    assert "points" in body
    assert isinstance(body["points"], list)
    assert len(body["points"]) > 0


def test_monitoring_rainfall(client):
    """雨量数据应正常返回"""
    r = client.get("/monitoring/?data_type=rainfall")
    assert r.status_code == 200
    body = r.json()
    assert "points" in body
    assert len(body["points"]) > 0


def test_monitoring_unknown_type(client):
    """未知类型应返回模拟数据或空，不崩溃"""
    r = client.get("/monitoring/?data_type=unknown_type_xyz")
    # 后端实现是任何类型都返回模拟数据
    assert r.status_code == 200


# ---------- 上传 / 问答（公开接口契约）----------

def test_upload_without_filename(client):
    """上传缺少文件字段应返回 422（FastAPI 自动校验）"""
    r = client.post("/upload/")
    assert r.status_code in (400, 415, 422)


def test_query_with_empty_body(client):
    """问答空请求体应被 FastAPI 校验拒绝 422 或 500"""
    r = client.post("/query/", json={})
    # 缺必填参数
    assert r.status_code in (422, 500)
