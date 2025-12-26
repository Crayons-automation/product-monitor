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

LISTING_URLS = [
    "https://www.karzanddolls.com/details/mini+gt+/mini-gt-blister-pack/MTY2",
    "https://www.karzanddolls.com/details/mini+gt+/mini-gt/MTY1",
]

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

def clean_url(url: str) -> str:
    """Remove hash / tracking junk"""
    return url.split(" - ")[0].strip()

def detect_pack_type(url: str) -> str:
    """Source of truth: product URL"""
    if "/mini-gt-blister-pack/" in url:
        return "Mini GT Blister Pack"
    return "Mini GT Box Pack"

def normalize_key(name: str, pack_type: str) -> str:
    """Stable comparison key"""
    return f"{pack_type}::{name.lower().strip()}"

# =========================
# SCRAPING
# =========================

def fetch_products_from_page(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.select("div.show-product-small-bx")

    products = []

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
            products.append((name, link))

    return products


def fetch_all_products():
    all_products = {}

    for base_url in LISTING_URLS:
        for page in range(1, MAX_PAGES + 1):
            page_url = f"{base_url}?page={page}"
            items = fetch_products_from_page(page_url)

            if not items:
                break

            for name, link in items:
                pack_type = detect_pack_type(link)
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

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_TO

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)

        print("📩 Email alert sent")
    except Exception as e:
        print("❌ Email failed:", e)


def send_telegram(body):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials not set")
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": body,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        print("📲 Telegram alert sent")
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

    def group(keys, source):
        out = {
            "Mini GT Box Pack": [],
            "Mini GT Blister Pack": []
        }
        for k in keys:
            p = source[k]
            out[p["type"]].append(p)
        return out

    added = group(added_keys, current)
    removed = group(removed_keys, previous)

    counts = {
        "Mini GT Box Pack": sum(1 for p in current.values() if p["type"] == "Mini GT Box Pack"),
        "Mini GT Blister Pack": sum(1 for p in current.values() if p["type"] == "Mini GT Blister Pack"),
    }

    lines = []
    lines.append("🕒 *Mini GT Product Monitor*")
    lines.append(f"Run time: {datetime.now()}")
    lines.append(f"Run ID: {os.getenv('GITHUB_RUN_ID', 'local')}\n")

    lines.append("📊 *Current Inventory*")
    lines.append(f"• Mini GT Box Pack: {counts['Mini GT Box Pack']}")
    lines.append(f"• Mini GT Blister Pack: {counts['Mini GT Blister Pack']}\n")

    def render(title, data, show_url):
        lines.append(title)
        for pack in ["Mini GT Box Pack", "Mini GT Blister Pack"]:
            items = data[pack]
            lines.append(f"*{pack}* ({len(items)})")
            if not items:
                lines.append("• None")
            for p in items:
                lines.append(f"• {p['name']}")
                if show_url:
                    lines.append(f"  {p['url']}")
            lines.append("")

    render("➕ *Added Products*", added, True)
    render("➖ *Removed Products*", removed, False)

    if not added_keys and not removed_keys:
        lines.append("✅ *No changes since last run*")

    message = "\n".join(lines)

    send_email("📦 Mini GT Product Monitor Update", message)
    send_telegram(message)

    save_products(current)
    print("✅ Run completed")

# =========================
# ENTRY POINT (FAIL-SAFE)
# =========================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error = f"""🚨 *Mini GT Monitor FAILED*

Error:
{str(e)}

Time: {datetime.now()}
Repo: {os.getenv('GITHUB_REPOSITORY')}
Run ID: {os.getenv('GITHUB_RUN_ID')}
"""
        print(error)
        send_telegram(error)
        send_email("🚨 Mini GT Monitor FAILED", error)
        raise
