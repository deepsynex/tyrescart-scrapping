"""
app/visionadmin/Visionadminroute.py - VisionAdmin CMS Authentication & Studio Page Routes.

Serves the VisionAdmin HTML pages only (Pages/Blogs/Sections/Settings/Enquiries).
Authenticated and authorized against the `admin_users` table in the database.
"""

import functools
import re
import secrets
from flask import jsonify, make_response, redirect, render_template, request, session

from visionadmin.admin_auth import (
    check_admin_forgot_password_rate_limit,
    check_admin_login_rate_limit,
    check_admin_reset_password_rate_limit,
    clear_admin_login_failures,
    create_admin_password_reset_token,
    get_admin_user_by_email,
    get_admin_user_by_id,
    record_admin_forgot_password_request,
    record_admin_login_failure,
    record_admin_login_success,
    record_admin_reset_password_attempt,
    update_admin_user_password,
    verify_admin_password,
    verify_and_consume_admin_reset_token,
)
from mailer import send_email
from services.attribute_service import AttributeService
from services.cart_price_rule_service import CartPriceRuleService
import csv
import io

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

ALLOWED_ADMIN_ROLES = {'super_admin', 'superadmin', 'manager', 'support', 'admin'}


def is_authorized_admin(role: str) -> bool:
    """Case-insensitive check for admin privileges."""
    if not role:
        return False
    normalized = str(role).strip().lower().replace('-', '_').replace(' ', '_')
    return normalized in ALLOWED_ADMIN_ROLES or role.strip() in ('SuperAdmin', 'Admin')


def login_required_visionadmin(view):
    """Protects VisionAdmin page routes: requires authenticated administrator from admin_users table."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get('admin_user_id') or session.get('user_id')
        email = session.get('email')
        if not user_id and not email:
            return redirect(f'/visionadmin/login?next={request.path}')

        admin_u = None
        if user_id:
            admin_u = get_admin_user_by_id(user_id)
        if not admin_u and email:
            admin_u = get_admin_user_by_email(email)
            if admin_u:
                session['admin_user_id'] = admin_u['id']
                session['user_id'] = admin_u['id']
                session['name'] = admin_u['name']
                session['email'] = admin_u['email']
                session['role'] = admin_u['role']
                session['is_visionadmin'] = True

        if not admin_u:
            session.clear()
            return redirect(f'/visionadmin/login?next={request.path}')

        role = admin_u.get('role') or session.get('role')
        if not is_authorized_admin(role):
            return render_template(
                '404.html',
                page='403',
                requested_path=request.path,
                user_name=session.get('name'),
                user_email=session.get('email'),
                user_role=role,
                error_message='You do not have administrative permission to access VisionAdmin CMS.',
                unread_notifications=0,
                notifications=[]
            ), 403
        return view(*args, **kwargs)
    return wrapped


def register_visionadmin_routes(app):
    """Registers the /visionadmin (and /visonadmin, /admin aliases) authentication and page routes."""

    # ========================================================================
    # 1. AUTHENTICATION & SESSION ROUTES (admin_users table)
    # ========================================================================

    @app.route('/visionadmin/login', methods=['GET'])
    @app.route('/visonadmin/login', methods=['GET'])
    def visionadmin_login_page():
        """Renders the VisionAdmin login page or redirects if already signed in."""
        user_id = session.get('admin_user_id') or session.get('user_id')
        role = session.get('role')
        if user_id and is_authorized_admin(role):
            next_url = request.args.get('next') or '/visionadmin/pages'
            return redirect(next_url)
        return render_template('visionadmin/login.html')

    @app.route('/visionadmin/login', methods=['POST'])
    @app.route('/visonadmin/login', methods=['POST'])
    def visionadmin_login_submit():
        """Authenticates administrator against admin_users table with email & password."""
        data = request.get_json(silent=True) or request.form
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        remember = bool(data.get('remember'))

        if not email or not password:
            return jsonify({'error': 'Email and password are required.'}), 400

        # Rate limiting check
        is_locked, seconds_remaining, msg = check_admin_login_rate_limit(email)
        if is_locked:
            return jsonify({'error': msg}), 429

        # Query admin_users table
        admin_user = get_admin_user_by_email(email)
        if not admin_user or not verify_admin_password(password, admin_user.get('password', '')):
            record_admin_login_failure(email)
            return jsonify({'error': 'Invalid email or password.'}), 401

        # Check if active
        if not admin_user.get('is_active', 1):
            return jsonify({'error': 'This administrator account has been disabled. Contact support.'}), 403

        # Check role permission
        role = admin_user.get('role', 'manager')
        if not is_authorized_admin(role):
            return jsonify({'error': 'Access denied. Administrator privileges required.'}), 403

        # Success - Clear rate limit counters and record login timestamp
        clear_admin_login_failures(email)
        record_admin_login_success(admin_user['id'])

        session.clear()
        session.permanent = remember
        session['sid'] = secrets.token_hex(16)
        session['admin_user_id'] = admin_user['id']
        session['user_id'] = admin_user['id']
        session['userid'] = admin_user['id']
        session['id'] = admin_user['id']
        session['name'] = admin_user['name']
        session['Name'] = admin_user['name']
        session['email'] = admin_user['email']
        session['Email'] = admin_user['email']
        session['role'] = 'SuperAdmin' if admin_user['role'] in ('super_admin', 'superadmin', 'SuperAdmin') else ('Admin' if admin_user['role'] in ('manager', 'admin', 'Admin') else 'User')
        session['admin_role'] = admin_user['role']
        session['csrf_token'] = secrets.token_hex(16)
        session['is_visionadmin'] = True
        session['logged_in'] = True

        next_url = request.args.get('next') or '/visionadmin/pages'
        return jsonify({
            'success': True,
            'redirect': next_url,
            'user': {
                'id': admin_user['id'],
                'name': admin_user['name'],
                'email': admin_user['email'],
                'role': admin_user['role']
            }
        })

    @app.route('/visionadmin/logout', methods=['GET', 'POST'])
    @app.route('/visonadmin/logout', methods=['GET', 'POST'])
    def visionadmin_logout():
        """Clears administrator session and redirects to VisionAdmin login."""
        session.clear()
        if request.method == 'GET' or not (request.is_json or (request.headers.get('Accept') and 'application/json' in request.headers.get('Accept'))):
            return redirect('/visionadmin/login')
        return jsonify({'success': True, 'redirect': '/visionadmin/login'})

    @app.route('/visionadmin/forgot-password', methods=['GET', 'POST'])
    @app.route('/visonadmin/forgot-password', methods=['GET', 'POST'])
    def visionadmin_forgot_password():
        """Handles password reset requests for administrators using admin_users table."""
        if request.method == 'GET':
            return render_template('visionadmin/forgot_password.html')

        data = request.get_json(silent=True) or request.form or {}
        email = (data.get('email') or '').strip().lower()

        if not email or not EMAIL_RE.match(email):
            return jsonify({'error': 'Please enter a valid email address.'}), 400

        is_limited, seconds_remaining, msg = check_admin_forgot_password_rate_limit(email)
        if is_limited:
            return jsonify({'error': msg}), 429

        record_admin_forgot_password_request(email)

        # Lookup in admin_users table
        admin_user = get_admin_user_by_email(email)
        if admin_user and admin_user.get('is_active', 1):
            try:
                assets_url = 'https://tyrescart-scrapping.klever.ae' if ('localhost' in request.host_url or '127.0.0.1' in request.host_url) else request.host_url.rstrip('/')
                token = create_admin_password_reset_token(admin_user['email'])
                reset_link = f"{request.host_url.rstrip('/')}/visionadmin/reset-password?token={token}"
                html_body = render_template(
                    'emails/vison_forgotpass.html',
                    user_name=admin_user.get('name') or 'there',
                    user_email=admin_user.get('email') or email,
                    reset_link=reset_link,
                    expires_minutes=30,
                    assets_url=assets_url,
                )
                send_email(
                    admin_user['email'],
                    'Reset Your VisionAdmin Password',
                    html_body,
                )
            except Exception as e:
                app.logger.error(f'Error sending password reset email to admin: {e}')
                return jsonify({'error': f'Failed to send email: {str(e)}'}), 500

        return jsonify({
            'success': True,
            'message': 'If an administrator account exists with that email, a password reset link has been sent.',
        })

    @app.route('/visionadmin/reset-password', methods=['GET', 'POST'])
    @app.route('/visonadmin/reset-password', methods=['GET', 'POST'])
    def visionadmin_reset_password():
        """Handles password reset token consumption for admin_users table."""
        if request.method == 'GET':
            return render_template('visionadmin/reset_password.html', token=request.args.get('token', ''))

        data = request.get_json(silent=True) or request.form or {}
        token = (data.get('token') or '').strip()
        new_password = data.get('new_password') or ''
        confirm_password = data.get('confirm_password') or ''

        is_limited, seconds_remaining, msg = check_admin_reset_password_rate_limit()
        if is_limited:
            return jsonify({'error': msg}), 429

        record_admin_reset_password_attempt()

        if not token:
            return jsonify({'error': 'Reset token is required.'}), 400

        if not new_password or not confirm_password:
            return jsonify({'error': 'Both password fields are required.'}), 400

        if new_password != confirm_password:
            return jsonify({'error': 'Passwords do not match.'}), 400

        if len(new_password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters long.'}), 400

        # Verify and consume reset token against password_reset_tokens / admin_users
        admin_user = verify_and_consume_admin_reset_token(token)
        if not admin_user:
            return jsonify({'error': 'Invalid or expired reset link. Please request a new one.'}), 400

        if not admin_user.get('is_active', 1):
            return jsonify({'error': 'Account not found or inactive.'}), 404

        update_admin_user_password(admin_user['id'], new_password)
        return jsonify({
            'success': True,
            'message': 'Your password has been reset successfully. You can now sign in to VisionAdmin.',
            'redirect': '/visionadmin/login'
        })

    # ========================================================================
    # 2. VISIONADMIN CMS STUDIO PAGES (PROTECTED)
    # ========================================================================

    @app.route('/visionadmin', methods=['GET'])
    @app.route('/visionadmin/', methods=['GET'])
    @app.route('/visionadmin/pages', methods=['GET'])
    @app.route('/visonadmin', methods=['GET'])
    @app.route('/visonadmin/', methods=['GET'])
    @app.route('/admin/pages', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_pages():
        return render_template('visionadmin/pages.html', page='pages')

    # ── SEO MANAGER ──────────────────────────────────────────────────────────
    @app.route('/visionadmin/seo', methods=['GET'])
    @app.route('/visonadmin/seo', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_seo_manager():
        return render_template('visionadmin/seo_manager.html', page='seo')

    @app.route('/visionadmin/api/seo/pages', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_api_seo_pages():
        """Return all pages with their SEO status flags."""
        import json as _json
        import db as _db
        conn = _db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT slug, title, og_tags, schema_json
                       FROM pages
                       WHERE deleted_at IS NULL AND is_active = 1
                       ORDER BY id"""
                )
                rows = cur.fetchall()
            pages = []
            for r in rows:
                raw_title = r.get('title') or r[1] if isinstance(r, dict) else r[1]
                title_data = _json.loads(raw_title) if isinstance(raw_title, str) else raw_title
                title = (title_data.get('en') or next(iter(title_data.values()), '')) if isinstance(title_data, dict) else str(title_data)

                og_raw = r.get('og_tags') if isinstance(r, dict) else r[2]
                og_data = _json.loads(og_raw) if isinstance(og_raw, str) else (og_raw or {})

                schema_raw = r.get('schema_json') if isinstance(r, dict) else r[3]

                has_og = bool(og_data and any(v for v in og_data.values() if v))
                has_twitter = bool(og_data and any(k.startswith('twitter_') and v for k, v in og_data.items()))
                has_schema = bool(schema_raw and str(schema_raw).strip())

                pages.append({
                    'slug': r.get('slug') if isinstance(r, dict) else r[0],
                    'title': title,
                    'has_og': has_og,
                    'has_twitter': has_twitter,
                    'has_schema': has_schema,
                })
            return jsonify({'pages': pages})
        finally:
            conn.close()

    @app.route('/visionadmin/api/seo/<slug>', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_api_seo_get(slug):
        """Return OG tags and schema for a single page."""
        import json as _json
        import db as _db
        conn = _db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT og_tags, schema_json FROM pages WHERE slug = %s AND deleted_at IS NULL',
                    (slug,)
                )
                row = cur.fetchone()
            if not row:
                return jsonify({'error': 'Page not found'}), 404

            og_raw = row.get('og_tags') if isinstance(row, dict) else row[0]
            og_data = _json.loads(og_raw) if isinstance(og_raw, str) else (og_raw or {})

            schema_raw = row.get('schema_json') if isinstance(row, dict) else row[1]

            # Split og_data into OG and Twitter groups
            og_tags = {k: v for k, v in og_data.items() if not k.startswith('twitter_')}
            twitter_tags = {k: v for k, v in og_data.items() if k.startswith('twitter_')}

            return jsonify({
                'slug': slug,
                'og_tags': og_tags,
                'twitter_tags': twitter_tags,
                'schema_json': schema_raw or '',
            })
        finally:
            conn.close()

    @app.route('/visionadmin/api/seo/<slug>', methods=['PUT'])
    @login_required_visionadmin
    def visionadmin_api_seo_put(slug):
        """Save OG tags and schema for a page."""
        import json as _json
        import db as _db
        data = request.get_json(silent=True) or {}

        og_tags = data.get('og_tags') or {}
        twitter_tags = data.get('twitter_tags') or {}
        schema_raw = data.get('schema_json') or None

        # Validate schema JSON if provided
        if schema_raw and schema_raw.strip():
            try:
                _json.loads(schema_raw)
            except ValueError as e:
                return jsonify({'success': False, 'error': f'Invalid JSON-LD: {e}'}), 400
        else:
            schema_raw = None

        # Merge og + twitter into one JSON blob stored in og_tags column
        merged = {}
        merged.update({k: v for k, v in og_tags.items() if v is not None})
        merged.update({k: v for k, v in twitter_tags.items() if v is not None})

        conn = _db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT id FROM pages WHERE slug = %s AND deleted_at IS NULL', (slug,)
                )
                if not cur.fetchone():
                    return jsonify({'success': False, 'error': 'Page not found'}), 404

                cur.execute(
                    'UPDATE pages SET og_tags = %s, schema_json = %s, updated_at = NOW() WHERE slug = %s',
                    (_json.dumps(merged), schema_raw, slug)
                )
            conn.commit()
            return jsonify({'success': True, 'message': 'SEO tags saved successfully.'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            conn.close()

    @app.route('/visionadmin/blogs', methods=['GET'])
    @app.route('/visonadmin/blogs', methods=['GET'])
    @app.route('/admin/blogs', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_blogs():
        page_val = 'blog_categories' if request.args.get('open') == 'categories' else 'blogs'
        return render_template('visionadmin/blogs.html', page=page_val)

    @app.route('/visionadmin/blog-categories', methods=['GET'])
    @app.route('/visonadmin/blog-categories', methods=['GET'])
    @app.route('/admin/blog-categories', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_blog_categories():
        return render_template('visionadmin/blog_categories.html', page='blog_categories')

    @app.route('/visionadmin/blog-categories/new', methods=['GET'])
    @app.route('/visionadmin/blog-categories/create', methods=['GET'])
    @app.route('/visonadmin/blog-categories/new', methods=['GET'])
    @app.route('/visonadmin/blog-categories/create', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_blog_category_create():
        return render_template('visionadmin/blog_category_form.html', page='blog_categories', initial_mode='create', initial_cat_id=None)

    @app.route('/visionadmin/blog-categories/<int:cat_id>/edit', methods=['GET'])
    @app.route('/visonadmin/blog-categories/<int:cat_id>/edit', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_blog_category_edit(cat_id):
        return render_template('visionadmin/blog_category_form.html', page='blog_categories', initial_mode='edit', initial_cat_id=cat_id)

    @app.route('/visionadmin/sections', methods=['GET'])
    @app.route('/visionadmin/about-sections', methods=['GET'])
    @app.route('/visonadmin/sections', methods=['GET'])
    @app.route('/visonadmin/about-sections', methods=['GET'])
    @app.route('/admin/sections', methods=['GET'])
    @app.route('/admin/about-sections', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_sections():
        return render_template('visionadmin/sections.html', page='sections')

    @app.route('/visionadmin/sections/<int:section_id>/preview', methods=['GET'])
    @app.route('/visonadmin/sections/<int:section_id>/preview', methods=['GET'])
    @app.route('/admin/sections/<int:section_id>/preview', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_section_preview(section_id):
        from models.page_section import PageSection
        sec_raw = PageSection.find_by_id(section_id)
        if not sec_raw:
            return "<div style='padding:40px;text-align:center;font-family:sans-serif;'><h3>Section not found.</h3></div>", 404
        
        locale = request.args.get('locale', 'en').lower()
        if locale not in ('en', 'ar'):
            locale = 'en'
            
        sec = PageSection.to_localized_dict(sec_raw, locale=locale)
        resp = make_response(render_template('visionadmin/section_preview.html', sec=sec, locale=locale))
        resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
        return resp

    @app.route('/visionadmin/settings', methods=['GET'])
    @app.route('/visionadmin/config', methods=['GET'])
    @app.route('/visionadmin/reviewer-settings', methods=['GET'])
    @app.route('/visonadmin/settings', methods=['GET'])
    @app.route('/visonadmin/config', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_settings():
        return render_template('visionadmin/settings.html', page='settings')

    @app.route('/visionadmin/enquiries', methods=['GET'])
    @app.route('/visionadmin/enquiry', methods=['GET'])
    @app.route('/visionadmin/leads', methods=['GET'])
    @app.route('/visonadmin/enquiries', methods=['GET'])
    @app.route('/visonadmin/enquiry', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_enquiries():
        return render_template('visionadmin/enquiries.html', page='enquiries')

    @app.route('/visionadmin/users', methods=['GET'])
    @app.route('/visionadmin/admin-users', methods=['GET'])
    @app.route('/visonadmin/users', methods=['GET'])
    @app.route('/visonadmin/admin-users', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_users():
        """Renders Admin Users Management Studio (Super Admin only)."""
        role_norm = str(session.get('role') or '').strip().lower().replace('-', '_').replace(' ', '_')
        if role_norm not in ('super_admin', 'superadmin') and session.get('role') != 'SuperAdmin':
            return render_template(
                '404.html',
                page='403',
                requested_path=request.path,
                user_name=session.get('name'),
                user_email=session.get('email'),
                user_role=session.get('role'),
                error_message='Super Administrator privileges required to manage VisionAdmin accounts.',
                unread_notifications=0,
                notifications=[]
            ), 403
        return render_template('visionadmin/users.html', page='users')

    @app.route('/visionadmin/catalog/products', methods=['GET'])
    @app.route('/visionadmin/products', methods=['GET'])
    @app.route('/visonadmin/catalog/products', methods=['GET'])
    @app.route('/visonadmin/products', methods=['GET'])
    @app.route('/admin/products', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_products():
        sets = AttributeService.get_attribute_sets()
        return render_template('visionadmin/products.html', page='products', is_catalog=True, initial_view='list', attribute_sets=sets)

    @app.route('/visionadmin/catalog/products/new', methods=['GET'])
    @app.route('/visionadmin/products/new', methods=['GET'])
    @app.route('/visionadmin/products/create', methods=['GET'])
    @app.route('/visonadmin/products/new', methods=['GET'])
    @app.route('/visonadmin/products/create', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_products_create():
        sets = AttributeService.get_attribute_sets()
        return render_template('visionadmin/product_form.html', page='products', is_catalog=True, initial_view='new', attribute_sets=sets)

    @app.route('/visionadmin/catalog/products/<int:product_id>/edit', methods=['GET'])
    @app.route('/visionadmin/products/<int:product_id>/edit', methods=['GET'])
    @app.route('/visonadmin/products/<int:product_id>/edit', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_products_edit(product_id):
        sets = AttributeService.get_attribute_sets()
        return render_template('visionadmin/product_form.html', page='products', is_catalog=True, initial_view='edit', initial_product_id=product_id, attribute_sets=sets)

    @app.route('/visionadmin/catalog/brands', methods=['GET'])
    @app.route('/visionadmin/brands', methods=['GET'])
    @app.route('/visonadmin/catalog/brands', methods=['GET'])
    @app.route('/visonadmin/brands', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_brands():
        return render_template('visionadmin/brands.html', page='brands', is_catalog=True)

    @app.route('/visionadmin/catalog/brands/new', methods=['GET'])
    @app.route('/visionadmin/brands/new', methods=['GET'])
    @app.route('/visionadmin/brands/create', methods=['GET'])
    @app.route('/visonadmin/brands/new', methods=['GET'])
    @app.route('/visonadmin/brands/create', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_brands_create():
        return render_template('visionadmin/brand_form.html', page='brands', is_catalog=True, initial_mode='create')

    @app.route('/visionadmin/catalog/brands/<int:brand_id>/edit', methods=['GET'])
    @app.route('/visionadmin/brands/<int:brand_id>/edit', methods=['GET'])
    @app.route('/visonadmin/brands/<int:brand_id>/edit', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_brands_edit(brand_id):
        return render_template('visionadmin/brand_form.html', page='brands', is_catalog=True, initial_mode='edit', initial_brand_id=brand_id)

    @app.route('/visionadmin/catalog/categories', methods=['GET'])
    @app.route('/visionadmin/categories', methods=['GET'])
    @app.route('/visonadmin/catalog/categories', methods=['GET'])
    @app.route('/visonadmin/categories', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_categories():
        cat_id = request.args.get('id', type=int) or 2
        return render_template('visionadmin/category_form.html', page='categories', is_catalog=True, initial_mode='edit', initial_cat_id=cat_id)

    @app.route('/visionadmin/catalog/categories/new', methods=['GET'])
    @app.route('/visionadmin/categories/new', methods=['GET'])
    @app.route('/visionadmin/categories/create', methods=['GET'])
    @app.route('/visonadmin/categories/new', methods=['GET'])
    @app.route('/visonadmin/categories/create', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_categories_create():
        return render_template('visionadmin/category_form.html', page='categories', is_catalog=True, initial_mode='create')

    @app.route('/visionadmin/catalog/categories/<int:cat_id>/edit', methods=['GET'])
    @app.route('/visionadmin/categories/<int:cat_id>/edit', methods=['GET'])
    @app.route('/visonadmin/categories/<int:cat_id>/edit', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_categories_edit(cat_id):
        return render_template('visionadmin/category_form.html', page='categories', is_catalog=True, initial_mode='edit', initial_cat_id=cat_id)

    @app.route('/visionadmin/attributes', methods=['GET'])
    @app.route('/visionadmin/catalog/attributes', methods=['GET'])
    @app.route('/visonadmin/attributes', methods=['GET'])
    @app.route('/visonadmin/catalog/attributes', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_attributes():
        sets = AttributeService.get_attribute_sets()
        return render_template('visionadmin/attributes.html', page='attributes', attribute_sets=sets)

    @app.route('/visionadmin/attributes/new', methods=['GET'])
    @app.route('/visionadmin/attributes/create', methods=['GET'])
    @app.route('/visionadmin/catalog/attributes/new', methods=['GET'])
    @app.route('/visionadmin/catalog/attributes/create', methods=['GET'])
    @app.route('/visonadmin/attributes/new', methods=['GET'])
    @app.route('/visonadmin/attributes/create', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_attributes_create():
        return render_template('visionadmin/attribute_form.html', page='attributes', initial_mode='create')

    @app.route('/visionadmin/attributes/<int:attr_id>/edit', methods=['GET'])
    @app.route('/visionadmin/catalog/attributes/<int:attr_id>/edit', methods=['GET'])
    @app.route('/visonadmin/attributes/<int:attr_id>/edit', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_attributes_edit(attr_id):
        return render_template('visionadmin/attribute_form.html', page='attributes', initial_mode='edit', initial_attr_id=attr_id)

    @app.route('/visionadmin/attribute-sets/new', methods=['GET'])
    @app.route('/visionadmin/attribute-sets/create', methods=['GET'])
    @app.route('/visionadmin/catalog/attribute-sets/new', methods=['GET'])
    @app.route('/visionadmin/catalog/attribute-sets/create', methods=['GET'])
    @app.route('/visonadmin/attribute-sets/new', methods=['GET'])
    @app.route('/visonadmin/attribute-sets/create', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_attribute_sets_create():
        sets = AttributeService.get_attribute_sets()
        return render_template('visionadmin/attribute_set_form.html', page='attributes', initial_mode='create', attribute_sets=sets)

    @app.route('/visionadmin/attribute-sets/<int:set_id>/edit', methods=['GET'])
    @app.route('/visionadmin/catalog/attribute-sets/<int:set_id>/edit', methods=['GET'])
    @app.route('/visonadmin/attribute-sets/<int:set_id>/edit', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_attribute_sets_edit(set_id):
        sets = AttributeService.get_attribute_sets()
        return render_template('visionadmin/attribute_set_form.html', page='attributes', initial_mode='edit', initial_set_id=set_id, attribute_sets=sets)

    @app.route('/visionadmin/attribute-sets/<int:set_id>/builder', methods=['GET'])
    @app.route('/visionadmin/attribute-sets/<int:set_id>/schema', methods=['GET'])
    @app.route('/visionadmin/catalog/attribute-sets/<int:set_id>/builder', methods=['GET'])
    @app.route('/visonadmin/attribute-sets/<int:set_id>/builder', methods=['GET'])
    @app.route('/visonadmin/attribute-sets/<int:set_id>/schema', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_attribute_sets_builder(set_id):
        sets = AttributeService.get_attribute_sets()
        return render_template('visionadmin/attribute_set_builder.html', page='attributes', initial_set_id=set_id, attribute_sets=sets)

    @app.route('/visionadmin/stores', methods=['GET'])
    @app.route('/visionadmin/websites', methods=['GET'])
    @app.route('/visionadmin/settings/stores', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_stores():
        return render_template('visionadmin/stores.html', page='stores')

    @app.route('/visionadmin/audit-logs', methods=['GET'])
    @app.route('/visionadmin/activity-logs', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_audit_logs():
        return render_template('visionadmin/audit_logs.html', page='audit_logs')

    @app.route('/visionadmin/scrapers', methods=['GET'])
    @app.route('/visionadmin/scraper', methods=['GET'])
    @app.route('/visionadmin/scraper-dashboard', methods=['GET'])
    @app.route('/visionadmin/files', methods=['GET'])
    @app.route('/visonadmin/scrapers', methods=['GET'])
    @app.route('/visonadmin/scraper', methods=['GET'])
    @app.route('/visonadmin/files', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_scrapers():
        return redirect('/tcsadmin/files')

    @app.route('/visionadmin/reports', methods=['GET'])
    @app.route('/visonadmin/reports', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_reports():
        return redirect('/tcsadmin/reports')

    # ========================================================================
    # 11. MARKETING - CART PRICE RULES ROUTES (cart_price_rules tables)
    # ========================================================================

    @app.route('/visionadmin/marketing/cart-price-rules', methods=['GET'])
    @app.route('/visonadmin/marketing/cart-price-rules', methods=['GET'])
    @app.route('/visionadmin/cart-price-rules', methods=['GET'])
    @app.route('/visonadmin/cart-price-rules', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_cart_price_rules_list():
        counts = CartPriceRuleService.get_counts()
        lookups = CartPriceRuleService.get_lookups()
        return render_template(
            'visionadmin/cart_price_rules.html',
            page='cart_price_rules',
            section='marketing',
            counts=counts,
            customer_groups=lookups.get('customer_groups', []),
            websites=lookups.get('websites', [])
        )

    @app.route('/visionadmin/api/cart-price-rules/data', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_cart_price_rules_data_api():
        search = request.args.get('search')
        status = request.args.get('status')
        coupon_type = request.args.get('coupon_type')
        customer_group_id = request.args.get('customer_group_id')
        website_id = request.args.get('website_id')
        if not website_id:
            active_scope = session.get('active_scope') or {}
            website_id = active_scope.get('website_id')

        sort_by = request.args.get('sort_by', 'priority')
        sort_dir = request.args.get('sort_dir', 'asc')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 25))

        res = CartPriceRuleService.get_rules(
            search=search,
            status=status,
            coupon_type=coupon_type,
            customer_group_id=customer_group_id,
            website_id=website_id,
            sort_by=sort_by,
            sort_dir=sort_dir,
            page=page,
            per_page=per_page
        )
        res['counts'] = CartPriceRuleService.get_counts()
        return jsonify(res)

    @app.route('/visionadmin/marketing/cart-price-rules/new', methods=['GET'])
    @app.route('/visonadmin/marketing/cart-price-rules/new', methods=['GET'])
    @app.route('/visionadmin/cart-price-rules/new', methods=['GET'])
    @app.route('/visonadmin/cart-price-rules/new', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_cart_price_rules_create():
        lookups = CartPriceRuleService.get_lookups()
        return render_template(
            'visionadmin/cart_price_rule_form.html',
            page='cart_price_rules',
            section='marketing',
            initial_mode='create',
            rule=None,
            lookups=lookups
        )

    @app.route('/visionadmin/api/cart-price-rules', methods=['POST'])
    @login_required_visionadmin
    def visionadmin_cart_price_rules_store_api():
        data = request.get_json(silent=True) or request.form.to_dict()
        try:
            admin_id = session.get('admin_user_id') or session.get('user_id')
            rule_id = CartPriceRuleService.create_rule(data, admin_id=admin_id)
            return jsonify({
                'success': True,
                'message': 'Cart price rule created successfully.',
                'rule_id': rule_id,
                'redirect': '/visionadmin/marketing/cart-price-rules'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/visionadmin/marketing/cart-price-rules/<int:rule_id>/edit', methods=['GET'])
    @app.route('/visonadmin/marketing/cart-price-rules/<int:rule_id>/edit', methods=['GET'])
    @app.route('/visionadmin/cart-price-rules/<int:rule_id>/edit', methods=['GET'])
    @app.route('/visonadmin/cart-price-rules/<int:rule_id>/edit', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_cart_price_rules_edit(rule_id):
        rule = CartPriceRuleService.get_rule(rule_id)
        if not rule:
            return render_template('404.html', requested_path=request.path), 404
        lookups = CartPriceRuleService.get_lookups()
        return render_template(
            'visionadmin/cart_price_rule_form.html',
            page='cart_price_rules',
            section='marketing',
            initial_mode='edit',
            rule=rule,
            lookups=lookups
        )

    @app.route('/visionadmin/api/cart-price-rules/<int:rule_id>', methods=['POST', 'PUT'])
    @login_required_visionadmin
    def visionadmin_cart_price_rules_update_api(rule_id):
        data = request.get_json(silent=True) or request.form.to_dict()
        try:
            admin_id = session.get('admin_user_id') or session.get('user_id')
            CartPriceRuleService.update_rule(rule_id, data, admin_id=admin_id)
            return jsonify({
                'success': True,
                'message': 'Cart price rule updated successfully.',
                'rule_id': rule_id,
                'redirect': '/visionadmin/marketing/cart-price-rules'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/visionadmin/api/cart-price-rules/<int:rule_id>', methods=['DELETE'])
    @login_required_visionadmin
    def visionadmin_cart_price_rules_delete_api(rule_id):
        try:
            is_hard = request.args.get('hard') in ('1', 'true', 'True') or request.args.get('permanent') in ('1', 'true')
            if is_hard:
                ok = CartPriceRuleService.hard_delete_rule(rule_id)
                msg = 'Cart price rule permanently deleted from database.'
            else:
                ok = CartPriceRuleService.delete_rule(rule_id)
                msg = 'Cart price rule moved to trash.'
            if not ok:
                return jsonify({'success': False, 'error': 'Rule not found.'}), 404
            return jsonify({'success': True, 'message': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/visionadmin/api/cart-price-rules/<int:rule_id>/hard-delete', methods=['POST', 'DELETE'])
    @login_required_visionadmin
    def visionadmin_cart_price_rules_hard_delete_api(rule_id):
        try:
            ok = CartPriceRuleService.hard_delete_rule(rule_id)
            if not ok:
                return jsonify({'success': False, 'error': 'Rule not found.'}), 404
            return jsonify({'success': True, 'message': 'Cart price rule permanently deleted from database.'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/visionadmin/api/cart-price-rules/<int:rule_id>/restore', methods=['POST'])
    @login_required_visionadmin
    def visionadmin_cart_price_rules_restore_api(rule_id):
        try:
            ok = CartPriceRuleService.restore_rule(rule_id)
            if not ok:
                return jsonify({'success': False, 'error': 'Rule not found in trash.'}), 404
            return jsonify({'success': True, 'message': 'Cart price rule restored successfully.'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/visionadmin/api/cart-price-rules/<int:rule_id>/coupons/data', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_cart_price_rules_coupons_data_api(rule_id):
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        search = request.args.get('search')
        res = CartPriceRuleService.get_coupons(rule_id, page=page, per_page=per_page, search=search)
        return jsonify(res)

    @app.route('/visionadmin/api/cart-price-rules/<int:rule_id>/coupons/generate', methods=['POST'])
    @login_required_visionadmin
    def visionadmin_cart_price_rules_coupons_generate_api(rule_id):
        data = request.get_json(silent=True) or request.form.to_dict()
        try:
            admin_id = session.get('admin_user_id') or session.get('user_id')
            count = CartPriceRuleService.generate_coupons(rule_id, data, admin_id=admin_id)
            return jsonify({'success': True, 'count': count, 'message': f'Generated {count} coupon codes successfully.'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    @app.route('/visionadmin/api/cart-price-rules/<int:rule_id>/coupons/export', methods=['GET'])
    @login_required_visionadmin
    def visionadmin_cart_price_rules_coupons_export(rule_id):
        coupons = CartPriceRuleService.get_export_coupons(rule_id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Code', 'Usage Limit', 'Used Count', 'Is Primary', 'Created At'])
        for c in coupons:
            writer.writerow([
                c['code'],
                c['usage_limit'] if c['usage_limit'] is not None else 'Unlimited',
                c['used_count'],
                'Yes' if c['is_primary'] else 'No',
                c['created_at'].isoformat() if hasattr(c['created_at'], 'isoformat') else str(c['created_at'])
            ])
        resp = make_response(output.getvalue())
        resp.headers['Content-Disposition'] = f'attachment; filename=rule-{rule_id}-coupons.csv'
        resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
        return resp

    @app.route('/visionadmin/api/cart-price-rules/<int:rule_id>/coupons/<int:coupon_id>', methods=['DELETE'])
    @login_required_visionadmin
    def visionadmin_cart_price_rules_coupon_delete_api(rule_id, coupon_id):
        try:
            ok = CartPriceRuleService.delete_coupon(rule_id, coupon_id)
            if not ok:
                return jsonify({'success': False, 'error': 'Coupon not found.'}), 404
            return jsonify({'success': True, 'message': 'Coupon code deleted successfully.'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
