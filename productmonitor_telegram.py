import requests
from bs4 import BeautifulSoup
import time
import json
import os
from datetime import datetime

# =========================
# CONFIGURATION
# =========================

URLS = {
    "Mini GT Blister Pack": "https://www.karzanddolls.com/details/mini+gt+/mini-gt-blister-pack/MTY2",
    "Mini GT Box Pack": "https://www.karzanddolls.com/details/mini+gt+/mini-gt/MTY1"
}

DATA_FILE = "products_seen.json"
MAX_PAGES = 10

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# HELPERS
# =========================

def normalize_key(name, url):
    return url.strip().lower()

# =========================
# SCRAPING
# =========================

def fetch_products_from_page(base_url, page_no):
    url = f"{base_url}?page={page_no}"
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    products = []

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

        products.append({
            "name": name,
            "url": link
        })

    return products


def fetch_all_products():
    all_products = {}

    for label, base_url in URLS.items():
        for page in range(1, MAX_PAGES + 1):
            page_products = fetch_products_from_page(base_url, page)
            if not page_products:
                break

            for p in page_products:
                url = p["url"]
                name = p["name"]

                if label == "Mini GT Blister Pack" and "mini-gt-blister-pack" in url:
                    key = normalize_key(name, url)
                    all_products[key] = {
                        "type": "Blister",
                        "name": name,
                        "url": url
                    }

                elif label == "Mini GT Box Pack" and "/product/mini-gt/" in url:
                    key = normalize_key(name, url)
                    all_products[key] = {
                        "type": "Box",
                        "name": name,
                        "url": url
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
# TELEGRAM
# =========================

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials not set")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }

    requests.post(url, data=payload)

# =========================
# MAIN
# =========================

def main():
    now = datetime.now()

    previous = load_previous_products()
    current = fetch_all_products()

    prev_keys = set(previous.keys())
    curr_keys = set(current.keys())

    added_keys = curr_keys - prev_keys
    removed_keys = prev_keys - curr_keys

    box_count = sum(1 for v in current.values() if v["type"] == "Box")
    blister_count = sum(1 for v in current.values() if v["type"] == "Blister")

    message = f"""🕒 *Mini GT Product Monitor*
Run time: {now}

📊 *Current Inventory*
• Mini GT Box Pack: {box_count}
• Mini GT Blister Pack: {blister_count}
"""

    if added_keys:
        message += "\n➕ *Added Products*\n"
        for k in added_keys:
            p = current[k]
            message += f"*{p['type']}* • {p['name']}\n{p['url']}\n\n"

    if removed_keys:
        message += "\n➖ *Removed Products*\n"
        for k in removed_keys:
            p = previous[k]
            message += f"*{p['type']}* • {p['name']}\n\n"

    if not added_keys and not removed_keys:
        message += "\n✅ No changes since last run"

    send_telegram(message)

    save_products(current)

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    main()
