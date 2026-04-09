import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import datetime
import pandas as pd

# 读取配置
EMAIL_USER = os.environ.get("EMAIL_163_USER", "")
EMAIL_PASS = os.environ.get("EMAIL_163_PASS", "")
RECEIVER = EMAIL_USER

def send_email(excel_path):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = RECEIVER
    today = datetime.date.today().strftime("%Y%m%d")
    msg["Subject"] = f"院士请看文献_{today}"

    body = "本周文献已推送，请查看附件。"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with open(excel_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename=literature.xlsx")
    msg.attach(part)

    server = smtplib.SMTP_SSL("smtp.163.com", 465)
    server.login(EMAIL_USER, EMAIL_PASS)
    server.sendmail(EMAIL_USER, RECEIVER, msg.as_string())
    server.quit()

if __name__ == "__main__":
    data = {
        "标题": ["测试文献1", "测试文献2"],
        "期刊": ["Q1顶刊", "Q1顶刊"],
        "日期": ["2025", "2025"]
    }
    df = pd.DataFrame(data)
    df.to_excel("literature.xlsx", index=False)
    send_email("literature.xlsx")
    print("✅ 推送成功！")
