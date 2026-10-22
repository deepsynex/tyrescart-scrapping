"""
app/services/product_importer.py - Dynamic Multi-Type Product & Category CSV Importer Service

Handles importing products of any type (Tyres, Batteries, Wheels, Accessories, etc.):
- Automatically detects or maps attribute sets (Tyres, Battery, Wheels, Default, etc.).
- Dynamically matches CSV columns to database attribute definitions rather than static code.
- Automatically handles option resolution and auto-creation for select/multiselect attributes.
- Preserves all CSV columns in attributes_json and syncs to EAV product_attribute_values.
- Parses hierarchical category paths under root ID 2 (Default Category) via CategoryImporter.
- Auto-creates any missing brands.
- Partial update support: when updating existing products by SKU, ONLY the columns provided in the CSV
  are updated, completely preserving all untouched columns (names, images, brands, categories, descriptions, attributes).
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

SYSTEM_CORE_COLS = {
    'sku', 'item_code', 'name', 'product_name', 'title', 'product_title', 'display_name',
    'url_key', 'slug', 'price', 'sale_price', 'special_price', 'list_price', 'cost', 'cost_price',
    'qty', 'stock_qty', 'stock_status', 'manage_stock', 'min_order_qty', 'max_order_qty',
    'product_online', 'status', 'visibility',
    'base_image', 'image_path', 'image', 'small_image', 'image_alt', 'small_image_alt', 'gallery_json',
    'brand', 'brand_name', 'manufacturer',
    'categories', 'category', 'category_path', 'category_paths', '_category',
    'attribute_set_code', 'attribute_set', 'attribute_set_name', 'attribute_set_id',
    'short_description', 'short_desc', 'description', 'meta_title', 'meta_description', 'meta_desc',
    'product_websites', 'website_id', 'website_ids'
}


def _get_cell(row_dict: dict, *candidate_names):
    """
    Searches row_dict for any candidate column name (case-insensitive, trimmed).
    Returns (True, clean_value) if found and non-empty; else (False, None).
    """
    if not row_dict:
        return False, None
    for cand in candidate_names:
        c_low = cand.strip().lower()
        for k, v in row_dict.items():
            if k is not None and str(k).strip().lower() == c_low:
                if v is not None:
                    s = str(v).strip()
                    if s != '':
                        return True, s
    return False, None


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

        Supports partial updates: when a product already exists by SKU, only the columns
        present in the CSV are updated. All omitted columns (images, categories, brands,
        descriptions, untouched attributes) remain intact.
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

        stream = io.StringIO(text)
        reader = csv.DictReader(stream)
        rows = list(reader)
        if not rows:
            return {'success': False, 'error': 'CSV is empty.', 'imported': 0}

        csv_headers = [str(h).strip() for h in (reader.fieldnames or []) if h and str(h).strip()]
        csv_headers_lower = {h.lower() for h in csv_headers}

        # Step 1: Run CategoryImporter ONLY if category columns exist in the CSV
        has_category_col = any(c in csv_headers_lower for c in ('categories', 'category', 'category_path', 'category_paths', '_category'))
        if has_category_col:
            cat_result = CategoryImporter.import_csv(text, user_id=user_id)
        else:
            cat_result = {'success': True, 'message': 'No category columns in CSV, skipped category hierarchy import.'}

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
        matched_headers, missing_attributes, extra_headers = cls.validate_csv_headers(
            csv_headers, attr_map=attr_map, product_columns=product_columns
        )

        brand_map = {}
        has_brand_col = any(c in csv_headers_lower for c in ('brand', 'brand_name', 'manufacturer'))
        if has_brand_col:
            distinct_brands = set()
            for r in rows:
                b_val = (r.get('brand') or r.get('brand_name') or r.get('manufacturer') or '').strip()
                if b_val:
                    distinct_brands.add(b_val)

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
                has_sku, val_sku = _get_cell(row, 'sku', 'item_code')
                sku = val_sku.upper() if has_sku else ''
                if not sku:
                    errors.append(f"Row {idx}: Missing SKU, skipped.")
                    continue

                # Check if product exists in DB
                existing_p = existing_products_by_sku.get(sku)
                if not existing_p:
                    existing_p = Product.find_by_sku(sku)
                if not existing_p:
                    has_n_lookup, val_n_lookup = _get_cell(row, 'name', 'product_name', 'display_name', 'title')
                    if has_n_lookup:
                        existing_p = existing_products_by_name.get(val_n_lookup.lower())
                        if not existing_p:
                            existing_p = Product.find_by_name(val_n_lookup)

                if existing_p:
                    # =========================================================================
                    # PARTIAL UPDATE MODE: ONLY UPDATE FIELDS EXPLICITLY PROVIDED IN THIS ROW
                    # =========================================================================
                    update_payload = {}

                    # Name and Display Name
                    has_name, val_name = _get_cell(row, 'name', 'product_name', 'title', 'product_title')
                    has_dname, val_dname = _get_cell(row, 'display_name')
                    if has_name:
                        update_payload['name_en'] = val_name
                        update_payload['name'] = val_name
                    if has_dname:
                        update_payload['display_name'] = val_dname
                    elif has_name:
                        update_payload['display_name'] = val_name

                    # Item code
                    has_item, val_item = _get_cell(row, 'item_code')
                    if has_item:
                        update_payload['item_code'] = val_item

                    # Slug / URL key
                    has_slug, val_slug = _get_cell(row, 'url_key', 'slug')
                    if has_slug:
                        update_payload['slug'] = slugify(val_slug)

                    # Prices
                    has_price, val_price = _get_cell(row, 'price')
                    if has_price:
                        try:
                            update_payload['price'] = float(val_price.replace('$', '').replace('AED', '').replace(',', '').strip())
                        except (ValueError, TypeError):
                            pass

                    has_sale, val_sale = _get_cell(row, 'sale_price', 'special_price')
                    if has_sale:
                        try:
                            update_payload['sale_price'] = float(val_sale.replace('$', '').replace('AED', '').replace(',', '').strip())
                        except (ValueError, TypeError):
                            pass

                    has_list, val_list = _get_cell(row, 'list_price')
                    if has_list:
                        try:
                            update_payload['list_price'] = float(val_list.replace('$', '').replace('AED', '').replace(',', '').strip())
                        except (ValueError, TypeError):
                            pass

                    has_cost, val_cost = _get_cell(row, 'cost', 'cost_price')
                    if has_cost:
                        try:
                            update_payload['cost_price'] = float(val_cost.replace('$', '').replace('AED', '').replace(',', '').strip())
                        except (ValueError, TypeError):
                            pass

                    # Stock Qty & Stock Status
                    has_qty, val_qty = _get_cell(row, 'qty', 'stock_qty')
                    has_sstatus, val_sstatus = _get_cell(row, 'stock_status')
                    if has_qty:
                        try:
                            sq = int(float(val_qty))
                            update_payload['stock_qty'] = sq
                            if not has_sstatus:
                                update_payload['stock_status'] = 'in_stock' if sq > 0 else 'out_of_stock'
                        except (ValueError, TypeError):
                            pass
                    if has_sstatus:
                        update_payload['stock_status'] = val_sstatus.lower()

                    has_ms, val_ms = _get_cell(row, 'manage_stock')
                    if has_ms:
                        update_payload['manage_stock'] = 1 if val_ms.lower() in ('1', 'true', 'yes') else 0

                    has_min, val_min = _get_cell(row, 'min_order_qty')
                    if has_min:
                        try:
                            update_payload['min_order_qty'] = int(val_min)
                        except (ValueError, TypeError):
                            pass

                    has_max, val_max = _get_cell(row, 'max_order_qty')
                    if has_max:
                        try:
                            update_payload['max_order_qty'] = int(val_max)
                        except (ValueError, TypeError):
                            pass

                    # Status & Visibility
                    has_online, val_online = _get_cell(row, 'product_online')
                    has_st, val_st = _get_cell(row, 'status')
                    if has_online:
                        update_payload['status'] = 'inactive' if val_online.lower() in ('2', '0', 'inactive', 'disabled', 'false', 'no') else 'active'
                    elif has_st:
                        update_payload['status'] = 'inactive' if val_st.lower() in ('2', '0', 'inactive', 'disabled', 'false', 'no') else 'active'

                    has_vis, val_vis = _get_cell(row, 'visibility')
                    if has_vis:
                        update_payload['visibility'] = val_vis

                    # Images
                    has_img, val_img = _get_cell(row, 'base_image', 'image_path', 'image')
                    has_simg, val_simg = _get_cell(row, 'small_image')
                    has_ialt, val_ialt = _get_cell(row, 'image_alt')
                    has_sialt, val_sialt = _get_cell(row, 'small_image_alt')
                    has_gal, val_gal = _get_cell(row, 'gallery_json')

                    if has_img:
                        update_payload['image_path'] = val_img
                        if not has_simg:
                            update_payload['small_image'] = val_img
                    if has_simg:
                        update_payload['small_image'] = val_simg
                    if has_ialt:
                        update_payload['image_alt'] = val_ialt
                    if has_sialt:
                        update_payload['small_image_alt'] = val_sialt
                    if has_gal:
                        try:
                            update_payload['gallery_json'] = json.loads(val_gal) if val_gal.startswith('[') else [val_gal]
                        except Exception:
                            pass

                    # Brand
                    has_brand, val_brand = _get_cell(row, 'brand', 'brand_name', 'manufacturer')
                    if has_brand:
                        b_id = brand_map.get(val_brand.lower())
                        if b_id:
                            update_payload['brand_id'] = b_id

                    # Categories
                    has_cat, val_cat = _get_cell(row, 'categories', 'category', 'category_path', 'category_paths', '_category')
                    if has_cat:
                        parsed_paths = parse_category_paths(val_cat)
                        assigned_category_ids = []
                        for p in parsed_paths:
                            leaf_id = resolve_leaf_category_id(p)
                            if leaf_id and leaf_id not in assigned_category_ids:
                                assigned_category_ids.append(leaf_id)
                        if assigned_category_ids:
                            update_payload['category_id'] = assigned_category_ids[0]
                            update_payload['category_ids'] = assigned_category_ids

                    # Attribute Set
                    has_set, val_set = _get_cell(row, 'attribute_set_code', 'attribute_set', 'attribute_set_name', 'attribute_set_id')
                    if has_set:
                        raw_set = val_set.strip().lower()
                        s_id = set_lookup.get(raw_set) or (int(raw_set) if raw_set.isdigit() else None)
                        if s_id:
                            update_payload['attribute_set_id'] = s_id

                    # Descriptions & SEO
                    has_sdesc, val_sdesc = _get_cell(row, 'short_description', 'short_desc')
                    if has_sdesc:
                        update_payload['short_desc_en'] = val_sdesc
                    has_desc, val_desc = _get_cell(row, 'description')
                    if has_desc:
                        update_payload['description_en'] = val_desc
                    has_mtitle, val_mtitle = _get_cell(row, 'meta_title')
                    if has_mtitle:
                        update_payload['meta_title_en'] = val_mtitle
                    has_mdesc, val_mdesc = _get_cell(row, 'meta_description', 'meta_desc')
                    if has_mdesc:
                        update_payload['meta_desc_en'] = val_mdesc

                    # Weight
                    has_wt, val_wt = _get_cell(row, 'weight')
                    if has_wt:
                        try:
                            update_payload['weight'] = float(val_wt)
                        except (ValueError, TypeError):
                            pass

                    # Parts Category & Tyres Category
                    has_pc, val_pc = _get_cell(row, 'parts_category')
                    if has_pc:
                        update_payload['parts_category'] = val_pc

                    has_tc, val_tc = _get_cell(row, 'tyres_category')
                    if has_tc:
                        tc_l = val_tc.lower()
                        update_payload['tyres_category'] = 'Budget' if tc_l == 'budget' else ('Quality' if tc_l == 'quality' else ('Premium' if tc_l == 'premium' else val_tc))

                    # Year
                    has_yr, val_yr = _get_cell(row, 'year')
                    if has_yr:
                        try:
                            y_int = int(val_yr)
                            if 1901 <= y_int <= 2155:
                                update_payload['year'] = y_int
                        except (ValueError, TypeError):
                            pass

                    # Price Included
                    has_pi, val_pi = _get_cell(row, 'price_included', 'price_included_text')
                    if has_pi:
                        update_payload['price_included'] = val_pi

                    # Warranty
                    has_wm, val_wm = _get_cell(row, 'warranty', 'warranty_months', 'warranty_period')
                    if has_wm:
                        update_payload['warranty_months'] = val_wm

                    # Tyre Specifications
                    has_ts, val_ts = _get_cell(row, 'tire_size', 'tyre_size', 'size')
                    if has_ts:
                        update_payload['tire_size_label'] = val_ts

                    has_sr, val_sr = _get_cell(row, 'speed_rating', 'tire_speed_rating')
                    if has_sr:
                        update_payload['tire_speed_rating'] = val_sr.upper()

                    has_li, val_li = _get_cell(row, 'load_index', 'tire_load_index', 'load_speed_index')
                    if has_li:
                        m = re.match(r'^(\d{2,3})\s*([A-Za-z]+)$', val_li)
                        if m:
                            update_payload['tire_load_index'] = m.group(1)
                            if 'tire_speed_rating' not in update_payload:
                                update_payload['tire_speed_rating'] = m.group(2).upper()
                        else:
                            update_payload['tire_load_index'] = val_li

                    has_tp, val_tp = _get_cell(row, 'tire_pattern', 'pattern')
                    if has_tp:
                        update_payload['tire_pattern'] = val_tp

                    has_tt, val_tt = _get_cell(row, 'tire_type', 'tyre_type')
                    if has_tt:
                        update_payload['tire_type'] = val_tt

                    has_vt, val_vt = _get_cell(row, 'vehicle_type')
                    if has_vt:
                        update_payload['vehicle_type'] = val_vt

                    has_co, val_co = _get_cell(row, 'country_of_origin', 'country', 'origin')
                    if has_co:
                        update_payload['country_of_origin'] = val_co

                    has_rf, val_rf = _get_cell(row, 'run_flat', 'runflat')
                    if has_rf:
                        update_payload['run_flat'] = 1 if val_rf.lower() in ('1', 'true', 'yes') else 0

                    has_ev, val_ev = _get_cell(row, 'ev_rated', 'ev_tyre')
                    if has_ev:
                        update_payload['ev_rated'] = 1 if val_ev.lower() in ('1', 'true', 'yes') else 0

                    has_pl, val_pl = _get_cell(row, 'pay_later_eligible', 'tabby_payment')
                    if has_pl:
                        update_payload['pay_later_eligible'] = 1 if val_pl.lower() in ('1', 'true', 'yes') else 0

                    has_oem, val_oem = _get_cell(row, 'oem_brand', 'oem_tyres')
                    has_oap, val_oap = _get_cell(row, 'oem_approved')
                    if has_oem:
                        update_payload['oem_brand'] = val_oem
                        if not has_oap:
                            update_payload['oem_approved'] = 1 if val_oem else 0
                    if has_oap:
                        update_payload['oem_approved'] = 1 if val_oap.lower() in ('1', 'true', 'yes') else 0

                    # Dynamic Attributes
                    dyn_attrs_update = {}
                    for raw_k, raw_v in row.items():
                        if raw_k is None or raw_v is None:
                            continue
                        clean_k = str(raw_k).strip()
                        val_str = str(raw_v).strip()
                        if not clean_k or not val_str:
                            continue
                        k_lower = clean_k.lower()
                        if k_lower in SYSTEM_CORE_COLS:
                            continue

                        attr_def = attr_map.get(k_lower)
                        if not attr_def and k_lower in ATTRIBUTE_ALIAS_MAP:
                            target_code = ATTRIBUTE_ALIAS_MAP[k_lower]
                            attr_def = attr_map.get(target_code)

                        if attr_def:
                            code = attr_def['code']
                            a_type = attr_def['type']
                            normalized_val = ('Yes' if val_str.lower() in ('1', 'true', 'yes', 'y') else 'No') if a_type == 'boolean' else val_str
                            dyn_attrs_update[code] = normalized_val
                            dyn_attrs_update[clean_k] = val_str
                        elif k_lower in ('width', 'height', 'aspect_ratio', 'rim', 'rim_size', 'load_index', 'speed_rating', 'pattern', 'tyre_type', 'runflat', 'ev_tyre', 'country', 'origin', 'tax_class', 'promotion', 'parts_category', 'tyres_category', 'year', 'tabby_payment'):
                            dyn_attrs_update[clean_k] = val_str

                    # Smart additive helpers for domain-specific tyre size
                    if ('width' in dyn_attrs_update or 'height' in dyn_attrs_update or 'rim' in dyn_attrs_update) and 'tire_size_label' not in update_payload:
                        w = dyn_attrs_update.get('width')
                        h = dyn_attrs_update.get('height') or dyn_attrs_update.get('aspect_ratio')
                        r = dyn_attrs_update.get('rim') or dyn_attrs_update.get('rim_size')
                        if w and h and r:
                            sz = f"{w}/{h} R{r}"
                            update_payload['tire_size_label'] = sz
                            dyn_attrs_update['tire_size'] = sz

                    if dyn_attrs_update:
                        update_payload['dynamic_attributes'] = dyn_attrs_update
                        update_payload['attributes_json'] = dyn_attrs_update

                    if update_payload:
                        Product.update(existing_p['id'], update_payload, user_id=user_id)
                    updated += 1

                    # Keep in-memory caches synchronized
                    new_dname = update_payload.get('display_name') or existing_p.get('display_name')
                    new_slug = update_payload.get('slug') or existing_p.get('slug')
                    cached_record = {
                        'id': existing_p['id'],
                        'sku': sku,
                        'display_name': new_dname,
                        'slug': new_slug
                    }
                    existing_products_by_sku[sku] = cached_record
                    if new_dname:
                        existing_products_by_name[new_dname.strip().lower()] = cached_record

                else:
                    # =========================================================================
                    # FULL CREATION MODE: BRAND NEW PRODUCT INSERT
                    # =========================================================================
                    has_name, val_name = _get_cell(row, 'name', 'product_name', 'title', 'product_title')
                    has_dname, val_dname = _get_cell(row, 'display_name')
                    raw_name = val_name or val_dname or sku
                    name = raw_name.strip()
                    display_name = (val_dname or val_name or sku).strip()

                    has_item, val_item = _get_cell(row, 'item_code')
                    item_code = val_item or sku

                    has_price, val_price = _get_cell(row, 'price')
                    price = 0.0
                    if has_price:
                        try:
                            price = float(val_price.replace('$', '').replace('AED', '').replace(',', '').strip())
                        except Exception:
                            price = 0.0

                    has_cost, val_cost = _get_cell(row, 'cost', 'cost_price')
                    cost_price = None
                    if has_cost:
                        try:
                            cost_price = float(val_cost.replace('$', '').replace('AED', '').replace(',', '').strip())
                        except Exception:
                            cost_price = None

                    has_brand, val_brand = _get_cell(row, 'brand', 'brand_name', 'manufacturer')
                    brand_id = brand_map.get(val_brand.lower()) if has_brand else None

                    has_cat, val_cat = _get_cell(row, 'categories', 'category', 'category_path', 'category_paths', '_category')
                    assigned_category_ids = []
                    if has_cat:
                        parsed_paths = parse_category_paths(val_cat)
                        for p in parsed_paths:
                            leaf_id = resolve_leaf_category_id(p)
                            if leaf_id and leaf_id not in assigned_category_ids:
                                assigned_category_ids.append(leaf_id)
                    primary_category_id = assigned_category_ids[0] if assigned_category_ids else None

                    has_set, val_set = _get_cell(row, 'attribute_set_code', 'attribute_set', 'attribute_set_name', 'attribute_set_id', 'parts_category')
                    resolved_set_id = None
                    if has_set:
                        raw_set = val_set.strip().lower()
                        resolved_set_id = set_lookup.get(raw_set) or (int(raw_set) if raw_set.isdigit() else None)

                    if not resolved_set_id:
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

                    has_online, val_online = _get_cell(row, 'product_online')
                    has_st, val_st = _get_cell(row, 'status')
                    if has_online:
                        status = 'inactive' if val_online.lower() in ('2', '0', 'inactive', 'disabled', 'false', 'no') else 'active'
                    elif has_st:
                        status = 'inactive' if val_st.lower() in ('2', '0', 'inactive', 'disabled', 'false', 'no') else 'active'
                    else:
                        status = 'active'

                    has_vis, val_vis = _get_cell(row, 'visibility')
                    visibility = val_vis if has_vis else 'Catalog, Search'

                    has_img, val_img = _get_cell(row, 'base_image', 'image_path', 'image')
                    has_simg, val_simg = _get_cell(row, 'small_image')
                    base_image = val_img or ''
                    small_image = val_simg or base_image

                    has_slug, val_slug = _get_cell(row, 'url_key', 'slug')
                    url_key = slugify(val_slug) if has_slug else slugify(name)

                    has_wt, val_wt = _get_cell(row, 'weight')
                    weight = None
                    if has_wt:
                        try:
                            weight = float(val_wt)
                        except Exception:
                            weight = None

                    has_qty, val_qty = _get_cell(row, 'qty', 'stock_qty')
                    stock_qty = 10
                    if has_qty:
                        try:
                            stock_qty = int(float(val_qty))
                        except Exception:
                            stock_qty = 10
                    has_sstatus, val_sstatus = _get_cell(row, 'stock_status')
                    stock_status = val_sstatus.lower() if has_sstatus else ('in_stock' if stock_qty > 0 else 'out_of_stock')

                    dynamic_attrs = {}
                    for raw_k, raw_v in row.items():
                        if raw_k is None or raw_v is None:
                            continue
                        clean_k = str(raw_k).strip()
                        val_str = str(raw_v).strip()
                        if not clean_k or not val_str:
                            continue
                        k_lower = clean_k.lower()
                        if k_lower in ('attribute_set_id', 'attribute_set', 'attribute_set_code', 'attribute_set_name'):
                            continue
                        dynamic_attrs[clean_k] = val_str
                        attr_def = attr_map.get(k_lower)
                        if not attr_def and k_lower in ATTRIBUTE_ALIAS_MAP:
                            target_code = ATTRIBUTE_ALIAS_MAP[k_lower]
                            attr_def = attr_map.get(target_code)
                        if attr_def:
                            code = attr_def['code']
                            a_type = attr_def['type']
                            normalized_val = ('Yes' if val_str.lower() in ('1', 'true', 'yes', 'y') else 'No') if a_type == 'boolean' else val_str
                            dynamic_attrs[code] = normalized_val

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

                    country_val = dynamic_attrs.get('country') or dynamic_attrs.get('country_of_origin') or dynamic_attrs.get('origin')
                    if country_val:
                        dynamic_attrs['origin'] = country_val
                        dynamic_attrs['country'] = country_val
                        dynamic_attrs['country_of_origin'] = country_val

                    tax_val = dynamic_attrs.get('tax_class') or dynamic_attrs.get('tax_class_name') or 'Taxable Goods'
                    dynamic_attrs['tax_class'] = tax_val
                    dynamic_attrs['tax_class_name'] = tax_val

                    promo_val = dynamic_attrs.get('promotion') or dynamic_attrs.get('offers') or 'None'
                    dynamic_attrs['promotion'] = promo_val

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
                        s_tc = str(raw_tc).strip().lower()
                        tyres_cat = 'Budget' if s_tc == 'budget' else ('Quality' if s_tc == 'quality' else ('Premium' if s_tc == 'premium' else str(raw_tc).strip()))
                    dynamic_attrs['tyres_category'] = tyres_cat or ''

                    year_val = dynamic_attrs.get('year')
                    price_included = (dynamic_attrs.get('price_included_text') or dynamic_attrs.get('price_included') or 'Fitted Price').strip()

                    create_payload = {
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

                    if dynamic_attrs.get('tire_size'):
                        create_payload['tire_size_label'] = dynamic_attrs['tire_size']
                    if extracted_load:
                        create_payload['tire_load_index'] = extracted_load
                    if extracted_speed:
                        create_payload['tire_speed_rating'] = extracted_speed
                    if dynamic_attrs.get('pattern'):
                        create_payload['tire_pattern'] = dynamic_attrs['pattern']
                    if dynamic_attrs.get('tyre_type'):
                        create_payload['tire_type'] = dynamic_attrs['tyre_type']
                    if country_val:
                        create_payload['country_of_origin'] = country_val

                    new_p_id = Product.create(create_payload, user_id=user_id)
                    imported += 1
                    cached_record = {
                        'id': new_p_id,
                        'sku': sku,
                        'display_name': display_name,
                        'slug': create_payload['slug']
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
