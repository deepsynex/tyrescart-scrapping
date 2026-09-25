"""Scrape tyre catalogue from https://www.pitstoparabia.com using curl_cffi
for Cloudflare/WAF TLS-fingerprint compatibility (matches the approach
already used by scan-2.py for gcco.ae).

CLI contract (same as before):
  sys.argv[1]: output XLSX path
  sys.argv[2]: optional input CSV of specific sitemap/category URLs
"""

import csv
import os
import re
import sys
import time
import threading
import datetime
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

import openpyxl
from curl_cffi import requests as c_requests
from scrapy.selector import Selector

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

OUTPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    BASE_DIR, f'pitstoparabia_sitemap_data_{_TIMESTAMP}.xlsx'
)
INPUT_CSV = sys.argv[2] if len(sys.argv) > 2 else None

DEFAULT_URL = 'https://www.pitstoparabia.com/en/sitemap/tyre_sizes'

HEADERS = {
    'Accept': 'text/html, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                  ' (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest',
    'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
}

IMPERSONATIONS = ["chrome124", "chrome120", "safari17_0", "edge101"]

# Path fragments that are clearly not tyre category/product pages --
# skip these to avoid wasting requests on nav/footer/account junk.
JUNK_PATH_KEYWORDS = (
    '/contact', '/about', '/blog', '/cart', '/account', '/login',
    '/register', '/wishlist', '/compare', '/checkout', '/customer',
    '/terms', '/privacy', '/faq', '/careers', '/store-locator',
    '/facebook.com', '/instagram.com', '/twitter.com', '/x.com',
    '/youtube.com', '/linkedin.com', '/tiktok.com', '/wa.me',
    '/whatsapp.com', '/apple.com', '/google.com', '/play.google.com',
)

XLSX_HEADERS = [
    'Sku', 'Product Name', 'Brand', 'InStock', 'Size', 'Serv. Desc', 'Year',
    'Country', 'Tyre Type', 'Tyre Marking', 'Price', 'Set Price',
    'Promo Text', 'Promo Code', 'Vehicle Type', 'Warranty', 'Sidewall Style',
    'UTQG', 'Fuel Efficiency Rating', 'Wet Grip Rating', 'External Noise',
    'Image', 'Source',
]


def emit_status(url, status, parent=None, url_type=None):
    print(f"URL_STATUS|{url}|{status}|{parent or ''}|{url_type or ''}", flush=True)


def load_start_urls():
    """A CSV of specific sitemap/category URLs (one per line, same format
    pitstoparabiabycsv.py reads) can be passed as the second CLI arg to
    crawl only those starting points instead of the hardcoded default.
    """
    if INPUT_CSV and os.path.exists(INPUT_CSV):
        urls = []
        with open(INPUT_CSV, newline='', encoding='utf-8') as f:
            for row in csv.reader(f):
                if row and row[0].strip():
                    urls.append(row[0].strip())
        if urls:
            return urls
    return [DEFAULT_URL]


def fetch_with_impersonation(session, url, max_retries=3):
    """Fetches url with rotating browser TLS impersonations and exponential
    backoff -- same approach as scan-2.py's Cloudflare-compatible fetch."""
    for attempt in range(max_retries):
        imp = IMPERSONATIONS[attempt % len(IMPERSONATIONS)]
        try:
            r = session.get(url, impersonate=imp, headers=HEADERS, timeout=25)
            if r.status_code == 200 and len(r.text) > 50:
                return r
            time.sleep(0.3 * (attempt + 1))
        except Exception:
            time.sleep(0.3 * (attempt + 1))
    return None


def get_sel_text(selector, dont_skip=None):
    dont_skip = dont_skip or []
    assert isinstance(dont_skip, list), "'dont_skip' must be a 'list' or None type"

    required_tags = ['a', 'i', 'u', 'strong', 'b', 'em', 'span', 'sup', 'sub', 'font']
    required_tags.extend(dont_skip)

    results = []
    for text in selector.getall():
        for tag in required_tags:
            text = re.sub(r'<\s*%s>' % tag, '', text)
            text = re.sub(r'</\s*%s>' % tag, '', text)
            text = re.sub(r'<\s*%s[^\w][^>]*>' % tag, '', text)
            text = re.sub(r'</\s*%s[^\w]\s*>' % tag, '', text)

        text = text.replace('\r\n', ' ')
        text = re.sub(r'<!--.*?-->', '', text, re.S)
        sel = Selector(text=text)

        all_texts = sel.xpath(''.join([
            'descendant::text()/parent::*[name()!="td"]',
            '[name()!="script"][name()!="style"]/text()'
        ])).getall()
        all_texts = [x.strip() for x in all_texts]
        results += all_texts

    return list(filter(None, results))


def parse_brands(session, source_url):
    """Sitemap/category-index page -> list of listing-page URLs to crawl."""
    emit_status(source_url, 'running')
    r = fetch_with_impersonation(session, source_url)
    if not r:
        emit_status(source_url, 'blocked')
        return []

    sel = Selector(text=r.text)

    # Try XML sitemap format first (<loc>...</loc>)
    urls = sel.css('loc::text').getall()
    # Fall back to an HTML sitemap page (plain <a href="..."> links)
    if not urls:
        urls = sel.css('a::attr(href)').getall()

    listing_urls = []
    seen_urls = set()
    for url in urls:
        url = (url or '').strip()
        if not url or url in seen_urls:
            continue
        if url.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            continue
        if any(kw in url.lower() for kw in JUNK_PATH_KEYWORDS):
            continue
        if url.startswith('http') and 'pitstoparabia.com' not in url:
            continue
        seen_urls.add(url)
        full_url = url if url.startswith('http') else r.url.split('/en/')[0] + url
        listing_urls.append(full_url)

    emit_status(source_url, 'done')
    return listing_urls


def parse_listing(session, listing_url, source_url):
    """Category/listing page -> list of product page URLs."""
    r = fetch_with_impersonation(session, listing_url)
    if not r:
        return []

    try:
        sel = Selector(text=r.json()['products'])
    except Exception:
        sel = Selector(text=r.text)

    product_urls = []
    for url in sel.css('.product-item-link::attr(href)').getall():
        full_url = url if url.startswith('http') else r.url.rstrip('/').rsplit('/', 1)[0] + '/' + url.lstrip('/')
        emit_status(full_url, 'pending', parent=source_url, url_type='product')
        product_urls.append(full_url)

    return product_urls


def parse_detail(session, url, source_url):
    emit_status(url, 'running', parent=source_url, url_type='product')
    r = fetch_with_impersonation(session, url)
    if not r:
        emit_status(url, 'blocked', parent=source_url, url_type='product')
        return None

    try:
        response = Selector(text=r.text)

        add_to_cart_btn = response.css(
            'button#product-addtocart-button, div.actions.add-to-cart button, button.tocart, button.add-to-cart'
        )
        out_of_stock_div = response.css('div.stock.unavailable, .stock.unavailable')

        if add_to_cart_btn:
            in_stock = 'Yes'
        elif out_of_stock_div:
            in_stock = 'No'
        else:
            txt = ' '.join(response.css('div.stock::text, .stock::text').getall()).lower()
            in_stock = 'No' if ('out of stock' in txt or 'unavailable' in txt) else ''

        brand_val = response.css('.brand a::attr(title)').get('').strip()
        raw_name = response.css('h1[itemprop="name"]::text').get('').strip()

        item = OrderedDict()
        item['Sku'] = response.css('.sku::text').get('').strip()
        item['Product Name'] = raw_name.replace(brand_val, '').replace('  ', '').strip()
        item['Brand'] = brand_val
        item['InStock'] = in_stock
        item['Size'] = response.css('.size_block span:contains("Size:") + b::text').get('').strip().replace('  ', '').replace('/None', '')
        item['Serv. Desc'] = ''.join([t.strip() for t in response.css('span:contains("Serv. Desc")').xpath('parent::*/text()').getall() if t.strip()]).replace(' ', '')
        item['Year'] = response.css('[title="Year of manufacture"]::text').get('').strip()
        item['Country'] = ''.join([t.strip() for t in response.css('span:contains("Country")').xpath('parent::*/text()').getall()])
        item['Tyre Type'] = response.css('.detail_left .v_type::attr(alt)').get('').strip().replace('Run Flat', 'Runflat')
        item['Tyre Marking'] = response.css('[itemprop="name"] .part_no::text').get('').strip()
        item['Price'] = response.css('[class="product-info-price product_price"] .price::text').get('').strip().replace('AED ', '')
        item['Set Price'] = response.css('.set_price .price::text').get('').strip().replace('AED ', '')
        item['Promo Text'] = ' | '.join(get_sel_text(response.css('.offer_block_inner')))
        item['Promo Code'] = response.css('.promo_cnt b::text').get('').strip()
        item['Vehicle Type'] = response.css('.product_thumbnail_container .v_type::attr(alt)').get('').strip()
        item['Warranty'] = ' '.join(get_sel_text(response.css('.warranty span')))
        item['Sidewall Style'] = response.css('span:contains("Sidewall Style")').xpath('parent::li/text()').get('').strip()

        try:
            item['UTQG'] = ' '.join(get_sel_text(response.css('span:contains("UTQG")').xpath('parent::*/span/text()'))[1:])
        except Exception:
            item['UTQG'] = ' '.join([t.strip() for t in response.css('span:contains("UTQG")').xpath('parent::*/span/text()').getall()][1:])

        item['Fuel Efficiency Rating'] = (response.css('.tyres_labels .tyre_label::attr(title)').re_first('Fuel Efficiency Rating:(.+)') or '').strip()
        item['Wet Grip Rating'] = (response.css('.tyres_labels .tyre_label::attr(title)').re_first('Wet Grip Rating:(.+)') or '').strip()
        item['External Noise'] = (response.css('.tyres_labels .tyre_label::attr(title)').re_first('External Noise:(.+)') or '').strip()

        images = response.css('[property="og:image"]::attr(content)').getall()
        item['Image'] = images[-1] if images else ''
        item['Source'] = url

        emit_status(url, 'done', parent=source_url, url_type='product')
        return item
    except Exception:
        emit_status(url, 'blocked', parent=source_url, url_type='product')
        return None


class ExcelWriter:
    def __init__(self, file_path):
        self.file_path = file_path
        self.lock = threading.Lock()
        self.wb = openpyxl.Workbook()
        self.ws = self.wb.active
        self.ws.title = 'Sheet'
        self.ws.append(XLSX_HEADERS)
        self.save_count = 0
        os.makedirs(os.path.dirname(os.path.abspath(file_path)) or '.', exist_ok=True)
        self.wb.save(self.file_path)

    def write_row(self, item):
        if not item:
            return
        with self.lock:
            self.ws.append([item.get(h, '') for h in XLSX_HEADERS])
            self.save_count += 1
            if self.save_count % 25 == 0:
                self.wb.save(self.file_path)

    def close(self):
        with self.lock:
            self.wb.save(self.file_path)
            self.wb.close()


def main():
    writer = ExcelWriter(OUTPUT_FILE)
    session = c_requests.Session()

    start_urls = load_start_urls()
    for u in start_urls:
        emit_status(u, 'pending', url_type='sitemap')

    product_targets = []  # [(product_url, source_url), ...]

    # Discovery (sitemap -> listing pages -> product links) used to fetch
    # every listing page one at a time, which meant nothing reached the
    # product-scraping thread pool below until that whole chain finished --
    # for a sitemap with dozens of listing pages that's most of a run spent
    # idle. Fetching listing pages concurrently fixes that; parse_listing's
    # own per-request retry/backoff is untouched so behavior per-request
    # doesn't change, just how many run at once.
    discovery_sessions = threading.local()

    def get_discovery_session():
        if not hasattr(discovery_sessions, 'session'):
            discovery_sessions.session = c_requests.Session()
        return discovery_sessions.session

    for source_url in start_urls:
        listing_urls = parse_brands(session, source_url)
        if not listing_urls:
            continue
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_listing = {
                executor.submit(parse_listing, get_discovery_session(), listing_url, source_url): listing_url
                for listing_url in listing_urls
            }
            for future in as_completed(future_to_listing):
                try:
                    for product_url in future.result():
                        product_targets.append((product_url, source_url))
                except Exception:
                    emit_status(future_to_listing[future], 'blocked', parent=source_url, url_type='listing')

    if not product_targets:
        writer.close()
        return

    thread_sessions = threading.local()

    def get_thread_session():
        if not hasattr(thread_sessions, 'session'):
            thread_sessions.session = c_requests.Session()
        return thread_sessions.session

    def worker_task(product_url, source_url):
        try:
            item = parse_detail(get_thread_session(), product_url, source_url)
            if item:
                writer.write_row(item)
            return item
        except Exception:
            emit_status(product_url, 'blocked', parent=source_url, url_type='product')
            return None

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker_task, product_url, source_url) for product_url, source_url in product_targets]
        for _ in as_completed(futures):
            pass

    writer.close()


if __name__ == '__main__':
    main()
    