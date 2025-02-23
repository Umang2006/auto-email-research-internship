import os
import json
import time
import smtplib
import pandas as pd
import openai
from bs4 import BeautifulSoup
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PyPDF2 import PdfReader
from googleapiclient.discovery import build
from google.oauth2 import service_account

# ---- Load Gmail API Credentials ----
GMAIL_CREDENTIALS = "credentials.json"

# ---- Load OpenAI API Key ----
openai.api_key = os.getenv("OPENAI_API_KEY")

# ---- Read CV and Extract Skills & Interests ----
def extract_text_from_cv(cv_path):
    reader = PdfReader(cv_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

cv_text = extract_text_from_cv("cv.pdf")

# ---- Find Professors in Your Field ----
def find_professors(field):
    url = f"https://scholar.google.com/scholar?q={field}+professor"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    professors = []
    for result in soup.select(".gs_rt a")[:10]:  # Get 10 professors
        name = result.text
        link = result["href"]
        professors.append((name, link))
    return professors

professors = find_professors("Electrical Engineering")  # Example: Change field

# ---- Generate Personalized Emails ----
def generate_email(professor_name, professor_work):
    prompt = f"""
    Write a **concise, professional** cold email (max 150 words) to Professor {professor_name}.
    The email should:
    - Show genuine interest in their research.
    - Highlight my relevant skills: {cv_text[:500]}.
    - Attach my CV.
    
    Professor’s research area: {professor_work}.
    
    Email should be **formal, to the point, and engaging**.
    """
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response["choices"][0]["message"]["content"]

emails = []
for prof_name, prof_link in professors:
    emails.append((prof_name, generate_email(prof_name, prof_link)))

# ---- Send Emails Using Gmail ----
def send_email(to_email, subject, body):
    with open(GMAIL_CREDENTIALS, "r") as file:
        creds = json.load(file)
    
    sender_email = creds["client_email"]
    smtp_server = smtplib.SMTP("smtp.gmail.com", 587)
    smtp_server.starttls()
    smtp_server.login(sender_email, creds["private_key"])

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    
    smtp_server.sendmail(sender_email, to_email, msg.as_string())
    smtp_server.quit()

# ---- Send 10 Emails per Day ----
for name, email in emails[:10]:  # Limit to 10 per day
    send_email(email, f"Research Internship Inquiry - {name}", email)
    print(f"Sent email to {name}")

# ---- Log Emails in Google Sheets ----
def log_email_to_sheet(email, name):
    SERVICE_ACCOUNT_FILE = "credentials.json"
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)

    sheet = service.spreadsheets()
    sheet_id = "1AaXLpkdOXg0b5mP9FibbkRcx6__y_RVDywn4F_jGJ8k"
    values = [[name, email, time.strftime("%Y-%m-%d %H:%M:%S")]]
    
    request = sheet.values().append(spreadsheetId=sheet_id, range="Sheet1!A:C", valueInputOption="RAW", body={"values": values})
    request.execute()

for name, email in emails[:10]:
    log_email_to_sheet(email, name)
