"""pytest 全局 fixture 与配置"""
import sys
import os
import pytest

# 把项目根目录加入 import 路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(scope="session")
def project_root():
    """项目根目录路径"""
    return PROJECT_ROOT


@pytest.fixture
def temp_txt_file(tmp_path):
    """创建一个临时 TXT 文件"""
    def _create(content: str, suffix: str = ".txt") -> str:
        p = tmp_path / f"sample{suffix}"
        p.write_text(content, encoding="utf-8")
        return str(p)
    return _create
