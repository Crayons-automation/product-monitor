import requests
from bs4 import BeautifulSoup
import time
import json
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

# =========================
# CONFIGURATION
# =========================

URLS = {
    "Blister Pack": "https://www.karzanddolls.com/details/mini+gt+/mini-gt-blister-pack/MTY2",
    "Box Pack": "https://www.karzanddolls.com/details/mini+gt+/mini-gt/MTY1"
}

DATA_FILE = "products_seen.json"
MAX_PAGES = 30

EMAIL_FROM = os.getenv("GMAIL_USER")
EMAIL_TO = os.getenv("GMAIL_USER")
EMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {"User-Agent": "Mozilla/5.0"}

IST = timezone(timedelta(hours=5, minutes=30))

# =========================
# SCRAPING
# =========================

def clean_url(url: str) -> str:
    if " - /" in url:
        url = url.split(" - /")[0]
    return url.strip()

def fetch_products_from_page(base_url, page_no):
    url = f"{base_url}?page={page_no}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    products = set()

    for card in soup.select("div.show-product-small-bx"):
        title = card.select_one("div.detail-text h3")
        if not title:
            continue

        name = title.get_text(strip=True)

        link = None
        a = card.find("a", href=True)
        if a and "/product/" in a["href"]:
            link = a["href"]

        if not link:
            continue

        if link.startswith("/"):
            link = "https://www.karzanddolls.com" + link

        link = clean_url(link)

        if "/product/mini-gt" in link:
            products.add(f"{name} | {link}")

    return products

def fetch_all_products():
    all_products = set()

    for label, base_url in URLS.items():
        for page in range(1, MAX_PAGES + 1):
            products = fetch_products_from_page(base_url, page)
            if not products:
                break

            for p in products:
                name, link = p.split(" | ", 1)
                all_products.add(f"[{label}] {name} | {link}")

            time.sleep(1)

    return all_products

def count_by_type(products):
    return {
        "Box Pack": sum(p.startswith("[Box Pack]") for p in products),
        "Blister Pack": sum(p.startswith("[Blister Pack]") for p in products)
    }

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
        json.dump(sorted(products), f, indent=2)

# =========================
# NOTIFICATIONS
# =========================

def send_email(body):
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        print("❌ Gmail credentials not set")
        return
    msg = MIMEText(body)
    msg["Subject"] = "Mini GT Product Monitor"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
            s.starttls()
            s.login(EMAIL_FROM, EMAIL_PASSWORD)
            s.send_message(msg)
        print("📩 Email alert sent successfully")
    except Exception as e:
        print("❌ Email failed:", e)

def send_telegram(body):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials not set")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": body,
            "disable_web_page_preview": False
        }, timeout=10)
        print("📲 Telegram alert sent successfully")
    except Exception as e:
        print("❌ Telegram failed:", e)

# =========================
# MAIN
# =========================

def main():
    print("🔍 Product Monitor run started")

    previous = load_previous()
    current = fetch_all_products()

    added = sorted(current - previous)
    removed = sorted(previous - current)

    counts = count_by_type(current)
    timestamp = dateti
