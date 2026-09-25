"""Scrape tyre catalogue at https://www.proshop.ae/
Conforms to TyresCart protocol (sys.argv[1]=output, sys.argv[2]=input_csv, URL_STATUS).
"""

import os
import re
import sys
import csv
from collections import OrderedDict
from datetime import datetime

from scrapy import Request, Spider
from scrapy.crawler import CrawlerProcess


class ProshopScraper(Spider):
    name = "proshop"
    allowed_domains = ["www.proshop.ae", "proshop.ae"]

    # ---- OUTPUT FILE with DATE (sys.argv[1]) ----
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    today = datetime.now().strftime("%d-%m-%Y")
    output_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        base_dir, f"proshop_data_{today}.xlsx"
    )

    # ---- INPUT CSV (sys.argv[2]) ----
    csv_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        base_dir, "testurls.csv"
    )

    DEFAULT_START_URLS = ["https://www.proshop.ae/tyres.html?product_list_limit=36"]

    # ---- SETTINGS ----
    custom_settings = {
        "FEED_EXPORTERS": {"xlsx": "scrapy_xlsx.XlsxItemExporter"},
        "COOKIES_ENABLED": True,
        "FEEDS": {
            output_file: {"format": "xlsx", "encoding": "utf8", "store_empty": False}
        },
        "CONCURRENT_REQUESTS": 4,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 8,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504],
        "LOG_LEVEL": "INFO",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_requests = {}
        self.failed_sources = set()
        self.seen_detail_urls = set()

    # ---- TYRESCART PROTOCOL (KEEP) ----
    def emit_status(self, url, status, parent=None, url_type=None):
        print(f"URL_STATUS|{url}|{status}|{parent or ''}|{url_type or ''}")

    def make_tracked_request(self, url, source_url, callback):
        self.pending_requests[source_url] = self.pending_requests.get(source_url, 0) + 1
        return Request(
            url=url,
            callback=callback,
            errback=self.request_failed,
            headers=self.headers,
            meta={"source_url": source_url, "display_url": url},
            dont_filter=True,
        )

    def finish_source_request(self, source_url):
        remaining = self.pending_requests.get(source_url, 1) - 1
        if remaining > 0:
            self.pending_requests[source_url] = remaining
            return
        self.pending_requests.pop(source_url, None)
        status = "blocked" if source_url in self.failed_sources else "done"
        self.emit_status(source_url, status)

    def request_failed(self, failure):
        source_url = failure.request.meta.get("source_url", failure.request.url)
        self.emit_status(
            failure.request.meta.get("display_url", failure.request.url), "blocked"
        )
        self.failed_sources.add(source_url)
        self.logger.error("Request failed: %s", failure.request.url)
        self.finish_source_request(source_url)

    # ---- ENTRY POINT: reads input CSV ----
    async def start(self):
        urls = []
        if os.path.exists(self.csv_file):
            with open(self.csv_file, newline="", encoding="utf-8") as f:
                for row in csv.reader(f):
                    if not row:
                        continue
                    src = row[0].strip()
                    if src.startswith("http"):
                        urls.append(src)

        if not urls:
            urls = self.DEFAULT_START_URLS

        for source_url in urls:
            self.emit_status(source_url, "pending", url_type="root")
            yield self.make_tracked_request(
                source_url, source_url, self.parse_input_url
            )

    # ---- ROUTING: product vs listing ----
    def parse_input_url(self, response):
        is_product = bool(
            response.css("h1.page-title .base::text, form#product_addtocart_form").get()
        )
        if is_product:
            yield from self.parse_detail(response)
        else:
            yield from self.parse_listing(response)

    # ---- LISTING + PAGINATION ----
    def parse_listing(self, response):
        source_url = response.meta.get("source_url", response.url)
        self.emit_status(response.url, "running")
        try:
            links = response.css(
                "ol.products.list.items.product-items a.product-item-link::attr(href)"
            ).getall()
            self.logger.info("Listing %s: found %s products", response.url, len(links))

            for href in links:
                product_url = response.urljoin(href)
                key = product_url.rstrip("/")
                if key in self.seen_detail_urls:
                    continue
                self.seen_detail_urls.add(key)
                self.emit_status(product_url, "pending", parent=source_url, url_type="product")
                yield self.make_tracked_request(product_url, source_url, self.parse_detail)

            next_page = response.css(
                "a.link.next::attr(href), a.action.next::attr(href), link[rel='next']::attr(href)"
            ).get()
            if next_page:
                next_url = response.urljoin(next_page)
                self.emit_status(next_url, "pending", parent=source_url, url_type="listing")
                yield self.make_tracked_request(next_url, source_url, self.parse_listing)
        finally:
            self.emit_status(response.url, "done")
            self.finish_source_request(source_url)

    # ---- DETAIL EXTRACTION ----
    def parse_detail(self, response):
        source_url = response.meta.get("source_url", response.url)
        self.emit_status(response.url, "running")
        try:
            name = self._clean(response.css("h1.page-title .base::text").get())
            if not name:
                self.logger.warning("Skipping unexpected product page: %s", response.url)
                return

            specs = {}
            for row in response.css(".full-specifications > div"):
                key = self._clean(
                    " ".join(row.css("strong ::text, strong::text").getall())
                ).rstrip(":").lower()
                value = self._clean(
                    " ".join(row.css("span ::text, span::text").getall())
                )
                if key and value:
                    specs[key] = value

            quick_specs = self._labelled_values(response.css(".tyre-additional-details"))
            size = (
                self._clean(response.css(".tyre-size .value::text").get())
                or specs.get("size")
                or quick_specs.get("size", "")
            )
            width, aspect_ratio, rim_diameter = self._size_parts(size)
            load_speed = specs.get("load index") or quick_specs.get(
                "load index and speed rate", ""
            )

            regular_price = self._clean(
                response.css(
                    ".product-info-price .per-item-price .old-price .price::text"
                ).get()
            )
            special_price = self._clean(
                response.css(
                    ".product-info-price .per-item-price .special-price .price::text"
                ).get()
            )
            current_price = self._clean(
                response.css(".product-info-price .per-item-price .price::text").get()
            )
            if not special_price:
                regular_price = current_price

            item = OrderedDict()
            item["Scraped Date"] = datetime.now().strftime("%d-%m-%Y")
            item["Name"] = name
            item["Brand"] = specs.get("brand", self._brand_from_name(name))
            item["Pattern"] = specs.get("pattern", "")
            item["SKU"] = response.css(
                "form#product_addtocart_form::attr(data-product-sku)"
            ).get("").strip()
            item["Tire Size"] = size
            item["Width"] = specs.get("width", width)
            item["Aspect Ratio"] = aspect_ratio
            item["Rim Diameter"] = specs.get("rim diameter", rim_diameter)
            item["Load/Speed Index"] = load_speed
            item["Country of Origin"] = specs.get(
                "country of origin", quick_specs.get("origin", "")
            )
            item["Year"] = specs.get(
                "production year", quick_specs.get("production year", "")
            )
            item["Warranty"] = specs.get("warranty", quick_specs.get("warranty", ""))
            item["Tyre Type"] = specs.get("tyre type", "")
            item["Base Price"] = regular_price
            item["Offer Price"] = special_price
            item["In Stock"] = (
                "Yes"
                if response.css(
                    "form#product_addtocart_form button.tocart:not([disabled])"
                )
                else "No"
            )
            item["Image URL"] = response.css(
                'meta[property="og:image"]::attr(content)'
            ).get("").strip()
            item["Source"] = response.url

            # Extra attributes
            fixed_specifications = {
                "brand", "pattern", "size", "width", "rim diameter",
                "load index", "country of origin", "production year",
                "warranty", "tyre type",
            }
            for key, value in specs.items():
                if key in fixed_specifications:
                    continue
                column = key.title()
                if column not in item:
                    item[column] = value

            yield item
        finally:
            self.emit_status(response.url, "done")
            self.finish_source_request(source_url)

    # ---- HELPERS ----
    @staticmethod
    def _labelled_values(selector):
        values = {}
        for text in selector.css("li ::text, li::text").getall():
            clean = " ".join(text.split())
            if ":" in clean:
                key, value = clean.split(":", 1)
                values[key.strip().lower()] = value.strip()
        return values

    @staticmethod
    def _size_parts(size):
        match = re.search(
            r"(\d{3})\s*/\s*(\d{2,3}(?:\.\d+)?)\s*R?\s*(\d{2}(?:\.\d+)?)",
            size, re.I,
        )
        return match.groups() if match else ("", "", "")

    @staticmethod
    def _brand_from_name(name):
        match = re.search(r"\|\s*([^|]+?)(?:\s+Tyres)?$", name, re.I)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _clean(value):
        return " ".join((value or "").split())


if __name__ == "__main__":
    process = CrawlerProcess(ProshopScraper.custom_settings)
    process.crawl(ProshopScraper)
    process.start()
