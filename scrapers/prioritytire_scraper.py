"""Scrape tyre catalogue from https://www.prioritytire.com
Uses curl_cffi with automatic Cloudflare challenge bypass gateway fallback.
Conforms to TyresCart protocol:
  sys.argv[1]: output XLSX path
  sys.argv[2]: input CSV path (sitemap or product URLs)
"""

import csv
import json
import os
import random
import re
import sys
import time
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlparse

import openpyxl
import requests
from curl_cffi import requests as c_requests
from dotenv import load_dotenv
from scrapy.selector import Selector

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.now().strftime("%d-%m-%Y")

# Load .env automatically from project root
load_dotenv(os.path.join(BASE_DIR, ".env"))

DEFAULT_SITEMAPS = [
    "https://www.prioritytire.com/sitemap/sitemap-singleproducts-1.xml",
    "https://www.prioritytire.com/sitemap/sitemap-singleproducts-2.xml",
    "https://www.prioritytire.com/sitemap/sitemap-singleproducts-3.xml",
    "https://www.prioritytire.com/sitemap/sitemap-singleproducts-4.xml",
    "https://www.prioritytire.com/sitemap/sitemap-singleproducts-5.xml",
    "https://www.prioritytire.com/sitemap/sitemap-singleproducts-6.xml",
    "https://www.prioritytire.com/sitemap/sitemap-singleproducts-7.xml",
    "https://www.prioritytire.com/sitemap/sitemap-configurableproducts.xml",
]

SKIP_URL_PREFIXES = ("/tire-sets/",)

IMPERSONATIONS = ["chrome131", "chrome124", "safari17_0", "edge101"]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}

OUTPUT_FILE = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.path.join(BASE_DIR, f"prioritytire_data_{TODAY}.xlsx")
)

INPUT_CSV = sys.argv[2] if len(sys.argv) > 2 else None


def emit_status(url, status, parent=None, url_type=None):
    print(f"URL_STATUS|{url}|{status}|{parent or ''}|{url_type or ''}", flush=True)


def load_input_urls():
    if INPUT_CSV and os.path.exists(INPUT_CSV):
        urls = []
        with open(INPUT_CSV, newline='', encoding='utf-8') as f:
            for row in csv.reader(f):
                if row and row[0].strip() and row[0].strip().startswith("http"):
                    urls.append(row[0].strip())
        if urls:
            return urls
    return DEFAULT_SITEMAPS


def _get_cleaned_proxy():
    raw = os.environ.get("SCRAPER_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    if not raw:
        return None
    p = raw.strip()
    if "@https://" in p:
        p = p.replace("@https://", "@")
    elif "@http://" in p:
        p = p.replace("@http://", "@")
    return p


PROXY = _get_cleaned_proxy()


def fetch_page_with_fallback(session, url, max_retries=4, referer=None):
    """Fetches URL via direct TLS impersonation, falling back to Cloudflare bypass gateway."""
    proxies = {"http": PROXY, "https": PROXY} if PROXY else None
    headers = dict(BASE_HEADERS)
    if referer:
        headers["Referer"] = referer

    # Small randomized delay before every request so a burst of concurrently
    # submitted workers doesn't all land on the server in the same instant --
    # that request-velocity pattern is what trips Cloudflare's rate-based bot
    # detection even when the TLS fingerprint impersonation itself is fine.
    time.sleep(random.uniform(0.3, 0.8))

    # Step 1: Try direct connection with curl_cffi, backing off properly on
    # an actual Cloudflare challenge instead of retrying near-instantly.
    for attempt in range(max_retries):
        imp = IMPERSONATIONS[attempt % len(IMPERSONATIONS)]
        try:
            r = session.get(
                url,
                impersonate=imp,
                proxies=proxies,
                headers=headers,
                timeout=18,
            )
            # Check for valid HTML with actual content (not Cloudflare challenge)
            if r.status_code == 200 and len(r.text) > 100:
                if "Just a moment..." not in r.text and "__cf_chl_rt_tk" not in r.text:
                    return r.text
            if r.status_code == 403 or "Just a moment" in r.text:
                delay = min(2.0 * (attempt + 1) + random.uniform(0, 1.5), 12.0)
                time.sleep(delay)
            else:
                time.sleep(0.5 * (attempt + 1))
        except Exception:
            time.sleep(1.0 * (attempt + 1) + random.uniform(0, 1.0))

    # Step 2: Automatic Cloudflare challenge bypass gateway fallback
    try:
        jina_url = f"https://r.jina.ai/{url}"
        jina_headers = {"X-Return-Format": "html"}
        res = requests.get(jina_url, headers=jina_headers, timeout=30)
        if res.status_code == 200 and len(res.text) > 200 and "Just a moment..." not in res.text:
            return res.text
    except Exception:
        pass

    return None


def extract_product_urls_from_sitemap(session, sitemap_url):
    emit_status(sitemap_url, 'running', url_type='sitemap')
    html_text = fetch_page_with_fallback(session, sitemap_url)
    if not html_text:
        emit_status(sitemap_url, 'blocked', url_type='sitemap')
        return []

    try:
        sel = Selector(text=html_text)
        urls = sel.xpath("//*[local-name()='loc']/text()").getall() or sel.css("loc::text").getall()

        # Fallback to regex if XML wrapper was transformed by gateway
        if not urls:
            found_urls = re.findall(r'https://www\.prioritytire\.com/[^\s<"\'\]]+', html_text)
            urls = list(OrderedDict.fromkeys(found_urls))

        product_urls = []
        for i, u in enumerate(urls):
            u_clean = u.strip()
            if not u_clean or not u_clean.startswith("http"):
                continue
            path = urlparse(u_clean).path
            if any(path.startswith(p) for p in SKIP_URL_PREFIXES):
                continue
            product_urls.append(u_clean)
            if i < 50:
                emit_status(u_clean, 'pending', parent=sitemap_url, url_type='product')

        emit_status(sitemap_url, 'done', url_type='sitemap')
        return product_urls
    except Exception:
        emit_status(sitemap_url, 'blocked', url_type='sitemap')
        return []


def extract_product_urls_from_listing(session, listing_url):
    emit_status(listing_url, 'running', url_type='listing')
    html_text = fetch_page_with_fallback(session, listing_url)
    if not html_text:
        emit_status(listing_url, 'blocked', url_type='listing')
        return []

    try:
        sel = Selector(text=html_text)
        links = sel.css("a[href*='/by-brand/']::attr(href), a[href*='/tire/']::attr(href)").getall()
        if not links:
            found = re.findall(r'https://www\.prioritytire\.com/(?:by-brand|tire)/[^\s<"\'\]]+', html_text)
            links = list(OrderedDict.fromkeys(found))

        product_urls = []
        for link in links:
            prod_url = link
            if prod_url.startswith("/"):
                prod_url = f"https://www.prioritytire.com{prod_url}"
            path = urlparse(prod_url).path
            if any(path.startswith(p) for p in SKIP_URL_PREFIXES):
                continue
            product_urls.append(prod_url)
            emit_status(prod_url, 'pending', parent=listing_url, url_type='product')

        emit_status(listing_url, 'done', url_type='listing')
        return product_urls
    except Exception:
        emit_status(listing_url, 'blocked', url_type='listing')
        return []


def parse_product_page(session, url, parent_url):
    emit_status(url, 'running', parent=parent_url, url_type='product')
    html_text = fetch_page_with_fallback(session, url, referer=parent_url or "https://www.prioritytire.com/")
    if not html_text:
        emit_status(url, 'blocked', parent=parent_url, url_type='product')
        return None

    try:
        sel = Selector(text=html_text)
        raw = sel.css("script#__NEXT_DATA__::text").get("")
        product = None

        if raw:
            try:
                data = json.loads(raw)
                apollo = data.get("props", {}).get("pageProps", {}).get("apolloState", {})
                PRODUCT_TYPE_PREFIXES = (
                    "SimpleProduct:",
                    "ConfigurableProduct:",
                    "BundleProduct:",
                    "GroupedProduct:",
                    "VirtualProduct:",
                )
                for key, val in apollo.items():
                    if (
                        isinstance(val, dict)
                        and "sku" in val
                        and "price_range" in val
                        and any(key.startswith(p) for p in PRODUCT_TYPE_PREFIXES)
                    ):
                        product = val
                        break
            except Exception:
                product = None

        # Fallback to HTML meta & DOM if __NEXT_DATA__ is absent
        if not product:
            title = sel.css("h1::text").get("").strip()
            if not title:
                emit_status(url, 'blocked', parent=parent_url, url_type='product')
                return None
            product = {
                "name": title,
                "sku": url.split("-")[-1] if "-" in url else "",
                "country_of_origin": "",
                "stock_status": "In Stock",
            }

        attrs = {}
        for key, val in product.items():
            if "attribute_values" in key and isinstance(val, list):
                for attr in val:
                    code = attr.get("code", "")
                    values = attr.get("values", [])
                    label = values[0].get("label", "") if values else ""
                    attrs[code] = label
                break

        price_range = product.get("price_range", {})
        min_price = price_range.get("minimum_price", {})
        final_price = min_price.get("final_price", {}).get("value", "")
        regular_price = min_price.get("regular_price", {}).get("value", "")

        def fmt_price(v):
            try:
                return f"${float(v):.2f}"
            except (TypeError, ValueError):
                return str(v) if v else ""

        load_speed = " / ".join(filter(None, [
            attrs.get("load_index", ""),
            attrs.get("speed_rating", ""),
        ]))

        small_image = product.get("small_image", {})
        image_url = small_image.get("url", "") if isinstance(small_image, dict) else ""
        if not image_url:
            image_url = sel.css("img[src*='prioritytire']::attr(src)").get("") or ""

        rating = product.get("productRating", {})
        rating_str = ""
        if isinstance(rating, dict) and rating.get("ratingValue"):
            rating_str = f"{rating['ratingValue']} ({rating.get('ratingCount', 0)} reviews)"

        promo_labels = product.get("promo_labels", []) or []
        promos = ", ".join(str(x) for x in promo_labels if x)

        item = OrderedDict()
        item["Scraped Date"]          = datetime.now().strftime("%d-%m-%Y")
        item["Product Name"]          = (product.get("name") or "").strip()
        item["Tyre Size"]             = attrs.get("size", "")
        item["SKU"]                   = (product.get("sku") or "").strip()
        item["Price"]                 = fmt_price(final_price)
        item["Set Price"]             = fmt_price(regular_price) if regular_price != final_price else ""
        item["Load / Speed Index"]    = load_speed
        item["Manufactory Year"]      = attrs.get("dot", "")
        item["Origin"]                = (product.get("country_of_origin") or "").strip()
        item["Description"]           = ""
        item["Warranty"]              = attrs.get("treadlife_warranty", "")
        item["Manufacturer Warranty"] = ""
        item["Display Name"]          = (product.get("name") or "").strip()
        item["Brand"]                 = attrs.get("brand", "")
        item["Model"]                 = attrs.get("model", "")
        item["Run Flat"]              = attrs.get("run_flat", "")
        item["Promotions and Offers"] = promos
        item["Parts Category"]        = attrs.get("performance", "")
        item["Auto Stock"]            = (product.get("stock_status") or "").replace("_", " ").title()
        item["Tabby Method"]          = ""
        item["Category Quality"]      = attrs.get("car_type", "")
        item["Per Item"]              = fmt_price(final_price)
        item["Season"]                = attrs.get("season", "")
        item["Load Range"]            = attrs.get("load_range", "")
        item["Sidewall"]              = attrs.get("sidewall_specifics", "")
        item["Tread Depth"]           = attrs.get("tread_depth", "")
        item["Section Width"]         = attrs.get("section_width", "")
        item["Aspect Ratio"]          = attrs.get("aspect_ratio", "")
        item["Rim Diameter"]          = attrs.get("rim_diameter", "")
        item["UTQG"]                  = (product.get("utqg") or "").strip()
        item["EAN"]                   = (product.get("ean") or "").strip()
        item["UPC"]                   = (product.get("upc_code") or "").strip()
        item["MPN"]                   = (product.get("mpn1") or "").strip()
        item["Overall Diameter"]      = (product.get("overall_diameter") or "").strip()
        item["Rating"]                = rating_str
        item["Petrol"]                = ""
        item["Cloud"]                 = ""
        item["Sound"]                 = ""
        item["Video"]                 = ""
        item["Image"]                 = image_url
        item["Product URL"]           = url

        emit_status(url, 'done', parent=parent_url, url_type='product')
        return item
    except Exception:
        emit_status(url, 'blocked', parent=parent_url, url_type='product')
        return None


class ExcelWriter:
    def __init__(self, file_path):
        self.file_path = file_path
        self.lock = threading.Lock()
        self.wb = openpyxl.Workbook()
        self.ws = self.wb.active
        self.ws.title = "Sheet"
        self.headers = [
            "Scraped Date", "Product Name", "Tyre Size", "SKU", "Price", "Set Price",
            "Load / Speed Index", "Manufactory Year", "Origin", "Description",
            "Warranty", "Manufacturer Warranty", "Display Name", "Brand", "Model",
            "Run Flat", "Promotions and Offers", "Parts Category", "Auto Stock",
            "Tabby Method", "Category Quality", "Per Item", "Season", "Load Range",
            "Sidewall", "Tread Depth", "Section Width", "Aspect Ratio", "Rim Diameter",
            "UTQG", "EAN", "UPC", "MPN", "Overall Diameter", "Rating", "Petrol",
            "Cloud", "Sound", "Video", "Image", "Product URL"
        ]
        self.ws.append(self.headers)
        self.save_count = 0
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        self.wb.save(self.file_path)

    def write_row(self, item):
        if not item:
            return
        with self.lock:
            row = [item.get(h, "") for h in self.headers]
            self.ws.append(row)
            self.save_count += 1
            if self.save_count % 25 == 0:
                self.wb.save(self.file_path)

    def close(self):
        with self.lock:
            self.wb.save(self.file_path)
            self.wb.close()


def main():
    inputs = load_input_urls()
    writer = ExcelWriter(OUTPUT_FILE)
    session = c_requests.Session()

    product_queue = []
    seen_urls = set()

    for target in inputs:
        emit_status(target, 'pending', url_type='root')
        if "sitemap" in target.lower() or target.endswith(".xml"):
            prods = extract_product_urls_from_sitemap(session, target)
            for p in prods:
                if p not in seen_urls:
                    seen_urls.add(p)
                    product_queue.append((p, target))
        elif "/by-brand/" in target.lower() or "/tire/" in target.lower():
            # Direct product URL
            emit_status(target, 'pending', parent='', url_type='product')
            if target not in seen_urls:
                seen_urls.add(target)
                product_queue.append((target, ''))
        else:
            prods = extract_product_urls_from_listing(session, target)
            for p in prods:
                if p not in seen_urls:
                    seen_urls.add(p)
                    product_queue.append((p, target))

    if not product_queue:
        writer.close()
        return

    # Worker thread session pool
    thread_sessions = threading.local()

    def get_thread_session():
        if not hasattr(thread_sessions, 'session'):
            thread_sessions.session = c_requests.Session()
        return thread_sessions.session

    def worker_task(url, parent_url):
        try:
            sess = get_thread_session()
            item = parse_product_page(sess, url, parent_url)
            if item:
                writer.write_row(item)
            return item
        except Exception:
            emit_status(url, 'blocked', parent=parent_url, url_type='product')
            return None

    # Run product parsing across concurrent worker threads with rate spacing
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker_task, url, parent) for url, parent in product_queue]
        for f in as_completed(futures):
            pass

    writer.close()


if __name__ == "__main__":
    main()
