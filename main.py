import os
import smtplib
import requests
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import datetime

# 邮箱配置
EMAIL_USER = os.environ.get("EMAIL_163_USER", "")
EMAIL_PASS = os.environ.get("EMAIL_163_PASS", "")
RECEIVER = EMAIL_USER

# 研究方向：生态 + 公共管理 + 经济
KEYWORD = "ecology public management environmental policy"

def get_real_literature():
    print("正在抓取真实最新文献...")
    url = "https://api.openalex.org/works"
    params = {
        "filter": (
            f"default.search:{KEYWORD},"
            "publication_date:>2025-01-01,"
            "is_oa:true,"
            "type:article"
        ),
        "sort": "publication_date:desc",
        "per-page": 8
    }

    r = requests.get(url, params=params, timeout=30)
    data = r.json()

    papers = []
    for work in data.get("results", []):
        title = work.get("title", "")
        pub_date = work.get("publication_date", "")
        journal = work.get("host_venue", {}).get("display_name", "Unknown Journal")
        doi = work.get("doi", "")
        abstract = work.get("abstract", "")[:300] + "..." if work.get("abstract") else ""

        authors = []
        for a in work.get("authorships", []):
            author = a.get("author", {}).get("display_name", "")
            if author:
                authors.append(author)
        authors_str = "; ".join(authors[:3])

        papers.append([title, authors_str, journal, pub_date, doi, abstract])

    df = pd.DataFrame(papers, columns=[
        "标题", "作者", "期刊", "发表日期", "DOI", "摘要"
    ])
    return df

def send_email(df):
    today = datetime.date.today().strftime("%Y%m%d")
    filename = f"literature_{today}.xlsx"
    df.to_excel(filename, index=False)

    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = RECEIVER
    msg["Subject"] = f"院士请看文献_{today}"

    body = "最新真实文献已推送，包含标题、作者、期刊、日期、DOI、摘要。"
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
    print("✅ 真实文献推送完成")
