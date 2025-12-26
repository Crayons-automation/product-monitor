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
    "Mini GT Box Pack": "https://www.karzanddolls.com/details/mini+gt+/mini-gt/MTY1",
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

# =========================
# SCRAPING
# =========================

def clean_product_url(url: str) -> str:
    """Remove tracking/hash garbage from URL"""
    return url.split(" - ")[0].strip()

def fetch_products_from_page(base_url, page_no):
    url = f"{base_url}?page={page_no}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.select("div.show-product-small-bx")

    results = {}

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

        link = clean_product_url(link)

        if "/product/mini-gt" in link:
            results[link] = name

    return results


def fetch_all_products():
    all_products = {}

    for pack_type, base_url in URLS.items():
        for page in range(1, MAX_PAGES + 1):
            page_products = fetch_products_from_page(base_url, page)
            if not page_products:
                break

            for url, name in page_products.items():
                all_products[url] = {
                    "name": name,
                    "type": pack_type
                }

            time.sleep(1)

    return all_products

# =========================
# STORAGE
# =========================

def load_previous_products():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_products(products):
    with open(DATA_FILE, "w") as f:
        json.dump(products, f, indent=2)

# =========================
# COUNTS
# =========================

def count_by_type(products):
    counts = {"Mini GT Box Pack": 0, "Mini GT Blister Pack": 0}
    for p in products.values():
        counts[p["type"]] += 1
    return counts

# =========================
# NOTIFICATIONS
# =========================

def send_email(subject, body):
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        print("❌ Gmail credentials not set")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)
        print("📩 Email alert sent successfully")
    except Exception as e:
        print("❌ Email failed:", e)

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials not set")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        requests.post(url, data=payload, timeout=10)
        print("📲 Telegram alert sent successfully")
    except Exception as e:
        print("❌ Telegram failed:", e)

# =========================
# MAIN
# =========================

def main():
    print("🔍 Product Monitor run started")

    previous = load_previous_products()
    current = fetch_all_products()

    prev_urls = set(previous.keys())
    curr_urls = set(current.keys())

    added = curr_urls - prev_urls
    removed = prev_urls - curr_urls

    counts = count_by_type(current)

    lines = []
    lines.append("🕒 *Product Monitor Update*")
    lines.append(f"Run time: {datetime.now()}")
    lines.append("")
    lines.append("📊 *Current Inventory*")
    lines.append(f"• Mini GT Box Pack: {counts['Mini GT Box Pack']}")
    lines.append(f"• Mini GT Blister Pack: {counts['Mini GT Blister Pack']}")
    lines.append("")

    if added:
        lines.append(f"➕ *Newly Added ({len(added)})*")
        for url in added:
            p = current[url]
            lines.append(f"• {p['name']}")
            lines.append(f"  {url}")
        lines.append("")

    if removed:
        lines.append(f"➖ *Removed ({len(removed)})*")
        for url in removed:
            p = previous[url]
            lines.append(f"• {p['name']}")
        lines.append("")

    if not added and not removed:
        lines.append("✅ *No changes since last run*")

    message = "\n".join(lines)

    send_email("📦 Mini GT Product Monitor Update", message)
    send_telegram(message)

    save_products(current)
    print("🚀 Run completed")
    print("RUN CONTEXT:", os.getenv("GITHUB_REPOSITORY"))

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    main()
