"""
app/services/es_service.py - Elasticsearch Integration Service for Active Products
Handles index creation, mapping, data fetching from MySQL DB, bulk indexing,
single product synchronization, and faceted search.
"""

import os
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any, Generator

try:
    from elasticsearch import Elasticsearch, helpers
    from elasticsearch.exceptions import ConnectionError as ESConnectionError, NotFoundError
    HAS_ELASTICSEARCH = True
except ImportError:
    HAS_ELASTICSEARCH = False
    Elasticsearch = None
    helpers = None

from db import get_connection

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Suppress verbose transport connection logs
logging.getLogger("elastic_transport").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

DEFAULT_ES_URL = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
DEFAULT_ES_INDEX = os.environ.get("ELASTICSEARCH_INDEX", "active_products")
ES_USER = os.environ.get("ELASTICSEARCH_USER")
ES_PASSWORD = os.environ.get("ELASTICSEARCH_PASSWORD")
ES_API_KEY = os.environ.get("ELASTICSEARCH_API_KEY")


def _parse_json(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        s = val.strip()
        if (s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']')):
            try:
                return json.loads(s)
            except Exception:
                pass
    return val


def _extract_text(val: Any) -> str:
    """Extracts plain text string from string or multilingual dict."""
    parsed = _parse_json(val)
    if isinstance(parsed, dict):
        return str(parsed.get('en') or parsed.get('ar') or list(parsed.values())[0] or '').strip()
    if parsed is None:
        return ''
    return str(parsed).strip()


class ElasticsearchService:
    def __init__(
        self,
        url: Optional[str] = None,
        index_name: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 5
    ):
        self.url = url or DEFAULT_ES_URL
        self.index_name = index_name or DEFAULT_ES_INDEX
        self.user = user or ES_USER
        self.password = password or ES_PASSWORD
        self.api_key = api_key or ES_API_KEY
        self.timeout = timeout
        self._client: Optional[Elasticsearch] = None

    def get_client(self) -> Optional[Elasticsearch]:
        if not HAS_ELASTICSEARCH:
            logger.warning("elasticsearch package is not installed.")
            return None

        if self._client is not None:
            return self._client

        kwargs: Dict[str, Any] = {
            "hosts": [self.url],
            "request_timeout": self.timeout or 2,
            "max_retries": 0,
            "retry_on_timeout": False,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        elif self.user and self.password:
            kwargs["basic_auth"] = (self.user, self.password)

        try:
            self._client = Elasticsearch(**kwargs)
            return self._client
        except Exception as e:
            logger.error("Failed to initialize Elasticsearch client: %s", e)
            return None

    def check_connection(self) -> Dict[str, Any]:
        """Checks if Elasticsearch is reachable and returns health status."""
        client = self.get_client()
        if not client:
            return {
                "connected": False,
                "error": "Elasticsearch client library not available or failed to initialize",
                "url": self.url
            }
        try:
            info = client.info()
            exists = client.indices.exists(index=self.index_name)
            doc_count = 0
            if exists:
                count_res = client.count(index=self.index_name)
                doc_count = count_res.get("count", 0)
            return {
                "connected": True,
                "url": self.url,
                "index_name": self.index_name,
                "index_exists": bool(exists),
                "doc_count": doc_count,
                "cluster_name": info.get("cluster_name"),
                "version": info.get("version", {}).get("number")
            }
        except Exception as e:
            return {
                "connected": False,
                "url": self.url,
                "error": str(e)
            }

    @staticmethod
    def get_index_settings_and_mapping() -> Dict[str, Any]:
        """Returns the Elasticsearch mapping schema optimized for active tyre products."""
        return {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "product_analyzer": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": ["lowercase", "asciifolding"]
                        },
                        "autocomplete_analyzer": {
                            "type": "custom",
                            "tokenizer": "autocomplete_tokenizer",
                            "filter": ["lowercase", "asciifolding"]
                        }
                    },
                    "tokenizer": {
                        "autocomplete_tokenizer": {
                            "type": "edge_ngram",
                            "min_gram": 2,
                            "max_gram": 15,
                            "token_chars": ["letter", "digit"]
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "id": {"type": "integer"},
                    "website_id": {"type": "integer"},
                    "attribute_set_id": {"type": "integer"},
                    "sku": {"type": "keyword"},
                    "item_code": {"type": "keyword"},
                    "slug": {"type": "keyword"},
                    "name": {
                        "type": "text",
                        "analyzer": "product_analyzer",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 256},
                            "suggest": {"type": "text", "analyzer": "autocomplete_analyzer"}
                        }
                    },
                    "display_name": {
                        "type": "text",
                        "analyzer": "product_analyzer",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 256}
                        }
                    },
                    "brand_id": {"type": "integer"},
                    "brand_name": {
                        "type": "text",
                        "analyzer": "product_analyzer",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 128}
                        }
                    },
                    "brand_slug": {"type": "keyword"},
                    "category_id": {"type": "integer"},
                    "category_name": {
                        "type": "keyword"
                    },
                    "parts_category": {"type": "keyword"},
                    "tyres_category": {"type": "keyword"},
                    "year": {"type": "keyword"},
                    "price": {"type": "double"},
                    "list_price": {"type": "double"},
                    "sale_price": {"type": "double"},
                    "effective_price": {"type": "double"},
                    "stock_qty": {"type": "integer"},
                    "stock_status": {"type": "keyword"},
                    "status": {"type": "keyword"},
                    "vehicle_type": {"type": "keyword"},
                    "tire_size_label": {"type": "keyword"},
                    "width": {"type": "keyword"},
                    "aspect_ratio": {"type": "keyword"},
                    "rim_size": {"type": "keyword"},
                    "tire_pattern": {
                        "type": "text",
                        "analyzer": "product_analyzer",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 128}
                        }
                    },
                    "tire_speed_rating": {"type": "keyword"},
                    "tire_load_index": {"type": "keyword"},
                    "tire_type": {"type": "keyword"},
                    "oem_brand": {"type": "keyword"},
                    "tire_marking": {"type": "keyword"},
                    "run_flat": {"type": "boolean"},
                    "ev_rated": {"type": "boolean"},
                    "country_of_origin": {"type": "keyword"},
                    "warranty_months": {"type": "keyword"},
                    "warranty_period": {"type": "keyword"},
                    "promotion": {"type": "keyword"},
                    "image_path": {"type": "keyword", "index": False},
                    "small_image": {"type": "keyword", "index": False},
                    "is_featured": {"type": "boolean"},
                    "is_new": {"type": "boolean"},
                    "created_at": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||strict_date_optional_time"},
                    "updated_at": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||strict_date_optional_time"},
                    "attributes": {
                        "type": "object",
                        "dynamic": True
                    }
                }
            }
        }

    def create_active_products_index(self, recreate: bool = False) -> Dict[str, Any]:
        """Creates the active products index with optimized settings and mapping."""
        client = self.get_client()
        if not client:
            return {"success": False, "error": "Elasticsearch client not available"}

        try:
            exists = client.indices.exists(index=self.index_name)
            if exists:
                if recreate:
                    logger.info("Recreating Elasticsearch index: %s", self.index_name)
                    client.indices.delete(index=self.index_name)
                else:
                    return {"success": True, "message": f"Index '{self.index_name}' already exists."}

            schema = self.get_index_settings_and_mapping()
            client.indices.create(index=self.index_name, body=schema)
            logger.info("Successfully created Elasticsearch index: %s", self.index_name)
            return {"success": True, "message": f"Index '{self.index_name}' created successfully."}
        except Exception as e:
            logger.error("Failed to create index '%s': %s", self.index_name, e)
            return {"success": False, "error": str(e)}

    @staticmethod
    def transform_db_row_to_doc(row: Dict[str, Any]) -> Dict[str, Any]:
        """Transforms a MySQL active product row into a clean Elasticsearch document."""
        # Extract attributes from attributes_json
        raw_dyn = _parse_json(row.get('attributes_json'))
        dyn = raw_dyn if isinstance(raw_dyn, dict) else {}

        # Name / display_name
        name_str = _extract_text(row.get('name')) or row.get('display_name') or ''
        disp_name = row.get('display_name') or name_str

        # Prices
        price_val = float(row.get('price')) if row.get('price') is not None else 0.0
        sale_val = float(row.get('sale_price')) if row.get('sale_price') is not None else None
        effective_price = sale_val if (sale_val is not None and sale_val > 0 and sale_val < price_val) else price_val

        # Tyre sizing details
        tire_size_label = (row.get('tire_size_label') or dyn.get('tire_size_label') or dyn.get('tire_size') or dyn.get('tyre_size') or '').strip()
        width = str(dyn.get('width') or '').strip()
        aspect_ratio = str(dyn.get('height') or dyn.get('aspect_ratio') or '').strip()
        rim_size = str(dyn.get('rim') or dyn.get('rim_size') or '').strip()
        if not rim_size and tire_size_label:
            import re
            m = re.search(r'R\s*(\d{2})', tire_size_label, re.IGNORECASE)
            if m:
                rim_size = m.group(1)

        # Boolean flags
        run_flat = bool(row.get('run_flat') or dyn.get('runflat') in (1, '1', True, 'Yes', 'yes'))
        ev_rated = bool(row.get('ev_rated') or dyn.get('ev') in (1, '1', True, 'Yes', 'yes') or dyn.get('ev_tyre') in (1, '1', True, 'Yes', 'yes'))

        # Warranty
        war_period = (dyn.get('warranty_period') or dyn.get('warranty') or '').strip()
        war_months = row.get('warranty_months') or dyn.get('warranty_months') or None

        # Promotion
        promo = str(dyn.get('promotion') or dyn.get('offers') or '').strip()

        # Dates formatting
        def fmt_dt(dt):
            if isinstance(dt, datetime):
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            return str(dt) if dt else None

        # Sanitize attributes to avoid Elasticsearch key/type collisions (like pattern vs pattern.1)
        clean_dyn = {}
        if isinstance(dyn, dict):
            for k, v in dyn.items():
                clean_k = str(k).replace('.', '_').replace(' ', '_').strip()
                if not clean_k:
                    continue
                if v is None:
                    clean_dyn[clean_k] = ""
                elif isinstance(v, (bool, int, float)):
                    clean_dyn[clean_k] = str(v)
                elif isinstance(v, (dict, list)):
                    clean_dyn[clean_k] = json.dumps(v, ensure_ascii=False)
                else:
                    clean_dyn[clean_k] = str(v).strip()

        doc = {
            "id": int(row['id']),
            "website_id": int(row.get('website_id') or 1),
            "attribute_set_id": int(row.get('attribute_set_id') or 1),
            "sku": str(row.get('sku') or '').strip(),
            "item_code": str(row.get('item_code') or '').strip(),
            "slug": str(row.get('slug') or '').strip(),
            "name": name_str,
            "display_name": disp_name,
            "brand_id": int(row.get('brand_id')) if row.get('brand_id') else None,
            "brand_name": str(row.get('brand_name') or dyn.get('brand') or '').strip(),
            "brand_slug": str(row.get('brand_slug') or '').strip(),
            "category_id": int(row.get('category_id')) if row.get('category_id') else None,
            "category_name": _extract_text(row.get('category_name')),
            "parts_category": str(row.get('parts_category') or 'Tyres').strip(),
            "tyres_category": str(row.get('tyres_category') or dyn.get('tyres_category') or 'Budget').strip(),
            "year": str(row.get('year') or dyn.get('year') or '').strip(),
            "price": round(price_val, 2),
            "list_price": round(float(row['list_price']), 2) if row.get('list_price') is not None else None,
            "sale_price": round(sale_val, 2) if sale_val is not None else None,
            "effective_price": round(effective_price, 2),
            "stock_qty": int(row.get('stock_qty') or 0),
            "stock_status": str(row.get('stock_status') or 'in_stock').strip(),
            "status": str(row.get('status') or 'active').strip(),
            "vehicle_type": str(row.get('vehicle_type') or dyn.get('vehicle_type') or 'car').strip(),
            "tire_size_label": tire_size_label,
            "width": width,
            "aspect_ratio": aspect_ratio,
            "rim_size": rim_size,
            "tire_pattern": str(row.get('tire_pattern') or dyn.get('pattern') or dyn.get('tire_pattern') or '').strip(),
            "tire_speed_rating": str(row.get('tire_speed_rating') or dyn.get('tire_speed_rating') or '').strip(),
            "tire_load_index": str(row.get('tire_load_index') or dyn.get('tire_load_index') or dyn.get('load_index') or '').strip(),
            "tire_type": str(row.get('tire_type') or dyn.get('tire_type') or 'summer').strip(),
            "oem_brand": str(row.get('oem_brand') or dyn.get('oem_tyres') or '').strip(),
            "tire_marking": str(dyn.get('tyre_marking') or dyn.get('tire_marking') or dyn.get('marking') or '').strip() if str(dyn.get('tyre_marking') or dyn.get('tire_marking') or dyn.get('marking') or '').strip() not in ('', 'None', 'Standard', '0') else '',
            "run_flat": run_flat,
            "ev_rated": ev_rated,
            "country_of_origin": str(row.get('country_of_origin') or dyn.get('country') or '').strip(),
            "warranty_months": str(war_months) if war_months is not None else "",
            "warranty_period": war_period,
            "promotion": promo if promo != 'None' else "",
            "image_path": str(row.get('image_path') or row.get('small_image') or '').strip(),
            "small_image": str(row.get('small_image') or row.get('image_path') or '').strip(),
            "is_featured": bool(row.get('is_featured')),
            "is_new": bool(row.get('is_new')),
            "created_at": fmt_dt(row.get('created_at')),
            "updated_at": fmt_dt(row.get('updated_at')),
            "attributes": clean_dyn
        }
        return doc

    def fetch_products_from_db(self, batch_size: int = 1000, only_active: bool = False) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Streams products from MySQL database in chunked batches.
        Only fetches products where deleted_at IS NULL (excludes soft-deleted items).
        If only_active=True, also filters by status = 'active'.
        """
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                where_clause = "WHERE p.deleted_at IS NULL"
                if only_active:
                    where_clause += " AND p.status = 'active'"

                query = f"""
                    SELECT 
                        p.*,
                        b.name as brand_name,
                        b.slug as brand_slug,
                        c.name as category_name
                    FROM products p
                    LEFT JOIN brands b ON p.brand_id = b.id
                    LEFT JOIN categories c ON p.category_id = c.id
                    {where_clause}
                    ORDER BY p.id ASC
                """
                cur.execute(query)
                while True:
                    rows = cur.fetchmany(batch_size)
                    if not rows:
                        break
                    batch_docs = [self.transform_db_row_to_doc(r) for r in rows]
                    yield batch_docs
        finally:
            conn.close()

    # Backwards compatibility alias
    fetch_active_products_from_db = fetch_products_from_db

    def index_all_products(self, batch_size: int = 500, recreate: bool = False, only_active: bool = False) -> Dict[str, Any]:
        """
        Fetches products from MySQL and bulk-indexes them into Elasticsearch.
        By default indexes all non-deleted products (active and inactive).
        """
        client = self.get_client()
        if not client:
            return {"success": False, "error": "Elasticsearch client not connected"}

        # 1. Create or recreate index
        create_res = self.create_active_products_index(recreate=recreate)
        if not create_res.get("success"):
            return create_res

        total_indexed = 0
        total_failed = 0
        batch_num = 0

        target_label = "active products" if only_active else "all products"
        logger.info("Starting %s bulk indexing from database into '%s'...", target_label, self.index_name)

        try:
            for batch_docs in self.fetch_products_from_db(batch_size=batch_size, only_active=only_active):
                batch_num += 1
                actions = [
                    {
                        "_index": self.index_name,
                        "_id": str(doc["id"]),
                        "_source": doc
                    }
                    for doc in batch_docs
                ]

                success_count, failed_items = helpers.bulk(
                    client,
                    actions,
                    raise_on_error=False,
                    stats_only=False
                )
                total_indexed += success_count
                total_failed += len(failed_items) if isinstance(failed_items, list) else 0

                logger.info("Batch #%d: indexed %d docs into Elasticsearch (Total: %d)", batch_num, success_count, total_indexed)

            # Refresh index to make documents immediately searchable
            client.indices.refresh(index=self.index_name)

            return {
                "success": True,
                "message": f"Successfully indexed {total_indexed} products into Elasticsearch index '{self.index_name}'.",
                "indexed": total_indexed,
                "failed": total_failed,
                "batches": batch_num,
                "index_name": self.index_name
            }
        except Exception as e:
            logger.error("Bulk indexing failed: %s", e)
            return {
                "success": False,
                "error": str(e),
                "indexed": total_indexed,
                "failed": total_failed
            }

    # Backwards compatibility alias
    index_all_active_products = index_all_products

    def index_single_product(self, product_id: int, only_active: bool = False) -> bool:
        """Indexes or updates a single product into Elasticsearch by its ID."""
        client = self.get_client()
        if not client:
            return False

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT p.*, b.name as brand_name, b.slug as brand_slug, c.name as category_name
                    FROM products p
                    LEFT JOIN brands b ON p.brand_id = b.id
                    LEFT JOIN categories c ON p.category_id = c.id
                    WHERE p.id = %s
                """, (product_id,))
                row = cur.fetchone()
                if not row or row.get('deleted_at') is not None:
                    self.delete_single_product(product_id)
                    return True

                if only_active and str(row.get('status')).lower() != 'active':
                    self.delete_single_product(product_id)
                    return True

                doc = self.transform_db_row_to_doc(row)
                client.index(index=self.index_name, id=str(product_id), document=doc)
                return True
        except Exception as e:
            logger.error("Failed to index single product #%d: %s", product_id, e)
            return False
        finally:
            conn.close()

    def delete_single_product(self, product_id: int) -> bool:
        """Deletes a product document from Elasticsearch."""
        client = self.get_client()
        if not client:
            return False
        try:
            client.delete(index=self.index_name, id=str(product_id), ignore=[404])
            return True
        except Exception as e:
            logger.error("Failed to delete product #%d from Elasticsearch: %s", product_id, e)
            return False

    def search_products(
        self,
        query: str = "",
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        page: int = 1,
        per_page: int = 25
    ) -> Dict[str, Any]:
        """
        Executes an Elasticsearch search with full-text search, bool filtering,
        sorting, pagination, and faceted aggregations.
        """
        client = self.get_client()
        if not client:
            return {"success": False, "error": "Elasticsearch not connected", "total": 0, "items": []}

        filters = filters or {}
        must_clauses: List[Dict[str, Any]] = []
        filter_clauses: List[Dict[str, Any]] = []

        # Status filter (default: active, pass status='all' for all products)
        status_filter = filters.get("status", "active")
        if status_filter and status_filter != "all":
            filter_clauses.append({"term": {"status": str(status_filter).lower()}})

        # Full-text query
        q_clean = query.strip() if query else ""
        if q_clean:
            import re
            q_clean = re.sub(r'(\d+)\s*/\s*(\d+)\s*[rR]\s*(\d+)', r'\1/\2 R\3', q_clean)
            must_clauses.append({
                "multi_match": {
                    "query": q_clean,
                    "fields": [
                        "name^5",
                        "display_name^4",
                        "sku^6",
                        "brand_name^3",
                        "tire_size_label^4",
                        "tire_pattern^3",
                        "oem_brand^2"
                    ],
                    "type": "cross_fields",
                    "operator": "and"
                }
            })

        # Structured filters
        if filters.get("brand_id"):
            filter_clauses.append({"term": {"brand_id": int(filters["brand_id"])}})
        if filters.get("brand_name"):
            filter_clauses.append({"term": {"brand_name.keyword": str(filters["brand_name"])}})
        if filters.get("brand_slug"):
            filter_clauses.append({"term": {"brand_slug": str(filters["brand_slug"]).lower()}})
        if filters.get("category_id"):
            filter_clauses.append({"term": {"category_id": int(filters["category_id"])}})
        if filters.get("tyres_category"):
            filter_clauses.append({"term": {"tyres_category": str(filters["tyres_category"])}})
        if filters.get("parts_category"):
            filter_clauses.append({"term": {"parts_category": str(filters["parts_category"])}})
        if filters.get("vehicle_type"):
            filter_clauses.append({"term": {"vehicle_type": str(filters["vehicle_type"]).lower()}})
        if filters.get("rim_size"):
            filter_clauses.append({"term": {"rim_size": str(filters["rim_size"])}})
        if filters.get("speed_rating"):
            filter_clauses.append({"term": {"tire_speed_rating": str(filters["speed_rating"])}})
        if filters.get("country_of_origin"):
            filter_clauses.append({"term": {"country_of_origin": str(filters["country_of_origin"])}})
        if filters.get("year"):
            filter_clauses.append({"term": {"year": str(filters["year"])}})
        if filters.get("tire_pattern"):
            filter_clauses.append({"term": {"tire_pattern.keyword": str(filters["tire_pattern"])}})
        if filters.get("oem_brand"):
            filter_clauses.append({"term": {"oem_brand": str(filters["oem_brand"])}})
        if filters.get("run_flat") in (1, "1", True, "true"):
            filter_clauses.append({"term": {"run_flat": True}})
        if filters.get("ev_rated") in (1, "1", True, "true"):
            filter_clauses.append({"term": {"ev_rated": True}})

        # Price range filter
        price_range = {}
        if filters.get("min_price") is not None:
            try:
                price_range["gte"] = float(filters["min_price"])
            except ValueError:
                pass
        if filters.get("max_price") is not None:
            try:
                price_range["lte"] = float(filters["max_price"])
            except ValueError:
                pass
        if price_range:
            filter_clauses.append({"range": {"effective_price": price_range}})

        # Build bool query
        bool_query: Dict[str, Any] = {"filter": filter_clauses}
        if must_clauses:
            bool_query["must"] = must_clauses
        else:
            bool_query["must"] = [{"match_all": {}}]

        # Sorting
        if sort_by in ("price", "effective_price"):
            sort_field = "effective_price"
        elif sort_by in ("name", "name.keyword"):
            sort_field = "name.keyword"
        elif sort_by in ("sku", "sku.keyword"):
            sort_field = "sku"
        elif sort_by == "stock_qty":
            sort_field = "stock_qty"
        elif q_clean and (not sort_by or sort_by == "created_at"):
            sort_field = "_score"
        else:
            sort_field = "created_at"

        sort_expression = [{sort_field: {"order": "desc" if str(sort_dir).lower() == "desc" else "asc"}}]

        # Pagination
        from_offset = max(0, (page - 1) * per_page)

        # Facet Aggregations
        aggregations = {
            "brands": {"terms": {"field": "brand_name.keyword", "size": 50}},
            "patterns": {"terms": {"field": "tire_pattern.keyword", "size": 100}},
            "oems": {"terms": {"field": "oem_brand", "size": 50}},
            "tyres_categories": {"terms": {"field": "tyres_category", "size": 10}},
            "origins": {"terms": {"field": "country_of_origin", "size": 50}},
            "years": {"terms": {"field": "year", "size": 20}},
            "rim_sizes": {"terms": {"field": "rim_size", "size": 30}},
            "speed_ratings": {"terms": {"field": "tire_speed_rating", "size": 20}},
            "min_price": {"min": {"field": "effective_price"}},
            "max_price": {"max": {"field": "effective_price"}}
        }

        body = {
            "query": {"bool": bool_query},
            "sort": sort_expression,
            "from": from_offset,
            "size": per_page,
            "aggs": aggregations,
            "track_total_hits": True
        }

        try:
            res = client.search(index=self.index_name, body=body)
            hits_obj = res.get("hits", {})
            total_hits = hits_obj.get("total", {}).get("value", 0) if isinstance(hits_obj.get("total"), dict) else hits_obj.get("total", 0)
            items = [h["_source"] for h in hits_obj.get("hits", [])]

            # Parse aggregations
            raw_aggs = res.get("aggregations", {})
            facets = {}
            for agg_key, agg_data in raw_aggs.items():
                if "buckets" in agg_data:
                    facets[agg_key] = {b["key"]: b["doc_count"] for b in agg_data["buckets"]}
                elif "value" in agg_data:
                    facets[agg_key] = agg_data["value"]

            total_pages = max(1, (total_hits + per_page - 1) // per_page)

            return {
                "success": True,
                "total": total_hits,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "items": items,
                "facets": facets
            }
        except Exception as e:
            logger.error("Elasticsearch search query failed: %s", e)
            return {"success": False, "error": str(e), "total": 0, "items": []}


# Global singleton service instance
es_service = ElasticsearchService()
