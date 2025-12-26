import requests
from bs4 import BeautifulSoup
import time
import json
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# =========================
# CONFIG
# =========================

URLS = [
    "https://www.karzanddolls.com/details/mini+gt+/mini-gt-blister-pack/MTY2",
    "https://www.karzanddolls.com/details/mini+gt+/mini-gt/MTY1",
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

def normalize_name(name):
    return " ".join(name.lower().split())

def detect_type(url):
    if "/product/mini-gt-blister-pack/" in url:
        return "Mini GT Blister Pack"
    if "/product/mini-gt/" in url:
        return "Mini GT Box Pack"
    return None

def clean_url(url):
    return url.split(" - ")[0].strip()

# =========================
# SCRAPING
# =========================

def scrape_page(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    products = []

    cards = soup.select("div.show-product-small-bx")
    if not cards:
        return []

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

        link = clean_url(link)
        product_type = detect_type(link)

        if not product_type:
            continue

        products.append({
            "name": name,
            "type": product_type,
            "url": link
        })

    return products


def fetch_all_products():
    all_products = {}

    for base_url in URLS:
        for page in range(1, MAX_PAGES + 1):
            page_url = f"{base_url}?page={page}"
            items = scrape_page(page_url)

            if not items:
                break

            for p in items:
                key = f"{p['type']}::{normalize_name(p['name'])}"
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
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(EMAIL_FROM, EMAIL_PASSWORD)
        s.send_message(msg)


def send_telegram(body):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": body, "parse_mode": "Markdown"},
        timeout=10
    )

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
        out = {"Mini GT Box Pack": [], "Mini GT Blister Pack": []}
        for k in keys:
            p = source[k]
            out[p["type"]].append(p)
        return out

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

    def render(title, data, show_urls):
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

    render("➕ *Added Products*", added, True)
    render("➖ *Removed Products*", removed, False)

    if not added_keys and not removed_keys:
        lines.append("✅ *No changes since last run*")

    message = "\n".join(lines)

    send_email("📦 Mini GT Product Monitor Update", message)
    send_telegram(message)

    save_current(current)
    print("✅ Run completed")

# =========================
# ENTRY
# =========================

if __name__ == "__main__":
    main()
