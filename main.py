"""
main.py

主程序：把整个流程串起来，适合直接在 GitHub Actions 定时运行。

保留的功能点（与你需求一致）：
- 近 3 个月在线发表（用 OpenAlex 的 publication_date 过滤；缺日期则尽量不选入）
- 只保留 JCR Q1 期刊（公开接口不保证提供 JCR 分区 → 默认使用 data/journals_q1.csv 白名单）
- 生态、公共管理、经济学交叉领域（用 settings.json 里的关键词组合检索）
- 提取字段：标题、作者、摘要、研究方法、期刊、链接
- 生成 Excel 表格
- 163 邮箱自动发送，标题固定：院士请看文献_YYYYMMDD
- 使用 GPT 抽取研究方法
- 支持 GitHub Actions 部署
- 保留配置文件、邮件模块、Excel 模块（均复用现有 modules/ 下代码）

说明（重要）：
- OpenAlex/Crossref 都是免费公开接口，不需要 API Key。
- “JCR Q1”在公开接口里通常拿不到，因此强烈建议你维护 Q1 白名单：
  literature_pusher/data/journals_q1.csv
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode

import requests

from config import load_secrets
from modules.email_sender import SmtpConfig, build_subject_today, send_email_with_attachment
from modules.excel_writer import ExcelRow, write_excel
from modules.gpt_extractor import GptClientConfig, MethodExtractor
from modules.journal_filter import filter_papers_by_journal_tier
from modules.settings_store import SettingsStore
from modules.wos_client import Paper  # 复用已有 Paper 数据结构，减少改动面


def _fail(msg: str) -> None:
    """统一错误退出，方便 GitHub Actions 看日志定位问题。"""
    print(msg, file=sys.stderr)
    raise SystemExit(1)


def _date_str(d: dt.date) -> str:
    """把日期转成 OpenAlex/Crossref 常用的 YYYY-MM-DD 字符串。"""
    return d.strftime("%Y-%m-%d")


def _reconstruct_openalex_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """
    OpenAlex 的摘要经常以 abstract_inverted_index 形式提供：
    - key: 词
    - value: 该词在摘要中的位置列表

    我们把它复原成可读摘要（尽量还原原顺序）。
    """
    if not inverted_index:
        return ""
    positions: dict[int, str] = {}
    for word, idxs in inverted_index.items():
        for i in idxs:
            # 若同一位置发生冲突，保留先到的即可
            positions.setdefault(int(i), word)
    if not positions:
        return ""
    return " ".join(positions[i] for i in sorted(positions.keys()))


def _safe_get(d: dict[str, Any], path: Iterable[str], default: Any = None) -> Any:
    """安全地从嵌套 dict 中取值：取不到就返回 default。"""
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def _crossref_get_abstract_by_doi(crossref_base_url: str, doi: str, timeout_s: int = 30) -> str:
    """
    Crossref 有时会返回 abstract（通常为 JATS/HTML 片段），并不保证每篇都有。
    这里做“尽力而为”的补全：
    - 有就补
    - 没有就返回空
    """
    doi = (doi or "").strip()
    if not doi:
        return ""

    url = f"{crossref_base_url.rstrip('/')}/works/{doi}"
    headers = {
        # Crossref 建议加一个 mailto，方便他们联系你；不影响运行
        "User-Agent": "literature-pusher/1.0 (mailto:example@example.com)",
        "Accept": "application/json",
    }

    try:
        r = requests.get(url, headers=headers, timeout=timeout_s)
        if r.status_code != 200:
            return ""
        msg = r.json().get("message", {})
        abstract = msg.get("abstract") or ""
        # abstract 可能是带标签的字符串；这里先原样返回（Excel/邮件里一般可读性够用）
        return str(abstract).strip()
    except Exception:
        return ""


def _openalex_search(
    openalex_base_url: str,
    keywords: list[str],
    from_date: dt.date,
    to_date: dt.date,
    max_records: int,
    timeout_s: int = 60,
) -> list[Paper]:
    """
    使用 OpenAlex Works 接口检索近 3 个月文献。

    为什么不把“生态+公管+经济学交叉”写死成某个学科分类？
    - 公开接口的分类体系与“你的研究方向”往往不是一一对应；
    - 用“关键词集合 + 时间过滤 + Q1 白名单”是更稳定、可维护的工程方案；
    - 你后续也可以在网页后台直接改关键词，立刻生效。

    OpenAlex Filters 参考：
    https://docs.openalex.org/api-entities/works/filter-works
    """
    if not keywords:
        raise ValueError("settings.query.keywords 不能为空，请在 data/settings.json 中填写关键词。")

    base = openalex_base_url.rstrip("/") + "/works"
    # OpenAlex search 是“全文相关性”风格：我们把关键词拼成一串文本即可
    search_text = " ".join([k.strip() for k in keywords if k.strip()])

    filters = ",".join(
        [
            f"from_publication_date:{_date_str(from_date)}",
            f"to_publication_date:{_date_str(to_date)}",
            # 尽量贴近“文章/综述”的需求（OpenAlex 的 type 有时是 article/review）
            "type:article|review",
        ]
    )

    per_page = min(200, max_records)  # OpenAlex 单页上限通常为 200
    cursor = "*"  # cursor pagination（OpenAlex 推荐用 cursor 而不是 page）

    out: list[Paper] = []
    headers = {
        "Accept": "application/json",
        "User-Agent": "literature-pusher/1.0 (mailto:example@example.com)",
    }

    while len(out) < max_records:
        params = {
            "search": search_text,
            "filter": filters,
            "per-page": per_page,
            "cursor": cursor,
            "sort": "publication_date:desc",  # 新发表优先
        }
        url = f"{base}?{urlencode(params)}"
        resp = requests.get(url, headers=headers, timeout=timeout_s)
        if resp.status_code != 200:
            raise RuntimeError(f"OpenAlex 请求失败: {resp.status_code} {resp.text[:300]}")

        payload = resp.json()
        results = payload.get("results", []) or []
        if not results:
            break

        for w in results:
            title = (w.get("title") or "").strip()
            published_date = (w.get("publication_date") or "").strip()
            if not title:
                continue
            # 若 publication_date 缺失，这里仍先保留（后续你可改成严格剔除）
            # 但一般 OpenAlex 大多数 works 都有 publication_date。

            # 作者：OpenAlex authorships 里包含 author.display_name
            authorships = w.get("authorships") or []
            author_names: list[str] = []
            for a in authorships:
                n = _safe_get(a, ["author", "display_name"], "") or ""
                if n:
                    author_names.append(str(n))
            authors = ", ".join(author_names)

            # 期刊名：优先 primary_location.source.display_name，其次 host_venue.display_name
            journal = (
                _safe_get(w, ["primary_location", "source", "display_name"], "")
                or _safe_get(w, ["host_venue", "display_name"], "")
                or ""
            )

            # 链接：优先 DOI（OpenAlex 通常提供 https://doi.org/...），否则用 OpenAlex work id（也是个 URL）
            doi = (w.get("doi") or "").strip()
            url_link = (w.get("id") or "").strip()
            if doi:
                url_link = doi

            abstract = _reconstruct_openalex_abstract(w.get("abstract_inverted_index"))

            # quartile：公开接口通常拿不到 JCR 分区，因此置空，交给白名单过滤
            out.append(
                Paper(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    journal=str(journal).strip(),
                    url=str(url_link).strip(),
                    published_date=published_date,
                    jcr_quartile=None,
                )
            )

            if len(out) >= max_records:
                break

        cursor = payload.get("meta", {}).get("next_cursor")
        if not cursor:
            break

    return out[:max_records]


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    settings_path = repo_root / "data" / "settings.json"

    secrets = load_secrets()
    settings = SettingsStore(settings_path).load()

    # 机密信息校验：缺失就直接给出明确报错（GitHub Actions 里更好排查）
    if not secrets.email_user or not secrets.email_pass:
        _fail("缺少环境变量 EMAIL_163_USER / EMAIL_163_PASS（163 SMTP 授权码）。")
    if settings.gpt.enabled and not secrets.openai_api_key:
        _fail("已启用 GPT 抽取，但缺少环境变量 OPENAI_API_KEY。")

    # -----------------------------
    # 1) 拉取文献：OpenAlex（主）+ Crossref（补摘要）
    # -----------------------------
    today = dt.date.today()
    from_date = today - dt.timedelta(days=settings.time_window_days)
    to_date = today

    papers = _openalex_search(
        openalex_base_url=secrets.openalex_base_url,
        keywords=settings.query.keywords,
        from_date=from_date,
        to_date=to_date,
        max_records=settings.max_records,
    )

    # 若摘要缺失，尝试用 Crossref 按 DOI 补一下
    for i, p in enumerate(papers):
        if p.abstract:
            continue

        # DOI 可能是 https://doi.org/xxx，也可能是 10.xxxx/xxxx
        doi = p.url
        if doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "").strip()
        if doi.startswith("http://doi.org/"):
            doi = doi.replace("http://doi.org/", "").strip()

        if doi.startswith("10."):
            abstract = _crossref_get_abstract_by_doi(secrets.crossref_base_url, doi)
            if abstract:
                papers[i] = Paper(
                    title=p.title,
                    authors=p.authors,
                    abstract=abstract,
                    journal=p.journal,
                    url=p.url,
                    published_date=p.published_date,
                    jcr_quartile=p.jcr_quartile,
                )

    # -----------------------------
    # 2) 期刊质量过滤：JCR Q1（默认走白名单 data/journals_q1.csv）
    # -----------------------------
    papers = filter_papers_by_journal_tier(papers, settings.journal_filter)

    # -----------------------------
    # 3) GPT 方法抽取
    # -----------------------------
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

    # -----------------------------
    # 4) 导出 Excel
    # -----------------------------
    out_name = f"literature_{build_subject_today().split('_')[-1]}.xlsx"
    out_path = repo_root / "output" / out_name
    excel_path = write_excel(rows, out_path)

    # -----------------------------
    # 5) 发送邮件（163 SMTP）
    # -----------------------------
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
        f"数据源：OpenAlex + Crossref（公开免费接口）\n"
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
