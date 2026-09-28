"""
app/models/storelocator.py - Store Locator Model & Database Operations
Table: storelocator
"""

import json
import re
from datetime import datetime, timezone
from db import get_connection

class StoreLocator:
    @staticmethod
    def slugify(text: str) -> str:
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '-', text)
        return text.strip('-')

    @classmethod
    def _normalize_row(cls, row: dict) -> dict:
        if not row:
            return row
        # Ensure json fields are parsed if returned as str
        for field in ('store_views', 'schedule_json'):
            val = row.get(field)
            if isinstance(val, str):
                try:
                    row[field] = json.loads(val)
                except Exception:
                    pass
        # Normalize status & boolean fields to int/bool
        row['status'] = 1 if row.get('status') else 0
        row['is_mobile_van'] = 1 if row.get('is_mobile_van') else 0
        row['coming_soon'] = 1 if row.get('coming_soon') else 0
        row['is_deleted'] = 1 if row.get('is_deleted') else 0
        if row.get('shipping_amount') is not None:
            row['shipping_amount'] = float(row['shipping_amount'])
        return row

    @classmethod
    def get_metrics(cls) -> dict:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(CASE WHEN is_deleted = 0 THEN 1 END) AS total,
                        COUNT(CASE WHEN is_deleted = 0 AND status = 1 THEN 1 END) AS active,
                        COUNT(CASE WHEN is_deleted = 0 AND status = 0 THEN 1 END) AS inactive,
                        COUNT(CASE WHEN is_deleted = 1 THEN 1 END) AS trash
                    FROM storelocator
                """)
                return cur.fetchone() or {'total': 0, 'active': 0, 'inactive': 0, 'trash': 0}
        finally:
            conn.close()

    @classmethod
    def search_and_paginate(cls, query: str = None, status: str = None, city: str = None, is_deleted: int = 0, page: int = 1, per_page: int = 20) -> dict:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                where = ["is_deleted = %s"]
                params = [is_deleted]

                if query and query.strip():
                    term = f"%{query.strip()}%"
                    where.append("(name LIKE %s OR name_ar LIKE %s OR city LIKE %s OR city_ar LIKE %s OR address LIKE %s OR phone LIKE %s OR email LIKE %s)")
                    params.extend([term, term, term, term, term, term, term])

                if status is not None and status != '' and status != 'all':
                    where.append("status = %s")
                    params.append(1 if str(status).lower() in ('1', 'true', 'yes', 'active') else 0)

                if city and city.strip() and city != 'all':
                    where.append("city = %s")
                    params.append(city.strip())

                where_sql = " AND ".join(where)

                # Total count
                cur.execute(f"SELECT COUNT(*) AS total FROM storelocator WHERE {where_sql}", params)
                total = cur.fetchone()['total']

                offset = (page - 1) * per_page
                order_sql = "deleted_at DESC, id DESC" if is_deleted else "installer_sort_order ASC, name ASC, id DESC"

                cur.execute(f"""
                    SELECT id, name, name_ar, status, category, is_mobile_van, shipping_amount,
                           installer_sort_order, skip_days, cutoff_time, skip_hours, coming_soon,
                           opening_hours_one, opening_hours_two, longitude, latitude,
                           address_ar, city_ar, postcode, country, region, city, address,
                           external_link, phone, email, google_map, image, image_1, image_2, image_3, image_4, image_5,
                           intro, description, distance, nearest_station, url_key, store_details_image,
                           service_included, meta_title, meta_description, meta_title_ar, meta_description_ar,
                           store_views, schedule_json, is_deleted, created_at, updated_at, deleted_at
                    FROM storelocator
                    WHERE {where_sql}
                    ORDER BY {order_sql}
                    LIMIT %s OFFSET %s
                """, params + [per_page, offset])

                rows = cur.fetchall() or []
                items = [cls._normalize_row(r) for r in rows]

                return {
                    'items': items,
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': max(1, (total + per_page - 1) // per_page)
                }
        finally:
            conn.close()

    @classmethod
    def get_by_id(cls, item_id: int) -> dict:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM storelocator WHERE id = %s", (item_id,))
                row = cur.fetchone()
                return cls._normalize_row(row) if row else None
        finally:
            conn.close()

    @classmethod
    def get_by_url_key(cls, url_key: str) -> dict:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM storelocator WHERE url_key = %s AND is_deleted = 0 AND status = 1", (url_key,))
                row = cur.fetchone()
                return cls._normalize_row(row) if row else None
        finally:
            conn.close()

    @classmethod
    def get_unique_cities(cls) -> list:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT city FROM storelocator 
                    WHERE is_deleted = 0 AND city IS NOT NULL AND city != '' 
                    ORDER BY city ASC
                """)
                return [r['city'] for r in cur.fetchall() or []]
        finally:
            conn.close()

    @classmethod
    def create(cls, data: dict) -> int:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                store_views = data.get('store_views')
                if isinstance(store_views, (list, dict)):
                    store_views = json.dumps(store_views)

                schedule_json = data.get('schedule_json')
                if isinstance(schedule_json, (list, dict)):
                    schedule_json = json.dumps(schedule_json)

                url_key = data.get('url_key')
                if not url_key and data.get('name'):
                    url_key = cls.slugify(data['name'])

                sql = """
                INSERT INTO storelocator (
                    name, name_ar, status, category, is_mobile_van, shipping_amount,
                    installer_sort_order, skip_days, cutoff_time, skip_hours, coming_soon,
                    opening_hours_one, opening_hours_two, longitude, latitude,
                    address_ar, city_ar, postcode, country, region, city, address,
                    external_link, phone, email, google_map, image,
                    image_1, image_2, image_3, image_4, image_5,
                    intro, description, distance, nearest_station, url_key,
                    store_details_image, service_included, meta_title, meta_description,
                    meta_title_ar, meta_description_ar, store_views, schedule_json,
                    is_deleted, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    0, NOW(), NOW()
                )
                """
                cur.execute(sql, (
                    data.get('name', '').strip(),
                    data.get('name_ar') or None,
                    1 if data.get('status') in (1, '1', True, 'true', 'yes') else 0,
                    data.get('category') or None,
                    1 if data.get('is_mobile_van') in (1, '1', True, 'true', 'yes') else 0,
                    float(data.get('shipping_amount') or 0.0),
                    int(data.get('installer_sort_order') or 0),
                    int(data.get('skip_days') or 0),
                    data.get('cutoff_time') or None,
                    data.get('skip_hours') or None,
                    1 if data.get('coming_soon') in (1, '1', True, 'true', 'yes') else 0,
                    data.get('opening_hours_one') or None,
                    data.get('opening_hours_two') or None,
                    data.get('longitude', '').strip(),
                    data.get('latitude', '').strip(),
                    data.get('address_ar') or None,
                    data.get('city_ar') or None,
                    data.get('postcode') or None,
                    data.get('country') or 'United Arab Emirates',
                    data.get('region') or None,
                    data.get('city') or None,
                    data.get('address') or None,
                    data.get('external_link') or None,
                    data.get('phone') or None,
                    data.get('email') or None,
                    data.get('google_map') or None,
                    data.get('image') or None,
                    data.get('image_1') or None,
                    data.get('image_2') or None,
                    data.get('image_3') or None,
                    data.get('image_4') or None,
                    data.get('image_5') or None,
                    data.get('intro') or None,
                    data.get('description') or None,
                    data.get('distance') or None,
                    data.get('nearest_station') or None,
                    url_key or None,
                    data.get('store_details_image') or None,
                    data.get('service_included') or None,
                    data.get('meta_title') or None,
                    data.get('meta_description') or None,
                    data.get('meta_title_ar') or None,
                    data.get('meta_description_ar') or None,
                    store_views,
                    schedule_json
                ))
                conn.commit()
                return cur.lastrowid
        finally:
            conn.close()

    @classmethod
    def update(cls, item_id: int, data: dict) -> bool:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                store_views = data.get('store_views')
                if isinstance(store_views, (list, dict)):
                    store_views = json.dumps(store_views)

                schedule_json = data.get('schedule_json')
                if isinstance(schedule_json, (list, dict)):
                    schedule_json = json.dumps(schedule_json)

                url_key = data.get('url_key')
                if not url_key and data.get('name'):
                    url_key = cls.slugify(data['name'])

                sql = """
                UPDATE storelocator SET
                    name = %s,
                    name_ar = %s,
                    status = %s,
                    category = %s,
                    is_mobile_van = %s,
                    shipping_amount = %s,
                    installer_sort_order = %s,
                    skip_days = %s,
                    cutoff_time = %s,
                    skip_hours = %s,
                    coming_soon = %s,
                    opening_hours_one = %s,
                    opening_hours_two = %s,
                    longitude = %s,
                    latitude = %s,
                    address_ar = %s,
                    city_ar = %s,
                    postcode = %s,
                    country = %s,
                    region = %s,
                    city = %s,
                    address = %s,
                    external_link = %s,
                    phone = %s,
                    email = %s,
                    google_map = %s,
                    image = %s,
                    image_1 = %s,
                    image_2 = %s,
                    image_3 = %s,
                    image_4 = %s,
                    image_5 = %s,
                    intro = %s,
                    description = %s,
                    distance = %s,
                    nearest_station = %s,
                    url_key = %s,
                    store_details_image = %s,
                    service_included = %s,
                    meta_title = %s,
                    meta_description = %s,
                    meta_title_ar = %s,
                    meta_description_ar = %s,
                    store_views = %s,
                    schedule_json = %s,
                    updated_at = NOW()
                WHERE id = %s
                """
                cur.execute(sql, (
                    data.get('name', '').strip(),
                    data.get('name_ar') or None,
                    1 if data.get('status') in (1, '1', True, 'true', 'yes') else 0,
                    data.get('category') or None,
                    1 if data.get('is_mobile_van') in (1, '1', True, 'true', 'yes') else 0,
                    float(data.get('shipping_amount') or 0.0),
                    int(data.get('installer_sort_order') or 0),
                    int(data.get('skip_days') or 0),
                    data.get('cutoff_time') or None,
                    data.get('skip_hours') or None,
                    1 if data.get('coming_soon') in (1, '1', True, 'true', 'yes') else 0,
                    data.get('opening_hours_one') or None,
                    data.get('opening_hours_two') or None,
                    data.get('longitude', '').strip(),
                    data.get('latitude', '').strip(),
                    data.get('address_ar') or None,
                    data.get('city_ar') or None,
                    data.get('postcode') or None,
                    data.get('country') or 'United Arab Emirates',
                    data.get('region') or None,
                    data.get('city') or None,
                    data.get('address') or None,
                    data.get('external_link') or None,
                    data.get('phone') or None,
                    data.get('email') or None,
                    data.get('google_map') or None,
                    data.get('image') or None,
                    data.get('image_1') or None,
                    data.get('image_2') or None,
                    data.get('image_3') or None,
                    data.get('image_4') or None,
                    data.get('image_5') or None,
                    data.get('intro') or None,
                    data.get('description') or None,
                    data.get('distance') or None,
                    data.get('nearest_station') or None,
                    url_key or None,
                    data.get('store_details_image') or None,
                    data.get('service_included') or None,
                    data.get('meta_title') or None,
                    data.get('meta_description') or None,
                    data.get('meta_title_ar') or None,
                    data.get('meta_description_ar') or None,
                    store_views,
                    schedule_json,
                    item_id
                ))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    @classmethod
    def soft_delete(cls, item_id: int) -> bool:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE storelocator 
                    SET is_deleted = 1, deleted_at = NOW() 
                    WHERE id = %s
                """, (item_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    @classmethod
    def restore(cls, item_id: int) -> bool:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE storelocator 
                    SET is_deleted = 0, deleted_at = NULL 
                    WHERE id = %s
                """, (item_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    @classmethod
    def purge(cls, item_id: int) -> bool:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM storelocator WHERE id = %s", (item_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()
