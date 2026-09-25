"""Scrape tyre catalogue at https://www.tempetyres.com.au/
Conforms to TyresCart protocol (sys.argv[1]=output, sys.argv[2]=input_csv, URL_STATUS).
"""

import os
import re
import sys
import csv
from collections import OrderedDict
from datetime import datetime

from scrapy import Spider, Request, Selector
from scrapy.crawler import CrawlerProcess


class TempeTyresScraper(Spider):
    name = "tempetyres.com"
    allowed_domains = ["tempetyres.com.au", "www.tempetyres.com.au"]

    # ---- OUTPUT FILE with DATE (sys.argv[1]) ----
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    today = datetime.now().strftime("%d-%m-%Y")
    output_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        base_dir, f"tempetyres_data_{today}.xlsx"
    )

    # ---- INPUT CSV (sys.argv[2]) ----
    csv_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        base_dir, "testurls.csv"
    )

    DEFAULT_START_URLS = ["https://www.tempetyres.com.au/tyres"]

    # ---- SETTINGS ----
    custom_settings = {
        "FEED_EXPORTERS": {"xlsx": "scrapy_xlsx.XlsxItemExporter"},
        "COOKIES_ENABLED": True,
        "FEEDS": {
            output_file: {"format": "xlsx", "encoding": "utf8", "store_empty": False}
        },
        "DOWNLOAD_DELAY": 0.35,
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 5,
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

    # ---- ROUTING: brands index / listing / product ----
    def parse_input_url(self, response):
        if response.css('a[href*="/tyres?Brand="]').get():
            yield from self.parse_brands(response)
        elif response.css(".image-container a").get():
            yield from self.parse_listing(response)
        else:
            yield from self.parse_detail(response)

    # ---- BRANDS INDEX ----
    def parse_brands(self, response):
        source_url = response.meta.get("source_url", response.url)
        self.emit_status(response.url, "running")
        try:
            brand_links = response.css('a[href*="/tyres?Brand="]::attr(href)').getall()
            unique_brands = set(brand_links)
            self.logger.info(
                "Found %d brand links on %s", len(unique_brands), response.url
            )
            for url in unique_brands:
                brand_url = response.urljoin(url)
                self.emit_status(brand_url, "pending", parent=source_url, url_type="listing")
                yield self.make_tracked_request(brand_url, source_url, self.parse_listing)
        finally:
            self.emit_status(response.url, "done")
            self.finish_source_request(source_url)

    # ---- LISTING ----
    def parse_listing(self, response):
        source_url = response.meta.get("source_url", response.url)
        self.emit_status(response.url, "running")
        try:
            product_links = response.css(".image-container a::attr(href)").getall()
            unique_products = set(product_links)
            self.logger.info(
                "Brand page %s: Found %d products", response.url, len(unique_products)
            )
            for url in unique_products:
                product_url = response.urljoin(url)
                key = product_url.rstrip("/")
                if key in self.seen_detail_urls:
                    continue
                self.seen_detail_urls.add(key)
                self.emit_status(
                    product_url, "pending", parent=source_url, url_type="product"
                )
                yield self.make_tracked_request(
                    product_url, source_url, self.parse_detail
                )
        finally:
            self.emit_status(response.url, "done")
            self.finish_source_request(source_url)

    # ---- DETAIL EXTRACTION ----
    def parse_detail(self, response):
        source_url = response.meta.get("source_url", response.url)
        self.emit_status(response.url, "running")
        try:
            item = OrderedDict()
            item["Scraped Date"] = datetime.now().strftime("%d-%m-%Y")
            item["Product Name"] = ""
            item["Price"] = ""
            item["SKU"] = ""
            item["BRAND"] = ""
            item["PATTERN"] = ""
            item["WIDTH"] = ""
            item["PROFILE"] = ""
            item["DIAMETER"] = ""
            item["LOAD RATING"] = ""
            item["SPEED RATING"] = ""
            item["RUNFLAT"] = ""
            item["Description"] = ""
            item["Image"] = ""
            item["Product URL"] = response.url

            # Product name
            og_title = response.css('meta[property="og:title"]::attr(content)').get("")
            sub_heading = response.css(".sub-heading::text, h1::text").get("")
            product_name = og_title or sub_heading
            if "|" in product_name:
                product_name = product_name.split("|")[0]
            item["Product Name"] = product_name.strip()

            # Price
            item["Price"] = response.css(
                ".txtprice-large span::text, .txtprice-large::text, .price::text"
            ).get("").strip()

            # Specifications from table
            for more_info in response.css(
                "#tyre_specs tr, table.tyre-specs tr"
            ).getall():
                moreItem = Selector(text=more_info)
                key = moreItem.css("td:first-child::text").get()
                value = moreItem.xpath(".//td[2]/text()").get()
                if key and value:
                    clean_key = key.strip().replace(":", "")
                    item[clean_key] = value.strip()

            # Description
            descr = response.css(
                "#tyre_descr::text"
            ).get("") or response.css(
                'meta[name="description"]::attr(content)'
            ).get("")
            item["Description"] = descr.strip()

            # Image
            images = response.css(
                ".image-popup-vertical-fit img::attr(src), "
                'meta[property="og:image"]::attr(content)'
            ).getall()
            item["Image"] = response.urljoin(images[0]) if images else ""

            yield item
        finally:
            self.emit_status(response.url, "done")
            self.finish_source_request(source_url)


if __name__ == "__main__":
    process = CrawlerProcess(TempeTyresScraper.custom_settings)
    process.crawl(TempeTyresScraper)
    process.start()
