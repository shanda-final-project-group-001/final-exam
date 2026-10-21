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


def _resolve(raw: str, default: Path) -> Path:
    """环境变量里的相对路径按仓库根目录解析，避免受启动目录影响。"""
    path = Path(raw) if raw else default
    return path if path.is_absolute() else ROOT / path


def db_path() -> Path:
    load_env()
    return _resolve(os.getenv("VOLUNTEER_DB", ""), DEFAULT_DB)


def workspace_dir() -> Path:
    load_env()
    path = _resolve(os.getenv("WORKSPACE_DIR", ""), DEFAULT_WORKSPACE)
    path.mkdir(parents=True, exist_ok=True)
    return path
