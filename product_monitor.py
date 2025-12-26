import requests
from bs4 import BeautifulSoup
import time
import json
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from urllib.parse import urlparse

# =========================
# CONFIGURATION
# =========================

URLS = {
    "Mini GT Blister Pack": "https://www.karzanddolls.com/details/mini+gt+/mini-gt-blister-pack/MTY2",
    "Mini GT Box Pack": "https://www.karzanddolls.com/details/mini+gt+/mini-gt/MTY1"
}

DATA_FILE = "products_seen.json"
MAX_PAGES = 10

EMAIL_FROM = os.getenv("GMAIL_USER")
EMAIL_TO = os.getenv("GMAIL_USER")
EMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# HELPERS
# =========================

def extract_slug(product_url):
    """
    Extracts stable product slug.
    """
    path = urlparse(product_url).path
    parts = [p for p in path.split("/") if p]
    # slug is always the second-last segment
    if len(parts) >= 2:
        return parts[-2]
    return product_url


def normalize_url(product_url):
    """
    Removes encrypted tail.
    """
    path = urlparse(product_url).path
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        return f"https://www.karzanddolls.com/product/{parts[-3]}/{parts[-2]}"
    return product_url


# =========================
# SCRAPING
# =========================

def fetch_products_from_page(base_url, page_no):
    url = f"{base_url}?page={page_no}"
    res = requests.get(url, headers=HEADERS, timeout=20)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    cards = soup.select("div.show-product-small-bx")

    products = {}

    for card in cards:
        title = card.select_one("div.detail-text h3")
        if not title:
            continue

        name = title.get_text(strip=True)

        link = None
        a_tag = card.find("a", href=True)
        if a_tag and "/product/" in a_tag["href"]:
            link = a_tag["href"]

        if not link:
            cover = card.select_one("div.detail-cover")
            if cover and "window.location.href" in cover.get("onclick", ""):
                link = cover["onclick"].split("'")[1]

        if not link:
            continue

        if link.startswith("/"):
            link = "https://www.karzanddolls.com" + link

        slug = extract_slug(link)
        clean_url = normalize_url(link)

        products[slug] = {
            "name": name,
            "url": clean_url
        }

    return products, len(cards)


def fetch_all_products():
    all_products = {}

    for label, base_url in URLS.items():
        product_type = "Blister" if "blister" in base_url else "Box"

        for page in range(1, MAX_PAGES + 1):
            page_products, card_count = fetch_products_from_page(base_url, page)

            if card_count == 0:
                break

            for slug, data in page_products.items():
                all_products[slug] = {
                    "name": data["name"],
                    "url": data["url"],
                    "type": product_type
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
# ALERTS
# =========================

def send_email(subject, body):
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)


# =========================
# MAIN
# =========================

def main():
    print("🔍 Product Monitor run started")

    previous = load_previous()
    current = fetch_all_products()

    prev_keys = set(previous.keys())
    curr_keys = set(current.keys())

    added = curr_keys - prev_keys
    removed = prev_keys - curr_keys

    counts = {"Box": 0, "Blister": 0}
    for v in current.values():
        counts[v["type"]] += 1

    now = datetime.now()

    lines = []
    lines.append(f"🕒 Mini GT Product Monitor")
    lines.append(f"Run time: {now}")
    lines.append("")
    lines.append("📊 Current Inventory")
    lines.append(f"• Mini GT Box Pack: {counts['Box']}")
    lines.append(f"• Mini GT Blister Pack: {counts['Blister']}")
    lines.append("")

    if added:
        lines.append("➕ Added Products")
        for t in ["Box", "Blister"]:
            items = [current[k] for k in added if current[k]["type"] == t]
            if items:
                lines.append(f"*Mini GT {t} Pack*")
                for p in items:
                    lines.append(f"• {p['name']}")
                    lines.append(f"  {p['url']}")
                lines.append("")

    if removed:
        lines.append("➖ Removed Products")
        for t in ["Box", "Blister"]:
            items = [previous[k] for k in removed if previous[k]["type"] == t]
            if items:
                lines.append(f"*Mini GT {t} Pack*")
                for p in items:
                    lines.append(f"• {p['name']}")
                lines.append("")

    message = "\n".join(lines)

    send_email("Mini GT Product Monitor Update", message)
    send_telegram(message)

    save_current(current)

    print("✅ Run completed successfully")


# =========================
# ENTRY
# =========================

if __name__ == "__main__":
    main()
