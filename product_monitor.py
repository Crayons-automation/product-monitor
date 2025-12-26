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

DATA_FILE = "products_seen.json"
MAX_PAGES = 30

# Gmail (GitHub Secrets)
EMAIL_FROM = os.getenv("GMAIL_USER")
EMAIL_TO = os.getenv("GMAIL_USER")
EMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Telegram (GitHub Secrets)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# SCRAPING
# =========================

def fetch_products_from_page(base_url, page_no):
    url = f"{base_url}?page={page_no}"
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    products = set()

    cards = soup.select("div.show-product-small-bx")

    for card in cards:
        title_tag = card.select_one("div.detail-text h3")
        if not title_tag:
            continue

        name = title_tag.get_text(strip=True)

        link = None
        a_tag = card.find("a", href=True)
        if a_tag and "/product/" in a_tag["href"]:
            link = a_tag["href"]

        if not link:
            cover = card.select_one("div.detail-cover")
            if cover and cover.has_attr("onclick"):
                onclick = cover["onclick"]
                if "window.location.href" in onclick:
                    link = onclick.split("'")[1]

        if not link:
            continue

        if link.startswith("/"):
            link = "https://www.karzanddolls.com" + link

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

                if label == "Mini GT Blister Pack" and "mini-gt-blister-pack" in link:
                    all_products.add(f"[Blister Pack] {name}\n{link}")

                elif label == "Mini GT Box Pack" and "/product/mini-gt/" in link:
                    all_products.add(f"[Box Pack] {name}\n{link}")

            time.sleep(1)

    return all_products


def count_by_type(products):
    return {
        "Mini GT Box Pack": sum(p.startswith("[Box Pack]") for p in products),
        "Mini GT Blister Pack": sum(p.startswith("[Blister Pack]") for p in products)
    }

# =========================
# STORAGE
# =========================

def load_previous_products():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_products(products):
    with open(DATA_FILE, "w") as f:
        json.dump(sorted(products), f, indent=2)

# =========================
# EMAIL ALERT (WITH ERROR HANDLING)
# =========================

def send_email(subject, body):
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        print("❌ Gmail credentials not set")
        return

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_TO

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)

        print("📩 Email alert sent successfully")

    except Exception as e:
        print("❌ Email failed:", str(e))

# =========================
# TELEGRAM ALERT (WITH ERROR HANDLING)
# =========================

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials not set")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message[:3900],
            "disable_web_page_preview": True
        }

        response = requests.post(url, data=payload, timeout=20)

        if response.status_code == 200:
            print("📲 Telegram alert sent successfully")
        else:
            print("❌ Telegram failed:", response.text)

    except Exception as e:
        print("❌ Telegram exception:", str(e))

# =========================
# MAIN
# =========================

def main():
    print("🔍 Product Monitor run started")

    previous_products = load_previous_products()
    current_products = fetch_all_products()

    counts = count_by_type(current_products)

    new_products = current_products - previous_products

    if new_products:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        header = (
            "🚨 NEW MINI GT PRODUCTS ADDED 🚨\n\n"
            f"🕒 Detected at: {timestamp}\n\n"
            f"📦 Box Pack count: {counts['Mini GT Box Pack']}\n"
            f"🧊 Blister Pack count: {counts['Mini GT Blister Pack']}\n\n"
            "🆕 New Products:\n"
            "--------------------\n"
        )

        product_list = "\n\n".join(sorted(new_products))
        message = header + product_list

        send_email("🚨 New Mini GT Products Detected", message)
        send_telegram(message)

        save_products(current_products)
        print("🚨 New products alert sent")

    else:
        print(f"✅ No new products ({datetime.now()})")

    print("RUN CONTEXT:", os.getenv("GITHUB_REPOSITORY"))

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    main()
