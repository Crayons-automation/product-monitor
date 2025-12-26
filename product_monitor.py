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

URLS = [
    ("Mini GT Blister Pack", "https://www.karzanddolls.com/details/mini+gt+/mini-gt-blister-pack/MTY2"),
    ("Mini GT Box Pack", "https://www.karzanddolls.com/details/mini+gt+/mini-gt/MTY1"),
]

DATA_FILE = "products_seen.json"
MAX_PAGES = 10
HEADERS = {"User-Agent": "Mozilla/5.0"}

EMAIL_FROM = os.getenv("GMAIL_USER")
EMAIL_TO = EMAIL_FROM
EMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# =========================
# HELPERS
# =========================

def normalize_name(name: str) -> str:
    return " ".join(name.lower().split())

def make_key(pack_type: str, name: str) -> str:
    return f"{pack_type}::{normalize_name(name)}"

# =========================
# SCRAPING
# =========================

def scrape_page(url: str, pack_type: str):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.select("div.show-product-small-bx")

    products = []

    if not cards:
        return products

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
            if cover and cover.has_attr("onclick"):
                link = cover["onclick"].split("'")[1]

        if not link:
            continue

        if link.startswith("/"):
            link = "https://www.karzanddolls.com" + link

        products.append({
            "name": name,
            "type": pack_type,
            "url": link.strip()
        })

    return products


def fetch_all_products():
    all_products = {}

    for pack_type, base_url in URLS:
        for page in range(1, MAX_PAGES + 1):
            page_url = f"{base_url}?page={page}"
            items = scrape_page(page_url, pack_type)

            if not items:
                break

            for p in items:
                key = make_key(p["type"], p["name"])
                all_products[key] = p

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

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(EMAIL_FROM, EMAIL_PASSWORD)
        s.send_message(msg)

    print("📩 Email alert sent successfully")


def send_telegram(body):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials not set")
        return

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": body,
            "parse_mode": "Markdown"
        },
        timeout=10
    )

    print("📲 Telegram alert sent successfully")

# =========================
# MAIN
# =========================

def main():
    print("🔍 Product Monitor run started")

    previous = load_previous()
    current = fetch_all_products()

    prev_keys = set(previous.keys())
    curr_keys = set(current.keys())

    added_keys = curr_keys - prev_keys
    removed_keys = prev_keys - curr_keys

    def split(keys, source):
        result = {
            "Mini GT Box Pack": [],
            "Mini GT Blister Pack": []
        }
        for k in keys:
            p = source[k]
            result[p["type"]].append(p)
        return result

    added = split(added_keys, current)
    removed = split(removed_keys, previous)

    counts = {
        "Mini GT Box Pack": sum(1 for p in current.values() if p["type"] == "Mini GT Box Pack"),
        "Mini GT Blister Pack": sum(1 for p in current.values() if p["type"] == "Mini GT Blister Pack"),
    }

    lines = [
        "🕒 *Mini GT Product Monitor*",
        f"Run time: {datetime.now()}",
        "",
        "📊 *Current Inventory*",
        f"• Mini GT Box Pack: {counts['Mini GT Box Pack']}",
        f"• Mini GT Blister Pack: {counts['Mini GT Blister Pack']}",
        ""
    ]

    def render_section(title, data, show_urls):
        lines.append(title)
        for pack in ["Mini GT Box Pack", "Mini GT Blister Pack"]:
            items = data[pack]
            lines.append(f"*{pack}* ({len(items)})")
            if not items:
                lines.append("• None")
            for p in items:
                lines.append(f"• {p['name']}")
                if show_urls:
                    lines.append(f"  {p['url']}")
            lines.append("")

    render_section("➕ *Added Products*", added, True)
    render_section("➖ *Removed Products*", removed, False)

    if not added_keys and not removed_keys:
        lines.append("✅ *No changes since last run*")

    message = "\n".join(lines)

    send_email("📦 Mini GT Product Monitor Update", message)
    send_telegram(message)

    save_current(current)

    print("✅ Run completed")

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    main()
