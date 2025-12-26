import requests
from bs4 import BeautifulSoup
import json
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import time

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
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    products = {}

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
            products[link] = name

    return products


def fetch_all_products():
    all_products = {}

    for label, base_url in URLS.items():
        for page in range(1, MAX_PAGES + 1):
            page_products = fetch_products_from_page(base_url, page)
            if not page_products:
                break

            for url, name in page_products.items():
                all_products[url] = {
                    "name": name,
                    "type": label
                }

            time.sleep(1)

    return all_products

# =========================
# STORAGE
# =========================

def load_previous():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_current(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# =========================
# MESSAGE BUILDER
# =========================

def build_message(current, added, removed):
    counts = {"Mini GT Box Pack": 0, "Mini GT Blister Pack": 0}

    for p in current.values():
        counts[p["type"]] += 1

    lines = []
    lines.append("🕒 *Product Monitor Update*")
    lines.append(f"Run time: {datetime.now()}\n")
    lines.append(f"🆔 Run ID: {os.getenv('GITHUB_RUN_ID', 'local')}\n")
    lines.append("📊 *Current Inventory*")
    lines.append(f"• Mini GT Box Pack: {counts['Mini GT Box Pack']}")
    lines.append(f"• Mini GT Blister Pack: {counts['Mini GT Blister Pack']}\n")

    if added:
        lines.append(f"➕ *Newly Added ({len(added)})*")
        for url in added:
            lines.append(f"• {current[url]['name']}")
            lines.append(f"  {url}")
        lines.append("")

    if removed:
        lines.append(f"➖ *Removed ({len(removed)})*")
        for url, info in removed.items():
            lines.append(f"• {info['name']}")
        lines.append("")

    if not added and not removed:
        lines.append("✅ No product changes detected")

    return "\n".join(lines)

# =========================
# ALERTS
# =========================

def send_email(body):
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        print("❌ Gmail credentials not set")
        return

    try:
        msg = MIMEText(body)
        msg["Subject"] = "Mini GT Product Monitor Update"
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_TO

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)

        print("📩 Email alert sent successfully")
    except Exception as e:
        print("❌ Email error:", e)


def send_telegram(body):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials not set")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": body,
            "parse_mode": "Markdown"
        }
        requests.post(url, data=payload, timeout=20)
        print("📲 Telegram alert sent successfully")
    except Exception as e:
        print("❌ Telegram error:", e)

# =========================
# MAIN
# =========================

def main():
    print("🔍 Product Monitor run started")

    previous = load_previous()
    current = fetch_all_products()

    prev_urls = set(previous.keys())
    curr_urls = set(current.keys())

    added = curr_urls - prev_urls
    removed = {url: previous[url] for url in (prev_urls - curr_urls)}

    print(f"DEBUG: Total products scraped = {len(current)}")
    print(f"DEBUG: Added = {len(added)}, Removed = {len(removed)}")

    message = build_message(current, added, removed)

    print(message)

    send_email(message)
    send_telegram(message)

    save_current(current)

    print("RUN CONTEXT:", os.getenv("GITHUB_REPOSITORY"))

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    main()
