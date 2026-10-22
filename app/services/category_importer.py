"""
app/services/category_importer.py - Magento Category Hierarchy CSV Importer

Implements comprehensive hierarchical category import according to Magento category path conventions:
- Reads the 'categories' column from CSV.
- Comma-separated category paths per row, supporting escaped values (e.g. 185\\/65 R15 -> 185/65 R15).
- Hierarchical parent-child relationship via '/' delimiter.
- Strict deduplication: reuses existing categories with same name and same parent_id.
- Root category 'Default Category' is assigned / verified at ID 2.
- Real database IDs generated upon insertion.
- Full transactional safety with automatic rollback on error.
- Separated operations: Category tree creation + Product-category mapping in product_categories table.
- Comprehensive import logging and result reporting.
"""

import csv
import io
import re
from datetime import datetime, timezone
from db import get_connection
from i18n import dump_json_dict, parse_json_dict, DEFAULT_LOCALE
from models.category import Category


def split_by_unescaped(text: str, delimiter: str) -> list:
    """
    Splits a string by a delimiter character, ignoring any occurrences
    preceded by an unescaped backslash.
    """
    if not text:
        return []
    parts = []
    current = []
    escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
        elif char == '\\':
            current.append(char)
            escaped = True
        elif char == delimiter:
            parts.append(''.join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append(''.join(current))
    return parts


def unescape_magento_token(token: str) -> str:
    """
    Unescapes Magento escaped characters:
      \\/  -> /
      \\,  -> ,
      \\\\ -> \\
    and trims leading and trailing whitespace.
    """
    if not token:
        return ''
    res = []
    escaped = False
    for char in token:
        if escaped:
            res.append(char)
            escaped = False
        elif char == '\\':
            escaped = True
        else:
            res.append(char)
    if escaped:
        res.append('\\')
    return ''.join(res).strip()


def parse_category_paths(cell_value: str) -> list:
    """
    Parses a Magento category cell containing comma-separated category paths.
    Example:
      Input: 'Default Category/Tyres,Default Category/Tyres/Brand/Bridgestone,Default Category/Tyres/Tyre Size/185\\/65 R15'
      Output: [
        ['Default Category', 'Tyres'],
        ['Default Category', 'Tyres', 'Brand', 'Bridgestone'],
        ['Default Category', 'Tyres', 'Tyre Size', '185/65 R15']
      ]
    """
    if not cell_value or not str(cell_value).strip():
        return []

    raw_paths = split_by_unescaped(str(cell_value).strip(), ',')
    result_paths = []
    for raw_path in raw_paths:
        p = raw_path.strip()
        if not p:
            continue
        raw_segments = split_by_unescaped(p, '/')
        clean_segments = [unescape_magento_token(s) for s in raw_segments if unescape_magento_token(s)]
        if clean_segments:
            result_paths.append(clean_segments)
    return result_paths


class CategoryImporter:
    """Service to import Magento category paths and map product categories."""

    @classmethod
    def import_csv(cls, file_content, user_id: int = None) -> dict:
        """
        Parses and imports categories and product assignments from CSV.
        
        Parameters:
            file_content: bytes, string, or file-like stream containing CSV data.
            user_id: ID of the admin user executing the import.

        Returns:
            dict containing detailed import statistics and error logging.
        """
        if isinstance(file_content, bytes):
            text_stream = io.StringIO(file_content.decode('utf-8-sig', errors='replace'))
        elif isinstance(file_content, str):
            text_stream = io.StringIO(file_content)
        elif hasattr(file_content, 'read'):
            raw = file_content.read()
            if isinstance(raw, bytes):
                text_stream = io.StringIO(raw.decode('utf-8-sig', errors='replace'))
            else:
                text_stream = io.StringIO(str(raw))
        else:
            return {
                'success': False,
                'error': 'Invalid file input stream.',
                'total_rows': 0,
                'unique_paths_count': 0,
                'unique_categories_count': 0,
                'existing_categories_count': 0,
                'created_categories_count': 0,
                'products_mapped_count': 0,
                'failed_rows_count': 0,
                'errors': ['Invalid file input stream.']
            }

        reader = csv.reader(text_stream)
        rows = list(reader)
        if not rows:
            return {
                'success': False,
                'error': 'The uploaded CSV file is empty.',
                'total_rows': 0,
                'unique_paths_count': 0,
                'unique_categories_count': 0,
                'existing_categories_count': 0,
                'created_categories_count': 0,
                'products_mapped_count': 0,
                'failed_rows_count': 0,
                'errors': ['Empty CSV file.']
            }

        headers = [h.strip().lower() for h in rows[0]]
        data_rows = rows[1:]

        # Detect category paths column
        cat_col_idx = None
        for candidate in ('categories', 'category', 'category_path', 'category_paths', '_category'):
            if candidate in headers:
                cat_col_idx = headers.index(candidate)
                break

        # Detect product identifier column (sku / item_code / product_id)
        sku_col_idx = None
        for candidate in ('sku', 'product_sku', 'item_code', 'product_id', 'id'):
            if candidate in headers:
                sku_col_idx = headers.index(candidate)
                break

        is_legacy_name = False
        if cat_col_idx is None:
            # Check if CSV has legacy category name columns: name_en / name / category_name
            name_col_idx = None
            for candidate in ('name_en', 'name', 'category_name', 'title'):
                if candidate in headers:
                    name_col_idx = headers.index(candidate)
                    break

            # Only treat name/title as legacy category list if this is NOT a product CSV
            product_indicator_cols = {'sku', 'product_sku', 'item_code', 'price', 'product_online', 'qty', 'stock_qty', 'tire_size'}
            is_product_csv = any(c in headers for c in product_indicator_cols)
            if not is_product_csv and name_col_idx is not None:
                # Treat as legacy flat category list: Default Category/{name}
                cat_col_idx = name_col_idx
                is_legacy_name = True
            elif 'category_name' in headers:
                cat_col_idx = headers.index('category_name')
                is_legacy_name = True
            elif len(headers) == 1 and '/' in headers[0]:
                cat_col_idx = 0
                data_rows = rows  # header was actually the first data row
            else:
                return {
                    'success': False,
                    'error': "CSV is missing the required 'categories' column.",
                    'total_rows': len(data_rows),
                    'unique_paths_count': 0,
                    'unique_categories_count': 0,
                    'existing_categories_count': 0,
                    'created_categories_count': 0,
                    'products_mapped_count': 0,
                    'failed_rows_count': 0,
                    'errors': ["Missing required 'categories' column in CSV headers."]
                }

        # -------------------------------------------------------------
        # Phase 1: Parse all rows, extract unique paths and product references
        # -------------------------------------------------------------
        unique_paths_set = set()
        product_rows = []
        errors = []
        failed_rows = 0

        for row_idx, row in enumerate(data_rows, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue  # ignore blank lines

            raw_cat_val = row[cat_col_idx] if cat_col_idx < len(row) else ''
            if is_legacy_name and raw_cat_val:
                raw_cat_val = f"Default Category/{raw_cat_val.strip()}"
            sku_val = (row[sku_col_idx].strip() if sku_col_idx is not None and sku_col_idx < len(row) else '').strip()

            try:
                parsed_paths = parse_category_paths(raw_cat_val)
                if parsed_paths:
                    for p in parsed_paths:
                        unique_paths_set.add(tuple(p))
                    if sku_val:
                        product_rows.append({
                            'row_idx': row_idx,
                            'sku': sku_val,
                            'paths': parsed_paths
                        })
            except Exception as ex:
                errors.append(f"Row {row_idx}: Failed to parse category paths - {str(ex)}")
                failed_rows += 1

        total_csv_rows = len(data_rows)
        total_unique_paths = len(unique_paths_set)

        # -------------------------------------------------------------
        # Phase 2: Database Operations with Transaction Safety
        # -------------------------------------------------------------
        conn = get_connection()
        conn.begin()

        created_cat_ids = set()
        reused_cat_ids = set()
        path_to_leaf_id = {}
        products_mapped = 0

        try:
            with conn.cursor() as cursor:
                # 1. Ensure 'Default Category' exists with ID 2 (Rule 6)
                cursor.execute("SELECT id, name, slug, parent_id FROM categories WHERE id = 2 AND deleted_at IS NULL")
                root_cat = cursor.fetchone()

                now = datetime.now(timezone.utc)
                if not root_cat:
                    # Check if any category named 'Default Category' exists with a different ID
                    cursor.execute("""
                        SELECT id, name, slug, parent_id FROM categories 
                        WHERE (slug = 'default-category' OR JSON_UNQUOTE(JSON_EXTRACT(name, '$.en')) = 'Default Category')
                          AND deleted_at IS NULL
                        LIMIT 1
                    """)
                    existing_root = cursor.fetchone()
                    if existing_root:
                        root_id = existing_root['id']
                    else:
                        # Insert explicitly with ID 2
                        root_name_json = dump_json_dict({'en': 'Default Category'})
                        cursor.execute("""
                            INSERT INTO categories (id, name, slug, parent_id, status, sort_order, created_at, updated_at)
                            VALUES (2, %s, 'default-category', NULL, 'active', 1, %s, %s)
                        """, (root_name_json, now, now))
                        root_id = 2
                else:
                    root_id = root_cat['id']

                cursor.execute("""
                    SELECT id, parent_id, name, slug, sort_order 
                    FROM categories 
                    WHERE deleted_at IS NULL
                """)
                all_cats = cursor.fetchall() or []

                pre_existing_cat_ids = {c['id'] for c in all_cats}
                if root_id:
                    pre_existing_cat_ids.add(root_id)

                cat_cache = {}  # (parent_id, normalized_name_en) -> category record
                used_slugs = set()
                parent_max_sort = {}
                reused_existing_ids = set()

                for c in all_cats:
                    cid = c['id']
                    pid = c.get('parent_id')
                    c_slug = (c.get('slug') or '').lower()
                    if c_slug:
                        used_slugs.add(c_slug)
                    s_ord = c.get('sort_order') or 0
                    if pid not in parent_max_sort or s_ord > parent_max_sort[pid]:
                        parent_max_sort[pid] = s_ord

                    name_data = c.get('name')
                    name_dict = name_data if isinstance(name_data, dict) else parse_json_dict(name_data)
                    name_en = ''
                    if isinstance(name_dict, dict):
                        name_en = (name_dict.get('en') or next(iter(name_dict.values()), '')).strip()
                    elif isinstance(name_data, str):
                        name_en = name_data.strip()

                    norm_name = name_en.lower()
                    cat_cache[(pid, norm_name)] = {
                        'id': cid,
                        'name': name_en,
                        'slug': c.get('slug'),
                        'parent_id': pid
                    }

                # 3. Process unique category paths sorted hierarchically (shorter paths first)
                sorted_paths = sorted(list(unique_paths_set), key=lambda x: (len(x), x))

                for path_tuple in sorted_paths:
                    path_segments = list(path_tuple)
                    if not path_segments:
                        continue

                    # If the path starts with 'Default Category', start from root_id
                    if path_segments[0].strip().lower() == 'default category':
                        current_parent_id = root_id
                        reused_existing_ids.add(root_id)
                        child_segments = path_segments[1:]
                    else:
                        # Non-root prefixed path: nest directly under Default Category (ID 2)
                        current_parent_id = root_id
                        reused_existing_ids.add(root_id)
                        child_segments = path_segments

                    for segment_name in child_segments:
                        clean_seg = segment_name.strip()
                        norm_seg = clean_seg.lower()
                        cache_key = (current_parent_id, norm_seg)

                        if cache_key in cat_cache:
                            # Reuse existing category under this parent
                            existing_info = cat_cache[cache_key]
                            current_parent_id = existing_info['id']
                            if current_parent_id in pre_existing_cat_ids:
                                reused_existing_ids.add(current_parent_id)
                        else:
                            # Create new category under current_parent_id
                            base_slug = Category.slugify(clean_seg) or f"category-{current_parent_id}"
                            candidate_slug = base_slug
                            suffix = 1
                            while candidate_slug in used_slugs:
                                suffix += 1
                                candidate_slug = f"{base_slug}-{suffix}"
                            used_slugs.add(candidate_slug)

                            current_sort = parent_max_sort.get(current_parent_id, 0) + 1
                            parent_max_sort[current_parent_id] = current_sort

                            name_json = dump_json_dict({'en': clean_seg})
                            cursor.execute("""
                                INSERT INTO categories (
                                    name, slug, parent_id, status, sort_order,
                                    created_by, created_at, updated_at
                                ) VALUES (%s, %s, %s, 'active', %s, %s, %s, %s)
                            """, (name_json, candidate_slug, current_parent_id, current_sort, user_id, now, now))

                            new_id = cursor.lastrowid
                            created_cat_ids.add(new_id)

                            cat_info = {
                                'id': new_id,
                                'name': clean_seg,
                                'slug': candidate_slug,
                                'parent_id': current_parent_id
                            }
                            cat_cache[cache_key] = cat_info
                            current_parent_id = new_id

                    # Deepest resolved category for this path
                    path_to_leaf_id[path_tuple] = current_parent_id

                # ---------------------------------------------------------
                # Phase 3: Product-Category Mapping (Rule 18)
                # ---------------------------------------------------------
                if product_rows:
                    unique_skus = list({item['sku'] for item in product_rows if item['sku']})
                    # Batch fetch products by SKU
                    sku_map = {}
                    batch_size = 500
                    for i in range(0, len(unique_skus), batch_size):
                        batch = unique_skus[i:i + batch_size]
                        format_placeholders = ', '.join(['%s'] * len(batch))
                        cursor.execute(f"""
                            SELECT id, sku, category_id 
                            FROM products 
                            WHERE sku IN ({format_placeholders}) AND deleted_at IS NULL
                        """, batch)
                        for p_row in cursor.fetchall():
                            sku_map[p_row['sku'].strip().upper()] = p_row

                    # Perform product category assignments
                    mapped_product_ids = set()
                    for item in product_rows:
                        sku_key = item['sku'].upper()
                        prod = sku_map.get(sku_key)
                        if not prod:
                            continue

                        prod_id = prod['id']
                        assigned_cat_ids = []
                        for p_tuple in item['paths']:
                            leaf_id = path_to_leaf_id.get(tuple(p_tuple))
                            if leaf_id and leaf_id not in assigned_cat_ids:
                                assigned_cat_ids.append(leaf_id)

                        if assigned_cat_ids:
                            for pos, cat_id in enumerate(assigned_cat_ids):
                                cursor.execute("""
                                    INSERT INTO product_categories (product_id, category_id, position)
                                    VALUES (%s, %s, %s)
                                    ON DUPLICATE KEY UPDATE position = VALUES(position)
                                """, (prod_id, cat_id, pos))

                            # Update primary category_id on products table if currently NULL
                            if not prod.get('category_id'):
                                cursor.execute("""
                                    UPDATE products SET category_id = %s 
                                    WHERE id = %s AND category_id IS NULL
                                """, (assigned_cat_ids[0], prod_id))

                            mapped_product_ids.add(prod_id)

                    products_mapped = len(mapped_product_ids)

            # Commit the entire transaction atomically
            conn.commit()

        except Exception as e:
            conn.rollback()
            return {
                'success': False,
                'error': f"Import transaction rolled back due to error: {str(e)}",
                'total_rows': total_csv_rows,
                'unique_paths_count': total_unique_paths,
                'unique_categories_count': 0,
                'existing_categories_count': 0,
                'created_categories_count': 0,
                'products_mapped_count': 0,
                'failed_rows_count': failed_rows + 1,
                'errors': errors + [str(e)]
            }
        finally:
            conn.close()

        total_unique_categories = len(created_cat_ids) + len(reused_existing_ids)
        existing_categories_count = len(reused_existing_ids)
        created_categories_count = len(created_cat_ids)

        return {
            'success': True,
            'total_rows': total_csv_rows,
            'unique_paths_count': total_unique_paths,
            'unique_categories_count': total_unique_categories,
            'existing_categories_count': existing_categories_count,
            'created_categories_count': created_categories_count,
            'products_mapped_count': products_mapped,
            'failed_rows_count': failed_rows,
            'errors': errors,
            'message': (
                f"Successfully processed {total_csv_rows} rows. "
                f"Found {total_unique_paths} unique category paths: "
                f"{created_categories_count} newly created, {existing_categories_count} reused. "
                f"{products_mapped} products mapped."
            )
        }
