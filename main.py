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

def get_test_literature():
    # 真实、可运行的测试文献
    data = {
        "标题": [
            "Sustainable Ecology Policy in Public Management",
            "Economic Impact of Environmental Governance",
            "Ecosystem Services and Public Policy Design",
            "Climate Policy and Economic Development",
            "Urban Ecology and Public Administration"
        ],
        "期刊": ["Q1 Top Journal", "Q1 Top Journal", "Q1 Top Journal", "Q1 Top Journal", "Q1 Top Journal"],
        "发表日期": ["2025-04-10", "2025-04-09", "2025-04-08", "2025-04-07", "2025-04-06"],
        "DOI": ["10.1000/test1", "10.1000/test2", "10.1000/test3", "10.1000/test4", "10.1000/test5"]
    }
    return pd.DataFrame(data)

def send_email(df):
    today = datetime.date.today().strftime("%Y%m%d")
    filename = f"literature_{today}.xlsx"
    df.to_excel(filename, index=False)

    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = RECEIVER
    msg["Subject"] = f"院士请看文献_{today}"

    body = "最新 Q1 顶刊文献已推送，请查收附件。"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with open(filename, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename={filename}")
    msg.attach(part)

    try:
        server = smtplib.SMTP_SSL("smtp.163.com", 465)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, RECEIVER, msg.as_string())
        server.quit()
        print("✅ 邮件发送成功")
    except Exception as e:
        print("❌ 发邮件失败:", e)

if __name__ == "__main__":
    df = get_test_literature()
    send_email(df)
