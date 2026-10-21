"""项目公共路径与环境变量。

数据层与工具层只依赖本模块读取配置，Agent / UI 层可在此基础上扩展。
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "volunteer_demo.db"
DEFAULT_WORKSPACE = ROOT / "workspace"


def load_env() -> None:
    """加载仓库根目录的 .env；未安装 python-dotenv 时静默跳过。"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def db_path() -> Path:
    load_env()
    return Path(os.getenv("VOLUNTEER_DB", str(DEFAULT_DB)))


def workspace_dir() -> Path:
    load_env()
    path = Path(os.getenv("WORKSPACE_DIR", str(DEFAULT_WORKSPACE)))
    path.mkdir(parents=True, exist_ok=True)
    return path
