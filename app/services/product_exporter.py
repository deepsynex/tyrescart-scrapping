"""
app/services/product_exporter.py - Catalog Product CSV Exporter
Exports catalog products matching Magento 2 catalog product CSV format
(identical 138-column schema of export_catalog_product_20261008_100327.csv).
"""

import csv
import io
import json
from datetime import datetime
from db import get_connection

MAGENTO_CATALOG_CSV_HEADERS = [
    'sku', 'store_view_code', 'attribute_set_code', 'product_type', 'categories', 'product_websites',
    'name', 'description', 'short_description', 'weight', 'product_online', 'tax_class_name',
    'visibility', 'price', 'special_price', 'special_price_from_date', 'special_price_to_date',
    'url_key', 'meta_title', 'meta_keywords', 'meta_description', 'base_image', 'base_image_label',
    'small_image', 'small_image_label', 'thumbnail_image', 'thumbnail_image_label', 'swatch_image',
    'swatch_image_label', 'created_at', 'updated_at', 'new_from_date', 'new_to_date',
    'display_product_options_in', 'map_price', 'msrp_price', 'map_enabled', 'gift_message_available',
    'custom_design', 'custom_design_from', 'custom_design_to', 'custom_layout_update', 'page_layout',
    'product_options_container', 'msrp_display_actual_price_type', 'country_of_manufacture',
    'back_space_inches', 'barari_code', 'bike_tyre_type', 'brand', 'capacity_ah',
    'cold_test_current_a', 'color', 'color_finish', 'construction', 'cost', 'country',
    'custom_layout_update_file', 'dimension', 'display_name', 'dwb_code', 'ev', 'gcc_code',
    'height', 'hold_down_type', 'hub_bore', 'item_code', 'load_index', 'lookin_code', 'model',
    'oem_marking', 'oem_tyres', 'offers', 'offset', 'parts_category', 'pattern', 'pcd',
    'post_positions', 'price_included_text', 'price_per_item', 'psa_code', 'rim', 'runflat',
    'size', 'tabby_payment', 'terminal_type', 'tyres_category', 'tyre_marking', 'tyre_size',
    'tyre_type', 'vehicle_compatible', 'voltage_v', 'warranty_period', 'wheel_type', 'width',
    'year', 'additional_attributes', 'qty', 'out_of_stock_qty', 'use_config_min_qty',
    'is_qty_decimal', 'allow_backorders', 'use_config_backorders', 'min_cart_qty',
    'use_config_min_sale_qty', 'max_cart_qty', 'use_config_max_sale_qty', 'is_in_stock',
    'notify_on_stock_below', 'use_config_notify_stock_qty', 'manage_stock',
    'use_config_manage_stock', 'use_config_qty_increments', 'qty_increments',
    'use_config_enable_qty_inc', 'enable_qty_increments', 'is_decimal_divided', 'website_id',
    'related_skus', 'related_position', 'crosssell_skus', 'crosssell_position', 'upsell_skus',
    'upsell_position', 'additional_images', 'additional_image_labels', 'hide_from_product_page',
    'bundle_price_type', 'bundle_sku_type', 'bundle_price_view', 'bundle_weight_type',
    'bundle_values', 'bundle_shipment_type', 'associated_skus', 'downloadable_links',
    'downloadable_samples', 'configurable_variations', 'configurable_variation_labels'
]


class ProductExporter:
    @staticmethod
    def _parse_name(val):
        if not val:
            return ""
        if isinstance(val, dict):
            return val.get('en') or val.get('ar') or next(iter(val.values()), '')
        if isinstance(val, str):
            val_s = val.strip()
            if val_s.startswith('{') and val_s.endswith('}'):
                try:
                    d = json.loads(val_s)
                    if isinstance(d, dict):
                        return d.get('en') or d.get('ar') or next(iter(d.values()), '')
                except Exception:
                    pass
            return val_s
        return str(val)

    @classmethod
    def generate_csv_stream(cls, product_ids=None, filters=None):
        """
        Yields CSV text lines in chunks for streaming large exports.
        """
        conn = get_connection()
        try:
            where_clauses = []
            params = []

            if product_ids:
                clean_ids = [int(i) for i in product_ids if str(i).isdigit()]
                if clean_ids:
                    placeholders = ','.join(['%s'] * len(clean_ids))
                    where_clauses.append(f"p.id IN ({placeholders})")
                    params.extend(clean_ids)
            elif filters:
                if filters.get('trash') in ('1', 'true', True):
                    where_clauses.append("p.deleted_at IS NOT NULL")
                else:
                    where_clauses.append("p.deleted_at IS NULL")

                search = filters.get('search')
                if search:
                    s_term = f"%{search.strip()}%"
                    where_clauses.append("(p.sku LIKE %s OR p.display_name LIKE %s OR p.name LIKE %s OR p.slug LIKE %s OR p.tire_pattern LIKE %s)")
                    params.extend([s_term, s_term, s_term, s_term, s_term])

                if filters.get('brand_id'):
                    where_clauses.append("p.brand_id = %s")
                    params.append(int(filters['brand_id']))

                if filters.get('category_id'):
                    where_clauses.append("p.category_id = %s")
                    params.append(int(filters['category_id']))

                if filters.get('attribute_set_id'):
                    where_clauses.append("p.attribute_set_id = %s")
                    params.append(int(filters['attribute_set_id']))

                if filters.get('status'):
                    where_clauses.append("p.status = %s")
                    params.append(filters['status'])

                if filters.get('stock_status'):
                    where_clauses.append("p.stock_status = %s")
                    params.append(filters['stock_status'])

                if filters.get('vehicle_type'):
                    where_clauses.append("p.vehicle_type = %s")
                    params.append(filters['vehicle_type'])

                if filters.get('tyres_category'):
                    where_clauses.append("p.tyres_category = %s")
                    params.append(filters['tyres_category'])

                if filters.get('parts_category'):
                    where_clauses.append("p.parts_category = %s")
                    params.append(filters['parts_category'])

                if filters.get('year'):
                    where_clauses.append("p.year = %s")
                    params.append(int(filters['year']))

                if filters.get('country_of_origin'):
                    where_clauses.append("p.country_of_origin LIKE %s")
                    params.append(f"%{filters['country_of_origin'].strip()}%")

                if filters.get('run_flat') in ('1', 'true', 1, True):
                    where_clauses.append("p.run_flat = 1")
                elif filters.get('run_flat') in ('0', 'false', 0, False):
                    where_clauses.append("p.run_flat = 0")

                if filters.get('ev_rated') in ('1', 'true', 1, True):
                    where_clauses.append("p.ev_rated = 1")
                elif filters.get('ev_rated') in ('0', 'false', 0, False):
                    where_clauses.append("p.ev_rated = 0")

                if filters.get('has_image') in ('1', 'true', 1, True):
                    where_clauses.append("(p.image_path IS NOT NULL AND p.image_path != '')")
                elif filters.get('has_image') in ('0', 'false', 0, False):
                    where_clauses.append("(p.image_path IS NULL OR p.image_path = '')")
            else:
                where_clauses.append("p.deleted_at IS NULL")

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            sql = f"""
                SELECT p.*, b.name as brand_name, c.name as cat_name, s.name as set_name
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                LEFT JOIN categories c ON p.category_id = c.id
                LEFT JOIN attribute_sets s ON p.attribute_set_id = s.id
                {where_sql}
                ORDER BY p.id ASC
            """

            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                
                # Output Header with UTF-8 BOM
                yield '\ufeff'
                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=MAGENTO_CATALOG_CSV_HEADERS, lineterminator='\r\n', extrasaction='ignore')
                writer.writeheader()
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate(0)

                while True:
                    rows = cur.fetchmany(1000)
                    if not rows:
                        break

                    for p in rows:
                        attrs = {}
                        if p.get('attributes_json'):
                            try:
                                attrs = json.loads(p['attributes_json']) if isinstance(p['attributes_json'], str) else p['attributes_json']
                            except Exception:
                                pass

                        # Map row values with priority to direct product table columns
                        row = {col: attrs.get(col, '') for col in MAGENTO_CATALOG_CSV_HEADERS}

                        row['sku'] = p.get('sku') or attrs.get('sku', '')
                        row['attribute_set_code'] = p.get('set_name') or attrs.get('attribute_set_code') or 'Tyres'
                        row['product_type'] = attrs.get('product_type') or 'simple'
                        row['categories'] = attrs.get('categories') or (f"Default Category/{p.get('set_name') or 'Tyres'}")
                        row['product_websites'] = attrs.get('product_websites') or 'base,saudi,qatar,bahrain,kuwait,oman,syria'
                        
                        # Name & Descriptions
                        prod_name = cls._parse_name(p.get('name')) or p.get('display_name') or attrs.get('name', '')
                        row['name'] = prod_name
                        if p.get('description'):
                            row['description'] = p['description']
                        if p.get('short_desc'):
                            row['short_description'] = p['short_desc']

                        # Status & Tax & Visibility
                        if p.get('status') == 'active':
                            row['product_online'] = '1'
                        elif p.get('status') == 'inactive':
                            row['product_online'] = '2'
                        if not row['product_online']:
                            row['product_online'] = attrs.get('product_online', '1')

                        row['tax_class_name'] = attrs.get('tax_class_name') or 'Taxable Goods'
                        row['visibility'] = p.get('visibility') or attrs.get('visibility') or 'Catalog, Search'

                        # Prices
                        if p.get('price') is not None:
                            try:
                                p_float = float(p['price'])
                                row['price'] = f"{p_float:.0f}" if p_float.is_integer() else f"{p_float:.2f}"
                            except Exception:
                                row['price'] = str(p['price'])

                        if p.get('sale_price') is not None:
                            try:
                                sp_float = float(p['sale_price'])
                                row['special_price'] = f"{sp_float:.0f}" if sp_float.is_integer() else f"{sp_float:.2f}"
                            except Exception:
                                row['special_price'] = str(p['sale_price'])

                        row['url_key'] = p.get('slug') or attrs.get('url_key', '')
                        row['meta_title'] = p.get('meta_title') or attrs.get('meta_title', '')
                        row['meta_description'] = p.get('meta_desc') or attrs.get('meta_description', '')

                        # Images
                        img = p.get('image_path') or attrs.get('base_image', '')
                        small_img = p.get('small_image') or img or attrs.get('small_image', '')
                        row['base_image'] = img
                        row['small_image'] = small_img
                        row['thumbnail_image'] = small_img
                        row['swatch_image'] = small_img

                        # Dates
                        if p.get('created_at'):
                            try:
                                row['created_at'] = p['created_at'].strftime('%m-%d-%y')
                            except Exception:
                                pass
                        if p.get('updated_at'):
                            try:
                                row['updated_at'] = p['updated_at'].strftime('%m/%d/%y')
                            except Exception:
                                pass

                        # Brand & Core specs
                        row['brand'] = p.get('brand_name') or attrs.get('brand', '')
                        row['country'] = p.get('country_of_origin') or attrs.get('country', '')
                        row['display_name'] = p.get('display_name') or attrs.get('display_name', '')
                        row['item_code'] = p.get('item_code') or attrs.get('item_code', '')
                        row['pattern'] = p.get('tire_pattern') or attrs.get('pattern', '')
                        row['price_included_text'] = p.get('price_included') or attrs.get('price_included_text', 'Fitted Price')
                        row['price_per_item'] = row['price']

                        # Tyres specs
                        row['tyres_category'] = p.get('tyres_category') or attrs.get('tyres_category', '')
                        row['parts_category'] = p.get('parts_category') or attrs.get('parts_category', '')
                        row['year'] = str(p.get('year') or attrs.get('year', ''))
                        
                        load_speed = (str(p.get('tire_load_index') or '') + str(p.get('tire_speed_rating') or '')).strip()
                        row['load_index'] = attrs.get('load_speed_index') or attrs.get('load_index') or load_speed
                        
                        if p.get('run_flat') is not None:
                            row['runflat'] = 'Runflat' if p['run_flat'] else ''
                        if p.get('ev_rated') is not None:
                            row['ev'] = 'Yes' if p['ev_rated'] else 'No'

                        if p.get('tire_size_label'):
                            row['tyre_size'] = p['tire_size_label']
                        elif attrs.get('tire_size'):
                            row['tyre_size'] = attrs.get('tire_size')

                        if p.get('vehicle_type'):
                            row['tyre_type'] = p['vehicle_type'].capitalize() if p['vehicle_type'].lower() == 'car' else p['vehicle_type']

                        if p.get('warranty_months'):
                            row['warranty_period'] = f"{p['warranty_months']} Months" if p['warranty_months'] != 12 else '1 Year Warranty'
                        elif not row['warranty_period']:
                            row['warranty_period'] = '1 Year Warranty'

                        # Stock & Inventory
                        if p.get('stock_qty') is not None:
                            row['qty'] = str(p['stock_qty'])
                        if p.get('stock_status') == 'in_stock':
                            row['is_in_stock'] = '1'
                        elif p.get('stock_status') == 'out_of_stock':
                            row['is_in_stock'] = '0'

                        # Standard Magento Inventory Configs defaults if empty
                        row['use_config_min_qty'] = row['use_config_min_qty'] or '1'
                        row['is_qty_decimal'] = row['is_qty_decimal'] or '0'
                        row['allow_backorders'] = row['allow_backorders'] or '0'
                        row['use_config_backorders'] = row['use_config_backorders'] or '1'
                        row['min_cart_qty'] = row['min_cart_qty'] or '1'
                        row['use_config_min_sale_qty'] = row['use_config_min_sale_qty'] or '1'
                        row['max_cart_qty'] = row['max_cart_qty'] or '10000'
                        row['use_config_max_sale_qty'] = row['use_config_max_sale_qty'] or '1'
                        row['notify_on_stock_below'] = row['notify_on_stock_below'] or '1'
                        row['use_config_notify_stock_qty'] = row['use_config_notify_stock_qty'] or '1'
                        row['manage_stock'] = row['manage_stock'] or '1'
                        row['use_config_manage_stock'] = row['use_config_manage_stock'] or '1'
                        row['use_config_qty_increments'] = row['use_config_qty_increments'] or '1'
                        row['qty_increments'] = row['qty_increments'] or '1'
                        row['use_config_enable_qty_inc'] = row['use_config_enable_qty_inc'] or '1'
                        row['enable_qty_increments'] = row['enable_qty_increments'] or '0'
                        row['is_decimal_divided'] = row['is_decimal_divided'] or '0'
                        row['website_id'] = row['website_id'] or '0'

                        writer.writerow(row)

                    yield buf.getvalue()
                    buf.seek(0)
                    buf.truncate(0)

        finally:
            conn.close()


generate_csv_stream = ProductExporter.generate_csv_stream

