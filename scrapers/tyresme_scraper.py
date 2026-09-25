"""Scrape tyre catalogue at https://tyresme.com/
Conforms to TyresCart protocol (sys.argv[1]=output, sys.argv[2]=input_csv, URL_STATUS).
"""

import os
import re
import sys
import csv
import json
from collections import OrderedDict
from datetime import datetime

from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess


class TyresMeScraper(Spider):
    name = "tyresme"
    allowed_domains = ["tyresme.com", "www.tyresme.com"]

    # ---- OUTPUT FILE with DATE (sys.argv[1]) ----
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    today = datetime.now().strftime("%d-%m-%Y")
    output_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        base_dir, f"tyresme_data_{today}.xlsx"
    )

    # ---- INPUT CSV (sys.argv[2]) ----
    csv_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        base_dir, "testurls.csv"
    )

    DEFAULT_SITEMAPS = ["https://tyresme.com/sitemap_products_1.xml?from=1&to=999999999"]

    # ---- SETTINGS ----
    custom_settings = {
        "FEED_EXPORTERS": {"xlsx": "scrapy_xlsx.XlsxItemExporter"},
        "COOKIES_ENABLED": True,
        "FEEDS": {
            output_file: {"format": "xlsx", "encoding": "utf8", "store_empty": False}
        },
        "CONCURRENT_REQUESTS": 3,
        "DOWNLOAD_DELAY": 0.5,
        "HTTPERROR_ALLOWED_CODES": [429, 503],
        "RETRY_HTTP_CODES": [500, 502, 504, 408],
        "LOG_LEVEL": "INFO",
        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/html, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/html, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    SPEC_TOKENS = re.compile(
        r"\b(BLT|BSW|WL|OWL|VSB|TL|RFT|MOE|SSR|MFS|FO|AO|MO1?|NO|TO|RO|[EJ]O|AT|HT|MT|ST|OE|XL|LT|C)\b",
        re.IGNORECASE,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pending_requests = {}
        self.failed_sources = set()
        self.seen_detail_urls = set()

    # ---- TYRESCART PROTOCOL (KEEP) ----
    def emit_status(self, url, status, parent=None, url_type=None):
        print(f"URL_STATUS|{url}|{status}|{parent or ''}|{url_type or ''}")

    def make_tracked_request(self, url, source_url, callback, cb_kwargs=None):
        self.pending_requests[source_url] = self.pending_requests.get(source_url, 0) + 1
        return Request(
            url=url,
            callback=callback,
            errback=self.request_failed,
            headers=self.headers,
            meta={
                "source_url": source_url,
                "display_url": url,
                "handle_httpstatus_list": [429, 503],
            },
            cb_kwargs=cb_kwargs or {},
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
            urls = self.DEFAULT_SITEMAPS

        for source_url in urls:
            self.emit_status(source_url, "pending", url_type="root")
            yield self.make_tracked_request(
                source_url, source_url, self.parse_input_url
            )

    # ---- ROUTING: collection vs product vs sitemap ----
    def parse_input_url(self, response):
        url = response.url
        if "/products/" in url:
            handle = url.rstrip("/").split("/products/")[-1]
            json_url = f"https://tyresme.com/products/{handle}.json"
            yield from self._request_product_json(json_url, response.meta.get("source_url", url), product_url=url)
        elif ".xml" in url or "sitemap" in url:
            yield from self.parse_sitemap(response)
        else:
            yield from self.parse_collection(response)

    def _request_product_json(self, json_url, source_url, product_url=None):
        key = json_url.rstrip("/")
        if key in self.seen_detail_urls:
            return
        self.seen_detail_urls.add(key)
        self.emit_status(json_url, "pending", parent=source_url, url_type="product")
        yield self.make_tracked_request(
            json_url,
            source_url,
            self.parse_product,
            cb_kwargs={"product_url": product_url or json_url.replace(".json", "")},
        )

    # ---- SITEMAP PARSER ----
    def parse_sitemap(self, response):
        source_url = response.meta.get("source_url", response.url)
        self.emit_status(response.url, "running")
        try:
            urls = response.xpath("//*[local-name()='loc']/text()").getall()
            self.logger.info("Sitemap %s: %d URLs found", response.url, len(urls))
            for u in urls:
                u = u.strip()
                if not u:
                    continue
                if "/products/" in u:
                    handle = u.rstrip("/").split("/products/")[-1]
                    json_url = f"https://tyresme.com/products/{handle}.json"
                    yield from self._request_product_json(json_url, source_url, product_url=u)
                elif "sitemap" in u and ".xml" in u:
                    self.emit_status(u, "pending", parent=source_url, url_type="listing")
                    yield self.make_tracked_request(u, source_url, self.parse_sitemap)
        finally:
            self.emit_status(response.url, "done")
            self.finish_source_request(source_url)

    # ---- COLLECTION PARSER ----
    def parse_collection(self, response):
        source_url = response.meta.get("source_url", response.url)
        self.emit_status(response.url, "running")
        try:
            base = response.url.split("?")[0].rstrip("/")
            page = int(response.meta.get("collection_page", 1))

            content_type = response.headers.get(
                "Content-Type", b""
            ).decode("utf-8", errors="ignore")
            if "json" not in content_type:
                if not base.endswith("/products"):
                    api_url = f"{base}/products.json?page=1&limit=250"
                else:
                    api_url = f"{base}.json?page=1&limit=250"
                self.emit_status(api_url, "pending", parent=source_url, url_type="listing")
                yield self.make_tracked_request(api_url, source_url, self.parse_collection)
                return

            try:
                data = response.json()
            except Exception:
                self.logger.warning("Non-JSON collection response: %s", response.url)
                return

            products = data.get("products", [])
            self.logger.info(
                "Collection page %d: %d products at %s", page, len(products), response.url
            )

            for product in products:
                handle = product.get("handle", "")
                if not handle:
                    continue
                json_url = f"https://tyresme.com/products/{handle}.json"
                product_url = f"https://tyresme.com/products/{handle}"
                yield from self._request_product_json(json_url, source_url, product_url)

            if len(products) == 250:
                next_page = page + 1
                api_base = response.url.split("?")[0]
                next_url = f"{api_base}?page={next_page}&limit=250"
                self.emit_status(
                    next_url, "pending", parent=source_url, url_type="listing"
                )
                req = self.make_tracked_request(
                    next_url, source_url, self.parse_collection
                )
                req.meta["collection_page"] = next_page
                yield req
        finally:
            self.emit_status(response.url, "done")
            self.finish_source_request(source_url)

    # ---- PRODUCT DETAIL (Shopify JSON API) ----
    def parse_product(self, response, product_url=""):
        source_url = response.meta.get("source_url", response.url)
        self.emit_status(response.url, "running")
        try:
            if response.status in (429, 503):
                self.logger.warning("Rate limited (%d): %s", response.status, response.url)
                self.failed_sources.add(source_url)
                return

            try:
                data = response.json()
            except Exception as e:
                self.logger.error("JSON parse error at %s: %s", response.url, e)
                return

            product = data.get("product", {})
            if not product:
                return

            title = product.get("title", "").strip()
            vendor = product.get("vendor", "").strip()
            body_html = product.get("body_html", "") or ""
            tags = product.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            variants = product.get("variants", [])
            variant = variants[0] if variants else {}
            sku = variant.get("sku", "")
            price = variant.get("price", "") or ""
            compare_at_price = variant.get("compare_at_price", "") or ""
            available = variant.get("available", True)

            if compare_at_price and compare_at_price not in ("0.00", price):
                base_price = compare_at_price
                offer_price = price
            else:
                base_price = price
                offer_price = ""

            images = product.get("images", [])
            image_url = images[0].get("src", "") if images else ""

            # Dimensions from title
            size_match = re.search(
                r"(\d{3})[/\-](\d{2,3})[R\s\-](\d{2}(?:\.\d+)?)",
                title, re.IGNORECASE,
            )
            width = size_match.group(1) if size_match else ""
            ratio = size_match.group(2) if size_match else ""
            rim = size_match.group(3) if size_match else ""

            ls_match = re.search(r"\b(\d{2,3}(?:/\d{2,3})?)([A-Z])\b", title)
            load_index = ls_match.group(1) if ls_match else ""
            speed_rating = ls_match.group(2) if ls_match else ""

            year_matches = re.findall(r"\b(20\d{2})\b", title)
            year = year_matches[-1] if year_matches else ""

            pattern = tags[0] if tags else ""

            seen, specs = set(), []
            for tok in self.SPEC_TOKENS.findall(title):
                if tok.upper() not in seen:
                    seen.add(tok.upper())
                    specs.append(tok.upper())
            spec = " ".join(specs)

            origin = self._extract_field(
                body_html, r"ORIGIN[:\s]+([A-Z][A-Za-z\s]+?)(?:<|,|\n|&|$)"
            )
            warranty = self._extract_field(
                body_html, r"WARRANTY[:\s]+([^<\n,]+)"
            )

            item = OrderedDict()
            item["Scraped Date"] = datetime.now().strftime("%d-%m-%Y")
            item["Title"] = title
            item["Brand"] = vendor
            item["Pattern"] = pattern
            item["SKU"] = sku
            item["Width"] = width
            item["Aspect Ratio"] = ratio
            item["Rim Diameter"] = rim
            item["Load Index"] = load_index
            item["Speed Rating"] = speed_rating
            item["Spec"] = spec
            item["Year"] = year
            item["Origin"] = origin
            item["Warranty"] = warranty
            item["Base Price"] = f"Dhs. {base_price}" if base_price else ""
            item["Offer Price"] = f"Dhs. {offer_price}" if offer_price else ""
            item["In Stock"] = "Yes" if available else "No"
            item["Image URL"] = image_url
            item["Source"] = product_url or response.url

            yield item
        finally:
            self.emit_status(response.url, "done")
            self.finish_source_request(source_url)

    @staticmethod
    def _extract_field(html_str, pattern):
        m = re.search(pattern, html_str, re.IGNORECASE)
        if not m:
            return ""
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()


if __name__ == "__main__":
    process = CrawlerProcess(TyresMeScraper.custom_settings)
    process.crawl(TyresMeScraper)
    process.start()
