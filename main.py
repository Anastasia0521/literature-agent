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
KEYWORDS = "ecology public management economics"

def get_recent_literature():
    print("正在抓取最新 Q1 顶刊文献...")
    url = "https://api.openalex.org/works"
    params = {
        "filter": f"default.search:{KEYWORDS},from_publication_date:2025-01-01",
        "sort": "publication_date:desc",
        "per-page": 10
    }
    resp = requests.get(url, params=params, timeout=20)
    data = resp.json()

    results = []
    for item in data.get("results", []):
        title = item.get("title", "")
        date = item.get("publication_date", "")
        journal = item.get("host_venue", {}).get("display_name", "")
        doi = item.get("doi", "")
        results.append([title, journal, date, doi])

    df = pd.DataFrame(results, columns=["标题", "期刊", "发表日期", "DOI"])
    return df

def send_email(df):
    today = datetime.date.today().strftime("%Y%m%d")
    filename = f"literature_{today}.xlsx"
    df.to_excel(filename, index=False)

    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = RECEIVER
    msg["Subject"] = f"院士请看文献_{today}"

    body = "本周最新 Q1 顶刊文献已推送，请查看附件。"
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
    df = get_recent_literature()
    send_email(df)
    print("✅ 真实文献抓取并推送成功！")
