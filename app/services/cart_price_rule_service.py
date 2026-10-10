"""
app/services/cart_price_rule_service.py - Service layer for Cart Price Rules in VisionAdmin.
Handles database operations for:
- cart_price_rules
- cart_price_rule_customer_groups
- cart_price_rule_coupons
- cart_price_rule_coupon_usages
"""

import json
import math
import random
import re
import string
from datetime import datetime, date
from decimal import Decimal
import db


def _serialize_row(row):
    """Convert dates, decimals, and json fields to JSON-serializable types."""
    if not row:
        return row
    res = dict(row)
    for k, v in res.items():
        if isinstance(v, (datetime, date)):
            res[k] = v.isoformat()
        elif isinstance(v, Decimal):
            res[k] = float(v)
        elif isinstance(v, bytes):
            res[k] = bool(int.from_bytes(v, 'big'))
    return res


class CartPriceRuleService:

    @staticmethod
    def get_counts():
        """Returns summary counts for cart price rules."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(CASE WHEN deleted_at IS NULL THEN 1 END) AS total,
                        SUM(CASE WHEN is_active = 1 AND deleted_at IS NULL THEN 1 ELSE 0 END) AS active,
                        SUM(CASE WHEN coupon_type = 'NO_COUPON' AND is_active = 1 AND deleted_at IS NULL THEN 1 ELSE 0 END) AS auto_apply,
                        SUM(CASE WHEN coupon_type = 'SPECIFIC_COUPON' AND deleted_at IS NULL THEN 1 ELSE 0 END) AS coupon_rules,
                        SUM(CASE WHEN deleted_at IS NOT NULL THEN 1 ELSE 0 END) AS trash
                    FROM cart_price_rules
                """)
                row = cur.fetchone() or {}
                return {
                    'total': int(row.get('total') or 0),
                    'active': int(row.get('active') or 0),
                    'auto_apply': int(row.get('auto_apply') or 0),
                    'coupon_rules': int(row.get('coupon_rules') or 0),
                    'trash': int(row.get('trash') or 0),
                }
        finally:
            conn.close()

    @staticmethod
    def get_rules(search=None, status=None, coupon_type=None, customer_group_id=None, website_id=None, sort_by='priority', sort_dir='asc', page=1, per_page=25):
        """Fetches paginated cart price rules with customer groups, websites, and primary coupon."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                if status == 'trash':
                    conditions = ["r.deleted_at IS NOT NULL"]
                else:
                    conditions = ["r.deleted_at IS NULL"]
                    if status in ('active', '1'):
                        conditions.append("r.is_active = 1")
                    elif status in ('inactive', '0'):
                        conditions.append("r.is_active = 0")
                params = []

                if coupon_type in ('NO_COUPON', 'SPECIFIC_COUPON'):
                    conditions.append("r.coupon_type = %s")
                    params.append(coupon_type)

                if customer_group_id:
                    conditions.append("EXISTS (SELECT 1 FROM cart_price_rule_customer_groups cg WHERE cg.cart_price_rule_id = r.id AND cg.customer_group_id = %s)")
                    params.append(int(customer_group_id))

                if website_id:
                    conditions.append("EXISTS (SELECT 1 FROM cart_price_rule_websites cw WHERE cw.cart_price_rule_id = r.id AND cw.website_id = %s)")
                    params.append(int(website_id))

                where_clause = " WHERE " + " AND ".join(conditions)

                # Total count
                cur.execute(f"SELECT COUNT(DISTINCT r.id) AS cnt FROM cart_price_rules r {where_clause}", params)
                total = cur.fetchone()['cnt']

                # Sorting validation
                allowed_sort = {
                    'id': 'r.id',
                    'name': 'r.name',
                    'priority': 'r.priority',
                    'from_date': 'r.from_date',
                    'to_date': 'r.to_date',
                    'is_active': 'r.is_active',
                    'coupon_type': 'r.coupon_type',
                    'created_at': 'r.created_at'
                }
                order_col = allowed_sort.get(sort_by, 'r.priority')
                direction = 'DESC' if str(sort_dir).lower() == 'desc' else 'ASC'

                offset = (max(1, int(page)) - 1) * int(per_page)
                query = f"""
                    SELECT r.*,
                           c.code AS primary_coupon_code,
                           c.id AS primary_coupon_id,
                           c.used_count AS primary_coupon_used_count
                    FROM cart_price_rules r
                    LEFT JOIN cart_price_rule_coupons c ON c.cart_price_rule_id = r.id AND c.is_primary = 1
                    {where_clause}
                    ORDER BY {order_col} {direction}, r.id DESC
                    LIMIT %s OFFSET %s
                """
                cur.execute(query, params + [int(per_page), offset])
                raw_rules = cur.fetchall()

                # Eager-load customer groups & websites for the fetched rules
                rule_ids = [r['id'] for r in raw_rules]
                groups_map = {}
                websites_map = {}
                if rule_ids:
                    format_ids = ','.join(['%s'] * len(rule_ids))
                    cur.execute(f"""
                        SELECT cg.cart_price_rule_id, g.id, g.name, g.code
                        FROM cart_price_rule_customer_groups cg
                        JOIN customer_groups g ON g.id = cg.customer_group_id
                        WHERE cg.cart_price_rule_id IN ({format_ids})
                    """, rule_ids)
                    for row in cur.fetchall():
                        rid = row['cart_price_rule_id']
                        groups_map.setdefault(rid, []).append({'id': row['id'], 'name': row['name'], 'code': row['code']})

                    cur.execute(f"""
                        SELECT cw.cart_price_rule_id, w.id, w.name, w.code, w.is_default
                        FROM cart_price_rule_websites cw
                        JOIN websites w ON w.id = cw.website_id
                        WHERE cw.cart_price_rule_id IN ({format_ids})
                    """, rule_ids)
                    for row in cur.fetchall():
                        rid = row['cart_price_rule_id']
                        websites_map.setdefault(rid, []).append({'id': row['id'], 'name': row['name'], 'code': row['code'], 'is_default': bool(row.get('is_default'))})

                rules = []
                for r in raw_rules:
                    item = _serialize_row(r)
                    item['customer_groups'] = groups_map.get(r['id'], [])
                    item['websites'] = websites_map.get(r['id'], [])
                    item['website_ids'] = [w['id'] for w in item['websites']]
                    if isinstance(item.get('conditions_json'), str):
                        try:
                            item['conditions_json'] = json.loads(item['conditions_json'])
                        except Exception:
                            pass
                    if isinstance(item.get('item_conditions_json'), str):
                        try:
                            item['item_conditions_json'] = json.loads(item['item_conditions_json'])
                        except Exception:
                            pass
                    rules.append(item)

                last_page = math.ceil(total / int(per_page)) if total > 0 else 1
                return {
                    'data': rules,
                    'meta': {
                        'current_page': int(page),
                        'per_page': int(per_page),
                        'total': total,
                        'last_page': last_page
                    }
                }
        finally:
            conn.close()

    @staticmethod
    def get_rule(rule_id):
        """Fetches single rule by ID with customer groups and primary coupon."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT r.*,
                           c.code AS primary_coupon_code,
                           c.id AS primary_coupon_id,
                           c.usage_limit AS primary_coupon_usage_limit,
                           c.used_count AS primary_coupon_used_count
                    FROM cart_price_rules r
                    LEFT JOIN cart_price_rule_coupons c ON c.cart_price_rule_id = r.id AND c.is_primary = 1
                    WHERE r.id = %s AND r.deleted_at IS NULL
                """, (rule_id,))
                rule = cur.fetchone()
                if not rule:
                    return None

                # Load customer groups
                cur.execute("""
                    SELECT g.id, g.name, g.code
                    FROM cart_price_rule_customer_groups cg
                    JOIN customer_groups g ON g.id = cg.customer_group_id
                    WHERE cg.cart_price_rule_id = %s
                """, (rule_id,))
                groups = cur.fetchall()

                # Load websites
                cur.execute("""
                    SELECT w.id, w.name, w.code, w.is_default
                    FROM cart_price_rule_websites cw
                    JOIN websites w ON w.id = cw.website_id
                    WHERE cw.cart_price_rule_id = %s
                """, (rule_id,))
                websites = cur.fetchall()

                item = _serialize_row(rule)
                item['customer_groups'] = groups
                item['customer_group_ids'] = [g['id'] for g in groups]
                item['websites'] = websites
                item['website_ids'] = [w['id'] for w in websites]

                # Parse JSON fields
                for field in ('conditions_json', 'item_conditions_json'):
                    if isinstance(item.get(field), str):
                        try:
                            item[field] = json.loads(item[field])
                        except Exception:
                            pass
                    elif item.get(field) is None:
                        item[field] = {}

                return item
        finally:
            conn.close()

    @staticmethod
    def create_rule(data, admin_id=None):
        """Creates a new cart price rule with customer groups and optional coupon."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                name = str(data.get('name') or '').strip()
                if not name:
                    raise ValueError("Rule name is required.")

                description = data.get('description') or None
                is_active = 1 if data.get('is_active') in (1, '1', True, 'true', 'on') else 0
                coupon_type = 'SPECIFIC_COUPON' if data.get('coupon_type') == 'SPECIFIC_COUPON' else 'NO_COUPON'
                uses_per_customer = int(data['uses_per_customer']) if data.get('uses_per_customer') else None
                from_date = data.get('from_date') or None
                to_date = data.get('to_date') or None
                priority = int(data.get('priority') or 0)
                label_default = str(data.get('label_default') or '').strip() or None

                discount_type = data.get('discount_type') or 'percent_of_original'
                if discount_type not in ('percent_of_original', 'fixed_per_item', 'fixed_for_cart'):
                    discount_type = 'percent_of_original'

                discount_amount = Decimal(str(data.get('discount_amount') or 0))
                discount_qty_step = int(data['discount_qty_step']) if data.get('discount_qty_step') else None
                max_discount_qty = int(data['max_discount_qty']) if data.get('max_discount_qty') else None
                apply_to_shipping = 1 if data.get('apply_to_shipping') in (1, '1', True, 'true') else 0
                _shipping = data.get('_shipping') if data.get('_shipping') in ('no', 'matching_items', 'shipment') else 'no'
                discard_subsequent_rules = 1 if data.get('discard_subsequent_rules') in (1, '1', True, 'true') else 0

                conditions_json = data.get('conditions_json')
                if isinstance(conditions_json, (dict, list)):
                    conditions_json = json.dumps(conditions_json)
                elif conditions_json is not None and not isinstance(conditions_json, str):
                    conditions_json = None

                item_conditions_json = data.get('item_conditions_json')
                if isinstance(item_conditions_json, (dict, list)):
                    item_conditions_json = json.dumps(item_conditions_json)
                elif item_conditions_json is not None and not isinstance(item_conditions_json, str):
                    item_conditions_json = None

                cur.execute("""
                    INSERT INTO cart_price_rules (
                        name, description, is_active, coupon_type, uses_per_customer,
                        from_date, to_date, priority, conditions_json, discount_type,
                        discount_amount, discount_qty_step, max_discount_qty, apply_to_shipping,
                        _shipping, discard_subsequent_rules, item_conditions_json,
                        label_default, created_by, updated_by, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, NOW(), NOW()
                    )
                """, (
                    name, description, is_active, coupon_type, uses_per_customer,
                    from_date, to_date, priority, conditions_json, discount_type,
                    discount_amount, discount_qty_step, max_discount_qty, apply_to_shipping,
                    _shipping, discard_subsequent_rules, item_conditions_json,
                    label_default, admin_id, admin_id
                ))
                rule_id = cur.lastrowid

                # Sync customer groups
                group_ids = data.get('customer_group_ids') or []
                if isinstance(group_ids, str):
                    group_ids = [int(x.strip()) for x in group_ids.split(',') if x.strip().isdigit()]
                elif isinstance(group_ids, list):
                    group_ids = [int(x) for x in group_ids if str(x).isdigit()]

                for gid in group_ids:
                    cur.execute("""
                        INSERT IGNORE INTO cart_price_rule_customer_groups (cart_price_rule_id, customer_group_id)
                        VALUES (%s, %s)
                    """, (rule_id, gid))

                # Sync websites
                web_ids = data.get('website_ids') or []
                if isinstance(web_ids, str):
                    web_ids = [int(x.strip()) for x in web_ids.split(',') if x.strip().isdigit()]
                elif isinstance(web_ids, list):
                    web_ids = [int(x) for x in web_ids if str(x).isdigit()]

                for wid in web_ids:
                    cur.execute("""
                        INSERT IGNORE INTO cart_price_rule_websites (cart_price_rule_id, website_id)
                        VALUES (%s, %s)
                    """, (rule_id, wid))

                # Handle Primary Coupon Code if SPECIFIC_COUPON
                if coupon_type == 'SPECIFIC_COUPON' and data.get('coupon_code'):
                    code = str(data['coupon_code']).strip().upper()
                    cur.execute("""
                        INSERT INTO cart_price_rule_coupons (
                            cart_price_rule_id, code, usage_limit, used_count, is_primary,
                            created_by, updated_by, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, 0, 1,
                            %s, %s, NOW(), NOW()
                        )
                    """, (rule_id, code, None, admin_id, admin_id))

                conn.commit()
                return rule_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def update_rule(rule_id, data, admin_id=None):
        """Updates an existing cart price rule."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                name = str(data.get('name') or '').strip()
                if not name:
                    raise ValueError("Rule name is required.")

                description = data.get('description') or None
                is_active = 1 if data.get('is_active') in (1, '1', True, 'true', 'on') else 0
                coupon_type = 'SPECIFIC_COUPON' if data.get('coupon_type') == 'SPECIFIC_COUPON' else 'NO_COUPON'
                uses_per_customer = int(data['uses_per_customer']) if data.get('uses_per_customer') else None
                from_date = data.get('from_date') or None
                to_date = data.get('to_date') or None
                priority = int(data.get('priority') or 0)
                label_default = str(data.get('label_default') or '').strip() or None

                discount_type = data.get('discount_type') or 'percent_of_original'
                if discount_type not in ('percent_of_original', 'fixed_per_item', 'fixed_for_cart'):
                    discount_type = 'percent_of_original'

                discount_amount = Decimal(str(data.get('discount_amount') or 0))
                discount_qty_step = int(data['discount_qty_step']) if data.get('discount_qty_step') else None
                max_discount_qty = int(data['max_discount_qty']) if data.get('max_discount_qty') else None
                apply_to_shipping = 1 if data.get('apply_to_shipping') in (1, '1', True, 'true') else 0
                _shipping = data.get('_shipping') if data.get('_shipping') in ('no', 'matching_items', 'shipment') else 'no'
                discard_subsequent_rules = 1 if data.get('discard_subsequent_rules') in (1, '1', True, 'true') else 0

                conditions_json = data.get('conditions_json')
                if isinstance(conditions_json, (dict, list)):
                    conditions_json = json.dumps(conditions_json)

                item_conditions_json = data.get('item_conditions_json')
                if isinstance(item_conditions_json, (dict, list)):
                    item_conditions_json = json.dumps(item_conditions_json)

                cur.execute("""
                    UPDATE cart_price_rules SET
                        name = %s, description = %s, is_active = %s, coupon_type = %s,
                        uses_per_customer = %s, from_date = %s, to_date = %s, priority = %s,
                        conditions_json = %s, discount_type = %s, discount_amount = %s,
                        discount_qty_step = %s, max_discount_qty = %s, apply_to_shipping = %s,
                        _shipping = %s, discard_subsequent_rules = %s, item_conditions_json = %s,
                        label_default = %s, updated_by = %s, updated_at = NOW()
                    WHERE id = %s AND deleted_at IS NULL
                """, (
                    name, description, is_active, coupon_type,
                    uses_per_customer, from_date, to_date, priority,
                    conditions_json, discount_type, discount_amount,
                    discount_qty_step, max_discount_qty, apply_to_shipping,
                    _shipping, discard_subsequent_rules, item_conditions_json,
                    label_default, admin_id, rule_id
                ))

                # Sync customer groups
                group_ids = data.get('customer_group_ids') or []
                if isinstance(group_ids, str):
                    group_ids = [int(x.strip()) for x in group_ids.split(',') if x.strip().isdigit()]
                elif isinstance(group_ids, list):
                    group_ids = [int(x) for x in group_ids if str(x).isdigit()]

                cur.execute("DELETE FROM cart_price_rule_customer_groups WHERE cart_price_rule_id = %s", (rule_id,))
                for gid in group_ids:
                    cur.execute("""
                        INSERT INTO cart_price_rule_customer_groups (cart_price_rule_id, customer_group_id)
                        VALUES (%s, %s)
                    """, (rule_id, gid))

                # Sync websites
                web_ids = data.get('website_ids')
                if web_ids is not None:
                    if isinstance(web_ids, str):
                        web_ids = [int(x.strip()) for x in web_ids.split(',') if x.strip().isdigit()]
                    elif isinstance(web_ids, list):
                        web_ids = [int(x) for x in web_ids if str(x).isdigit()]
                    cur.execute("DELETE FROM cart_price_rule_websites WHERE cart_price_rule_id = %s", (rule_id,))
                    for wid in web_ids:
                        cur.execute("""
                            INSERT INTO cart_price_rule_websites (cart_price_rule_id, website_id)
                            VALUES (%s, %s)
                        """, (rule_id, wid))

                # Handle Primary Coupon
                if coupon_type == 'SPECIFIC_COUPON':
                    if data.get('coupon_code'):
                        code = str(data['coupon_code']).strip().upper()
                        # Check if primary coupon exists
                        cur.execute("SELECT id FROM cart_price_rule_coupons WHERE cart_price_rule_id = %s AND is_primary = 1", (rule_id,))
                        prim = cur.fetchone()
                        if prim:
                            cur.execute("""
                                UPDATE cart_price_rule_coupons SET code = %s, updated_by = %s, updated_at = NOW()
                                WHERE id = %s
                            """, (code, admin_id, prim['id']))
                        else:
                            cur.execute("""
                                INSERT INTO cart_price_rule_coupons (
                                    cart_price_rule_id, code, usage_limit, used_count, is_primary,
                                    created_by, updated_by, created_at, updated_at
                                ) VALUES (%s, %s, %s, 0, 1, %s, %s, NOW(), NOW())
                            """, (rule_id, code, None, admin_id, admin_id))
                else:
                    # Switched to NO_COUPON: Delete coupons
                    cur.execute("DELETE FROM cart_price_rule_coupons WHERE cart_price_rule_id = %s", (rule_id,))

                conn.commit()
                return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def delete_rule(rule_id, hard=False):
        """Deletes a cart price rule. If hard=True, permanently removes from DB."""
        if hard:
            return CartPriceRuleService.hard_delete_rule(rule_id)
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE cart_price_rules SET deleted_at = NOW(), is_active = 0
                    WHERE id = %s AND deleted_at IS NULL
                """, (rule_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def hard_delete_rule(rule_id):
        """Permanently hard-deletes a cart price rule and all associated child records from DB."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                # 1. Delete coupon usages
                cur.execute("""
                    DELETE FROM cart_price_rule_coupon_usages 
                    WHERE rule_id = %s OR coupon_id IN (
                        SELECT id FROM cart_price_rule_coupons WHERE cart_price_rule_id = %s
                    )
                """, (rule_id, rule_id))

                # 2. Delete coupons
                cur.execute("DELETE FROM cart_price_rule_coupons WHERE cart_price_rule_id = %s", (rule_id,))

                # 3. Delete customer group mappings
                cur.execute("DELETE FROM cart_price_rule_customer_groups WHERE cart_price_rule_id = %s", (rule_id,))

                # 4. Delete website mappings
                cur.execute("DELETE FROM cart_price_rule_websites WHERE cart_price_rule_id = %s", (rule_id,))

                # 5. Delete the rule record itself
                cur.execute("DELETE FROM cart_price_rules WHERE id = %s", (rule_id,))
                deleted = cur.rowcount > 0

                conn.commit()
                return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def restore_rule(rule_id):
        """Restores a soft-deleted cart price rule from trash."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE cart_price_rules SET deleted_at = NULL
                    WHERE id = %s AND deleted_at IS NOT NULL
                """, (rule_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            conn.close()

    @staticmethod
    def get_coupons(rule_id, page=1, per_page=50, search=None):
        """Fetches paginated coupons for a rule."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                conds = ["cart_price_rule_id = %s"]
                params = [rule_id]

                if search:
                    conds.append("code LIKE %s")
                    params.append(f"%{search.strip().upper()}%")

                where = " WHERE " + " AND ".join(conds)

                cur.execute(f"SELECT COUNT(*) AS cnt FROM cart_price_rule_coupons {where}", params)
                total = cur.fetchone()['cnt']

                offset = (max(1, int(page)) - 1) * int(per_page)
                cur.execute(f"""
                    SELECT id, code, usage_limit, used_count, is_primary, created_at
                    FROM cart_price_rule_coupons
                    {where}
                    ORDER BY is_primary DESC, id DESC
                    LIMIT %s OFFSET %s
                """, params + [int(per_page), offset])
                rows = [_serialize_row(r) for r in cur.fetchall()]

                return {
                    'data': rows,
                    'meta': {
                        'current_page': int(page),
                        'per_page': int(per_page),
                        'total': total,
                        'last_page': math.ceil(total / int(per_page)) if total > 0 else 1
                    }
                }
        finally:
            conn.close()

    @staticmethod
    def generate_coupons(rule_id, options, admin_id=None):
        """Bulk generates unique coupons for a specific rule."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                # Check rule exists and requires coupons
                cur.execute("SELECT id, coupon_type FROM cart_price_rules WHERE id = %s AND deleted_at IS NULL", (rule_id,))
                rule = cur.fetchone()
                if not rule or rule['coupon_type'] != 'SPECIFIC_COUPON':
                    raise ValueError("Coupons can only be generated for active rules with Specific Coupon type.")

                qty = min(5000, max(1, int(options.get('quantity') or 10)))
                length = min(32, max(4, int(options.get('length') or 10)))
                code_format = options.get('format') or 'alphanumeric'
                prefix = str(options.get('prefix') or '').strip().upper()
                suffix = str(options.get('suffix') or '').strip().upper()
                dash_interval = int(options.get('dash_interval') or 0)
                usage_limit = int(options['usage_limit']) if options.get('usage_limit') else None

                if code_format == 'letters_only':
                    chars = string.ascii_uppercase
                elif code_format == 'digits_only':
                    chars = string.digits
                else:
                    chars = string.ascii_uppercase + string.digits

                # Load existing codes to avoid duplicate generation
                cur.execute("SELECT code FROM cart_price_rule_coupons WHERE cart_price_rule_id = %s", (rule_id,))
                existing_codes = {r['code'] for r in cur.fetchall()}

                generated_batch = []
                attempts = 0
                max_attempts = qty * 5

                while len(generated_batch) < qty and attempts < max_attempts:
                    attempts += 1
                    body = ''.join(random.choices(chars, k=length))
                    if dash_interval > 0 and len(body) > dash_interval:
                        body = '-'.join(body[i:i + dash_interval] for i in range(0, len(body), dash_interval))

                    full_code = f"{prefix}{body}{suffix}"
                    if full_code not in existing_codes:
                        existing_codes.add(full_code)
                        generated_batch.append((
                            rule_id, full_code, usage_limit, 0, 0, admin_id, admin_id
                        ))

                if not generated_batch:
                    return 0

                cur.executemany("""
                    INSERT IGNORE INTO cart_price_rule_coupons (
                        cart_price_rule_id, code, usage_limit, used_count, is_primary,
                        created_by, updated_by, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, generated_batch)
                conn.commit()
                return len(generated_batch)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def delete_coupon(rule_id, coupon_id):
        """Deletes a coupon code if it is not primary and has never been used."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT is_primary, used_count FROM cart_price_rule_coupons
                    WHERE id = %s AND cart_price_rule_id = %s
                """, (coupon_id, rule_id))
                c = cur.fetchone()
                if not c:
                    return False
                if c['is_primary']:
                    raise ValueError("Cannot delete the primary rule coupon code.")
                if c['used_count'] > 0:
                    raise ValueError("Cannot delete a coupon code that has already been used in orders.")

                cur.execute("DELETE FROM cart_price_rule_coupons WHERE id = %s", (coupon_id,))
                conn.commit()
                return True
        finally:
            conn.close()

    @staticmethod
    def get_export_coupons(rule_id):
        """Returns all coupons for CSV export."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT code, usage_limit, used_count, is_primary, created_at
                    FROM cart_price_rule_coupons
                    WHERE cart_price_rule_id = %s
                    ORDER BY is_primary DESC, id ASC
                """, (rule_id,))
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_lookups():
        """Fetches customer groups, brands, categories, tyre sizes, patterns for rule builder."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, code FROM customer_groups WHERE status = 'active' ORDER BY name ASC")
                customer_groups = cur.fetchall()

                cur.execute("SELECT id, name FROM brands ORDER BY name ASC")
                brands = cur.fetchall()

                cur.execute("SELECT id, name FROM categories WHERE status = 'active' ORDER BY name ASC LIMIT 100")
                categories = cur.fetchall()

                # Get distinct tyre sizes from products
                cur.execute("SELECT DISTINCT tire_size_label FROM products WHERE tire_size_label IS NOT NULL AND tire_size_label != '' ORDER BY tire_size_label ASC LIMIT 100")
                sizes = [r['tire_size_label'] for r in cur.fetchall()]

                # Get distinct patterns from products
                cur.execute("SELECT DISTINCT tire_pattern FROM products WHERE tire_pattern IS NOT NULL AND tire_pattern != '' ORDER BY tire_pattern ASC LIMIT 100")
                patterns = [r['tire_pattern'] for r in cur.fetchall()]

                # Get websites
                cur.execute("SELECT id, name, code, is_default FROM websites WHERE deleted_at IS NULL ORDER BY sort_order ASC, id ASC")
                websites = cur.fetchall()

                return {
                    'customer_groups': customer_groups,
                    'websites': websites,
                    'brands': brands,
                    'categories': categories,
                    'tyre_sizes': sizes,
                    'patterns': patterns,
                }
        finally:
            conn.close()
