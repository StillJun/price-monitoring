#!/usr/bin/env python3
"""
Price Monitor
by StillJun

Tracks the price of a product on a web page over time and alerts you when
it changes. Useful for watching prices on stores that don't have their
own "notify me" feature.

Usage:
    python monitor.py add <url> --selector ".price" --name "Product name"
    python monitor.py check
    python monitor.py list
    python monitor.py remove <id>

Run `check` on a schedule (cron, Task Scheduler, etc.) to get regular updates.
"""

import argparse
import json
import re
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_FILE = Path(__file__).parent / "tracked_products.json"
USER_AGENT = "price-monitor-by-StillJun/1.0"
REQUEST_TIMEOUT = 15


def load_data() -> dict:
    if not DATA_FILE.exists():
        return {"products": [], "next_id": 1}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def extract_price(html: str, selector: str) -> float:
    """
    Extracts a price from HTML using a CSS selector, then pulls the first
    number out of the matched element's text (handles things like
    "$19.99", "19,99 zł", "PLN 19.99" etc.).
    """
    soup = BeautifulSoup(html, "html.parser")
    element = soup.select_one(selector)

    if element is None:
        raise ValueError(f"No element found matching selector: {selector}")

    text = element.get_text(strip=True)

    # Normalize: remove currency symbols/letters, keep digits, dots, commas
    cleaned = re.sub(r"[^\d.,]", "", text)

    if not cleaned:
        raise ValueError(f"Could not find a number in matched text: '{text}'")

    # Handle both "19,99" (European) and "19.99" (US) decimal formats.
    # Heuristic: if there's a comma after the last dot (or no dot at all),
    # treat the comma as the decimal separator.
    if "," in cleaned and "." in cleaned:
        if cleaned.rindex(",") > cleaned.rindex("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    return float(cleaned)


def fetch_price(url: str, selector: str) -> float:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return extract_price(response.text, selector)


def add_product(url: str, selector: str, name: str) -> None:
    data = load_data()

    try:
        current_price = fetch_price(url, selector)
    except (requests.RequestException, ValueError) as e:
        print(f"Could not fetch initial price: {e}")
        sys.exit(1)

    product = {
        "id": data["next_id"],
        "name": name,
        "url": url,
        "selector": selector,
        "history": [
            {"price": current_price, "checked_at": datetime.now().isoformat(timespec="seconds")}
        ],
    }

    data["products"].append(product)
    data["next_id"] += 1
    save_data(data)

    print(f"Added '{name}' (id {product['id']}) — current price: {current_price}")


def check_all(notify_email: str | None = None) -> None:
    data = load_data()

    if not data["products"]:
        print("No products being tracked. Use 'add' first.")
        return

    changes = []

    for product in data["products"]:
        last_price = product["history"][-1]["price"]

        try:
            new_price = fetch_price(product["url"], product["selector"])
        except (requests.RequestException, ValueError) as e:
            print(f"[{product['name']}] Error checking price: {e}")
            continue

        product["history"].append({
            "price": new_price,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        })

        if new_price != last_price:
            direction = "dropped" if new_price < last_price else "increased"
            changes.append({
                "name": product["name"],
                "url": product["url"],
                "old_price": last_price,
                "new_price": new_price,
                "direction": direction,
            })
            print(f"[{product['name']}] Price {direction}: {last_price} -> {new_price}")
        else:
            print(f"[{product['name']}] No change ({new_price})")

    save_data(data)

    if changes and notify_email:
        send_email_alert(changes, notify_email)


def list_products() -> None:
    data = load_data()

    if not data["products"]:
        print("No products being tracked.")
        return

    for p in data["products"]:
        latest = p["history"][-1]
        print(f"[{p['id']}] {p['name']}")
        print(f"    URL: {p['url']}")
        print(f"    Latest price: {latest['price']} (checked {latest['checked_at']})")
        print(f"    History points: {len(p['history'])}")


def remove_product(product_id: int) -> None:
    data = load_data()
    before = len(data["products"])
    data["products"] = [p for p in data["products"] if p["id"] != product_id]

    if len(data["products"]) == before:
        print(f"No product found with id {product_id}")
        return

    save_data(data)
    print(f"Removed product {product_id}")


def send_email_alert(changes: list, to_email: str) -> None:
    """
    Sends a simple email summary of price changes.
    Expects local SMTP relay or configured environment — see README for setup.
    """
    body_lines = ["Price changes detected:\n"]
    for c in changes:
        body_lines.append(
            f"- {c['name']}: {c['old_price']} -> {c['new_price']} ({c['direction']})\n  {c['url']}"
        )

    msg = MIMEText("\n".join(body_lines))
    msg["Subject"] = f"Price Monitor: {len(changes)} change(s) detected"
    msg["From"] = "price-monitor@localhost"
    msg["To"] = to_email

    try:
        with smtplib.SMTP("localhost") as server:
            server.send_message(msg)
        print(f"Alert email sent to {to_email}")
    except (smtplib.SMTPException, ConnectionRefusedError) as e:
        print(f"Could not send email alert: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Track product prices and get alerted on changes.",
        epilog="by StillJun",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Start tracking a new product")
    add_parser.add_argument("url", help="Product page URL")
    add_parser.add_argument("--selector", required=True, help="CSS selector for the price element")
    add_parser.add_argument("--name", required=True, help="A friendly name for this product")

    check_parser = subparsers.add_parser("check", help="Check all tracked products for price changes")
    check_parser.add_argument("--email", help="Send an email alert to this address if prices changed")

    subparsers.add_parser("list", help="List all tracked products")

    remove_parser = subparsers.add_parser("remove", help="Stop tracking a product")
    remove_parser.add_argument("id", type=int, help="Product id (see 'list')")

    args = parser.parse_args()

    if args.command == "add":
        add_product(args.url, args.selector, args.name)
    elif args.command == "check":
        check_all(notify_email=args.email)
    elif args.command == "list":
        list_products()
    elif args.command == "remove":
        remove_product(args.id)


if __name__ == "__main__":
    main()
