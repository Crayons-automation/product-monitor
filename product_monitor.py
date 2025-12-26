import requests
from bs4 import BeautifulSoup
import json
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from urllib.parse import urlparse

# =========================
# CONFIG
# =========================

URLS = {
    "Blister": "https://www.karzanddolls.com/details/mini+gt+/mini-gt-blister-pack/MTY2",
    "Box": "https://www.karzanddolls.com/details/mini+gt+/mini-gt/MTY1",
}

MAX_PAGES = 10
DATA_FILE = "products_seen.json"

EMAIL_FROM = os.getenv("GMAIL_USER")
EMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
EMAIL_TO = EMAIL_FROM

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {"User-Agent": "Mozilla/5.0"}

# =========================
# HELPERS
# =========================

def clean_product_path(url):
    """
    Removes encrypted tail, keeps stable path.
    """
    path = urlparse(url).path
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        return f"/product/{parts[-3]}/{parts[-2]}"
    return path


def product_key(product_type, clean_path):
    return f"{product_type}|{clean_path}"

# =========================
# SCRAPE
# =========================

def fetch_products(base_url, product_type):
    products = {}
    count = 0

    for page in range(1, MAX_PAGES + 1):
        url = f"{base_url}?page={page}"
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div.show-product-small-bx")

        if not cards:
            break

        count += len(cards)

        for card in cards:
            title = card.select_one("div.detail-text h3")
            if not title:
                continue

            name = title.get_text(strip=True)

            link = None
            a = card.find("a", href=True)
            if a and "/product/" in a["href"]:
                link = a["href"]

            if not link:
                cover = card.select_one("div.detail-cover")
                if cover and "window.location.href" in cover.get("onclick", ""):
                    link = cover["onclick"].split("'")[1]

            if not link:
                continue

            if link.startswith("/"):
                link = "https://www.karzanddolls.com" + link

            clean_path = clean_product_path(link)
            key = product_key(product_type, clean_path)

            products[key] = {
                "name": name,
                "url": "https://www.karzanddolls.com" + clean_path,
                "type": product_type,
            }

    return products, count

# =========================
# STORAGE
# =========================

def load_previous():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}

def save_current(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# =========================
# ALERTS
# =========================

def send_email(body):
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        return

    msg = MIMEText(body)
    msg["Subject"] = "Mini GT Product Monitor"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(EMAIL_FROM, EMAIL_PASSWORD)
        s.send_message(msg)

def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
    )

# =========================
# MAIN
# =========================

def main():
    previous = load_previous()
    current = {}

    blister_products, blister_count = fetch_products(URLS["Blister"], "Blister")
    box_products, box_count = fetch_products(URLS["Box"], "Box")

    current.update(blister_products)
    current.update(box_products)

    prev_keys = set(previous.keys())
    curr_keys = set(current.keys())

    added = curr_keys - prev_keys
    removed = prev_keys - curr_keys

    lines = []
    lines.append("🕒 Mini GT Product Monitor")
    lines.append(str(datetime.now()))
    lines.append("")
    lines.append("📊 Current Inventory")
    lines.append(f"• Mini GT Box Pack: {box_count}")
    lines.append(f"• Mini GT Blister Pack: {blister_count}")
    lines.append("")

    if added:
        lines.append("➕ Added Products")
        for k in added:
            p = current[k]
            lines.append(f"• [{p['type']}] {p['name']}")
            lines.append(p["url"])
        lines.append("")

    if removed:
        lines.append("➖ Removed Products")
        for k in removed:
            p = previous[k]
            lines.append(f"• [{p['type']}] {p['name']}")
        lines.append("")

    message = "\n".join(lines)

    send_email(message)
    send_telegram(message)

    save_current(current)

# =========================
# ENTRY
# =========================

if __name__ == "__main__":
    main()
