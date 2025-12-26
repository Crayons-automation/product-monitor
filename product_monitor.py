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
# HELPERS
# =========================

def normalize_key(name, pack_type):
    """Stable comparison key"""
    return f"{pack_type}::{name.lower().strip()}"

def clean_url(url):
    """Remove hash / tracking junk"""
    return url.split(" - ")[0].strip()

# =========================
# SCRAPING
# =========================

def fetch_products_from_page(base_url):
    r = requests.get(base_url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.select("div.show-product-small-bx")

    results = []

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

        link = clean_url(link)

        if "/product/mini-gt" in link:
            results.append((name, link))

    return results


def fetch_all_products():
    all_products = {}

    for pack_type, base_url in URLS.items():
        for page in range(1, MAX_PAGES + 1):
            url = f"{base_url}?page={page}"
            products = fetch_products_from_page(url)

            if not products:
                break

            for name, link in products:
                key = normalize_key(name, pack_type)
                all_products[key] = {
                    "name": name,
                    "type": pack_type,
                    "url": link
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
        print("📩 Email sent")
    except Exception as e:
        print("❌ Email failed:", e)


def send_telegram(body):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials not set")
        return

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": body,
        "parse_mode": "Markdown"
    }

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=payload,
            timeout=10
        )
        print("📲 Telegram sent")
    except Exception as e:
        print("❌ Telegram failed:", e)

# =========================
# MAIN
# =========================

def main():
    print("🔍 Product Monitor run started")

    previous = load_previous_products()
    current = fetch_all_products()

    prev_keys = set(previous.keys())
    curr_keys = set(current.keys())

    added_keys = curr_keys - prev_keys
    removed_keys = prev_keys - curr_keys

    # Grouping
    def group(keys, source):
        result = {
            "Mini GT Box Pack": [],
            "Mini GT Blister Pack": []
        }
        for k in keys:
            p = source[k]
            result[p["type"]].append(p)
        return result

    added = group(added_keys, current)
    removed = group(removed_keys, previous)

    # Counts
    counts = {
        "Mini GT Box Pack": sum(1 for p in current.values() if p["type"] == "Mini GT Box Pack"),
        "Mini GT Blister Pack": sum(1 for p in current.values() if p["type"] == "Mini GT Blister Pack")
    }

    lines = []
    lines.append("🕒 *Mini GT Product Monitor*")
    lines.append(f"Run time: {datetime.now()}")
    lines.append(f"Run ID: {os.getenv('GITHUB_RUN_ID', 'local')}\n")

    lines.append("📊 *Current Inventory*")
    lines.append(f"• Box Pack: {counts['Mini GT Box Pack']}")
    lines.append(f"• Blister Pack: {counts['Mini GT Blister Pack']}\n")

    def render_section(title, data, show_url):
        lines.append(title)
        for pack_type in ["Mini GT Box Pack", "Mini GT Blister Pack"]:
            items = data[pack_type]
            lines.append(f"*{pack_type}* ({len(items)})")
            if not items:
                lines.append("• None")
            for p in items:
                lines.append(f"• {p['name']}")
                if show_url:
                    lines.append(f"  {p['url']}")
            lines.append("")

    render_section("➕ *Added Products*", added, True)
    render_section("➖ *Removed Products*", removed, False)

    if not added_keys and not removed_keys:
        lines.append("✅ *No changes since last run*")

    message = "\n".join(lines)

    send_email("📦 Mini GT Product Monitor Update", message)
    send_telegram(message)

    save_products(current)

    print("🚀 Run completed")

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    main()
