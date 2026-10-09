"""
app/services/product_importer.py - Dynamic Multi-Type Product & Category CSV Importer Service

Handles importing products of any type (Tyres, Batteries, Wheels, Accessories, etc.):
- Automatically detects or maps attribute sets (Tyres, Battery, Wheels, Default, etc.).
- Dynamically matches CSV columns to database attribute definitions rather than static code.
- Automatically handles option resolution and auto-creation for select/multiselect attributes.
- Preserves all CSV columns in attributes_json and syncs to EAV product_attribute_values.
- Parses hierarchical category paths under root ID 2 (Default Category) via CategoryImporter.
- Auto-creates any missing brands.
"""

import csv
import io
import re
from datetime import datetime, timezone
from db import get_connection
from i18n import dump_json_dict, parse_json_dict
from models.brand import Brand
from models.category import Category
from models.product import Product
from services.category_importer import CategoryImporter, parse_category_paths


def slugify(text: str) -> str:
    if not text:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')


# Common column aliases mapping user-friendly or legacy CSV column headers
# to canonical attribute codes defined in the attributes table.
ATTRIBUTE_ALIAS_MAP = {
    'tyre_size': 'tire_size',
    'tire_size_label': 'tire_size',
    'size': 'tire_size',
    'load_index': 'load_speed_index',
    'speed_rating': 'tire_speed_rating',
    'country': 'origin',
    'country_of_origin': 'origin',
    'country_of_manufacture': 'origin',
    'tax_class_name': 'tax_class',
    'tax_class_id': 'tax_class',
    'offers': 'promotion',
    'voltage': 'volts',
    'voltage_v': 'volts',
    'battery_capacity': 'mah',
    'capacity': 'mah',
    'cca_rating': 'cca',
    'cold_cranking_amps': 'cca',
    'warranty': 'warranty_period',
    'short_description': 'short_desc',
    'product_online': 'status',
}


class ProductImporter:
    @classmethod
    def validate_csv_headers(cls, csv_headers: list, attr_map: dict = None, product_columns: set = None) -> tuple:
        """
        Compares CSV headers with DB attributes and table columns.
        Returns: (matched_headers, missing_attributes, extra_headers)
        """
        if attr_map is None or product_columns is None:
            conn = get_connection()
            if attr_map is None:
                attr_map = {}
            if product_columns is None:
                product_columns = set()
            try:
                with conn.cursor() as cur:
                    if not attr_map:
                        cur.execute("SELECT id, code, name, type FROM attributes WHERE deleted_at IS NULL")
                        for a in cur.fetchall():
                            attr_map[a['code'].strip().lower()] = a
                    if not product_columns:
                        cur.execute("DESCRIBE products")
                        product_columns = {r['Field'].strip().lower() for r in cur.fetchall()}
            finally:
                conn.close()

        system_recognized_cols = {
            'sku', 'attribute_set_code', 'product_type', 'categories', 'product_websites',
            'name', 'description', 'short_description', 'product_online', 'tax_class_name',
            'visibility', 'price', 'special_price', 'special_price_from_date', 'special_price_to_date',
            'url_key', 'meta_title', 'meta_keywords', 'meta_description', 'base_image',
            'small_image', 'thumbnail_image', 'swatch_image', 'qty', 'stock_qty', 'stock_status',
            'weight', 'parts_category', 'tyres_category', 'price_included_text', 'price_included',
            'item_code', 'display_name', 'year', 'cost', 'cost_price', 'status'
        }

        matched_headers = []
        extra_headers = []
        for h in csv_headers:
            hl = str(h).strip().lower()
            if not hl:
                continue
            if (hl in attr_map or 
                hl in product_columns or 
                hl in system_recognized_cols or 
                hl in ATTRIBUTE_ALIAS_MAP or 
                ATTRIBUTE_ALIAS_MAP.get(hl) in attr_map or 
                ATTRIBUTE_ALIAS_MAP.get(hl) in product_columns):
                matched_headers.append(h)
            else:
                extra_headers.append(h)

        missing_attributes = [
            a_code for a_code in attr_map
            if a_code not in [str(h).strip().lower() for h in csv_headers] and
               a_code not in [ATTRIBUTE_ALIAS_MAP.get(str(h).strip().lower(), '') for h in csv_headers]
        ]
        return matched_headers, missing_attributes, extra_headers

    @classmethod
    def import_csv(cls, file_content, user_id: int = 1, progress_callback=None) -> dict:
        """
        Imports products of ANY type (Batteries, Wheels, Tyres, etc.) from CSV.
        Supports bytes, str, or file-like stream.

        progress_callback, if given, is called as progress_callback(rows_done, total_rows)
        after every row so a caller can report fine-grained progress rather than only
        knowing when the whole call (and therefore a whole chunk) has finished.
        """
        if isinstance(file_content, bytes):
            text = file_content.decode('utf-8-sig', errors='replace')
        elif isinstance(file_content, str):
            text = file_content
        elif hasattr(file_content, 'read'):
            raw = file_content.read()
            if isinstance(raw, bytes):
                text = raw.decode('utf-8-sig', errors='replace')
            else:
                text = str(raw)
        else:
            return {'success': False, 'error': 'Invalid file stream.', 'imported': 0}

        # Step 1: Run CategoryImporter to ensure all category hierarchies exist
        cat_result = CategoryImporter.import_csv(text, user_id=user_id)

        # Step 2: Build category tree cache: (parent_id, name_en.lower()) -> category_id
        conn = get_connection()
        cat_tree = {}
        set_lookup = {}
        attr_map = {}
        try:
            with conn.cursor() as cur:
                # Cache categories
                cur.execute("SELECT id, parent_id, name FROM categories WHERE deleted_at IS NULL")
                for c in cur.fetchall():
                    nd = parse_json_dict(c['name'])
                    name_en = (nd.get('en') if isinstance(nd, dict) else str(c['name'])).strip().lower()
                    cat_tree[(c['parent_id'], name_en)] = c['id']

                # Cache attribute sets (name -> id, slug -> id, singular/plural)
                cur.execute("SELECT id, name, slug FROM attribute_sets WHERE deleted_at IS NULL")
                for s in cur.fetchall():
                    s_id = s['id']
                    s_name = str(s['name']).strip().lower()
                    s_slug = str(s['slug']).strip().lower() if s.get('slug') else s_name
                    set_lookup[s_name] = s_id
                    set_lookup[s_slug] = s_id
                    set_lookup[str(s_id)] = s_id
                    if s_name.endswith('s'):
                        set_lookup[s_name[:-1]] = s_id
                    else:
                        set_lookup[s_name + 's'] = s_id

                # Cache all attribute definitions from DB
                cur.execute("SELECT id, code, name, type FROM attributes WHERE deleted_at IS NULL")
                for a in cur.fetchall():
                    c_code = a['code'].strip().lower()
                    attr_map[c_code] = a

                # Cache product table columns
                cur.execute("DESCRIBE products")
                product_columns = {r['Field'].strip().lower() for r in cur.fetchall()}

                # Cache existing products by SKU and by display_name for fast matching
                # (avoids a DB round-trip per row for both the primary SKU match and the
                # name fallback match below).
                cur.execute("SELECT id, sku, display_name, slug FROM products WHERE deleted_at IS NULL")
                existing_products_by_sku = {}
                existing_products_by_name = {}
                for p in cur.fetchall():
                    record = {
                        'id': p['id'],
                        'sku': p.get('sku'),
                        'display_name': p.get('display_name'),
                        'slug': p.get('slug')
                    }
                    p_sku = (p.get('sku') or '').strip().upper()
                    if p_sku:
                        existing_products_by_sku[p_sku] = record
                    p_name = (p.get('display_name') or '').strip().lower()
                    if p_name:
                        existing_products_by_name[p_name] = record
        finally:
            conn.close()

        def resolve_leaf_category_id(path_segments: list):
            if not path_segments:
                return None
            curr_id = 2  # Root Default Category
            segs = path_segments[1:] if path_segments[0].strip().lower() == 'default category' else path_segments
            for s in segs:
                norm_s = s.strip().lower()
                key = (curr_id, norm_s)
                if key in cat_tree:
                    curr_id = cat_tree[key]
                else:
                    return None
            return curr_id

        # Step 3: Ensure brands exist and build brand_map
        stream = io.StringIO(text)
        reader = csv.DictReader(stream)
        rows = list(reader)
        if not rows:
            return {'success': False, 'error': 'CSV is empty.', 'imported': 0}

        # Step 3.5: Inspect CSV headers vs attributes & product columns
        csv_headers = [str(h).strip() for h in (reader.fieldnames or []) if h and str(h).strip()]
        matched_headers, missing_attributes, extra_headers = cls.validate_csv_headers(
            csv_headers, attr_map=attr_map, product_columns=product_columns
        )

        distinct_brands = set()
        for r in rows:
            b_val = (r.get('brand') or r.get('brand_name') or r.get('manufacturer') or '').strip()
            if b_val:
                distinct_brands.add(b_val)

        brand_map = {}
        for b_name in distinct_brands:
            b_slug = Brand.slugify(b_name)
            existing_b = Brand.find_by_slug(b_slug)
            if existing_b:
                brand_map[b_name.lower()] = existing_b['id']
            else:
                new_b_id = Brand.create({
                    'name': b_name,
                    'slug': b_slug,
                    'status': 'active'
                }, user_id=user_id)
                brand_map[b_name.lower()] = new_b_id

        # Step 4: Import each product row dynamically
        imported = 0
        updated = 0
        errors = []

        for idx, row in enumerate(rows, start=2):
            try:
                sku = (row.get('sku') or row.get('item_code') or '').strip().upper()
                raw_name = (row.get('name') or row.get('product_name') or row.get('display_name') or row.get('title') or row.get('product_title') or '').strip()
                name = (raw_name or sku).strip()
                display_name = (row.get('display_name') or row.get('product_name') or row.get('name') or row.get('title') or row.get('pattern') or name).strip()
                item_code = (row.get('item_code') or sku).strip()

                if not sku:
                    errors.append(f"Row {idx}: Missing SKU, skipped.")
                    continue
                
                raw_price = row.get('price') or '0'
                try:
                    price = float(raw_price)
                except (ValueError, TypeError):
                    price = 0.0

                raw_cost = row.get('cost') or row.get('cost_price') or None
                try:
                    cost_price = float(raw_cost) if raw_cost else None
                except (ValueError, TypeError):
                    cost_price = None

                b_str = (row.get('brand') or row.get('brand_name') or row.get('manufacturer') or '').strip()
                brand_id = brand_map.get(b_str.lower())

                # Resolve category paths (accept the same column-name variants CategoryImporter does)
                cat_cell = (
                    row.get('categories') or row.get('category') or
                    row.get('category_path') or row.get('category_paths') or
                    row.get('_category') or ''
                )
                parsed_paths = parse_category_paths(cat_cell)
                assigned_category_ids = []
                for p in parsed_paths:
                    leaf_id = resolve_leaf_category_id(p)
                    if leaf_id and leaf_id not in assigned_category_ids:
                        assigned_category_ids.append(leaf_id)

                primary_category_id = assigned_category_ids[0] if assigned_category_ids else None

                # Resolve Attribute Set dynamically
                raw_set_hint = (
                    row.get('attribute_set_code') or 
                    row.get('attribute_set') or 
                    row.get('attribute_set_name') or 
                    row.get('attribute_set_id') or 
                    row.get('parts_category') or ''
                ).strip().lower()

                resolved_set_id = set_lookup.get(raw_set_hint)
                if not resolved_set_id and raw_set_hint.isdigit():
                    resolved_set_id = int(raw_set_hint)

                if not resolved_set_id:
                    # Infer set based on column indicators present in this row
                    cols_present = {k.strip().lower() for k, v in row.items() if v is not None and str(v).strip() != ''}
                    if {'volts', 'voltage', 'cca', 'battery_type', 'mah', 'terminal_layout'} & cols_present:
                        resolved_set_id = set_lookup.get('battery') or 3
                    elif {'bolt_pattern_pcd', 'wheel_type', 'offset', 'hub_bore', 'back_space_inches'} & cols_present:
                        resolved_set_id = set_lookup.get('wheels') or 7
                    elif {'bike_tyre_type'} & cols_present:
                        resolved_set_id = set_lookup.get('motorcycle tyres') or set_lookup.get('motorcycle_tyres') or 4
                    elif {'color_finish'} & cols_present and 'wheel_type' not in cols_present and 'offset' not in cols_present:
                        resolved_set_id = set_lookup.get('rim protectors') or set_lookup.get('rim_protectors') or 5
                    elif {'tyre_size', 'tire_size', 'width', 'height', 'rim', 'load_index', 'speed_rating', 'pattern', 'oem_tyres', 'runflat', 'tyre_type'} & cols_present:
                        resolved_set_id = set_lookup.get('tyres') or 1
                    else:
                        resolved_set_id = set_lookup.get('default') or 2

                # Standard core fields
                # Check 'product_online' first (Magento standard: 1=active, 2=inactive), then fallback to 'status'
                prod_online_raw = str(row.get('product_online') if row.get('product_online') is not None else '').strip()
                if prod_online_raw:
                    status = 'inactive' if prod_online_raw.lower() in ('2', '0', 'inactive', 'disabled', 'false', 'no') else 'active'
                else:
                    status_raw = str(row.get('status') or '1').strip().lower()
                    status = 'inactive' if status_raw in ('2', '0', 'inactive', 'disabled', 'false', 'no') else 'active'
                visibility = (row.get('visibility') or 'Catalog, Search').strip()
                base_image = (row.get('base_image') or row.get('image_path') or row.get('image') or '').strip()
                small_image = (row.get('small_image') or base_image).strip()
                url_key = (row.get('url_key') or slugify(name)).strip()

                raw_weight = row.get('weight')
                try:
                    weight = float(raw_weight) if raw_weight else None
                except (ValueError, TypeError):
                    weight = None

                raw_qty = row.get('qty') or row.get('stock_qty') or '10'
                try:
                    stock_qty = int(float(raw_qty))
                except (ValueError, TypeError):
                    stock_qty = 10
                stock_status = (row.get('stock_status') or ('in_stock' if stock_qty > 0 else 'out_of_stock')).strip()

                # Build dynamic attributes dictionary from ALL columns present in CSV
                dynamic_attrs = {}
                for raw_k, raw_v in row.items():
                    if raw_k is None or raw_v is None:
                        continue
                    clean_k = str(raw_k).strip()
                    if not clean_k:
                        continue

                    val_str = str(raw_v).strip()

                    # Ignore attribute set indicators from dynamic attributes as attribute_set_id is a core column
                    k_lower = clean_k.lower()
                    if k_lower in ('attribute_set_id', 'attribute_set', 'attribute_set_code', 'attribute_set_name'):
                        continue

                    # Keep raw column value
                    dynamic_attrs[clean_k] = val_str

                    # Match against database attributes table
                    k_lower = clean_k.lower()
                    attr_def = attr_map.get(k_lower)
                    if not attr_def and k_lower in ATTRIBUTE_ALIAS_MAP:
                        target_code = ATTRIBUTE_ALIAS_MAP[k_lower]
                        attr_def = attr_map.get(target_code)

                    if attr_def:
                        code = attr_def['code']
                        a_type = attr_def['type']
                        if a_type == 'boolean':
                            normalized_val = 'Yes' if val_str.lower() in ('1', 'true', 'yes', 'y') else 'No'
                        else:
                            normalized_val = val_str
                        dynamic_attrs[code] = normalized_val

                # Smart additive helpers for domain-specific attributes (only if relevant fields present)
                width = dynamic_attrs.get('width') or ''
                height = dynamic_attrs.get('height') or dynamic_attrs.get('aspect_ratio') or ''
                rim = dynamic_attrs.get('rim') or dynamic_attrs.get('rim_size') or ''
                if width and height and rim and not dynamic_attrs.get('tire_size'):
                    auto_size = f"{width}/{height} R{rim}"
                    dynamic_attrs['tire_size'] = auto_size
                    dynamic_attrs['tire_size_label'] = auto_size

                raw_load = dynamic_attrs.get('load_index') or dynamic_attrs.get('load_speed_index') or ''
                extracted_speed = dynamic_attrs.get('speed_rating') or dynamic_attrs.get('tire_speed_rating') or ''
                extracted_load = raw_load
                if raw_load:
                    m = re.match(r'^(\d{2,3})\s*([A-Za-z]+)$', raw_load)
                    if m:
                        extracted_load = m.group(1)
                        if not extracted_speed:
                            extracted_speed = m.group(2).upper()
                    dynamic_attrs['load_speed_index'] = raw_load
                    dynamic_attrs['load_index'] = extracted_load
                    dynamic_attrs['tire_load_index'] = extracted_load
                    if extracted_speed:
                        dynamic_attrs['tire_speed_rating'] = extracted_speed

                # Country / Origin normalization
                country_val = dynamic_attrs.get('country') or dynamic_attrs.get('country_of_origin') or dynamic_attrs.get('origin')
                if country_val:
                    dynamic_attrs['origin'] = country_val
                    dynamic_attrs['country'] = country_val
                    dynamic_attrs['country_of_origin'] = country_val

                # Tax class normalization
                tax_val = dynamic_attrs.get('tax_class') or dynamic_attrs.get('tax_class_name') or 'Taxable Goods'
                dynamic_attrs['tax_class'] = tax_val
                dynamic_attrs['tax_class_name'] = tax_val

                # Promotion normalization
                promo_val = dynamic_attrs.get('promotion') or dynamic_attrs.get('offers') or 'None'
                dynamic_attrs['promotion'] = promo_val

                # Boolean flags
                runflat_raw = str(dynamic_attrs.get('runflat') or '').strip().lower()
                run_flat = 1 if runflat_raw in ('yes', '1', 'true') else 0
                ev_raw = str(dynamic_attrs.get('ev_tyre') or '').strip().lower()
                ev_rated = 1 if ev_raw in ('yes', '1', 'true') else 0
                tabby_raw = str(dynamic_attrs.get('tabby_payment') or '').strip().lower()
                pay_later_eligible = 1 if tabby_raw in ('yes', '1', 'true') else 0

                parts_cat = (dynamic_attrs.get('parts_category') or row.get('parts_category') or row.get('attribute_set_code') or 'Tyres').strip()
                raw_tc = dynamic_attrs.get('tyres_category') or row.get('tyres_category')
                tyres_cat = None
                if raw_tc and str(raw_tc).strip():
                    s_tc = str(raw_tc).strip()
                    tc_l = s_tc.lower()
                    if tc_l == 'budget':
                        tyres_cat = 'Budget'
                    elif tc_l == 'quality':
                        tyres_cat = 'Quality'
                    elif tc_l == 'premium':
                        tyres_cat = 'Premium'
                    else:
                        tyres_cat = s_tc
                dynamic_attrs['tyres_category'] = tyres_cat or ''
                year_val = dynamic_attrs.get('year')
                price_included = (dynamic_attrs.get('price_included_text') or dynamic_attrs.get('price_included') or 'Fitted Price').strip()

                # Build universal product payload
                product_payload = {
                    'sku': sku,
                    'website_id': 1,
                    'website_ids': [1],
                    'item_code': item_code,
                    'parts_category': parts_cat,
                    'tyres_category': tyres_cat,
                    'year': year_val,
                    'price_included': price_included,
                    'small_image': small_image,
                    'small_image_alt': display_name,
                    'display_name': display_name,
                    'name_en': name,
                    'slug': url_key,
                    'attribute_set_id': resolved_set_id,
                    'brand_id': brand_id,
                    'category_id': primary_category_id,
                    'category_ids': assigned_category_ids,
                    'price': price,
                    'cost_price': cost_price,
                    'stock_qty': stock_qty,
                    'stock_status': stock_status,
                    'weight': weight,
                    'run_flat': run_flat,
                    'ev_rated': ev_rated,
                    'pay_later_eligible': pay_later_eligible,
                    'image_path': base_image,
                    'status': status,
                    'visibility': visibility,
                    'short_desc_en': (row.get('short_description') or '').strip(),
                    'description_en': (row.get('description') or '').strip(),
                    'meta_title_en': (row.get('meta_title') or '').strip(),
                    'meta_desc_en': (row.get('meta_description') or '').strip(),
                    'dynamic_attributes': dynamic_attrs,
                    'attributes_json': dynamic_attrs
                }

                # Direct columns for tyre attributes if present
                if dynamic_attrs.get('tire_size'):
                    product_payload['tire_size_label'] = dynamic_attrs['tire_size']
                if extracted_load:
                    product_payload['tire_load_index'] = extracted_load
                if extracted_speed:
                    product_payload['tire_speed_rating'] = extracted_speed
                if dynamic_attrs.get('pattern'):
                    product_payload['tire_pattern'] = dynamic_attrs['pattern']
                if dynamic_attrs.get('tyre_type'):
                    product_payload['tire_type'] = dynamic_attrs['tyre_type']
                if country_val:
                    product_payload['country_of_origin'] = country_val

                # Match existing product by SKU first, then fall back to an exact
                # display_name match (e.g. the same tyre re-exported under a new SKU)
                # so re-imports update the existing row instead of duplicating it.
                # Both lookups go through the in-memory caches built above so a 17k-row
                # import doesn't do two DB round-trips per row.
                existing_p = existing_products_by_sku.get(sku)
                if not existing_p:
                    existing_p = Product.find_by_sku(sku)
                if not existing_p and display_name:
                    existing_p = existing_products_by_name.get(display_name.strip().lower())
                if not existing_p and display_name:
                    existing_p = Product.find_by_name(display_name)

                # If updating an existing product and the CSV row did not provide an explicit url_key/slug,
                # preserve the existing product's slug so products sharing the same name keep their unique URLs.
                if existing_p and not (row.get('url_key') or row.get('slug')):
                    product_payload['slug'] = existing_p.get('slug') or product_payload['slug']

                # Insert or Update product
                if existing_p:
                    Product.update(existing_p['id'], product_payload, user_id=user_id)
                    updated += 1
                    # Keep in-memory caches synchronized for subsequent rows in the same CSV
                    cached_record = {
                        'id': existing_p['id'],
                        'sku': sku,
                        'display_name': display_name,
                        'slug': product_payload['slug']
                    }
                    existing_products_by_sku[sku] = cached_record
                    if display_name:
                        existing_products_by_name[display_name.strip().lower()] = cached_record
                else:
                    new_p_id = Product.create(product_payload, user_id=user_id)
                    imported += 1
                    # Add to in-memory caches
                    cached_record = {
                        'id': new_p_id,
                        'sku': sku,
                        'display_name': display_name,
                        'slug': product_payload['slug']
                    }
                    existing_products_by_sku[sku] = cached_record
                    if display_name:
                        existing_products_by_name[display_name.strip().lower()] = cached_record

            except Exception as ex:
                errors.append(f"Row {idx} ({row.get('sku')}): {str(ex)}")

            if progress_callback:
                try:
                    progress_callback(idx - 1, len(rows))
                except Exception:
                    pass

        warning_msg = None
        if extra_headers:
            warning_msg = f"Found {len(extra_headers)} column(s) in the CSV that do not match any existing product attribute: {', '.join(extra_headers)}. Please create these attributes in Attribute Manager if needed. All matched attributes were imported successfully."

        return {
            'success': True,
            'total_rows': len(rows),
            'imported': imported,
            'updated': updated,
            'matched_attributes': matched_headers,
            'extra_attributes': extra_headers,
            'missing_attributes': missing_attributes,
            'category_result': cat_result,
            'warning': warning_msg,
            'errors': errors,
            'message': f"Successfully processed {len(rows)} products ({imported} imported, {updated} updated)." + (f" Note: {len(extra_headers)} unrecognized column(s) detected ({', '.join(extra_headers[:3])}{'...' if len(extra_headers) > 3 else ''})." if extra_headers else "")
        }
