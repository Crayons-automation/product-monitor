import requests
from bs4 import BeautifulSoup
import time
import json
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# =========================
# CONFIGURATION
# =========================

URLS = {
    "Mini GT Blister Pack": "https://www.karzanddolls.com/details/mini+gt+/mini-gt-blister-pack/MTY2",
    "Mini GT Box Pack": "https://www.karzanddolls.com/details/mini+gt+/mini-gt/MTY1"
}

# IMPORTANT:
# GitHub Actions already runs every 5 minutes
# So we do NOT loop forever in cloud
CHECK_INTERVAL = 0  

DATA_FILE = "products_seen.json"
MAX_PAGES = 30

# Gmail (from GitHub Secrets)
EMAIL_FROM = os.getenv("GMAIL_USER")
EMAIL_TO = os.getenv("GMAIL_USER")
EMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Telegram (from GitHub Secrets)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# PRODUCT SCRAPING
# =========================

def fetch_products_from_page(base_url, page_no):
    url = f"{base_url}?page={page_no}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    products = set()

    for a in soup.select("a"):
        name = a.get_text(strip=True)
        link = a.get("href", "")

        if "/details/" in link and name:
            full_link = "https://www.karzanddolls.com" + link
            products.add(f"{name} | {full_link}")

    return products

def fetch_all_products():
    all_products = set()

    for label, base_url in URLS.items():
        for page in range(1, MAX_PAGES + 1):
            products = fetch_products_from_page(base_url, page)
            if not products:
                break

            for p in products:
                all_products.add(f"[{label}] {p}")

            time.sleep(1)

    return all_products

# =========================
# STORAGE
# =========================

def load_previous():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_current(products):
    with open(DATA_FILE, "w") as f:
        json.dump(sorted(list(products)), f, indent=2)

# =========================
# EMAIL ALERT
# =========================

def send_email(new_items):
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        print("❌ Gmail credentials not set")
        return

    body = "\n\n".join(new_items)
    msg = MIMEText(body)
    msg["Subject"] = "🚨 New Mini GT Products Added"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)

    print("📩 Email alert sent")

# =========================
# TELEGRAM ALERT
# =========================

def send_telegram(new_items):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials not set")
        return

    message = "🚨 *New Mini GT Products Added!*\n\n"
    for item in new_items:
        message += f"➕ {item}\n\n"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID_
