"""
app/services/email_template_service.py - Service layer for Email Templates in VisionAdmin.
Handles database operations for:
- email_templates
- email_template_variables
"""

import re
from datetime import datetime, date
from decimal import Decimal
import db


def _serialize_row(row):
    """Convert dates, decimals, and bytes to JSON-serializable types."""
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


class EmailTemplateService:

    @staticmethod
    def get_counts():
        """Returns summary counts for email templates."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(CASE WHEN deleted_at IS NULL THEN 1 END) AS total,
                        SUM(CASE WHEN status = 'active' AND deleted_at IS NULL THEN 1 ELSE 0 END) AS active,
                        SUM(CASE WHEN is_default = 1 AND deleted_at IS NULL THEN 1 ELSE 0 END) AS default_count,
                        SUM(CASE WHEN is_default = 0 AND deleted_at IS NULL THEN 1 ELSE 0 END) AS custom_count,
                        SUM(CASE WHEN deleted_at IS NOT NULL THEN 1 ELSE 0 END) AS trash
                    FROM email_templates
                """)
                row = cur.fetchone() or {}
                return {
                    'total': int(row.get('total') or 0),
                    'active': int(row.get('active') or 0),
                    'default_count': int(row.get('default_count') or 0),
                    'custom_count': int(row.get('custom_count') or 0),
                    'trash': int(row.get('trash') or 0),
                }
        finally:
            conn.close()

    @staticmethod
    def get_templates(search=None, status=None, is_default=None, sort_by='name', sort_dir='asc', page=1, per_page=25):
        """Returns paginated email templates matching filters."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                conditions = []
                params = []

                if status == 'trash':
                    conditions.append("deleted_at IS NOT NULL")
                else:
                    conditions.append("deleted_at IS NULL")
                    if status and status in ('active', 'inactive'):
                        conditions.append("status = %s")
                        params.append(status)

                if is_default is not None and is_default != '':
                    conditions.append("is_default = %s")
                    params.append(int(is_default))

                if search:
                    term = f"%{search.strip()}%"
                    conditions.append("(name LIKE %s OR code LIKE %s OR subject LIKE %s)")
                    params.extend([term, term, term])

                where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

                # Count query
                cur.execute(f"SELECT COUNT(*) AS cnt FROM email_templates {where_clause}", params)
                total = cur.fetchone()['cnt']

                # Sorting whitelist
                allowed_cols = {
                    'id': 'id',
                    'name': 'name',
                    'code': 'code',
                    'subject': 'subject',
                    'type': 'type',
                    'status': 'status',
                    'is_default': 'is_default',
                    'updated_at': 'updated_at',
                    'created_at': 'created_at'
                }
                col = allowed_cols.get(sort_by, 'name')
                direction = 'DESC' if str(sort_dir).lower() == 'desc' else 'ASC'

                offset = (max(1, page) - 1) * per_page
                query = f"""
                    SELECT id, name, code, subject, content, styles, type, status, is_default, created_at, updated_at
                    FROM email_templates
                    {where_clause}
                    ORDER BY {col} {direction}
                    LIMIT %s OFFSET %s
                """
                cur.execute(query, params + [per_page, offset])
                rows = [_serialize_row(r) for r in cur.fetchall()]

                return {
                    'items': rows,
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'pages': (total + per_page - 1) // per_page if per_page else 1
                }
        finally:
            conn.close()

    @staticmethod
    def get_default_templates():
        """Returns all default templates for the 'Load Default Template' selector."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, code, subject, content, styles, type
                    FROM email_templates
                    WHERE is_default = 1 AND deleted_at IS NULL
                    ORDER BY name ASC
                """)
                return [_serialize_row(r) for r in cur.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get_template_by_id(template_id):
        """Fetches a single email template by ID."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, code, subject, content, styles, type, status, is_default, created_at, updated_at
                    FROM email_templates
                    WHERE id = %s
                """, (template_id,))
                return _serialize_row(cur.fetchone())
        finally:
            conn.close()

    @staticmethod
    def create_template(data, user_id=None):
        """Creates a new email template."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                name = (data.get('name') or '').strip()
                code = (data.get('code') or '').strip()
                if not code:
                    # Auto-generate code from name
                    code = re.sub(r'[^a-zA-Z0-9_]+', '_', name.lower()).strip('_')
                subject = (data.get('subject') or '').strip()
                content = data.get('content') or ''
                styles = data.get('styles') or ''
                type_val = data.get('type') or 'html'
                status = data.get('status') or 'active'
                is_default = 1 if data.get('is_default') in (1, '1', True) else 0

                cur.execute("""
                    INSERT INTO email_templates 
                    (name, code, subject, content, styles, type, status, is_default, created_by, updated_by, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, (name, code, subject, content, styles, type_val, status, is_default, user_id, user_id))
                new_id = cur.lastrowid
                conn.commit()
                return new_id
        finally:
            conn.close()

    @staticmethod
    def update_template(template_id, data, user_id=None):
        """Updates an existing email template."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                name = (data.get('name') or '').strip()
                code = (data.get('code') or '').strip()
                subject = (data.get('subject') or '').strip()
                content = data.get('content') or ''
                styles = data.get('styles') or ''
                type_val = data.get('type') or 'html'
                status = data.get('status') or 'active'
                is_default = 1 if data.get('is_default') in (1, '1', True) else 0

                cur.execute("""
                    UPDATE email_templates
                    SET name = %s, code = %s, subject = %s, content = %s, styles = %s, 
                        type = %s, status = %s, is_default = %s, updated_by = %s, updated_at = NOW()
                    WHERE id = %s
                """, (name, code, subject, content, styles, type_val, status, is_default, user_id, template_id))
                conn.commit()
                return True
        finally:
            conn.close()

    @staticmethod
    def delete_template(template_id, permanent=False):
        """Soft deletes or permanently removes a template."""
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                if permanent:
                    cur.execute("DELETE FROM email_templates WHERE id = %s", (template_id,))
                else:
                    cur.execute("UPDATE email_templates SET deleted_at = NOW() WHERE id = %s", (template_id,))
                conn.commit()
                return True
        finally:
            conn.close()

    @staticmethod
    def get_template_variables():
        """
        Returns all active variables from email_template_variables
        grouped by `group` in order of appearance.
        """
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, variable_code, label, description, `group`, example_value, sort_order
                    FROM email_template_variables
                    WHERE status = 'active' AND deleted_at IS NULL
                    ORDER BY sort_order ASC, id ASC
                """)
                rows = [_serialize_row(r) for r in cur.fetchall()]

                # First group all rows by their group column
                grouped = {}
                for r in rows:
                    grp = r.get('group') or 'Other'
                    if grp not in grouped:
                        grouped[grp] = []
                    grouped[grp].append(r)

                # Order grouped variables exactly matching Image 1 layout
                preferred_order = [
                    'Web',
                    'Store Email Addresses / General Contact',
                    'Store Email Addresses / Sales Representative',
                    'Store Email Addresses / Customer Support',
                    'Store Email Addresses / Custom Email 1',
                    'Store Email Addresses / Custom Email 2',
                    'General / Store Information',
                    'Customer Information',
                    'Order Information'
                ]
                ordered_grouped = {}
                for grp_name in preferred_order:
                    if grp_name in grouped:
                        ordered_grouped[grp_name] = grouped[grp_name]
                for grp_name, vlist in grouped.items():
                    if grp_name not in ordered_grouped:
                        ordered_grouped[grp_name] = vlist

                ordered_list = [{'group': grp_name, 'vars': vlist} for grp_name, vlist in ordered_grouped.items()]

                return {
                    'raw': rows,
                    'grouped': ordered_grouped,
                    'ordered_list': ordered_list
                }
        finally:
            conn.close()

    @staticmethod
    def render_template_content(content, context=None, styles=None):
        """
        Renders template content by replacing all {{var ...}} placeholders
        and {{ ... }} variables with values from the context dictionary.
        """
        if not content:
            return ""

        ctx = context or {}
        user_name = ctx.get('user_name') or ctx.get('customer_name') or ctx.get('name') or 'Valued Customer'
        user_email = ctx.get('user_email') or ctx.get('customer_email') or ctx.get('email') or ''
        user_phone = ctx.get('user_phone') or ctx.get('customer_phone') or ctx.get('phone') or ''
        reset_link = ctx.get('reset_link') or '#'
        login_link = ctx.get('login_link') or '#'
        expires_minutes = str(ctx.get('expires_minutes') or '30')
        user_role = ctx.get('user_role') or 'Administrator'
        store_name = ctx.get('store_name') or 'TyresVision'
        base_url = ctx.get('base_url') or ctx.get('assets_url') or 'https://tyresvision.com'
        secure_base_url = ctx.get('secure_base_url') or base_url
        support_email = ctx.get('support_email') or 'support@tyresvision.com'
        support_name = ctx.get('support_name') or f"{store_name} Customer Care"
        sales_email = ctx.get('sales_email') or 'sales@tyresvision.com'
        sales_name = ctx.get('sales_name') or f"{store_name} Sales"
        general_email = ctx.get('general_email') or 'info@tyresvision.com'
        general_name = ctx.get('general_name') or store_name
        phone_number = ctx.get('phone_number') or ctx.get('store_phone') or '+971 50 506 9575'
        order_id = ctx.get('order_id') or ctx.get('order_number') or 'ORD-1001'
        order_total = ctx.get('order_total') or ctx.get('grand_total') or 'AED 0.00'
        order_items = ctx.get('order_items_html') or ctx.get('order_items') or ''

        # Canonical replacement map
        mapping = {
            "{{var customer.name}}": user_name,
            "{{var customer.email}}": user_email,
            "{{var customer.phone}}": user_phone,
            "{{var reset_link}}": reset_link,
            "{{var login_link}}": login_link,
            "{{var expires_minutes}}": expires_minutes,
            "{{var user_role}}": user_role,
            "{{var store.name}}": store_name,
            "{{var store.base_url}}": base_url,
            "{{var store.secure_base_url}}": secure_base_url,
            "{{var store.phone}}": phone_number,
            "{{var store.phone_number}}": phone_number,
            "{{var store.hours}}": ctx.get('store_hours', 'Mon - Sat: 8:00 AM - 10:00 PM'),
            "{{var store.country}}": ctx.get('store_country', 'United Arab Emirates'),
            "{{var store.region}}": ctx.get('store_region', 'Dubai'),
            "{{var store.postal_code}}": ctx.get('store_postcode', '00000'),
            "{{var store.city}}": ctx.get('store_city', 'Dubai'),
            "{{var store.street_address}}": ctx.get('store_street', 'Al Quoz Industrial Area 3'),
            "{{var store.street_address_2}}": ctx.get('store_street_2', 'Behind Times Square Center'),
            "{{var store.vat_number}}": ctx.get('vat_number', '100234567890003'),
            "{{var trans_email.ident_general.name}}": general_name,
            "{{var trans_email.ident_general.email}}": general_email,
            "{{var trans_email.ident_sales.name}}": sales_name,
            "{{var trans_email.ident_sales.email}}": sales_email,
            "{{var trans_email.ident_support.name}}": support_name,
            "{{var trans_email.ident_support.email}}": support_email,
            "{{var order.increment_id}}": order_id,
            "{{var order.grand_total}}": order_total,
            "{{var order.total}}": order_total,
            "{{var order.items_html}}": order_items,
            # Also handle simple Jinja placeholders if present in raw content
            "{{ user_name }}": user_name,
            "{{ user_email }}": user_email,
            "{{ reset_link }}": reset_link,
            "{{ login_link }}": login_link,
            "{{ expires_minutes }}": expires_minutes,
            "{{ assets_url }}": base_url,
        }

        rendered = content
        for placeholder, val in mapping.items():
            rendered = rendered.replace(placeholder, str(val))

        # Also replace any arbitrary ctx keys if present as {{var key}}, {{ key }}, {{key}}, case-insensitive
        for k, v in ctx.items():
            val_str = str(v)
            rendered = rendered.replace(f"{{{{var {k}}}}}", val_str)
            rendered = rendered.replace(f"{{{{ {k} }}}}", val_str)
            rendered = rendered.replace(f"{{{{{k}}}}}", val_str)
            try:
                pattern = re.compile(r'\{\{\s*(?:var\s+)?' + re.escape(str(k).strip()) + r'\s*\}\}', re.IGNORECASE)
                rendered = pattern.sub(val_str, rendered)
            except Exception:
                pass

        if styles and styles.strip():
            rendered = f"<style>{styles}</style>\n" + rendered

        return rendered

    @classmethod
    def render_template_by_code(cls, code, context=None, default_subject=None, default_template_file=None):
        """
        Dynamically renders an email template from the database using its unique code.
        If not found or error, falls back to default_template_file via Flask render_template.
        Returns (rendered_subject, rendered_html).
        """
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT name, subject, content, styles, type
                    FROM email_templates
                    WHERE code = %s AND status = 'active' AND deleted_at IS NULL
                    ORDER BY is_default DESC, id DESC
                    LIMIT 1
                """, (code,))
                tmpl = cur.fetchone()
                if tmpl:
                    subject = cls.render_template_content(tmpl['subject'], context)
                    html = cls.render_template_content(tmpl['content'], context, styles=tmpl.get('styles'))
                    return subject, html
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error fetching email template '{code}' from DB: {e}")
        finally:
            conn.close()

        # Fallback to file rendering if template not found in DB
        subject = default_subject or "Notification from TyresVision"
        if default_template_file:
            try:
                from flask import render_template
                html = render_template(default_template_file, **(context or {}))
                return subject, html
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Fallback rendering of '{default_template_file}' failed: {e}")

        return subject, f"<p>Notification: {subject}</p>"

    @classmethod
    def preview_template(cls, content, styles=None):
        """
        Renders template content with mock sample variables so the admin can preview.
        """
        mock_context = {
            'user_name': 'Ahmed Al Mansoori',
            'user_email': 'ahmed@example.com',
            'customer_name': 'Ahmed Al Mansoori',
            'customer_email': 'ahmed@example.com',
            'customer_phone': '+971 50 123 4567',
            'reset_link': 'https://tyresvision.com/visionadmin/reset-password?token=sample_token_12345',
            'login_link': 'https://tyresvision.com/visionadmin/login?email=ahmed@example.com',
            'expires_minutes': 30,
            'user_role': 'Administrator',
            'store_name': 'TyresVision UAE',
            'base_url': 'https://tyresvision.com',
            'secure_base_url': 'https://tyresvision.com',
            'support_email': 'support@tyresvision.com',
            'support_name': 'TyresVision Customer Care',
            'sales_email': 'sales@tyresvision.com',
            'sales_name': 'TyresVision Sales',
            'general_email': 'info@tyresvision.com',
            'general_name': 'TyresVision',
            'phone_number': '+971 50 506 9575',
            'order_id': 'ORD-2026-8941',
            'order_total': 'AED 1,480.00',
            'order_items': '4x Michelin Primacy 4 225/55 R17',
            'order_items_html': '4x Michelin Primacy 4 225/55 R17',
            'store_hours': 'Mon - Sat: 8:00 AM - 10:00 PM',
            'store_country': 'United Arab Emirates',
            'store_region': 'Dubai',
            'store_city': 'Dubai',
            'store_street': 'Al Quoz Industrial Area 3',
            'store_street_2': 'Behind Times Square Center',
            'vat_number': '100234567890003',
            # Contact & Product Enquiry Variables
            'client name': 'Deep Patel',
            'client mobile': '+971 50 123 4567',
            'client number': '+971501234567',
            'client email': 'alice@klever.ae',
            'client Email': 'alice@klever.ae',
            'service': 'Product Enquiry • Tyres Catalog',
            'product Name': 'Tracmax 185/55 R16 83V X Privilo TX5 2024',
            'Note': 'Customer requested direct quote and mobile installation availability in Dubai.',
        }
        rendered = cls.render_template_content(content, mock_context, styles=styles)
        # In browser preview, convert cid: inline image references to static web path
        rendered = rendered.replace('cid:tyresvision_logo', '/static/assets/images/logo/tyresvision-logo-white.png')
        return rendered
