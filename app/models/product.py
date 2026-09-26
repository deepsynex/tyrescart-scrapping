"""
app/models/product.py - Product Model & ORM Helpers
Table: products
Phase 2.1 & 3.1 & 6.4 Catalog Product Implementation
"""

import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from db import get_connection
from services.attribute_service import AttributeService
from i18n import localize_value
try:
    from services.es_service import es_service
except Exception:
    es_service = None


class Product:
    @staticmethod
    def slugify(text: str) -> str:
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '-', text)
        return text.strip('-')

    @staticmethod
    def _parse_json_field(val):
        if val is None:
            return None
        if isinstance(val, (dict, list)):
            return val
        if isinstance(val, str):
            val_str = val.strip()
            if (val_str.startswith('{') and val_str.endswith('}')) or (val_str.startswith('[') and val_str.endswith(']')):
                try:
                    return json.loads(val_str)
                except Exception:
                    pass
        return val

    @staticmethod
    def _safe_int(v, default=None):
        if v is None:
            return default
        if isinstance(v, int) and not isinstance(v, bool):
            return v
        s = str(v).strip()
        if not s or s.lower() in ('none', 'null', 'undefined'):
            return default
        try:
            return int(float(s))
        except (ValueError, TypeError):
            m = re.search(r'^-?\d+', s)
            if m:
                try:
                    return int(m.group(0))
                except (ValueError, TypeError):
                    pass
            return default

    @staticmethod
    def _safe_decimal(v, default=None):
        if v is None:
            return default
        if isinstance(v, Decimal):
            return v
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        s = str(v).strip()
        if not s or s.lower() in ('none', 'null', 'undefined'):
            return default
        try:
            return Decimal(s)
        except Exception:
            m = re.search(r'[-+]?\d*\.?\d+', s.replace(',', ''))
            if m:
                try:
                    return Decimal(m.group(0))
                except Exception:
                    pass
            return default

    @staticmethod
    def _safe_warranty_months(v, default=None):
        if v is None:
            return default
        if isinstance(v, int) and not isinstance(v, bool):
            return max(0, min(v, 120))
        s = str(v).strip()
        if not s or s.lower() in ('none', 'null', 'undefined', 'n/a', '-'):
            return default
        try:
            return max(0, min(int(s), 120))
        except ValueError:
            pass
        m_year = re.search(r'(\d+(?:\.\d+)?)\s*(?:year|yr)', s, re.IGNORECASE)
        if m_year:
            try:
                val = int(round(float(m_year.group(1)) * 12))
                return max(0, min(val, 120))
            except (ValueError, TypeError):
                pass
        m_month = re.search(r'(\d+)\s*(?:month|mo)', s, re.IGNORECASE)
        if m_month:
            try:
                val = int(m_month.group(1))
                return max(0, min(val, 120))
            except (ValueError, TypeError):
                pass
        m_digit = re.search(r'\d+', s)
        if m_digit:
            try:
                val = int(m_digit.group(0))
                return max(0, min(val, 120))
            except (ValueError, TypeError):
                pass
        return default

    @staticmethod
    def _safe_visibility(v, default='visible'):
        if not v:
            return default
        v_clean = str(v).strip().lower().replace(' ', '_')
        if 'catalog' in v_clean and 'search' in v_clean:
            return 'visible'
        if v_clean in ('visible', 'active'):
            return 'visible'
        if v_clean in ('not_visible', 'notvisible', 'hidden', 'disabled'):
            return 'not_visible'
        if v_clean == 'catalog':
            return 'catalog'
        if v_clean == 'search':
            return 'search'
        return default

    @staticmethod
    def _safe_tire_type(v, default='summer'):
        if not v:
            return default
        v_clean = str(v).strip().lower().replace('-', '_').replace(' ', '_')
        valid = ('summer', 'winter', 'all_season', 'all_terrain', 'mud_terrain')
        if v_clean in valid:
            return v_clean
        if 'winter' in v_clean:
            return 'winter'
        if 'all' in v_clean and 'terrain' in v_clean:
            return 'all_terrain'
        if 'mud' in v_clean:
            return 'mud_terrain'
        if 'all' in v_clean:
            return 'all_season'
        return default

    @staticmethod
    def _safe_vehicle_type(v, default='car'):
        if not v:
            return default
        v_clean = str(v).strip().lower().replace(' ', '_')
        valid = ('car', 'bike', 'suv', 'van', 'ev', '4x4')
        if v_clean in valid:
            return v_clean
        if 'suv' in v_clean or '4x4' in v_clean or '4wd' in v_clean:
            return 'suv'
        if 'bike' in v_clean or 'motorcycle' in v_clean:
            return 'bike'
        if 'van' in v_clean or 'truck' in v_clean or 'commercial' in v_clean:
            return 'van'
        if 'ev' in v_clean or 'electric' in v_clean:
            return 'ev'
        return default

    @staticmethod
    def _safe_stock_status(v, default='in_stock'):
        if not v:
            return default
        v_clean = str(v).strip().lower().replace(' ', '_').replace('-', '_')
        if v_clean in ('in_stock', 'instock', 'available', '1'):
            return 'in_stock'
        if v_clean in ('out_of_stock', 'outofstock', 'unavailable', '0'):
            return 'out_of_stock'
        if v_clean in ('backorder', 'back_order', 'on_backorder'):
            return 'backorder'
        return default

    @staticmethod
    def _safe_status(v, default='active'):
        if not v:
            return default
        v_clean = str(v).strip().lower()
        if v_clean in ('active', 'enabled', '1', 'true', 'yes'):
            return 'active'
        if v_clean in ('inactive', 'disabled', '0', 'false', '2', 'no'):
            return 'inactive'
        return default

    @classmethod
    def to_dict(cls, row):
        if not row:
            return None
        from services.store_context import StoreContext
        from i18n import get_translated_value
        loc = StoreContext.get_current_language()

        d = dict(row)
        # Parse JSON fields safely
        for k in ['name', 'description', 'short_desc', 'meta_title', 'meta_desc', 'gallery_json', 'make_ids', 'price_included', 'attributes_json']:
            if k in d:
                d[k] = cls._parse_json_field(d[k])

        # Ensure tyres_category and parts_category are synced with attributes_json
        if not d.get('tyres_category') and isinstance(d.get('attributes_json'), dict):
            d['tyres_category'] = d['attributes_json'].get('tyres_category')
        if not d.get('parts_category') and isinstance(d.get('attributes_json'), dict):
            d['parts_category'] = d['attributes_json'].get('parts_category')
        if isinstance(d.get('attributes_json'), dict):
            if d.get('tyres_category') and not d['attributes_json'].get('tyres_category'):
                d['attributes_json']['tyres_category'] = d['tyres_category']
            if d.get('parts_category') and not d['attributes_json'].get('parts_category'):
                d['attributes_json']['parts_category'] = d['parts_category']

        # Resolve display name string
        if isinstance(d.get('name'), dict):
            d['display_name'] = get_translated_value(d['name'], loc)
            d['name_en'] = get_translated_value(d['name'], 'en') or d['display_name']
        elif isinstance(d.get('name'), str):
            d['display_name'] = d['name']
            d['name_en'] = d['name']
        else:
            d['display_name'] = d.get('display_name') or ''
            d['name_en'] = d.get('display_name') or ''

        # Localized description / short_desc / meta
        if isinstance(d.get('description'), dict):
            d['description_display'] = get_translated_value(d['description'], loc)
        if isinstance(d.get('short_desc'), dict):
            d['short_desc_display'] = get_translated_value(d['short_desc'], loc)
        if isinstance(d.get('meta_title'), dict):
            d['meta_title_display'] = get_translated_value(d['meta_title'], loc)
        if isinstance(d.get('meta_desc'), dict):
            d['meta_desc_display'] = get_translated_value(d['meta_desc'], loc)

        # Resolve category name if JSON
        if d.get('category_name'):
            cat_raw = d['category_name']
            if isinstance(cat_raw, str) and cat_raw.strip().startswith('{'):
                try:
                    d['category_name'] = json.loads(cat_raw)
                except Exception:
                    pass
            if isinstance(d['category_name'], dict):
                d['category_name_display'] = get_translated_value(d['category_name'], loc)
                d['category_name'] = d['category_name_display']
            else:
                d['category_name_display'] = str(d['category_name'])

        # Decimal / Float conversions for JSON serialization
        for k in ['price', 'list_price', 'sale_price', 'cost_price', 'weight']:
            if k in d and d[k] is not None:
                d[k] = float(d[k])

        # Resolve category_ids
        if 'category_ids_str' in d:
            raw_cids = d.pop('category_ids_str')
            if raw_cids:
                d['category_ids'] = [int(x) for x in str(raw_cids).split(',') if x.strip().isdigit()]
            else:
                d['category_ids'] = [d['category_id']] if d.get('category_id') else []
        elif 'category_ids' not in d and d.get('category_id'):
            d['category_ids'] = [d['category_id']]

        # Normalize image paths
        for img_k in ['image_path', 'small_image']:
            val = d.get(img_k)
            if val and str(val).strip():
                s = str(val).strip().replace('\\', '/')
                if not (s.startswith('http://') or s.startswith('https://') or s.startswith('data:')):
                    if not s.startswith('/'):
                        s = '/' + s
                d[img_k] = s
            else:
                d[img_k] = '/static/assets/images/no-image-available.svg'

        # Date / Timestamp formatting
        for k in ['created_at', 'updated_at', 'deleted_at', 'sale_start_date', 'sale_end_date']:
            if k in d and d[k] is not None:
                d[k] = d[k].isoformat() if hasattr(d[k], 'isoformat') else str(d[k])

        # OEM Car Brand Logos
        try:
            from siteapp.clientroute import resolve_oem_car_logos
            d['oem_logos'] = resolve_oem_car_logos(d)
        except Exception:
            d['oem_logos'] = []

        return d

    @classmethod
    def get_counts(cls):
        """Returns statistics for product metrics cards."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        COUNT(CASE WHEN deleted_at IS NULL THEN 1 END) as total_active,
                        COUNT(CASE WHEN deleted_at IS NULL AND stock_status = 'in_stock' THEN 1 END) as in_stock,
                        COUNT(CASE WHEN deleted_at IS NULL AND stock_status = 'out_of_stock' THEN 1 END) as out_of_stock,
                        COUNT(CASE WHEN deleted_at IS NULL AND status = 'inactive' THEN 1 END) as inactive,
                        COUNT(CASE WHEN deleted_at IS NOT NULL THEN 1 END) as trash_count
                    FROM products
                """)
                row = cursor.fetchone() or {}
                return {
                    'total': row.get('total_active', 0),
                    'in_stock': row.get('in_stock', 0),
                    'out_of_stock': row.get('out_of_stock', 0),
                    'inactive': row.get('inactive', 0),
                    'trash': row.get('trash_count', 0),
                }
        finally:
            conn.close()

    @classmethod
    def paginate(cls, page: int = 1, per_page: int = 25, search: str = None,
                 brand_id: int = None, category_id: int = None, status: str = None,
                 stock_status: str = None, vehicle_type: str = None, attribute_set_id: int = None,
                 is_trash: bool = False, sort_by: str = 'created_at', sort_dir: str = 'DESC',
                 tyres_category: str = None, parts_category: str = None,
                 run_flat = None, ev_rated = None,
                 rim_size: str = None, speed_rating: str = None,
                 country_of_origin: str = None, year = None,
                 oem_tyres = None,
                 attr_code: str = None, attr_value: str = None):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                where_clauses = []
                params = []

                if is_trash:
                    where_clauses.append("p.deleted_at IS NOT NULL")
                else:
                    where_clauses.append("p.deleted_at IS NULL")

                if search:
                    s = f"%{search.strip()}%"
                    where_clauses.append("(p.sku LIKE %s OR p.display_name LIKE %s OR p.tire_size_label LIKE %s OR p.slug LIKE %s)")
                    params.extend([s, s, s, s])

                if brand_id:
                    where_clauses.append("p.brand_id = %s")
                    params.append(brand_id)

                if category_id:
                    where_clauses.append("(p.category_id = %s OR EXISTS (SELECT 1 FROM product_categories pc WHERE pc.product_id = p.id AND pc.category_id = %s))")
                    params.extend([category_id, category_id])

                if attribute_set_id:
                    where_clauses.append("p.attribute_set_id = %s")
                    params.append(attribute_set_id)

                if status:
                    where_clauses.append("p.status = %s")
                    params.append(status)

                if stock_status:
                    where_clauses.append("p.stock_status = %s")
                    params.append(stock_status)

                if vehicle_type:
                    where_clauses.append("p.vehicle_type = %s")
                    params.append(vehicle_type)

                if tyres_category:
                    tc_val = str(tyres_category).strip()
                    where_clauses.append("(p.tyres_category = %s OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.tyres_category')) = %s)")
                    params.extend([tc_val, tc_val])

                if parts_category:
                    pc_val = str(parts_category).strip()
                    where_clauses.append("(p.parts_category = %s OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.parts_category')) = %s)")
                    params.extend([pc_val, pc_val])

                if run_flat is not None and str(run_flat).strip() != '':
                    rf_val = 1 if str(run_flat).strip().lower() in ('1', 'true', 'yes') else 0
                    where_clauses.append("p.run_flat = %s")
                    params.append(rf_val)

                if ev_rated is not None and str(ev_rated).strip() != '':
                    ev_val = 1 if str(ev_rated).strip().lower() in ('1', 'true', 'yes') else 0
                    where_clauses.append("p.ev_rated = %s")
                    params.append(ev_val)

                if rim_size:
                    clean_rim = str(rim_size).strip().upper().replace('R', '').replace('"', '')
                    where_clauses.append("""
                        (p.tire_size_label LIKE %s 
                         OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.rim')) = %s 
                         OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.rim_size')) = %s)
                    """)
                    params.extend([f"%R{clean_rim}%", clean_rim, clean_rim])

                if speed_rating:
                    sr = str(speed_rating).strip().upper()
                    where_clauses.append("""
                        (p.tire_speed_rating = %s 
                         OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.tire_speed_rating')) = %s 
                         OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.speed_rating')) = %s)
                    """)
                    params.extend([sr, sr, sr])

                if country_of_origin:
                    co = str(country_of_origin).strip()
                    where_clauses.append("""
                        (p.country_of_origin = %s 
                         OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.country')) = %s 
                         OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.country_of_origin')) = %s)
                    """)
                    params.extend([co, co, co])

                if year:
                    try:
                        y_int = int(str(year).strip())
                        where_clauses.append("(p.year = %s OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.year')) = %s)")
                        params.extend([y_int, str(y_int)])
                    except (ValueError, TypeError):
                        pass

                if oem_tyres:
                    if isinstance(oem_tyres, str):
                        oem_list = [s.strip() for s in oem_tyres.split(',') if s.strip()]
                    elif isinstance(oem_tyres, (list, tuple)):
                        oem_list = [str(s).strip() for s in oem_tyres if str(s).strip()]
                    else:
                        oem_list = []

                    if oem_list:
                        oem_clauses = []
                        for oem_item in oem_list:
                            oem_clauses.append("""(
                                p.oem_brand LIKE %s
                                OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.oem_tyres')) LIKE %s
                                OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.oem_brand')) LIKE %s
                                OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.oem_marking')) LIKE %s
                            )""")
                            like_str = f"%{oem_item}%"
                            params.extend([like_str, like_str, like_str, like_str])
                        where_clauses.append(f"({' OR '.join(oem_clauses)})")

                if attr_code and attr_value is not None and str(attr_value).strip() != '':
                    c_code = re.sub(r'[^a-zA-Z0-9_]', '', str(attr_code).strip())
                    c_val = str(attr_value).strip()
                    if c_code:
                        direct_cols = {'sku', 'display_name', 'tire_size_label', 'tire_speed_rating', 'tire_load_index', 
                                       'tire_type', 'tire_pattern', 'vehicle_type', 'country_of_origin', 'parts_category', 
                                       'tyres_category', 'year', 'item_code'}
                        if c_code in direct_cols:
                            where_clauses.append(f"(p.{c_code} = %s OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, %s)) = %s)")
                            params.extend([c_val, f"$.{c_code}", c_val])
                        else:
                            where_clauses.append("""
                                (JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, %s)) = %s
                                 OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, %s)) LIKE %s
                                 OR EXISTS (
                                     SELECT 1 FROM product_attribute_values pav
                                     JOIN attributes a ON a.id = pav.attribute_id
                                     WHERE pav.product_id = p.id AND a.code = %s AND (pav.value_text = %s OR pav.value_number = %s)
                                 ))
                            """)
                            params.extend([f"$.{c_code}", c_val, f"$.{c_code}", f"%{c_val}%", c_code, c_val, c_val])

                where_sql = " AND ".join(where_clauses)
                if where_sql:
                    where_sql = "WHERE " + where_sql

                # Allowed sort columns
                allowed_sorts = {
                    'id': 'p.id',
                    'sku': 'p.sku',
                    'display_name': 'p.display_name',
                    'price': 'p.price',
                    'stock_qty': 'p.stock_qty',
                    'created_at': 'p.created_at',
                    'status': 'p.status'
                }
                order_col = allowed_sorts.get(sort_by, 'p.id')
                direction = 'ASC' if str(sort_dir).upper() == 'ASC' else 'DESC'

                # Total count
                count_sql = f"SELECT COUNT(*) as cnt FROM products p {where_sql}"
                cursor.execute(count_sql, tuple(params))
                total_items = cursor.fetchone()['cnt']

                # Paginated items with brand, category and attribute set names joined
                offset = max(0, (page - 1) * per_page)
                items_sql = f"""
                    SELECT p.*,
                           b.name as brand_name,
                           b.logo as brand_logo,
                           c.name as category_name,
                           s.name as attribute_set_name,
                           s.slug as attribute_set_slug,
                           (SELECT GROUP_CONCAT(pc.category_id ORDER BY pc.position ASC, pc.id ASC) FROM product_categories pc WHERE pc.product_id = p.id) as category_ids_str
                    FROM products p
                    LEFT JOIN brands b ON b.id = p.brand_id
                    LEFT JOIN categories c ON c.id = p.category_id
                    LEFT JOIN attribute_sets s ON s.id = p.attribute_set_id
                    {where_sql}
                    ORDER BY {order_col} {direction}
                    LIMIT %s OFFSET %s
                """
                page_params = list(params) + [per_page, offset]
                cursor.execute(items_sql, tuple(page_params))
                rows = cursor.fetchall() or []

                total_pages = max(1, (total_items + per_page - 1) // per_page)
                return {
                    'items': [cls.to_dict(r) for r in rows],
                    'total': total_items,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': total_pages,
                    'has_prev': page > 1,
                    'has_next': page < total_pages
                }
        finally:
            conn.close()

    @classmethod
    def find_by_id(cls, product_id: int, include_trash: bool = False):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT p.*,
                           b.name as brand_name,
                           b.logo as brand_logo,
                           c.name as category_name,
                           s.name as attribute_set_name,
                           s.slug as attribute_set_slug
                    FROM products p
                    LEFT JOIN brands b ON b.id = p.brand_id
                    LEFT JOIN categories c ON c.id = p.category_id
                    LEFT JOIN attribute_sets s ON s.id = p.attribute_set_id
                    WHERE p.id = %s
                """
                if not include_trash:
                    sql += " AND p.deleted_at IS NULL"
                cursor.execute(sql, (product_id,))
                row = cursor.fetchone()
                res = cls.to_dict(row) if row else None
                if res:
                    res['url_key'] = res.get('slug')
                    try:
                        res['scoped_attributes'] = AttributeService.get_product_scoped_attributes(product_id)
                    except Exception:
                        res['scoped_attributes'] = {}
                    try:
                        cursor.execute("SELECT website_id FROM product_websites WHERE product_id = %s", (product_id,))
                        w_rows = cursor.fetchall() or []
                        res['website_ids'] = [r['website_id'] for r in w_rows]
                        if not res['website_ids'] and res.get('website_id'):
                            res['website_ids'] = [res['website_id']]
                    except Exception:
                        res['website_ids'] = [res.get('website_id')] if res.get('website_id') else [1]
                    try:
                        cursor.execute("SELECT category_id FROM product_categories WHERE product_id = %s ORDER BY position ASC, id ASC", (product_id,))
                        c_rows = cursor.fetchall() or []
                        res['category_ids'] = [r['category_id'] for r in c_rows]
                        if not res['category_ids'] and res.get('category_id'):
                            res['category_ids'] = [res['category_id']]
                    except Exception:
                        res['category_ids'] = [res.get('category_id')] if res.get('category_id') else []
                return res
        finally:
            conn.close()

    @classmethod
    def find_by_sku(cls, sku: str, exclude_id: int = None):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT id, sku FROM products WHERE sku = %s"
                params = [sku.strip()]
                if exclude_id:
                    sql += " AND id != %s"
                    params.append(exclude_id)
                cursor.execute(sql, tuple(params))
                return cursor.fetchone()
        finally:
            conn.close()

    @classmethod
    def find_by_slug(cls, slug: str, exclude_id: int = None):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT id, slug FROM products WHERE slug = %s"
                params = [slug.strip()]
                if exclude_id:
                    sql += " AND id != %s"
                    params.append(exclude_id)
                cursor.execute(sql, tuple(params))
                return cursor.fetchone()
        finally:
            conn.close()

    @classmethod
    def create(cls, data: dict, user_id: int = None):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                from services.store_context import StoreContext
                from i18n import parse_json_dict, get_translated_value
                curr_lang = StoreContext.get_current_language()
                now = datetime.now(timezone.utc)

                sku = str(data.get('sku') or '').strip().upper()
                name_val = data.get('name') or data.get('name_en') or data.get('display_name') or ''
                if isinstance(name_val, dict):
                    name_json = dict(name_val)
                elif isinstance(name_val, str) and name_val.strip().startswith('{'):
                    parsed = parse_json_dict(name_val)
                    name_json = dict(parsed) if isinstance(parsed, dict) else {curr_lang: name_val.strip()}
                else:
                    name_str = str(name_val).strip()
                    name_json = {curr_lang: name_str}
                if 'en' not in name_json and name_json:
                    name_json['en'] = next(iter(name_json.values()), '')
                display_name = get_translated_value(name_json, 'en') or get_translated_value(name_json)

                slug_candidate = data.get('url_key') or data.get('slug') or display_name or sku
                slug = cls.slugify(slug_candidate)

                # Ensure slug uniqueness
                base_slug = slug
                counter = 1
                while cls.find_by_slug(slug):
                    slug = f"{base_slug}-{counter}"
                    counter += 1

                # Pricing
                price = cls._safe_decimal(data.get('price'), Decimal('0'))
                list_price = cls._safe_decimal(data.get('list_price'))
                sale_price = cls._safe_decimal(data.get('sale_price'))
                cost_price = cls._safe_decimal(data.get('cost_price'))

                # Inventory
                stock_qty = cls._safe_int(data.get('stock_qty'), 0)
                stock_status = cls._safe_stock_status(data.get('stock_status'), ('in_stock' if stock_qty > 0 else 'out_of_stock'))
                manage_stock = 1 if data.get('manage_stock', True) else 0
                min_order_qty = cls._safe_int(data.get('min_order_qty'), 1)
                max_order_qty = cls._safe_int(data.get('max_order_qty'), 99)

                # Tyre size label auto-formatting if width/aspect/rim given
                tire_size_label = (data.get('tire_size_label') or '').strip()
                if not tire_size_label and data.get('width') and data.get('aspect_ratio') and data.get('rim_size'):
                    tire_size_label = f"{data.get('width')}/{data.get('aspect_ratio')}R{data.get('rim_size')}"

                tire_speed_rating = (data.get('tire_speed_rating') or '').strip() or None
                tire_load_index = (data.get('tire_load_index') or '').strip() or None
                tire_type = cls._safe_tire_type(data.get('tire_type'), 'summer')
                tire_pattern = (data.get('tire_pattern') or '').strip() or None
                run_flat = 1 if data.get('run_flat') else 0
                ev_rated = 1 if data.get('ev_rated') else 0
                oem_approved = 1 if data.get('oem_approved') else 0
                oem_brand = (data.get('oem_brand') or '').strip() or None
                vehicle_type = cls._safe_vehicle_type(data.get('vehicle_type'), 'car')

                brand_id = cls._safe_int(data.get('brand_id'))
                category_id = cls._safe_int(data.get('category_id'))

                image_path = (data.get('image_path') or '').strip() or None
                image_alt = (data.get('image_alt') or display_name).strip() or None
                gallery_json = json.dumps(data.get('gallery_json') or [])

                def _prepare_multilingual_field(val, def_en=""):
                    if isinstance(val, dict):
                        d = dict(val)
                    elif isinstance(val, str) and val.strip().startswith('{'):
                        parsed = parse_json_dict(val)
                        d = dict(parsed) if isinstance(parsed, dict) else {curr_lang: val.strip()}
                    elif val is not None and str(val).strip():
                        d = {curr_lang: str(val).strip()}
                    else:
                        d = {}
                    if def_en and 'en' not in d:
                        d['en'] = def_en
                    return d

                description = json.dumps(_prepare_multilingual_field(data.get('description'), data.get('description_en', '')), ensure_ascii=False)
                short_desc = json.dumps(_prepare_multilingual_field(data.get('short_desc'), data.get('short_desc_en', '')), ensure_ascii=False)

                weight = cls._safe_decimal(data.get('weight'))
                country_of_origin = (data.get('country_of_origin') or '').strip() or None
                warranty_months = cls._safe_warranty_months(data.get('warranty_months'))
                is_featured = 1 if data.get('is_featured') else 0
                is_new = 1 if data.get('is_new') else 0
                sort_order = cls._safe_int(data.get('sort_order'), 0)
                status_raw = data.get('product_online') if data.get('product_online') is not None else data.get('status')
                status = cls._safe_status(status_raw, 'active')
                visibility = cls._safe_visibility(data.get('visibility'), 'visible')
                pay_later_eligible = 1 if data.get('pay_later_eligible', True) else 0

                meta_title = json.dumps(_prepare_multilingual_field(data.get('meta_title'), data.get('meta_title_en', display_name)), ensure_ascii=False)
                meta_desc = json.dumps(_prepare_multilingual_field(data.get('meta_desc'), data.get('meta_desc_en', '')), ensure_ascii=False)
                canonical_url = (data.get('canonical_url') or '').strip() or None

                attribute_set_id = cls._safe_int(data.get('attribute_set_id'), 1)
                dyn_attrs = data.get('dynamic_attributes') or data.get('attributes_json') or {}
                if isinstance(dyn_attrs, str):
                    try:
                        dyn_attrs = json.loads(dyn_attrs)
                    except Exception:
                        dyn_attrs = {}
                attributes_json = json.dumps(dyn_attrs)

                # Sync tyre size from dynamic attributes if present
                if not tire_size_label and dyn_attrs.get('tire_size_label'):
                    tire_size_label = str(dyn_attrs['tire_size_label']).strip()

                website_id = cls._safe_int(data.get('website_id'), 1)
                item_code = (data.get('item_code') or dyn_attrs.get('item_code') or '').strip() or None
                parts_category = (data.get('parts_category') or dyn_attrs.get('parts_category') or '').strip() or None
                raw_tc = data.get('tyres_category') or dyn_attrs.get('tyres_category')
                tyres_category = (str(raw_tc).strip()) if raw_tc else None
                if tyres_category:
                    tc_l = tyres_category.lower()
                    if tc_l == 'budget':
                        tyres_category = 'Budget'
                    elif tc_l == 'quality':
                        tyres_category = 'Quality'
                    elif tc_l == 'premium':
                        tyres_category = 'Premium'

                raw_year = data.get('year') or dyn_attrs.get('year')
                year = None
                if raw_year:
                    try:
                        y_int = int(str(raw_year).strip())
                        if 1901 <= y_int <= 2155:
                            year = y_int
                    except (ValueError, TypeError):
                        year = None

                make_ids = data.get('make_ids')
                if make_ids is not None and not isinstance(make_ids, str):
                    make_ids = json.dumps(make_ids)
                elif isinstance(make_ids, str) and not make_ids.strip():
                    make_ids = None

                price_included = data.get('price_included') or data.get('price_included_text')
                if price_included:
                    if isinstance(price_included, dict):
                        price_included = json.dumps(price_included, ensure_ascii=False)
                    elif isinstance(price_included, str):
                        if price_included.strip().startswith('{'):
                            price_included = price_included.strip()
                        else:
                            price_included = json.dumps({'en': price_included.strip()}, ensure_ascii=False)
                else:
                    price_included = None

                small_image = (data.get('small_image') or image_path or '').strip() or None
                small_image_alt = (data.get('small_image_alt') or image_alt or display_name or '').strip() or None

                cursor.execute("""
                    INSERT INTO products (
                        website_id, attribute_set_id, attributes_json,
                        sku, item_code, parts_category, tyres_category, year, make_ids, price_included,
                        display_name, slug, name, description, short_desc,
                        price, list_price, sale_price, cost_price, currency,
                        stock_qty, stock_status, manage_stock, min_order_qty, max_order_qty,
                        tire_size_label, tire_speed_rating, tire_load_index, tire_type, tire_pattern,
                        run_flat, ev_rated, oem_approved, oem_brand, vehicle_type,
                        brand_id, category_id, image_path, image_alt, small_image, small_image_alt, gallery_json,
                        weight, country_of_origin, warranty_months,
                        is_featured, is_new, sort_order, status, visibility, pay_later_eligible,
                        canonical_url, meta_title, meta_desc,
                        created_by, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s
                    )
                """, (
                    website_id, attribute_set_id, attributes_json,
                    sku, item_code, parts_category, tyres_category, year, make_ids, price_included,
                    display_name, slug, json.dumps(name_json), description, short_desc,
                    price, list_price, sale_price, cost_price, 'AED',
                    stock_qty, stock_status, manage_stock, min_order_qty, max_order_qty,
                    tire_size_label, tire_speed_rating, tire_load_index, tire_type, tire_pattern,
                    run_flat, ev_rated, oem_approved, oem_brand, vehicle_type,
                    brand_id, category_id, image_path, image_alt, small_image, small_image_alt, gallery_json,
                    weight, country_of_origin, warranty_months,
                    is_featured, is_new, sort_order, status, visibility, pay_later_eligible,
                    canonical_url, meta_title, meta_desc,
                    user_id, now, now
                ))
                conn.commit()
                new_id = cursor.lastrowid

                # Save dynamic attributes to EAV product_attribute_values
                if dyn_attrs:
                    for attr_code, attr_val in dyn_attrs.items():
                        if attr_val is None or attr_val == '':
                            continue
                        cursor.execute("SELECT id FROM attributes WHERE code = %s AND deleted_at IS NULL", (attr_code,))
                        attr_row = cursor.fetchone()
                        if attr_row:
                            try:
                                AttributeService.save_product_scoped_attribute(
                                    product_id=new_id,
                                    attribute_id=attr_row['id'],
                                    value=attr_val,
                                    user_id=user_id
                                )
                            except Exception:
                                pass

                # Save product websites
                website_ids = data.get('website_ids')
                if not website_ids and data.get('website_id'):
                    website_ids = [data.get('website_id')]
                if not website_ids:
                    website_ids = [1]
                for wid in website_ids:
                    try:
                        wid_int = cls._safe_int(wid)
                        if wid_int is not None:
                            cursor.execute("""
                                INSERT INTO product_websites (product_id, website_id, created_by, updated_by, created_at, updated_at)
                                VALUES (%s, %s, %s, %s, NOW(), NOW())
                            """, (new_id, wid_int, user_id, user_id))
                    except Exception:
                        pass
                if website_ids:
                    try:
                        first_wid = cls._safe_int(website_ids[0])
                        if first_wid is not None:
                            cursor.execute("UPDATE products SET website_id = %s WHERE id = %s", (first_wid, new_id))
                    except Exception:
                        pass

                # Sync product categories
                category_ids = data.get('category_ids')
                if not category_ids and category_id:
                    category_ids = [category_id]
                if category_ids:
                    for idx, cid in enumerate(category_ids):
                        cid_int = cls._safe_int(cid)
                        if cid_int:
                            try:
                                cursor.execute("""
                                    INSERT IGNORE INTO product_categories (product_id, category_id, position)
                                    VALUES (%s, %s, %s)
                                """, (new_id, cid_int, idx))
                            except Exception:
                                pass
                conn.commit()

                if es_service:
                    try:
                        es_service.index_single_product(new_id)
                    except Exception:
                        pass

                return new_id
        finally:
            conn.close()

    @classmethod
    def update(cls, product_id: int, data: dict, user_id: int = None):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # Check existing
                cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
                existing = cursor.fetchone()
                if not existing:
                    return False

                fields = []
                params = []

                if 'sku' in data:
                    fields.append("sku = %s")
                    params.append(str(data['sku']).strip().upper())

                from services.store_context import StoreContext
                from i18n import parse_json_dict, get_translated_value
                curr_lang = StoreContext.get_current_language()

                if 'display_name' in data or 'name_en' in data or 'name' in data:
                    name_val = data.get('name') or data.get('name_en') or data.get('display_name')
                    existing_name = parse_json_dict(existing.get('name')) if existing.get('name') else {}
                    if not isinstance(existing_name, dict):
                        existing_name = {}
                    if isinstance(name_val, dict):
                        existing_name.update(name_val)
                    elif isinstance(name_val, str):
                        s = name_val.strip()
                        if s.startswith('{'):
                            try:
                                p = json.loads(s)
                                if isinstance(p, dict):
                                    existing_name.update(p)
                                else:
                                    existing_name[curr_lang] = s
                            except Exception:
                                existing_name[curr_lang] = s
                        else:
                            existing_name[curr_lang] = s
                    if data.get('name_en'):
                        existing_name['en'] = str(data['name_en']).strip()
                    display_name = get_translated_value(existing_name, 'en') or get_translated_value(existing_name)
                    fields.extend(["display_name = %s", "name = %s"])
                    params.extend([display_name, json.dumps(existing_name, ensure_ascii=False)])

                dyn_attrs = data.get('dynamic_attributes') or data.get('attributes_json') or {}
                if isinstance(dyn_attrs, str):
                    try:
                        dyn_attrs = json.loads(dyn_attrs)
                    except Exception:
                        dyn_attrs = {}

                slug_candidate = data.get('slug') or data.get('url_key')
                if not slug_candidate and dyn_attrs:
                    slug_candidate = dyn_attrs.get('url_key')
                if slug_candidate:
                    clean_slug = cls.slugify(slug_candidate)
                    fields.append("slug = %s")
                    params.append(clean_slug)

                for price_col in ['price', 'list_price', 'sale_price', 'cost_price']:
                    if price_col in data:
                        val = cls._safe_decimal(data[price_col])
                        fields.append(f"{price_col} = %s")
                        params.append(val)

                if 'stock_qty' in data:
                    sq = cls._safe_int(data['stock_qty'], 0)
                    fields.append("stock_qty = %s")
                    params.append(sq)
                    if 'stock_status' not in data:
                        fields.append("stock_status = %s")
                        params.append('in_stock' if sq > 0 else 'out_of_stock')

                if 'stock_status' in data:
                    fields.append("stock_status = %s")
                    params.append(cls._safe_stock_status(data['stock_status']))

                if 'status' in data or 'product_online' in data:
                    st_val = data.get('product_online') if data.get('product_online') is not None else data.get('status')
                    fields.append("status = %s")
                    params.append(cls._safe_status(st_val))

                if 'visibility' in data:
                    fields.append("visibility = %s")
                    params.append(cls._safe_visibility(data['visibility']))

                if 'tire_type' in data:
                    fields.append("tire_type = %s")
                    params.append(cls._safe_tire_type(data['tire_type']))

                if 'vehicle_type' in data:
                    fields.append("vehicle_type = %s")
                    params.append(cls._safe_vehicle_type(data['vehicle_type']))

                if 'tire_size_label' in data:
                    fields.append("tire_size_label = %s")
                    params.append(data['tire_size_label'])

                for spec_col in ['tire_speed_rating', 'tire_load_index', 'tire_pattern',
                                 'oem_brand', 'country_of_origin']:
                    if spec_col in data:
                        fields.append(f"{spec_col} = %s")
                        params.append(data[spec_col] or None)

                for bool_col in ['run_flat', 'ev_rated', 'oem_approved', 'is_featured', 'is_new', 'manage_stock', 'pay_later_eligible']:
                    if bool_col in data:
                        fields.append(f"{bool_col} = %s")
                        params.append(1 if data[bool_col] else 0)

                if 'weight' in data:
                    fields.append("weight = %s")
                    params.append(cls._safe_decimal(data['weight']))

                for fk_col in ['brand_id', 'category_id', 'warranty_months', 'sort_order', 'min_order_qty', 'max_order_qty']:
                    if fk_col in data:
                        if fk_col == 'warranty_months':
                            val = cls._safe_warranty_months(data[fk_col])
                        else:
                            val = cls._safe_int(data[fk_col])
                        fields.append(f"{fk_col} = %s")
                        params.append(val)

                dyn_attrs = data.get('dynamic_attributes') or data.get('attributes_json')
                if isinstance(dyn_attrs, str):
                    try:
                        dyn_attrs = json.loads(dyn_attrs)
                    except Exception:
                        dyn_attrs = {}
                elif not isinstance(dyn_attrs, dict):
                    dyn_attrs = None

                for str_col in ['image_path', 'image_alt', 'small_image', 'small_image_alt', 'canonical_url']:
                    if str_col in data:
                        fields.append(f"{str_col} = %s")
                        params.append((str(data[str_col]).strip()) if data[str_col] else None)

                if 'item_code' in data or (dyn_attrs and 'item_code' in dyn_attrs):
                    val = data.get('item_code') if 'item_code' in data else dyn_attrs.get('item_code')
                    fields.append("item_code = %s")
                    params.append((str(val).strip()) if val else None)

                if 'parts_category' in data or (dyn_attrs and 'parts_category' in dyn_attrs):
                    val = data.get('parts_category') if 'parts_category' in data else dyn_attrs.get('parts_category')
                    fields.append("parts_category = %s")
                    params.append((str(val).strip()) if val else None)

                if 'website_id' in data:
                    fields.append("website_id = %s")
                    params.append(cls._safe_int(data['website_id'], 1))

                if 'tyres_category' in data or (dyn_attrs and 'tyres_category' in dyn_attrs):
                    raw_tc = data.get('tyres_category') if 'tyres_category' in data else dyn_attrs.get('tyres_category')
                    tc = (str(raw_tc).strip()) if raw_tc else None
                    if tc:
                        tc_l = tc.lower()
                        if tc_l == 'budget':
                            tc = 'Budget'
                        elif tc_l == 'quality':
                            tc = 'Quality'
                        elif tc_l == 'premium':
                            tc = 'Premium'
                    fields.append("tyres_category = %s")
                    params.append(tc)

                if 'year' in data or (dyn_attrs and 'year' in dyn_attrs):
                    raw_y = data.get('year') if 'year' in data else dyn_attrs.get('year')
                    y_val = None
                    if raw_y:
                        try:
                            y_int = int(str(raw_y).strip())
                            if 1901 <= y_int <= 2155:
                                y_val = y_int
                        except (ValueError, TypeError):
                            y_val = None
                    fields.append("year = %s")
                    params.append(y_val)

                if 'make_ids' in data:
                    m_ids = data['make_ids']
                    if m_ids is not None and not isinstance(m_ids, str):
                        m_ids = json.dumps(m_ids)
                    elif isinstance(m_ids, str) and not m_ids.strip():
                        m_ids = None
                    fields.append("make_ids = %s")
                    params.append(m_ids)

                if 'price_included' in data or 'price_included_text' in data:
                    pi = data.get('price_included') or data.get('price_included_text')
                    if pi:
                        if isinstance(pi, dict):
                            pi = json.dumps(pi, ensure_ascii=False)
                        elif isinstance(pi, str):
                            if pi.strip().startswith('{'):
                                pi = pi.strip()
                            else:
                                pi = json.dumps({'en': pi.strip()}, ensure_ascii=False)
                    else:
                        pi = None
                    fields.append("price_included = %s")
                    params.append(pi)

                if 'gallery_json' in data:
                    fields.append("gallery_json = %s")
                    params.append(json.dumps(data['gallery_json'] or []))

                for fld, col in [('description', 'description'), ('short_desc', 'short_desc'), ('meta_title', 'meta_title'), ('meta_desc', 'meta_desc')]:
                    fld_en = f'{fld}_en'
                    has_plain = fld in data
                    has_en = fld_en in data
                    if has_plain or has_en:
                        val = data.get(fld) if has_plain else None
                        exist_d = parse_json_dict(existing.get(col)) if existing.get(col) else {}
                        if not isinstance(exist_d, dict):
                            exist_d = {}
                        if isinstance(val, dict):
                            exist_d.update(val)
                        elif isinstance(val, str):
                            s = val.strip()
                            if s.startswith('{'):
                                try:
                                    p = json.loads(s)
                                    if isinstance(p, dict):
                                        exist_d.update(p)
                                    else:
                                        exist_d[curr_lang] = s
                                except Exception:
                                    exist_d[curr_lang] = s
                            else:
                                exist_d[curr_lang] = s
                        elif val is None and not has_en:
                            exist_d = {}
                        if has_en:
                            en_val = data.get(fld_en)
                            if en_val is not None and str(en_val).strip():
                                exist_d['en'] = str(en_val).strip()
                        fields.append(f"{col} = %s")
                        params.append(json.dumps(exist_d, ensure_ascii=False))

                if 'attribute_set_id' in data and data['attribute_set_id']:
                    fields.append("attribute_set_id = %s")
                    params.append(cls._safe_int(data['attribute_set_id'], 1))

                if 'dynamic_attributes' in data or 'attributes_json' in data:
                    fields.append("attributes_json = %s")
                    params.append(json.dumps(dyn_attrs or {}))

                    # Sync tyre_size_label from dynamic attributes if present
                    if dyn_attrs and dyn_attrs.get('tire_size_label') and 'tire_size_label' not in data:
                        fields.append("tire_size_label = %s")
                        params.append(str(dyn_attrs['tire_size_label']).strip())

                now = datetime.now(timezone.utc)
                fields.extend(["updated_by = %s", "updated_at = %s"])
                params.extend([user_id, now])

                sql = f"UPDATE products SET {', '.join(fields)} WHERE id = %s"
                params.append(product_id)

                cursor.execute(sql, tuple(params))
                conn.commit()

                # Sync dynamic attributes into EAV product_attribute_values
                if dyn_attrs is not None:
                    for attr_code, attr_val in dyn_attrs.items():
                        if attr_val is None or attr_val == '':
                            continue
                        cursor.execute("SELECT id FROM attributes WHERE code = %s AND deleted_at IS NULL", (attr_code,))
                        attr_row = cursor.fetchone()
                        if attr_row:
                            try:
                                AttributeService.save_product_scoped_attribute(
                                    product_id=product_id,
                                    attribute_id=attr_row['id'],
                                    value=attr_val,
                                    user_id=user_id
                                )
                            except Exception:
                                pass

                # Sync product websites
                if 'website_ids' in data or 'website_id' in data:
                    website_ids = data.get('website_ids')
                    if not website_ids and data.get('website_id'):
                        website_ids = [data.get('website_id')]
                    if website_ids is not None:
                        cursor.execute("DELETE FROM product_websites WHERE product_id = %s", (product_id,))
                        for wid in website_ids:
                            try:
                                wid_int = cls._safe_int(wid)
                                if wid_int is not None:
                                    cursor.execute("""
                                        INSERT INTO product_websites (product_id, website_id, created_by, updated_by, created_at, updated_at)
                                        VALUES (%s, %s, %s, %s, NOW(), NOW())
                                    """, (product_id, wid_int, user_id, user_id))
                            except Exception:
                                pass
                        if website_ids:
                            try:
                                first_wid = cls._safe_int(website_ids[0])
                                if first_wid is not None:
                                    cursor.execute("UPDATE products SET website_id = %s WHERE id = %s", (first_wid, product_id))
                            except Exception:
                                pass

                # Sync product categories
                if 'category_ids' in data or 'category_id' in data:
                    category_ids = data.get('category_ids')
                    if category_ids is None and data.get('category_id'):
                        category_ids = [data.get('category_id')]
                    if category_ids is not None:
                        try:
                            cursor.execute("DELETE FROM product_categories WHERE product_id = %s", (product_id,))
                            for idx, cid in enumerate(category_ids):
                                cid_int = cls._safe_int(cid)
                                if cid_int:
                                    cursor.execute("""
                                        INSERT IGNORE INTO product_categories (product_id, category_id, position)
                                        VALUES (%s, %s, %s)
                                    """, (product_id, cid_int, idx))
                            if category_ids:
                                first_cid = cls._safe_int(category_ids[0])
                                if first_cid:
                                    cursor.execute("UPDATE products SET category_id = %s WHERE id = %s", (first_cid, product_id))
                            else:
                                cursor.execute("UPDATE products SET category_id = NULL WHERE id = %s", (product_id,))
                        except Exception:
                            pass
                conn.commit()

                if es_service:
                    try:
                        es_service.index_single_product(product_id)
                    except Exception:
                        pass

                return True
        finally:
            conn.close()

    @classmethod
    def soft_delete(cls, product_id: int, user_id: int = None):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                now = datetime.now(timezone.utc)
                cursor.execute("""
                    UPDATE products
                    SET deleted_at = %s, deleted_by = %s
                    WHERE id = %s AND deleted_at IS NULL
                """, (now, user_id, product_id))
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted and es_service:
                    try:
                        es_service.delete_single_product(product_id)
                    except Exception:
                        pass
                return deleted
        finally:
            conn.close()

    @classmethod
    def restore(cls, product_id: int, user_id: int = None):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                now = datetime.now(timezone.utc)
                cursor.execute("""
                    UPDATE products
                    SET deleted_at = NULL, deleted_by = NULL, updated_at = %s, updated_by = %s
                    WHERE id = %s AND deleted_at IS NOT NULL
                """, (now, user_id, product_id))
                conn.commit()
                restored = cursor.rowcount > 0
                if restored and es_service:
                    try:
                        es_service.index_single_product(product_id)
                    except Exception:
                        pass
                return restored
        finally:
            conn.close()

    @classmethod
    def purge(cls, product_id: int):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
                conn.commit()
                purged = cursor.rowcount > 0
                if purged and es_service:
                    try:
                        es_service.delete_single_product(product_id)
                    except Exception:
                        pass
                return purged
        finally:
            conn.close()

    @classmethod
    def bulk_action(cls, action: str, ids: list, user_id: int = None):
        if not ids:
            return 0
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                now = datetime.now(timezone.utc)
                placeholders = ', '.join(['%s'] * len(ids))
                if action == 'delete':
                    sql = f"UPDATE products SET deleted_at = %s, deleted_by = %s WHERE id IN ({placeholders}) AND deleted_at IS NULL"
                    cursor.execute(sql, [now, user_id] + ids)
                elif action == 'restore':
                    sql = f"UPDATE products SET deleted_at = NULL, deleted_by = NULL, updated_at = %s WHERE id IN ({placeholders}) AND deleted_at IS NOT NULL"
                    cursor.execute(sql, [now] + ids)
                elif action == 'in_stock':
                    sql = f"UPDATE products SET stock_status = 'in_stock', updated_at = %s WHERE id IN ({placeholders})"
                    cursor.execute(sql, [now] + ids)
                elif action == 'out_of_stock':
                    sql = f"UPDATE products SET stock_status = 'out_of_stock', updated_at = %s WHERE id IN ({placeholders})"
                    cursor.execute(sql, [now] + ids)
                elif action == 'active':
                    sql = f"UPDATE products SET status = 'active', updated_at = %s WHERE id IN ({placeholders})"
                    cursor.execute(sql, [now] + ids)
                elif action == 'inactive':
                    sql = f"UPDATE products SET status = 'inactive', updated_at = %s WHERE id IN ({placeholders})"
                    cursor.execute(sql, [now] + ids)
                conn.commit()
                affected = cursor.rowcount
                if es_service and ids:
                    try:
                        if action in ('delete', 'inactive'):
                            for pid in ids:
                                es_service.delete_single_product(int(pid))
                        else:
                            for pid in ids:
                                es_service.index_single_product(int(pid))
                    except Exception:
                        pass
                return affected
        finally:
            conn.close()
