"""
config.py

这一层只做两件事：
1) 读取环境变量（适配 GitHub Actions Secrets / 本地 .env）
2) 统一给主程序提供“运行所需的机密信息与基础常量”

说明：
- 可被网页后台在线修改的“业务配置”（关键词、频率、收件人、返回数量等）
  不放在环境变量里，而是放在 data/settings.json 中，便于即时生效。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()  # 允许本地使用 .env；在 GitHub Actions 中则来自 Secrets


@dataclass(frozen=True)
class Secrets:
    # 数据源（完全免费、无需 API Key）
    # OpenAlex: https://docs.openalex.org/
    openalex_base_url: str = "https://api.openalex.org"
    # Crossref: https://api.crossref.org/
    crossref_base_url: str = "https://api.crossref.org"

    # 163 SMTP
    email_user: str = ""
    email_pass: str = ""  # SMTP 授权码（不是登录密码）
    smtp_host: str = "smtp.163.com"
    smtp_port_ssl: int = 465

    # GPT（OpenAI 兼容）
    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_model: str = "gpt-4.1-mini"


def load_secrets() -> Secrets:
    """
    读取机密信息。如果缺失，会在 main.py 里统一报错提示。
    """
    return Secrets(
        openalex_base_url=os.getenv("OPENALEX_BASE_URL", "https://api.openalex.org").strip(),
        crossref_base_url=os.getenv("CROSSREF_BASE_URL", "https://api.crossref.org").strip(),
        email_user=os.getenv("EMAIL_163_USER", "").strip(),
        email_pass=os.getenv("EMAIL_163_PASS", "").strip(),
        smtp_host=os.getenv("SMTP_HOST", "smtp.163.com").strip(),
        smtp_port_ssl=int(os.getenv("SMTP_PORT_SSL", "465").strip()),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "").strip() or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
    )
