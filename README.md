# Price Monitor

*by StillJun*

A command-line tool that tracks the price of a product on a web page over time and reports when it changes. Built for stores that don't have a built-in "notify me when the price drops" feature.

## Features

- Track any number of products by URL + a CSS selector pointing to the price element
- Handles multiple price formats automatically: `$19.99`, `€1,299.50`, `19,99 zł`, `1.234,56 PLN`, etc. — the parser detects whether a comma or a dot is being used as the decimal separator
- Keeps a full price history per product, not just the latest value
- Optional email alert when a price change is detected (via local SMTP)
- Designed to be run on a schedule (cron / Task Scheduler) for hands-off monitoring

## Usage

```bash
# Start tracking a product
python monitor.py add "https://example-shop.com/product/123" --selector ".price" --name "Mechanical Keyboard"

# Check all tracked products for changes
python monitor.py check

# Check and send an email alert if anything changed
python monitor.py check --email you@example.com

# List everything being tracked, with latest price and history length
python monitor.py list

# Stop tracking a product
python monitor.py remove 1
```

## Finding the right CSS selector

Open the product page in your browser, right-click the price, choose **Inspect**, and look at the element's class or id in DevTools. For example, if the price is in `<span class="product-price">$49.99</span>`, the selector to use is `.product-price`.

## Automating checks

On Linux/macOS, add a cron job to check daily at 9 AM:
```bash
0 9 * * * cd /path/to/price-monitor && python3 monitor.py check --email you@example.com
```

On Windows, use Task Scheduler to run the same command on a schedule.

## How price parsing handles different formats

The trickiest part of scraping prices across different stores is that "19.99" and "19,99" can mean the same thing depending on locale, and "1.234,56" (European) vs "1,234.56" (US) need to be told apart. The parser strips everything except digits, dots, and commas, then uses a simple rule: whichever of `,` or `.` appears **last** in the string is treated as the decimal separator, and the other is treated as a thousands separator and removed.

## Data storage

Tracked products and their price history are stored in `tracked_products.json` in the same folder as the script — no database required for personal use at this scale.

## Requirements

```
pip install requests beautifulsoup4
```

## Limitations

- Some stores render prices via JavaScript after the page loads, which a simple HTTP GET + HTML parse won't see — that would require a headless browser (e.g. Playwright or Selenium) instead of `requests`.
- Email alerts assume a local SMTP relay is available; on most personal machines this needs additional setup (e.g. using a real SMTP provider's credentials instead of `localhost`).
- Always check a site's terms of service before scraping it regularly — some sites explicitly disallow automated price tracking.

## Possible improvements

- Headless browser support for JS-rendered prices
- Telegram or Discord webhook notifications instead of email
- A simple price history chart (e.g. with `matplotlib`)
