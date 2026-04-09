import os
import smtplib
import requests
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import datetime
from datetime import date, timedelta

# 邮箱配置
EMAIL_USER = os.environ.get("EMAIL_163_USER", "")
EMAIL_PASS = os.environ.get("EMAIL_163_PASS", "")
RECEIVER = EMAIL_USER

# ===================== 你的精准 PRISMA 关键词 =====================
topic_keywords = (
    '"Payment for ecosystem services" OR "Payment for environmental services" OR PES '
    'OR "Eco-compensation" OR "Ecological compensation"'
)

attribute_keywords = (
    'Dynamic OR Non-equilibrium OR Spatiotemporal OR "Spatio-temporal" OR Time-varying '
    'OR Threshold OR Non-linear OR Fluctuation OR Uncertainty OR "Adaptive management" '
    'OR Trans-boundary OR Transboundary OR Horizontal OR "Inter-jurisdictional" OR Inter-regional '
    'OR "Upstream-downstream" OR "Upstream-downstream cooperation" OR Cross-border '
    'OR "User-financed" OR "Market-based" OR Coasean OR "Private-to-private" OR Cost-sharing '
    'OR "Tradable permit" OR "Trading scheme"'
)

# 组合成精准检索式
KEYWORD = f"({topic_keywords}) AND ({attribute_keywords})"
# =================================================================

def get_real_literature():
    one_year_ago = (date.today() - timedelta(days=365)).isoformat()

    params = {
        "query": KEYWORD,
        "filter": f"from-pub-date:{one_year_ago},type:journal-article",
        "rows": 10,
        "sort": "published"
    }

    r = requests.get("https://api.crossref.org/works", params=params, timeout=30)
    data = r.json()

    papers = []
    for item in data.get("message", {}).get("items", []):
        title = item.get("title", [None])[0]
        if not title:
            continue

        authors = []
        for a in item.get("author", []):
            given = a.get("given", "")
            family = a.get("family", "")
            if given and family:
                authors.append(f"{given} {family}")
        author_str = "; ".join(authors[:3])

        journal = item.get("container-title", [None])[0]
        year = item.get("published", {}).get("date-parts", [[None]])[0][0]
        doi = item.get("DOI", None)
        abstract = item.get("abstract", "")
        if abstract:
            abstract = abstract[:300] + "..."

        papers.append([title, author_str, journal, year, doi, abstract])

    df = pd.DataFrame(papers, columns=["标题", "作者", "期刊", "年份", "DOI", "摘要"])
    return df

def send_email(df):
    today_str = datetime.date.today().strftime("%Y%m%d")
    filename = f"literature_{today_str}.xlsx"
    df.to_excel(filename, index=False)

    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = RECEIVER
    msg["Subject"] = f"院士请看文献_{today_str}"

    body = (
        "✅ 本周精准文献推送（生态补偿 / PES / 动态时空 / 跨区域）\n"
        "完全基于你的 PRISMA 检索策略，高度相关。"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with open(filename, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename={filename}")
    msg.attach(part)

    server = smtplib.SMTP_SSL("smtp.163.com", 465)
    server.login(EMAIL_USER, EMAIL_PASS)
    server.sendmail(EMAIL_USER, RECEIVER, msg.as_string())
    server.quit()

if __name__ == "__main__":
    df = get_real_literature()
    send_email(df)
    print("✅ 精准文献推送完成")
