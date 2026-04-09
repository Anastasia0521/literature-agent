"""
main.py

主程序：把整个流程串起来，适合直接在 GitHub Actions 定时运行。

流程：
1) 读取机密信息（WoS API Key、163 SMTP 授权码、OpenAI Key）
2) 读取业务配置（data/settings.json）
3) 生成 WoS 检索式并拉取近 3 个月文献
4) 按 JCR Q1（或你配置的等级）做过滤
5) 使用 GPT 抽取“研究方法”
6) 生成 Excel
7) 通过 163 邮件推送
"""

from __future__ import annotations

import sys
from pathlib import Path

from config import load_secrets
from modules.email_sender import SmtpConfig, build_subject_today, send_email_with_attachment
from modules.excel_writer import ExcelRow, write_excel
from modules.gpt_extractor import GptClientConfig, MethodExtractor
from modules.journal_filter import filter_papers_by_journal_tier
from modules.settings_store import SettingsStore
from modules.wos_client import WosClient, build_wos_query


def _fail(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    settings_path = repo_root / "data" / "settings.json"

    secrets = load_secrets()
    settings = SettingsStore(settings_path).load()

    # 机密信息校验：缺失就直接给出明确报错（GitHub Actions 里更好排查）
    if not secrets.wos_api_key:
        _fail("缺少环境变量 WOS_API_KEY（Web of Science API Key）。")
    if not secrets.email_user or not secrets.email_pass:
        _fail("缺少环境变量 EMAIL_163_USER / EMAIL_163_PASS（163 SMTP 授权码）。")
    if settings.gpt.enabled and not secrets.openai_api_key:
        _fail("已启用 GPT 抽取，但缺少环境变量 OPENAI_API_KEY。")

    query = build_wos_query(settings.query.keywords, settings.query.additional_filter)
    wos = WosClient(base_url=secrets.wos_base_url, api_key=secrets.wos_api_key)
    papers = wos.search_recent_papers(
        query=query,
        max_records=settings.max_records,
        days=settings.time_window_days,
    )

    papers = filter_papers_by_journal_tier(papers, settings.journal_filter)

    # GPT 方法抽取
    extractor: MethodExtractor | None = None
    if settings.gpt.enabled:
        extractor = MethodExtractor(
            GptClientConfig(
                api_key=secrets.openai_api_key,
                base_url=secrets.openai_base_url,
                model=secrets.openai_model,
            )
        )

    rows: list[ExcelRow] = []
    for p in papers:
        method = ""
        if extractor:
            method = extractor.extract_method(
                title=p.title,
                abstract=p.abstract,
                max_chars=settings.gpt.max_chars_from_abstract,
            )
        rows.append(
            ExcelRow(
                title=p.title,
                authors=p.authors,
                abstract=p.abstract,
                method=method,
                journal=p.journal,
                url=p.url,
            )
        )

    # 导出 Excel
    out_name = f"literature_{build_subject_today().split('_')[-1]}.xlsx"
    out_path = repo_root / "output" / out_name
    excel_path = write_excel(rows, out_path)

    # 发送邮件
    smtp = SmtpConfig(
        host=secrets.smtp_host,
        port_ssl=secrets.smtp_port_ssl,
        user=secrets.email_user,
        password=secrets.email_pass,
    )

    subject = build_subject_today()
    body = (
        f"今日推送文献数：{len(rows)}\n"
        f"检索关键词：{', '.join(settings.query.keywords)}\n"
        f"时间窗口：近 {settings.time_window_days} 天\n"
        f"期刊筛选：{settings.journal_filter.tier}\n"
    )

    send_email_with_attachment(
        smtp=smtp,
        to_addrs=settings.email.to,
        cc_addrs=settings.email.cc,
        subject=subject,
        body_text=body,
        attachment_path=str(excel_path) if settings.email.send_excel_as_attachment else None,
    )

    print(f"完成：已生成 {excel_path} 并发送邮件。")


if __name__ == "__main__":
    main()

