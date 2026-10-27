"""
app/services/product_sync.py - Pulls the Tyrescart (Magento) catalog over GraphQL,
compares it with the local `products` table, and applies selected changes.

Flow (driven by static/visionadmin/product_sync.js):
  1. fetch_page(n)      -> one page of remote products, option IDs already resolved to labels
  2. compare(items)     -> classifies each remote product as new / update / unchanged
  3. import_rows(rows)  -> re-fetches the chosen SKUs from GraphQL (the browser's copy is
                           never trusted for writes), re-diffs against the DB, then calls
                           Product.create / Product.update, which also write EAV + reindex ES.

Local storage conventions mirror the Magento-export CSV import that originally loaded the
catalog: `display_name` holds the full product name, `oem_brand` holds the OEM Tyres label,
and most tyre specs are also kept in `attributes_json` under their Magento attribute codes.
"""

import csv
import html
import io
import json
import logging
import math
import os
import re
import threading
import time

import requests

from db import get_connection
from i18n import parse_json_dict
from models.brand import Brand
from models.product import Product
from services.category_importer import CategoryImporter

try:
    from services.es_service import es_service
except Exception:
    es_service = None

logger = logging.getLogger(__name__)

GRAPHQL_URL = os.getenv('PRODUCT_SYNC_GRAPHQL_URL', 'https://www.tyrescart.ae/graphql')
GRAPHQL_TOKEN = os.getenv('PRODUCT_SYNC_GRAPHQL_TOKEN', '')
PAGE_SIZE = 1000
REQUEST_TIMEOUT = 120
OPTION_CACHE_TTL = 30 * 60
# Tyrescart's GraphQL price excludes UAE VAT; the local catalog stores ceil(price * 1.05).
PRICE_MULTIPLIER = float(os.getenv('PRODUCT_SYNC_PRICE_MULTIPLIER', '1.05'))

OPTION_ATTRS = [
    'status', 'visibility', 'brand', 'pattern', 'tyre_marking', 'parts_category', 'oem_tyres',
    'tyre_size', 'width', 'height', 'rim', 'country', 'ev', 'runflat', 'year', 'warranty_period',
    'tyre_type', 'tyres_category', 'price_included_text', 'tabby_payment',
]

ITEM_FIELDS = """
      status name display_name sku url_key attribute_set_id visibility
      brand item_code pattern tyre_marking parts_category oem_tyres
      tyre_size width height rim load_index country ev runflat
      year warranty_period tyre_type tyres_category
      price_per_item price_included_text tabby_payment stock_status
      price_range { minimum_price { regular_price { value currency } final_price { value currency } } }
      categories { id name url_path level }
      image { url }
      short_description { html }
      description { html }
      meta_title meta_keyword meta_description
"""

PRODUCTS_QUERY = """query Products($filter: ProductAttributeFilterInput, $page: Int!, $size: Int!) {
  products(filter: $filter, pageSize: $size, currentPage: $page) {
    total_count
    page_info { current_page page_size total_pages }
    items { %s }
  }
}""" % ITEM_FIELDS

LABELS_QUERY = """{ customAttributeMetadataV2(attributes: [%s]) { items { code options { label value } } } }""" % ", ".join(
    '{attribute_code: "%s", entity_type: "catalog_product"}' % code for code in OPTION_ATTRS
)

# (key, label shown in the review modal). Order = display order.
COMPARE_FIELDS = [
    ('name', 'Product Name'),
    ('status', 'Enable Product'),
    ('price', 'Price'),
    ('stock_status', 'Stock Status'),
    ('item_code', 'Item Code'),
    ('brand', 'Brand'),
    ('pattern', 'Pattern'),
    ('tyre_size', 'Tyre Size'),
    ('width', 'Width'),
    ('height', 'Height'),
    ('rim', 'Rim'),
    ('load_index', 'Load/Speed Index'),
    ('tyre_marking', 'Tyre Marking'),
    ('oem_tyres', 'OEM Tyres'),
    ('parts_category', 'Parts Category'),
    ('tyres_category', 'Tyres Category'),
    ('tyre_type', 'Tyre Type'),
    ('country', 'Origin'),
    ('ev', 'EV Tyre'),
    ('runflat', 'RunFlat'),
    ('year', 'Year'),
    ('warranty_period', 'Warranty Period'),
    ('price_per_item', 'Price Per Item'),
    ('price_included_text', 'Price Included Text'),
    ('tabby_payment', 'Tabby Payment'),
    ('visibility', 'Visibility'),
    ('short_description', 'Short Description'),
    ('description', 'Description'),
    ('meta_title', 'Meta Title'),
    ('meta_keyword', 'Meta Keywords'),
    ('meta_description', 'Meta Description'),
]
COMPARE_KEYS = [k for k, _ in COMPARE_FIELDS]
NUMERIC_FIELDS = {'price', 'price_per_item'}
BOOL_FIELDS = {'ev', 'runflat', 'tabby_payment'}
TEXT_BLOCK_FIELDS = {'short_description', 'description', 'meta_title', 'meta_keyword', 'meta_description'}

_option_cache = {'at': 0.0, 'maps': None}
_option_lock = threading.Lock()


class SyncError(Exception):
    pass


# ---------------------------------------------------------------------------
# GraphQL
# ---------------------------------------------------------------------------

RETRY_DELAYS = (2, 5, 10)


def _post(query, variables=None):
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if GRAPHQL_TOKEN:
        headers['Authorization'] = f'Bearer {GRAPHQL_TOKEN}'
    # Tyrescart intermittently resets connections or returns 5xx under load; retry those.
    resp = None
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            resp = requests.post(GRAPHQL_URL, json={'query': query, 'variables': variables or {}},
                                 headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code < 500:
                break
            reason = f'HTTP {resp.status_code}'
        except requests.RequestException as e:
            reason = type(e).__name__
            resp = None
        if attempt == len(RETRY_DELAYS):
            raise SyncError(f'Tyrescart did not respond after {attempt + 1} attempts ({reason}). Try again in a few minutes.')
        logger.warning('Tyrescart GraphQL %s, retrying in %ss', reason, RETRY_DELAYS[attempt])
        time.sleep(RETRY_DELAYS[attempt])
    if resp.status_code != 200:
        raise SyncError(f'Tyrescart GraphQL returned HTTP {resp.status_code}.')
    try:
        payload = resp.json()
    except ValueError as e:
        raise SyncError('Tyrescart GraphQL returned a non-JSON response.') from e
    if payload.get('errors'):
        raise SyncError('Tyrescart GraphQL error: ' + '; '.join(
            str(err.get('message', err)) for err in payload['errors'][:3]))
    return payload.get('data') or {}


def fetch_option_maps(force=False):
    """attribute code -> {option_id: label}. Cached so pages 2..N don't re-request it."""
    with _option_lock:
        fresh = _option_cache['maps'] is not None and time.time() - _option_cache['at'] < OPTION_CACHE_TTL
        if fresh and not force:
            return _option_cache['maps']
        data = _post(LABELS_QUERY)
        maps = {}
        for item in (data.get('customAttributeMetadataV2') or {}).get('items') or []:
            maps[item['code']] = {str(o.get('value')): (o.get('label') or '').strip()
                                  for o in (item.get('options') or [])}
        _option_cache.update(at=time.time(), maps=maps)
        return maps


def fetch_page(page, size=PAGE_SIZE):
    maps = fetch_option_maps(force=(page == 1))
    data = _post(PRODUCTS_QUERY, {'filter': {}, 'page': int(page), 'size': int(size)})
    products = data.get('products') or {}
    return {
        'total_count': products.get('total_count') or 0,
        'page_info': products.get('page_info') or {},
        'items': [normalize_item(i, maps) for i in (products.get('items') or []) if i and i.get('sku')],
    }


def fetch_by_skus(skus):
    """Fresh remote records for specific SKUs (used at import time)."""
    maps = fetch_option_maps()
    out = {}
    for i in range(0, len(skus), 100):
        batch = skus[i:i + 100]
        data = _post(PRODUCTS_QUERY, {'filter': {'sku': {'in': batch}}, 'page': 1, 'size': len(batch)})
        for item in (data.get('products') or {}).get('items') or []:
            rec = normalize_item(item, maps)
            out[rec['sku']] = rec
    return out


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _label(maps, code, raw):
    if raw is None or raw == '':
        return ''
    opts = maps.get(code) or {}
    parts = [p.strip() for p in str(raw).split(',') if p.strip()]
    labels = [(opts.get(p, p) or '').strip() for p in parts]
    return ','.join(lbl for lbl in labels if lbl)


def _strip_page_builder(raw):
    s = (raw or '').strip()
    m = re.match(r'^<div[^>]*data-content-type="html"[^>]*>(.*)</div>$', s, re.DOTALL)
    if m:
        s = m.group(1).strip()
        if '&lt;' in s:
            s = html.unescape(s)
    return s


def _num(v):
    if v is None or v == '':
        return None
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _local_price(remote_value):
    if remote_value is None:
        return None
    return float(math.ceil(round(remote_value * PRICE_MULTIPLIER, 6)))


def _year(v):
    try:
        y = int(str(v).strip())
        return y if 1901 <= y <= 2155 else None
    except (TypeError, ValueError):
        return None


def normalize_item(item, maps):
    lbl = lambda code: _label(maps, code, item.get(code))
    minimum = ((item.get('price_range') or {}).get('minimum_price') or {})
    final = minimum.get('final_price') or {}
    regular = minimum.get('regular_price') or {}
    stock = (item.get('stock_status') or '').upper()

    return {
        'sku': str(item.get('sku') or '').strip().upper(),
        'name': (item.get('name') or '').strip(),
        'display_name': (item.get('display_name') or '').strip(),
        'url_key': (item.get('url_key') or '').strip(),
        'status': 'inactive' if lbl('status').lower() == 'disabled' else 'active',
        'visibility': Product._safe_visibility(lbl('visibility')),
        'attribute_set_id': item.get('attribute_set_id'),
        'brand': lbl('brand'),
        'item_code': (item.get('item_code') or '').strip(),
        'pattern': lbl('pattern'),
        'tyre_marking': lbl('tyre_marking'),
        'parts_category': lbl('parts_category'),
        'oem_tyres': lbl('oem_tyres'),
        'tyre_size': lbl('tyre_size'),
        'width': lbl('width'),
        'height': lbl('height'),
        'rim': lbl('rim'),
        'load_index': (item.get('load_index') or '').strip(),
        'country': lbl('country'),
        'ev': bool(lbl('ev')),
        'runflat': bool(lbl('runflat')),
        'year': _year(lbl('year')),
        'warranty_period': lbl('warranty_period'),
        'tyre_type': lbl('tyre_type'),
        'tyres_category': lbl('tyres_category'),
        'price': _local_price(_num(final.get('value'))),
        'source_price': _num(final.get('value')),
        'regular_price': _num(regular.get('value')),
        'currency': final.get('currency') or 'AED',
        'price_per_item': _num(item.get('price_per_item')),
        'price_included_text': lbl('price_included_text'),
        'tabby_payment': lbl('tabby_payment').lower() == 'yes',
        'stock_status': 'in_stock' if stock == 'IN_STOCK' else 'out_of_stock',
        'image_url': ((item.get('image') or {}).get('url') or '').strip(),
        'categories': [
            {'name': c.get('name') or '', 'url_path': c.get('url_path') or '', 'level': c.get('level')}
            for c in (item.get('categories') or []) if c
        ],
        'short_description': _strip_page_builder((item.get('short_description') or {}).get('html')),
        'description': _strip_page_builder((item.get('description') or {}).get('html')),
        'meta_title': (item.get('meta_title') or '').strip(),
        'meta_keyword': (item.get('meta_keyword') or '').strip(),
        'meta_description': (item.get('meta_description') or '').strip(),
    }


def _ml(val):
    """English text of a multilingual JSON column."""
    if val is None:
        return ''
    d = parse_json_dict(val) if not isinstance(val, dict) else val
    if isinstance(d, dict):
        return str(d.get('en') or next(iter(d.values()), '') or '').strip()
    return str(val).strip()


def _local_record(row):
    aj = parse_json_dict(row.get('attributes_json')) if row.get('attributes_json') else {}
    if not isinstance(aj, dict):
        aj = {}
    a = lambda k: str(aj.get(k) or '').strip()

    load = a('load_speed_index') or a('load_index')
    if not load:
        load = f"{row.get('tire_load_index') or ''}{row.get('tire_speed_rating') or ''}".strip()

    item_code = (row.get('item_code') or '').strip()
    if item_code.upper() == (row.get('sku') or '').strip().upper():
        item_code = ''  # the CSV importer falls back to the SKU when Magento has no item code

    return {
        'name': (row.get('display_name') or '').strip(),
        'status': row.get('status') or '',
        'price': _num(row.get('price')),
        'stock_status': row.get('stock_status') or '',
        'item_code': item_code,
        'brand': (row.get('brand_name') or '').strip(),
        'pattern': (row.get('tire_pattern') or '').strip(),
        'tyre_size': (row.get('tire_size_label') or '').strip(),
        'width': a('width'),
        'height': a('height'),
        'rim': a('rim'),
        'load_index': load,
        'tyre_marking': a('tyre_marking'),
        'oem_tyres': (row.get('oem_brand') or '').strip() or a('oem_tyres'),
        'parts_category': (row.get('parts_category') or '').strip(),
        'tyres_category': (row.get('tyres_category') or '').strip(),
        'tyre_type': a('tyre_type'),
        'country': (row.get('country_of_origin') or '').strip(),
        'ev': bool(row.get('ev_rated')),
        'runflat': bool(row.get('run_flat')),
        'year': _year(row.get('year')),
        'warranty_period': a('warranty_period'),
        'price_per_item': _num(aj.get('price_per_item')),
        'price_included_text': _ml(row.get('price_included')),
        'tabby_payment': bool(row.get('pay_later_eligible')),
        'visibility': row.get('visibility') or '',
        'short_description': _ml(row.get('short_desc')),
        'description': _ml(row.get('description')),
        'meta_title': _ml(row.get('meta_title')),
        'meta_keyword': a('meta_keywords') or a('meta_keyword'),
        'meta_description': _ml(row.get('meta_desc')),
    }


def _norm_for_compare(key, val):
    if key in NUMERIC_FIELDS:
        return _num(val)
    if key in BOOL_FIELDS:
        return bool(val)
    if key == 'year':
        return _year(val)
    s = '' if val is None else str(val)
    if key in TEXT_BLOCK_FIELDS:
        s = html.unescape(re.sub(r'<[^>]+>', ' ', s))
        return re.sub(r'\s+', ' ', s).strip()
    if key == 'oem_tyres':
        return ','.join(p.strip() for p in s.split(',') if p.strip())
    return s.strip()


def diff(local, remote):
    changes = {}
    for key in COMPARE_KEYS:
        lv, rv = local.get(key), remote.get(key)
        if _norm_for_compare(key, lv) != _norm_for_compare(key, rv):
            changes[key] = [lv, rv]
    return changes


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

_LOCAL_SQL = """
    SELECT p.*, b.name AS brand_name
    FROM products p
    LEFT JOIN brands b ON b.id = p.brand_id
    WHERE p.sku IN ({placeholders})
"""


def _load_local(skus):
    found = {}
    if not skus:
        return found
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for i in range(0, len(skus), 500):
                batch = skus[i:i + 500]
                cur.execute(_LOCAL_SQL.format(placeholders=', '.join(['%s'] * len(batch))), batch)
                for row in cur.fetchall():
                    key = (row.get('sku') or '').strip().upper()
                    # Prefer the live row if a trashed duplicate also exists.
                    if key not in found or found[key].get('deleted_at'):
                        found[key] = row
    finally:
        conn.close()
    return found


def compare(items):
    remote = {}
    for it in items or []:
        sku = str((it or {}).get('sku') or '').strip().upper()
        if sku:
            remote[sku] = it
    local = _load_local(list(remote))

    new, update = [], []
    unchanged = 0
    for sku, rec in remote.items():
        row = local.get(sku)
        if not row:
            new.append({'sku': sku})
            continue
        changes = diff(_local_record(row), rec)
        in_trash = bool(row.get('deleted_at'))
        if changes or in_trash:
            update.append({'sku': sku, 'id': row['id'], 'in_trash': in_trash, 'changes': changes})
        else:
            unchanged += 1
    return {'new': new, 'update': update, 'unchanged_count': unchanged}


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def _split_load_index(raw):
    m = re.match(r'^(\d{2,3})\s*([A-Za-z]{1,2})$', raw or '')
    if m:
        return m.group(1), m.group(2).upper()
    return (raw or None), None


def _yes_no(flag):
    return 'Yes' if flag else 'No'


class _BrandResolver:
    def __init__(self, user_id):
        self.user_id = user_id
        self.cache = {}

    def id_for(self, name):
        name = (name or '').strip()
        if not name:
            return None
        key = name.lower()
        if key not in self.cache:
            slug = Brand.slugify(name)
            existing = Brand.find_by_slug(slug)
            self.cache[key] = existing['id'] if existing else Brand.create(
                {'name': name, 'slug': slug, 'status': 'active'}, user_id=self.user_id)
        return self.cache[key]


def _attribute_set_id(parts_category):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, slug FROM attribute_sets WHERE deleted_at IS NULL")
            sets = cur.fetchall()
    finally:
        conn.close()
    lookup = {}
    for s in sets:
        for k in (str(s['name']).strip().lower(), str(s.get('slug') or '').strip().lower()):
            if k:
                lookup[k] = s['id']
                lookup[k[:-1] if k.endswith('s') else k + 's'] = s['id']
    pc = (parts_category or 'Tyres').strip().lower()
    return lookup.get(pc) or lookup.get('tyres') or lookup.get('default') or 1


def _field_payload(key, rec, brands):
    """Product.create/update kwargs + attributes_json entries for one synced field."""
    v = rec.get(key)
    data, dyn = {}, {}
    if key == 'name':
        data.update(name=v, name_en=v)
        dyn['name'] = v
    elif key == 'status':
        data['status'] = v
        dyn['status'] = 'Yes' if v == 'active' else 'No'
    elif key == 'price':
        data['price'] = v if v is not None else 0
        dyn['price'] = '' if v is None else str(v)
    elif key == 'stock_status':
        data['stock_status'] = v
    elif key == 'item_code':
        data['item_code'] = v
        dyn['item_code'] = v
    elif key == 'brand':
        data['brand_id'] = brands.id_for(v)
        dyn['brand'] = v
    elif key == 'pattern':
        data['tire_pattern'] = v
        dyn['pattern'] = v
    elif key == 'tyre_size':
        data['tire_size_label'] = v
        dyn.update(tyre_size=v, tire_size=v, tire_size_label=v)
    elif key in ('width', 'height', 'rim', 'tyre_marking'):
        dyn[key] = v
    elif key == 'load_index':
        load, speed = _split_load_index(v)
        data.update(tire_load_index=load, tire_speed_rating=speed)
        dyn.update(load_index=v, load_speed_index=v, tire_load_index=load or '')
        if speed:
            dyn['tire_speed_rating'] = speed
    elif key == 'oem_tyres':
        data['oem_brand'] = v
        dyn['oem_tyres'] = v
    elif key == 'parts_category':
        data['parts_category'] = v
        dyn['parts_category'] = v
    elif key == 'tyres_category':
        data['tyres_category'] = v
        dyn['tyres_category'] = v
    elif key == 'tyre_type':
        data['vehicle_type'] = Product._safe_vehicle_type(v)
        dyn['tyre_type'] = v
    elif key == 'country':
        data['country_of_origin'] = v
        dyn.update(country=v, origin=v, country_of_origin=v)
    elif key == 'ev':
        data['ev_rated'] = 1 if v else 0
        dyn['ev'] = _yes_no(v)
    elif key == 'runflat':
        data['run_flat'] = 1 if v else 0
        dyn['runflat'] = 'RunFlat' if v else ''
    elif key == 'year':
        data['year'] = v
        dyn['year'] = '' if v is None else str(v)
    elif key == 'warranty_period':
        data['warranty_months'] = Product._safe_warranty_months(v)
        dyn['warranty_period'] = v
    elif key == 'price_per_item':
        dyn['price_per_item'] = '' if v is None else str(v)
    elif key == 'price_included_text':
        data['price_included'] = v
        dyn['price_included_text'] = json.dumps({'en': v}, ensure_ascii=False) if v else ''
    elif key == 'tabby_payment':
        data['pay_later_eligible'] = 1 if v else 0
        dyn['tabby_payment'] = _yes_no(v)
    elif key == 'visibility':
        data['visibility'] = v
        dyn['visibility'] = v
    elif key == 'short_description':
        data['short_desc'] = {'en': v}
        dyn['short_description'] = v
    elif key == 'description':
        data['description'] = {'en': v}
        dyn['description'] = v
    elif key == 'meta_title':
        data['meta_title'] = {'en': v}
        dyn['meta_title'] = v
    elif key == 'meta_keyword':
        dyn['meta_keywords'] = v
        dyn['meta_keyword'] = v
    elif key == 'meta_description':
        data['meta_desc'] = {'en': v}
        dyn['meta_description'] = v
    return data, dyn


def _update_payload(rec, fields, brands, local_row):
    data, dyn = {}, {}
    for key in fields:
        d, a = _field_payload(key, rec, brands)
        data.update(d)
        dyn.update(a)
    if 'stock_status' in fields:
        qty = local_row.get('stock_qty') or 0
        if rec['stock_status'] == 'out_of_stock' and qty > 0:
            data['stock_qty'] = 0
        elif rec['stock_status'] == 'in_stock' and qty <= 0:
            data['stock_qty'] = 10
    if dyn:
        data['dynamic_attributes'] = dyn
    return data


def _create_payload(rec, brands, attribute_set_id):
    data, dyn = {}, {}
    for key in COMPARE_KEYS:
        d, a = _field_payload(key, rec, brands)
        data.update(d)
        dyn.update(a)

    name = rec['name'] or rec['sku']
    for fld in ('short_desc', 'description', 'meta_title', 'meta_desc'):
        data.pop(fld, None)
    data.update({
        'sku': rec['sku'],
        'website_id': 1,
        'website_ids': [1],
        'display_name': name,
        'name': name,
        'slug': rec['url_key'] or Product.slugify(name),
        'item_code': rec['item_code'] or rec['sku'],
        'parts_category': rec['parts_category'] or 'Tyres',
        'attribute_set_id': attribute_set_id,
        'stock_qty': 10 if rec['stock_status'] == 'in_stock' else 0,
        'image_path': '',
        'short_desc_en': rec['short_description'],
        'description_en': rec['description'],
        'meta_title_en': rec['meta_title'] or name,
        'meta_desc_en': rec['meta_description'],
    })
    dyn.update({
        'sku': rec['sku'],
        'url_key': data['slug'],
        'display_name': rec['display_name'],
        'tax_class': 'Taxable Goods',
        'tax_class_name': 'Taxable Goods',
        'promotion': 'None',
    })
    data['dynamic_attributes'] = {k: v for k, v in dyn.items() if v not in (None, '')}
    return data


def _escape_cat(name):
    return str(name).replace('\\', '\\\\').replace('/', '\\/').replace(',', '\\,')


def _category_paths(rec):
    """
    Magento-style category paths built from the remote category list. The remote
    "Tyre Size" assignment is sometimes wrong, so it's rebuilt from the tyre_size field.
    """
    by_path = {c['url_path']: c['name'] for c in rec.get('categories') or [] if c.get('url_path')}
    paths = []
    for url_path in sorted(by_path, key=lambda p: p.count('/')):
        parts = url_path.split('/')
        if len(parts) >= 2 and parts[0] == 'tyres' and parts[1] == 'size':
            continue
        is_top = len(parts) == 1
        is_leaf = not any(other.startswith(url_path + '/') for other in by_path)
        if not (is_top or is_leaf):
            continue
        names = []
        for i in range(1, len(parts) + 1):
            prefix = '/'.join(parts[:i])
            if prefix not in by_path:
                names = []
                break
            names.append(by_path[prefix])
        if names:
            paths.append(['Default Category'] + names)
    if rec.get('tyre_size') and any(p[1:2] == ['Tyres'] for p in paths):
        paths.append(['Default Category', 'Tyres', 'Tyre Size', rec['tyre_size']])
    return ','.join('/'.join(_escape_cat(n) for n in p) for p in paths)


def _assign_categories(created, user_id):
    rows = [(sku, _category_paths(rec)) for sku, rec in created]
    rows = [r for r in rows if r[1]]
    if not rows:
        return None
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['sku', 'categories'])
    w.writerows(rows)
    return CategoryImporter.import_csv(out.getvalue(), user_id=user_id)


def import_rows(rows, user_id=None):
    """
    rows: [{"sku": "...", "fields": [...]}]  -- fields omitted/null means "create as new".
    Returns {"created", "updated", "restored", "skipped", "failed": [{"sku", "error"}]}.
    """
    requested = {}
    for r in rows or []:
        sku = str((r or {}).get('sku') or '').strip().upper()
        if not sku:
            continue
        fields = r.get('fields')
        requested[sku] = None if fields is None else [f for f in fields if f in COMPARE_KEYS]

    result = {'created': 0, 'updated': 0, 'restored': 0, 'skipped': 0, 'failed': []}
    if not requested:
        return result

    remote = fetch_by_skus(list(requested))
    local = _load_local(list(requested))
    brands = _BrandResolver(user_id)
    created = []
    created_ids = []
    set_cache = {}

    for sku, fields in requested.items():
        rec = remote.get(sku)
        if not rec:
            result['failed'].append({'sku': sku, 'error': 'No longer returned by Tyrescart.'})
            continue
        row = local.get(sku)
        try:
            if not row:
                pc = rec['parts_category'] or 'Tyres'
                if pc not in set_cache:
                    set_cache[pc] = _attribute_set_id(pc)
                new_id = Product.create(_create_payload(rec, brands, set_cache[pc]), user_id=user_id)
                created.append((sku, rec))
                created_ids.append(new_id)
                result['created'] += 1
                continue

            if row.get('deleted_at'):
                Product.restore(row['id'], user_id=user_id)
                result['restored'] += 1

            if fields is None:
                # Sent as "new" but the SKU appeared locally after the compare; applying the
                # full diff here would bypass the admin's field selection (e.g. SEO meta).
                result['skipped'] += 1
                continue

            live_changes = diff(_local_record(row), rec)
            apply = [f for f in fields if f in live_changes]
            if not apply:
                result['skipped'] += 1
                continue
            Product.update(row['id'], _update_payload(rec, apply, brands, row), user_id=user_id)
            result['updated'] += 1
        except Exception as e:
            logger.exception('Product sync failed for %s', sku)
            result['failed'].append({'sku': sku, 'error': str(e)})

    if created:
        try:
            cat_result = _assign_categories(created, user_id)
            if cat_result and not cat_result.get('success'):
                result['failed'].append({'sku': '-', 'error': 'Category assignment: ' + str(cat_result.get('error'))})
        except Exception as e:
            logger.exception('Product sync category assignment failed')
            result['failed'].append({'sku': '-', 'error': f'Category assignment: {e}'})
        if es_service:
            for pid in created_ids:
                try:
                    es_service.index_single_product(pid)
                except Exception as e:
                    logger.warning('Elasticsearch reindex failed for product %s: %s', pid, e)

    return result


# Local SEO copy was rewritten on most products ("Buy ... Online"), so these differ almost
# everywhere; the review modal leaves them unticked unless the admin opts in.
DEFAULT_OFF_FIELDS = {'meta_title', 'meta_description'}


def field_labels():
    return [{'key': k, 'label': lbl, 'default_on': k not in DEFAULT_OFF_FIELDS} for k, lbl in COMPARE_FIELDS]
