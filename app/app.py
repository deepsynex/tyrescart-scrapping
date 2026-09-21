import os
import sys

# Ensure app directory, submodules, and project root are always in sys.path
_app_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_app_dir)
_scraperapp_dir = os.path.join(_app_dir, 'scraperapp')
_visionadmin_dir = os.path.join(_app_dir, 'visionadmin')
_siteapp_dir = os.path.join(_app_dir, 'siteapp')
_models_dir = os.path.join(_app_dir, 'models')
_scrapers_dir = os.path.join(_root_dir, 'scrapers')
for _p in reversed([_app_dir, _root_dir, _scraperapp_dir, _visionadmin_dir, _siteapp_dir, _models_dir, _scrapers_dir]):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from datetime import timedelta

from flask import Flask, jsonify, render_template, request, session, send_from_directory, g, redirect

from scraperapp.tcsadmin import register_tcsadmin_routes
from visionadmin import register_visionadmin_routes
from siteapp import site_bp
from api import register_api_routes
from api_versioning import inject_api_version_headers, register_version_endpoints

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, 'scrapers'))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static'),
)

# High-Performance HTTP Response Compression (Brotli + Gzip)
try:
    from flask_compress import Compress
    Compress(app)
    app.config['COMPRESS_ALGORITHM'] = ['brotli', 'gzip', 'deflate']
    app.config['COMPRESS_MIN_SIZE'] = 500
except ImportError:
    pass

# Flask-CKEditor Integration (Rich Text & Code Snippet / Source Editing)
from flask_ckeditor import CKEditor
app.config['CKEDITOR_PKG_TYPE'] = 'full-all'
app.config['CKEDITOR_SERVE_LOCAL'] = False
app.config['CKEDITOR_HEIGHT'] = 260
app.config['CKEDITOR_ENABLE_CODESNIPPET'] = True
app.config['CKEDITOR_CODE_THEME'] = 'monokai_sublime'
ckeditor = CKEditor(app)

app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'tyresvision-cms-secret-key-production-89f4b1e7c2a5d3e6')
app.permanent_session_lifetime = timedelta(days=7)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 604800  # 7 days browser cache for static files


from i18n import (
    get_locale as get_current_locale,
    translate as i18n_translate,
    is_rtl,
    get_translated_value,
    localize_value
)
from services.store_context import StoreContext


@app.before_request
def resolve_request_store_context():
    """Resolves active Website, Store, and Store View (Locale) context per HTTP request."""
    if request.path.startswith('/static/'):
        return
    try:
        StoreContext.resolve_current_context()
    except Exception:
        pass


@app.context_processor
def inject_i18n():
    """Provides dynamic multi-language translation helper, Store Context, and locale utilities."""
    current_lang = StoreContext.get_current_language()
    current_dir = StoreContext.get_current_direction()
    if request.path.startswith('/visionadmin') or request.path.startswith('/admin') or request.path.startswith('/visonadmin'):
        current_dir = 'ltr'

    def _(text):
        return i18n_translate(text, current_lang)

    return dict(
        _=_,
        locale=current_lang,
        current_language=current_lang,
        current_direction=current_dir,
        current_store=getattr(g, 'current_store', None),
        current_store_view=getattr(g, 'current_store_view', None),
        current_website=getattr(g, 'current_website', None),
        is_rtl=is_rtl,
        get_translated_value=get_translated_value,
        localize_value=localize_value
    )


@app.context_processor
def inject_page_seo():
    """Injects per-page OG tags and Schema.org JSON-LD into client templates from the pages table."""
    import json as _json

    # Only run for public client routes (not admin, API, or static)
    path = request.path
    if path.startswith(('/visionadmin', '/visonadmin', '/admin', '/tcsadmin', '/api/', '/static/')):
        return {}

    # Derive slug from path (strip leading slash and any trailing slash)
    slug = path.strip('/')
    if not slug:
        slug = 'home'

    try:
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT og_tags, schema_json FROM pages WHERE slug = %s AND deleted_at IS NULL AND is_active = 1',
                    (slug,)
                )
                row = cur.fetchone()
        finally:
            conn.close()

        if not row:
            return {}

        og_raw = row.get('og_tags') if isinstance(row, dict) else row[0]
        schema_raw = row.get('schema_json') if isinstance(row, dict) else row[1]

        og_data = {}
        if og_raw:
            try:
                og_data = _json.loads(og_raw) if isinstance(og_raw, str) else (og_raw or {})
            except Exception:
                og_data = {}

        og_tags = {k: v for k, v in og_data.items() if not k.startswith('twitter_') and v}
        twitter_tags = {k: v for k, v in og_data.items() if k.startswith('twitter_') and v}

        return dict(
            page_og_tags=og_tags,
            page_twitter_tags=twitter_tags,
            page_schema_json=schema_raw or '',
        )
    except Exception:
        return {}


@app.after_request
def add_performance_headers(response):
    """Adds caching headers for static assets, enables keep-alive, and injects API version headers."""
    if request.path.startswith('/static/visionadmin/') or request.path in (
        '/static/css/client.css', '/static/js/client.js', '/static/js/client-page-sections.js'
    ):
        # VisionAdmin's own CSS/JS, and the storefront's client.css/client.js/
        # client-page-sections.js, are actively developed and re-deployed
        # constantly — a 7-day browser/CDN cache was serving stale code long
        # after a fresh deploy (query-string cache-busting isn't reliable
        # against Cloudflare, which can cache each distinct ?v= value forever
        # rather than treating them as one revalidating resource).
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    elif request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=604800, stale-while-revalidate=86400'
    elif request.path.startswith(('/visionadmin', '/visonadmin', '/tcsadmin')):
        # Authenticated admin responses must never be stored. Without an explicit policy
        # here Cloudflare's Browser Cache TTL was stamping these pages with
        # `max-age=2678400`, pinning stale admin HTML in the browser for 31 days.
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return inject_api_version_headers(response)


# ============================================================================
# REGISTER PAGE ROUTES + CENTRALIZED API LAYER + VERSION CONTROL
#
#   tcsadmin.py            -> /tcsadmin/*   page routes (scraper admin)
#   Visionadminroute.py    -> /visionadmin/* page routes (CMS)
#   clientroute.py         -> /             page routes (public storefront)
#   api.py                 -> /tcsadmin/api/*, /visionadmin/api/*, /api/*
#   api_versioning.py      -> /api/v1/version, /visionadmin/api/v1/version
# ============================================================================

register_tcsadmin_routes(app)
register_visionadmin_routes(app)
app.register_blueprint(site_bp)
register_api_routes(app)
register_version_endpoints(app)


# ============================================================================
# MEDIA & IMAGE ASSETS ROUTING (FALLBACK PLACEHOLDER SUPPORT)
# ============================================================================

@app.route('/tyrescart/<path:filename>')
def serve_tyrescart_image(filename):
    """Serves tyrescart product images if available locally, else falls back to clean placeholder."""
    for folder in [
        os.path.join(app.static_folder, 'tyrescart'),
        os.path.join(app.static_folder, 'uploads', 'products'),
        os.path.join(app.static_folder, 'uploads'),
        os.path.join(BASE_DIR, 'tmp', 'tyrescart'),
    ]:
        target = os.path.join(folder, filename)
        if os.path.isfile(target):
            return send_from_directory(folder, filename)

    placeholder_dir = os.path.join(app.static_folder, 'assets', 'images')
    return send_from_directory(placeholder_dir, 'no-image-available.svg')


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def handle_404_error(e):
    """Gracefully handles unwanted page or API requests by serving custom 404, trailing-slash redirect, or image fallback."""
    raw_path = request.path
    if raw_path.endswith('/') and len(raw_path) > 1:
        clean_slash_path = raw_path.rstrip('/')
        try:
            adapter = app.url_map.bind(request.host, script_root=app.config.get('APPLICATION_ROOT', '') or '')
            adapter.match(clean_slash_path, method=request.method)
            qs = request.query_string.decode('utf-8')
            target = clean_slash_path + (f"?{qs}" if qs else "")
            return redirect(target, code=301)
        except Exception:
            pass

    clean_path = raw_path.lower().split('?')[0]
    if any(clean_path.endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.ico')):
        placeholder_dir = os.path.join(app.static_folder, 'assets', 'images')
        return send_from_directory(placeholder_dir, 'no-image-available.svg')

    if request.path.startswith(('/tcsadmin/api/', '/visionadmin/api/', '/api/')) or request.headers.get('Accept') == 'application/json':
        return jsonify({
            'error': 'The requested API resource was not found.',
            'status': 404,
            'path': request.path
        }), 404
    return render_template(
        '404.html',
        page='404',
        requested_path=request.path,
        user_name=session.get('name'),
        user_email=session.get('email'),
        user_role=session.get('role'),
        user_avatar=session.get('avatar'),
        unread_notifications=0,
        notifications=[]
    ), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8090))
    app.run(host="0.0.0.0", port=port, debug=True)
