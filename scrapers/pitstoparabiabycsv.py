import csv
import os
import random
import re
import sys
import threading
import time
from datetime import datetime
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests
from parsel import Selector
import openpyxl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cf_cookie_fetcher

# =========================
# OUTPUT & INPUT SETUP
# =========================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.now().strftime("%d-%m-%Y")

OUTPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    BASE_DIR, f"pitstoparabia_data_{TODAY}.xlsx"
)
CSV_FILE = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    BASE_DIR, "testurls.csv"
)

# Optional Proxy from environment
PROXY = os.environ.get('SCRAPER_PROXY') or None

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Not A(Brand";v="8", "Chromium";v="131", "Google Chrome";v="131"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


_print_lock = threading.Lock()


def emit_status(url, status, parent=None, url_type=None):
    """Protocol for dashboard live progress."""
    with _print_lock:
        print(f"URL_STATUS|{url}|{status}|{parent or ''}|{url_type or ''}", flush=True)


def normalise_url(url):
    return (url or '').split('#', 1)[0].rstrip('/')


def clean_text_list(texts):
    return [t.strip() for t in texts if t and t.strip()]


def get_sel_text(selector_list):
    results = []
    for sel in selector_list:
        texts = sel.xpath('.//text()[not(parent::script) and not(parent::style)]').getall()
        results.extend(clean_text_list(texts))
    return results


class PitstopArabiaScraper:
    def __init__(self, output_file, input_csv, max_workers=3, seed_workers=5):
        self.output_file = output_file
        self.input_csv = input_csv
        self.max_workers = max_workers
        self.seed_workers = seed_workers
        self.seen_urls = set()
        self.seen_product_keys = set()
        self.scraped_items = []
        self._items_lock = threading.Lock()

    def fetch(self, url, referer=None, retries=5):
        headers = HEADERS.copy()
        if referer:
            headers['Referer'] = referer

        # Small randomized delay before every request (not just retries) so a
        # burst of concurrently-submitted product fetches doesn't all land on
        # the server in the same instant, which is what trips its rate-based
        # bot detection even though curl_cffi's TLS impersonation otherwise
        # passes its fingerprint checks fine.
        time.sleep(random.uniform(0.2, 0.6))

        for attempt in range(retries):
            impersonate = 'chrome131' if attempt % 2 == 0 else 'safari17_0'
            try:
                kwargs = {
                    'headers': headers,
                    'impersonate': impersonate,
                    'timeout': 20,
                }
                if PROXY:
                    kwargs['proxies'] = {'http': PROXY, 'https': PROXY}

                resp = requests.get(url, **kwargs)
                if resp.status_code == 200:
                    return resp
                elif resp.status_code == 403:
                    # A real Cloudflare JS/Turnstile challenge (not just a
                    # transient rate-limit) can't be solved by retrying with
                    # curl_cffi no matter how long we back off -- go straight
                    # to the stealth-browser fallback instead of burning the
                    # rest of the retry budget on a request type that will
                    # never get past it.
                    if 'Just a moment' in resp.text or '__cf_chl_rt_tk' in resp.text:
                        break
                    delay = min(2.0 * (attempt + 1) + random.uniform(0, 1.5), 12.0)
                    time.sleep(delay)
                else:
                    time.sleep(1.0 + random.uniform(0, 0.5))
            except Exception:
                time.sleep(1.5 * (attempt + 1) + random.uniform(0, 1.0))

        return _cf_cookie_fetcher.fetch(url)

    def parse_product_detail(self, url, html, source_url):
        emit_status(url, 'running')
        sel = Selector(text=html)

        # Check in-stock
        add_to_cart_btn = sel.css('button#product-addtocart-button, div.actions.add-to-cart button, button.tocart, button.add-to-cart')
        out_of_stock_div = sel.css('div.stock.unavailable, .stock.unavailable')

        if add_to_cart_btn:
            in_stock = 'Yes'
        elif out_of_stock_div:
            in_stock = 'No'
        else:
            txt = ' '.join(sel.css('div.stock::text, .stock::text').getall()).lower()
            in_stock = 'No' if ('out of stock' in txt or 'unavailable' in txt) else ''

        if in_stock != 'Yes':
            emit_status(url, 'done')
            return None

        brand_val = (sel.css('.brand a::attr(title)').get() or '').strip()
        raw_name = (sel.css('h1[itemprop="name"]::text').get() or '').strip()

        item = OrderedDict()
        item['Sku'] = (sel.css('.sku::text').get() or '').strip()
        item['Product Name'] = raw_name.replace(brand_val, '').replace('  ', '').strip()
        item['Brand'] = brand_val

        item['InStock'] = in_stock
        item['Size'] = (sel.css('.size_block span:contains("Size:") + b::text').get() or '').strip().replace('  ', '').replace('/None', '')
        item['Serv. Desc'] = '' if re.search(r'--[A-Za-z]', (sd := ''.join([t.strip() for t in sel.css('span:contains("Serv. Desc")').xpath('parent::*/text()').getall() if t.strip()]).replace(' ', ''))) else sd
        item['Year'] = (sel.css('[title="Year of manufacture"]::text').get() or '').strip()
        item['product_name'] = ' '.join(filter(None, [
            item['Brand'], item['Size'], item['Serv. Desc'], item['Product Name'], item['Year']
        ]))
        item['Country'] = ''.join([t.strip() for t in sel.css('span:contains("Country")').xpath('parent::*/text()').getall() if t.strip()])
        item['Tyre Type'] = (sel.css('.detail_left .v_type::attr(alt)').get() or '').strip().replace('Run Flat', 'Runflat')
        item['Tyre Marking'] = (sel.css('[itemprop="name"] .part_no::text').get() or '').strip()
        item['Price'] = (sel.css('[class="product-info-price product_price"] .price::text').get() or '').strip().replace('AED ', '')
        item['Set Price'] = (sel.css('.set_price .price::text').get() or '').strip().replace('AED ', '')
        item['Promo Text'] = ' | '.join(get_sel_text(sel.css('.offer_block_inner')))
        item['Promo Code'] = (sel.css('.promo_cnt b::text').get() or '').strip()
        item['Vehicle Type'] = (sel.css('.product_thumbnail_container .v_type::attr(alt)').get() or '').strip()
        item['Warranty'] = ' '.join(get_sel_text(sel.css('.warranty span')))
        item['Sidewall Style'] = (sel.css('span:contains("Sidewall Style")').xpath('parent::li/text()').get() or '').strip()

        try:
            item['UTQG'] = ' '.join(get_sel_text(sel.css('span:contains("UTQG")').xpath('parent::*/span'))[1:])
        except Exception:
            item['UTQG'] = ' '.join([t.strip() for t in sel.css('span:contains("UTQG")').xpath('parent::*/span/text()').getall()][1:])

        item['Fuel Efficiency Rating'] = (sel.css('.tyres_labels .tyre_label::attr(title)').re_first(r'Fuel Efficiency Rating:(.+)') or '').strip()
        item['Wet Grip Rating'] = (sel.css('.tyres_labels .tyre_label::attr(title)').re_first(r'Wet Grip Rating:(.+)') or '').strip()
        item['External Noise'] = (sel.css('.tyres_labels .tyre_label::attr(title)').re_first(r'External Noise:(.+)') or '').strip()

        images = sel.css('[property="og:image"]::attr(content)').getall()
        item['Image'] = images[-1] if images else ''
        item['Source'] = url

        emit_status(url, 'done')
        print(item['product_name'])
        return item

    def process_source_url(self, source_url):
        emit_status(source_url, 'running')
        resp = self.fetch(source_url)
        if not resp:
            emit_status(source_url, 'blocked')
            return

        sel = Selector(text=resp.text)
        is_product_page = bool(sel.css('h1[itemprop="name"], .product-info-price, #product-addtocart-button').get())

        if is_product_page:
            item = self.parse_product_detail(source_url, resp.text, source_url)
            if item:
                self.scraped_items.append(item)
            emit_status(source_url, 'done')
            return

        # Listing Crawling with Pagination
        current_page_url = source_url
        current_html = resp.text
        listing_pages_seen = set()

        while current_page_url:
            norm_page = normalise_url(current_page_url)
            if norm_page in listing_pages_seen:
                break
            listing_pages_seen.add(norm_page)

            page_sel = Selector(text=current_html)
            product_links = page_sel.css('a.product-item-link::attr(href)').getall()

            # Process product links in parallel
            product_tasks = []
            for link in product_links:
                if not link or not link.strip():
                    continue
                link = link.strip()
                if link.startswith('http'):
                    full_product_url = link
                elif link.startswith('/'):
                    full_product_url = f"https://www.pitstoparabia.com{link}"
                else:
                    full_product_url = f"https://www.pitstoparabia.com/en/tyres/{link}"

                prod_key = normalise_url(full_product_url)
                with self._items_lock:
                    if prod_key in self.seen_product_keys:
                        continue
                    self.seen_product_keys.add(prod_key)
                emit_status(full_product_url, 'pending', parent=source_url, url_type='product')
                product_tasks.append(full_product_url)

            # Scrape product detail pages
            if product_tasks:
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_url = {
                        executor.submit(self.fetch, purl, current_page_url): purl for purl in product_tasks
                    }
                    for future in as_completed(future_to_url):
                        purl = future_to_url[future]
                        try:
                            presp = future.result()
                            if presp and presp.status_code == 200:
                                item = self.parse_product_detail(purl, presp.text, source_url)
                                if item:
                                    self.scraped_items.append(item)
                            else:
                                emit_status(purl, 'blocked')
                        except Exception:
                            emit_status(purl, 'blocked')

            # Find next page
            next_page = page_sel.css('a.next::attr(href), .pages-item-next a::attr(href), a.action.next::attr(href)').get()
            if next_page:
                if not next_page.startswith('http'):
                    next_page = f"https://www.pitstoparabia.com{next_page}" if next_page.startswith('/') else f"https://www.pitstoparabia.com/en/tyres/{next_page}"
                
                emit_status(next_page, 'pending', parent=source_url, url_type='listing')
                emit_status(next_page, 'running')
                next_resp = self.fetch(next_page, referer=current_page_url)
                if next_resp and next_resp.status_code == 200:
                    emit_status(next_page, 'done')
                    current_page_url = next_page
                    current_html = next_resp.text
                else:
                    emit_status(next_page, 'blocked')
                    break
            else:
                break

        emit_status(source_url, 'done')

    def run(self):
        seed_urls = []
        if os.path.exists(self.input_csv):
            with open(self.input_csv, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row and row[0].strip().startswith('http'):
                        url = row[0].strip()
                        norm = normalise_url(url)
                        if norm not in self.seen_urls:
                            self.seen_urls.add(norm)
                            seed_urls.append(url)

        if not seed_urls:
            print("No valid URLs found in CSV.")
            return

        for url in seed_urls:
            emit_status(url, 'pending', url_type='root')

        # Seed (root) URLs used to be processed one at a time, which meant a
        # large input list spent most of its time idle waiting on whichever
        # single source URL was currently in flight. Processing several seed
        # URLs concurrently is what actually speeds up a big run -- the
        # per-request pacing/backoff inside fetch() is untouched, so the low
        # block rate is preserved regardless of how many seeds run at once.
        with ThreadPoolExecutor(max_workers=self.seed_workers) as executor:
            future_to_url = {executor.submit(self.process_source_url, url): url for url in seed_urls}
            for future in as_completed(future_to_url):
                try:
                    future.result()
                except Exception:
                    emit_status(future_to_url[future], 'blocked', url_type='root')

        # Write to Excel
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Products"

        headers = [
            'Sku', 'Product Name', 'product_name', 'Brand', 'InStock', 'Size', 'Serv. Desc',
            'Year', 'Country', 'Tyre Type', 'Tyre Marking', 'Price', 'Set Price',
            'Promo Text', 'Promo Code', 'Vehicle Type', 'Warranty', 'Sidewall Style',
            'UTQG', 'Fuel Efficiency Rating', 'Wet Grip Rating', 'External Noise',
            'Image', 'Source'
        ]
        ws.append(headers)

        for item in self.scraped_items:
            ws.append([item.get(h, '') for h in headers])

        os.makedirs(os.path.dirname(os.path.abspath(self.output_file)), exist_ok=True)
        wb.save(self.output_file)
        print(f"Scraping completed. Saved {len(self.scraped_items)} items to {self.output_file}")


if __name__ == '__main__':
    scraper = PitstopArabiaScraper(OUTPUT_FILE, CSV_FILE)
    try:
        scraper.run()
    finally:
        _cf_cookie_fetcher.close()
