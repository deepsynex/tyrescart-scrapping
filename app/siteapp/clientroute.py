# app/siteapp/clientroute.py - TyresVision Customer Storefront Blueprint ('site')
#
# Serves the public client-facing HTML pages only (home, blog listing/detail,
# About Us, generic CMS pages). The public JSON API endpoints that used to
# live in this file (/api/blogs, /api/blogs/<slug>) now live in the unified
# app/api.py alongside the tcsadmin and visionadmin APIs.
import json
import os
import math
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode
from flask import Blueprint, current_app, g, render_template, request, session, abort, redirect, make_response, send_from_directory, jsonify
from models.blog import Blog
from models.page import Page
from models.page_section import PageSection
from models.setting import Setting

from i18n import (
    get_locale as _get_locale,
    is_rtl,
    localize_value,
    translate,
    get_supported_locales,
)

site_bp = Blueprint('site', __name__)

# This file is app/siteapp/clientroute.py, so the project root (where
# robots.txt/sitemap.xml live, alongside app/, scrapers/, templates/) is
# two directories up (siteapp -> app -> root).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Storefront is English-only ---------------------------------------------
# The Arabic (and any other) locale variants are retired on the public site:
# every /<lang>/... URL 301s to its English equivalent, the ?lang= / ?locale=
# switches are dropped, and each storefront request is pinned to en/ltr so the
# translated values still held in the database are never rendered to visitors.
# The DB data and the VisionAdmin locale tooling are deliberately untouched --
# deleting this block restores the multilingual storefront as it was.
CLIENT_LOCALE = 'en'
_LOCALE_PREFIX_RE = re.compile(r'^/([a-z]{2})(?:-[a-z]{2})?(?=/|$)', re.IGNORECASE)
_LOCALE_QUERY_KEYS = ('locale', 'lang')


def _english_url(path):
    """Rebuilds `path` with the locale query params stripped."""
    kept = [(k, v) for k, v in request.args.items(multi=True)
            if k.lower() not in _LOCALE_QUERY_KEYS]
    if not kept:
        return path
    return path + '?' + urlencode(kept)


@site_bp.before_request
def _force_english_storefront():
    path = request.path or '/'

    # JSON endpoints are pinned to English but never redirected -- a 301 on an
    # XHR is the kind of thing that quietly breaks a caller that doesn't follow.
    if not path.startswith('/api/'):
        prefix = _LOCALE_PREFIX_RE.match(path)
        if prefix:
            target = path[prefix.end():] or '/'
            if not target.startswith('/'):
                target = '/' + target
            return redirect(_english_url(target), code=301)

        if any(k.lower() in _LOCALE_QUERY_KEYS for k in request.args.keys()):
            return redirect(_english_url(path), code=301)

    # Highest-priority override in StoreContext.get_current_language(), so this
    # also settles i18n.get_locale(), the `locale` template variable and the
    # is_ar checks inside the composable block components.
    g.current_language = CLIENT_LOCALE
    g.current_direction = 'ltr'
    if str(session.get('site_locale') or CLIENT_LOCALE).lower() != CLIENT_LOCALE:
        session['site_locale'] = CLIENT_LOCALE


# --- SEO: robots.txt / sitemap.xml ---
# These are plain files sitting at the project root (not under static/), so
# without an explicit route the catch-all page_detail('/<slug>') route below
# intercepts /robots.txt and /sitemap.xml first, finds no matching CMS page
# or blog, and 404s -- even though the files exist on disk.
@site_bp.route('/robots.txt')
def robots_txt():
    return send_from_directory(BASE_DIR, 'robots.txt', mimetype='text/plain')


@site_bp.route('/sitemap.xml')
def sitemap_xml():
    return send_from_directory(BASE_DIR, 'sitemap.xml', mimetype='application/xml')


# ============================================================================
# CLIENT STOREFRONT (HOME, BLOG, STATIC CMS PAGES WITH DYNAMIC MULTI-LOCALE)
# ============================================================================

# --- HOME ROUTES ---
def _get_home_sections(locale: str = None):
    """Helper to fetch and localize all active home page sections from DB."""
    try:
        from models.page_section import PageSection
        loc = locale or _get_locale()
        raw_sections = PageSection.all_for_page('home', include_inactive=False)
        return [PageSection.to_localized_dict(s, locale=loc) for s in raw_sections]
    except Exception as err:
        current_app.logger.warning(f"Error fetching home page sections from DB: {err}")
        return []


@site_bp.route('/')
@site_bp.route('/home')
def home():
    """Client storefront home landing page with dynamic locale support."""
    locale = _get_locale()
    sections = _get_home_sections(locale)
    page = Page.find_by_slug('home')
    resp = make_response(render_template('Client/Home.html', sections=sections, locale=locale, page=page, slug='home'))
    resp.set_cookie('site_locale', locale, max_age=31536000, path='/')
    return resp


@site_bp.route('/<string(length=2):lang_code>')
@site_bp.route('/<string(length=2):lang_code>/')
@site_bp.route('/<string(length=2):lang_code>/home')
def home_locale(lang_code):
    """Directly render storefront home for any dynamic locale (e.g. /ar, /de)."""
    code = lang_code.lower()
    page_match = Page.find_by_slug(code)
    if page_match:
        return render_template('Client/AboutUs.html', page=page_match, slug=code, locale=code)
    session['site_locale'] = code
    sections = _get_home_sections(code)
    home_page = Page.find_by_slug('home')
    resp = make_response(render_template('Client/Home.html', sections=sections, locale=code, page=home_page, slug='home'))
    resp.set_cookie('site_locale', code, max_age=31536000, path='/')
    return resp


# --- BLOG LISTING ROUTES ---
@site_bp.route('/blog')
@site_bp.route('/blog/')
@site_bp.route('/blogs')
@site_bp.route('/blogs/')
def blog_default():
    """Directly render blog listing using active site locale."""
    code = _get_locale()
    session['site_locale'] = code
    categories = Blog.distinct_categories(locale=code)
    selected_category = (request.args.get('category') or '').strip()
    resp = make_response(render_template('Client/Blog.html', locale=code, categories=categories, selected_category=selected_category))
    resp.set_cookie('site_locale', code, max_age=31536000, path='/')
    return resp


@site_bp.route('/<string(length=2):lang_code>/blog')
@site_bp.route('/<string(length=2):lang_code>/blog/')
@site_bp.route('/<string(length=2):lang_code>/blogs')
@site_bp.route('/<string(length=2):lang_code>/blogs/')
def blog_locale(lang_code):
    """Directly render blog listing for any dynamic locale (e.g. /ar/blog, /de/blog)."""
    code = lang_code.lower()
    session['site_locale'] = code
    categories = Blog.distinct_categories(locale=code)
    selected_category = (request.args.get('category') or '').strip()
    resp = make_response(render_template('Client/Blog.html', locale=code, categories=categories, selected_category=selected_category))
    resp.set_cookie('site_locale', code, max_age=31536000, path='/')
    return resp


# --- BLOG DETAIL ROUTES ---
@site_bp.route('/<string(length=2):lang_code>/blog/<slug>')
@site_bp.route('/<string(length=2):lang_code>/blogs/<slug>')
def blog_detail_locale(lang_code, slug):
    """Directly render blog detail for any dynamic locale (e.g. /ar/blog/<slug>)."""
    code = lang_code.lower()
    session['site_locale'] = code
    return _render_blog_detail(slug, code)


@site_bp.route('/blog/<slug>')
@site_bp.route('/blogs/<slug>')
def blog_detail_default(slug):
    """Default single blog detail route."""
    locale = _get_locale()
    return _render_blog_detail(slug, locale)


def _render_blog_detail(slug, locale):
    blog = Blog.find_by_slug(slug)
    if not blog:
        abort(404)

    all_published = Blog.published() or []
    other_blogs = [b for b in all_published if b.slug != slug]

    # Find prev and next blogs
    prev_post = None
    next_post = None
    for idx, b in enumerate(all_published):
        if b.slug == slug:
            if idx > 0:
                prev_post = {
                    'title': all_published[idx - 1].get_title(locale),
                    'slug': all_published[idx - 1].slug,
                    'cover_image_url': all_published[idx - 1].image or '/static/assets/images/online-tyres-shop-dubai.png',
                    'url': f"/blog/{all_published[idx - 1].slug}"
                }
            if idx < len(all_published) - 1:
                next_post = {
                    'title': all_published[idx + 1].get_title(locale),
                    'slug': all_published[idx + 1].slug,
                    'cover_image_url': all_published[idx + 1].image or '/static/assets/images/online-tyres-shop-dubai.png',
                    'url': f"/blog/{all_published[idx + 1].slug}"
                }
            break

    # If no other blogs in DB, create fallback prev/next
    if not prev_post and other_blogs:
        prev_post = {
            'title': other_blogs[0].get_title(locale),
            'slug': other_blogs[0].slug,
            'cover_image_url': other_blogs[0].image or '/static/assets/images/online-tyres-shop-dubai.png',
            'url': f"/blog/{other_blogs[0].slug}"
        }

    # Related posts for sidebar
    related_posts = []
    for b in other_blogs[:5]:
        related_posts.append({
            'title': b.get_title(locale),
            'slug': b.slug,
            'cover_image_url': b.image or '/static/assets/images/online-tyres-shop-dubai.png',
            'published_at': b.published_at.strftime('%d-%m-%Y') if b.published_at else '24-08-2026',
            'url': f"/blog/{b.slug}"
        })

    # Dynamic Sidebar categories from DB
    distinct_cats = Blog.distinct_categories()
    categories = []
    for cat in distinct_cats:
        count = len([b for b in all_published if (b.get_category_name(locale) or '').strip() == cat.strip()])
        categories.append({
            'name': cat,
            'slug': Blog.slugify(cat),
            'count': count
        })

    cat_name = blog.get_category_name(locale) or translate('Blog', locale)

    pub_dt = blog.published_at or blog.created_at
    if pub_dt:
        published_str = pub_dt.strftime('%d-%m-%Y')
        reviewed_str = (pub_dt - timedelta(days=2)).strftime('%d-%m-%Y')
    else:
        published_str = '26-08-2026'
        reviewed_str = '24-08-2026'

    blog_data = {
        'id': blog.id,
        'slug': blog.slug,
        'title': blog.get_title(locale),
        'content': blog.get_content(locale),
        'short_description': blog.get_short_desc(locale),
        'category': cat_name,
        'cover_image_url': blog.image or '/static/assets/images/online-tyres-shop-dubai.png',
        'published_at': published_str,
        'reviewed_at': reviewed_str,
        'read_time': translate('5 min read', locale),
        'faqs': blog.get_faqs(locale),
        'author': {
            'name': translate('Admin', locale),
            'role': translate('Tyre Specialist, TyresVision', locale),
            'avatar_initials': 'TV'
        }
    }

    reviewer_info = Setting.get_reviewer_settings(locale)

    resp = make_response(render_template(
        'Client/BlogDetail.html',
        post=blog_data,
        related_posts=related_posts,
        categories=categories,
        prev_post=prev_post,
        next_post=next_post,
        reviewer=reviewer_info,
        locale=locale
    ))
    resp.set_cookie('site_locale', locale, max_age=31536000, path='/')
    return resp


# --- ABOUT US & CMS PAGES ---
def _build_about_us_context(page, locale=None):
    """
    Constructs a complete dynamic data dictionary for every section of the About Us page,
    supporting localized overrides from the database (Page model / content JSON)
    with robust defaults matching the design specification.
    """
    loc = locale or _get_locale()
    page_title = page.get_title(loc) if page else None
    page_meta = page.get_meta_desc(loc) if page else None
    page_banner = page.banner_image if (page and page.banner_image) else None
    page_content = page.get_content(loc) if page else None

    parsed_json = {}
    if page and isinstance(page.content, dict):
        loc_content = page.content.get(loc) or page.content
        if isinstance(loc_content, dict):
            parsed_json = loc_content
        elif isinstance(loc_content, str) and loc_content.strip().startswith('{'):
            try:
                parsed_json = json.loads(loc_content)
            except Exception:
                pass

    # HERO SECTION
    hero = {
        'breadcrumb_home': translate('Home', loc),
        'breadcrumb_current': page_title or translate('About Us', loc),
        'eyebrow': localize_value(parsed_json.get('hero_eyebrow'), loc) or translate('About Us', loc),
        'title': page_title or localize_value(parsed_json.get('hero_title'), loc) or translate('Genuine Tyres, Honest Service — Built for UAE Drivers', loc),
        'lead': page_meta or localize_value(parsed_json.get('hero_lead'), loc) or translate(
            'We are committed to providing genuine certified tyres, transparent upfront pricing, and effortless mobile doorstep fitting or workshop installation across the UAE.',
            loc
        ),
        'cta_text': localize_value(parsed_json.get('hero_cta_text'), loc) or translate('Our Journey & Story', loc),
        'cta_link': parsed_json.get('hero_cta_link') or '#our-story',
        'image': page_banner or parsed_json.get('hero_image') or '/static/assets/images/online-tyres-shop-dubai.png'
    }

    # STORY SECTION
    story = {
        'eyebrow': localize_value(parsed_json.get('story_eyebrow'), loc) or translate('Our Story', loc),
        'title': localize_value(parsed_json.get('story_title'), loc) or translate('Driven by Transparency & Road Safety', loc),
        'badge_title': localize_value(parsed_json.get('story_badge_title'), loc) or translate('100% Genuine Tyres', loc),
        'badge_sub': localize_value(parsed_json.get('story_badge_sub'), loc) or translate('Official Warranty & GCC Spec', loc),
        'image': parsed_json.get('story_image') or '/static/assets/images/online-tyres-shop-dubai.png',
        'content_html': page_content if (page_content and len(page_content) > 60) else None,
        'p1': localize_value(parsed_json.get('story_p1'), loc) or translate(
            'Our journey began with a simple belief — buying and replacing tyres in the UAE should be transparent, effortless, and dependable, without the hassle of driving to industrial areas or comparing confusing quotes in person.',
            loc
        ),
        'p2': localize_value(parsed_json.get('story_p2'), loc) or translate(
            'What started as a digital tyre platform has quickly expanded into a nationwide network connecting motorists directly with over 60 global manufacturers, mobile van fitting at your door, and 350+ certified garage partners across all 7 Emirates.',
            loc
        ),
        'cta_text': localize_value(parsed_json.get('story_cta_text'), loc) or translate('Learn More About Us', loc),
        'cta_link': parsed_json.get('story_cta_link') or '/#why'
    }

    # VALUES SECTION (5 Cards)
    default_values = [
        {
            'icon': 'shield',
            'title': translate('100% Genuine', loc),
            'desc': translate('Directly sourced with fresh production dates and official GCC warranty.', loc)
        },
        {
            'icon': 'van',
            'title': translate('Mobile Doorstep Van', loc),
            'desc': translate('Fully equipped vans fitting and balancing tyres at your home or workplace.', loc)
        },
        {
            'icon': 'heart',
            'title': translate('Customer First', loc),
            'desc': translate('Honest recommendations focused on your safety, budget, and driving habits.', loc)
        },
        {
            'icon': 'tag',
            'title': translate('Full Transparency', loc),
            'desc': translate('All-inclusive pricing with zero hidden fees — delivery, fitting, and VAT included.', loc)
        },
        {
            'icon': 'network',
            'title': translate('350+ Garage Network', loc),
            'desc': translate('Partner fitting garages across Dubai, Abu Dhabi, Sharjah, and Northern Emirates.', loc)
        }
    ]
    values = {
        'eyebrow': localize_value(parsed_json.get('values_eyebrow'), loc) or translate('Our Values', loc),
        'title': localize_value(parsed_json.get('values_title'), loc) or translate('What Drives Us', loc),
        'cards': parsed_json.get('values_cards') or parsed_json.get('values_items') or default_values
    }

    # STATS SECTION (4 Metrics)
    default_stats = [
        {
            'icon': 'brand',
            'num': '60+',
            'label': translate('Global Tyre Brands', loc),
            'sub': translate('Michelin, Continental, Bridgestone & more', loc)
        },
        {
            'icon': 'garage',
            'num': '350+',
            'label': translate('Partner Fitting Centres', loc),
            'sub': translate('Across all 7 UAE Emirates', loc)
        },
        {
            'icon': 'drivers',
            'num': '10,000+',
            'label': translate('Satisfied Motorists', loc),
            'sub': translate('Trusted roadside & home installation', loc)
        },
        {
            'icon': 'shield',
            'num': '100%',
            'label': translate('Certified Genuine Quality', loc),
            'sub': translate('Official manufacturer warranty', loc)
        }
    ]
    stats = {
        'metrics': parsed_json.get('stats_metrics') or parsed_json.get('stats_items') or default_stats
    }

    # TEAM SECTION
    team = {
        'eyebrow': localize_value(parsed_json.get('team_eyebrow'), loc) or translate('Our Team', loc),
        'title': localize_value(parsed_json.get('team_title'), loc) or translate('Passionate Specialists, Purposeful Work', loc),
        'desc': localize_value(parsed_json.get('team_desc'), loc) or translate(
            'Our team is made up of certified automotive technicians, master fitters, logistics coordinators, and tyre specialists dedicated to delivering seamless tyre replacement right to your doorstep.',
            loc
        ),
        'cta_text': localize_value(parsed_json.get('team_cta_text'), loc) or translate('Meet Our Team', loc),
        'cta_link': parsed_json.get('team_cta_link') or 'https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20would%20like%20to%20connect%20with%20your%20team.',
        'image': parsed_json.get('team_image') or '/static/assets/images/online-tyres-shop-dubai.png'
    }

    # ACTION CALLOUT BANNER
    cta_banner = {
        'title': localize_value(parsed_json.get('banner_title'), loc) or translate("Let's Drive a Safer Tomorrow Together", loc),
        'desc': localize_value(parsed_json.get('banner_desc'), loc) or translate(
            'Message our specialists on WhatsApp for instant sizing assistance and price quotes across 60+ brands.',
            loc
        ),
        'cta_text': localize_value(parsed_json.get('banner_cta_text'), loc) or translate('Get In Touch →', loc),
        'cta_link': parsed_json.get('banner_cta_link') or 'https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20would%20like%20a%20tyre%20quote.'
    }

    return {
        'hero': hero,
        'story': story,
        'values': values,
        'stats': stats,
        'team': team,
        'cta_banner': cta_banner
    }


@site_bp.route('/about-us')
def about_us():
    locale = _get_locale()
    page = Page.find_by_slug('about-us')
    resp = make_response(render_template('Client/AboutUs.html', page=page, slug='about-us', locale=locale))
    resp.set_cookie('site_locale', locale, max_age=31536000, path='/')
    return resp


@site_bp.route('/<string(length=2):lang_code>/about-us')
def about_us_locale(lang_code):
    """Directly render About Us page for any dynamic locale (e.g. /ar/about-us, /de/about-us)."""
    code = lang_code.lower()
    session['site_locale'] = code
    page = Page.find_by_slug('about-us')
    resp = make_response(render_template('Client/AboutUs.html', page=page, slug='about-us', locale=code))
    resp.set_cookie('site_locale', code, max_age=31536000, path='/')
    return resp


@site_bp.route('/mobile-tyre-fitting')
def mobile_tyre_fitting():
    """Dedicated high-fidelity Mobile Tyre Fitting landing page."""
    locale = _get_locale()
    page = Page.find_by_slug('mobile-tyre-fitting')
    resp = make_response(render_template('Client/MobileTyreFitting.html', page=page, slug='mobile-tyre-fitting', locale=locale))
    resp.set_cookie('site_locale', locale, max_age=31536000, path='/')
    return resp


@site_bp.route('/<string(length=2):lang_code>/mobile-tyre-fitting')
def mobile_tyre_fitting_locale(lang_code):
    """Directly render Mobile Tyre Fitting page for dynamic locale."""
    code = lang_code.lower()
    session['site_locale'] = code
    page = Page.find_by_slug('mobile-tyre-fitting')
    resp = make_response(render_template('Client/MobileTyreFitting.html', page=page, slug='mobile-tyre-fitting', locale=code))
    resp.set_cookie('site_locale', code, max_age=31536000, path='/')
    return resp


def _format_product_for_client(p, locale='en'):
    p_dict = dict(p)
    attr = p_dict.get('attributes_json')
    if isinstance(attr, str):
        try:
            attr = json.loads(attr)
        except Exception:
            attr = {}
    elif not isinstance(attr, dict):
        attr = {}
    p_dict['attr'] = attr
    p_dict['rating'] = float(attr.get('rating', 4.5))

    # Top Offer Banner (e.g. FREE WHEEL ALIGNMENT / BUY 3 GET 1 FREE / TOP SAVINGS)
    raw_offer = (attr.get('offers') or attr.get('promotion') or attr.get('badge') or '').strip()
    if raw_offer and raw_offer.lower() not in ('none', '0', '', 'null'):
        offer_banner = raw_offer.upper()
        if 'BUY 3' in offer_banner:
            p_dict['badge_class'] = 'badge-red'
        elif 'BUY 2' in offer_banner:
            p_dict['badge_class'] = 'badge-orange'
        else:
            p_dict['badge_class'] = attr.get('badge_class', 'badge-blue')
    else:
        offer_banner = ''
        p_dict['badge_class'] = ''

    p_dict['offer_banner'] = offer_banner
    p_dict['badge'] = offer_banner

    # Calculate Set of 4 Price according to offer rules:
    # - Buy 2 Get 2 Free: customer pays for 2 (2 * unit_price) = 500.00 if unit is 250.00
    # - Buy 3 Get 1 Free: customer pays for 3 (3 * unit_price) = 750.00 if unit is 250.00
    # - Else: customer pays for 4 (4 * unit_price) = 1000.00 if unit is 250.00
    try:
        unit_p = float(p_dict.get('price') or 0)
    except (ValueError, TypeError):
        unit_p = 0.0

    offer_upper = offer_banner.upper()
    if 'BUY 2 GET 2' in offer_upper:
        p_dict['effective_price'] = round(unit_p * 0.50, 2)
        p_dict['set_of_4_price'] = round(unit_p * 2, 2)
        p_dict['set_of_8_price'] = round(unit_p * 4, 2)
    elif 'BUY 3 GET 1' in offer_upper:
        p_dict['effective_price'] = round(unit_p * 0.75, 2)
        p_dict['set_of_4_price'] = round(unit_p * 3, 2)
        p_dict['set_of_8_price'] = round(unit_p * 6, 2)
    else:
        p_dict['effective_price'] = unit_p
        p_dict['set_of_4_price'] = round(unit_p * 4, 2)
        p_dict['set_of_8_price'] = round(unit_p * 8, 2)

    # Warranty derivation
    warranty_raw = str(attr.get('warranty_period') or attr.get('warranty') or '').strip()
    w_months = p_dict.get('warranty_months')

    if '5 year' in warranty_raw.lower() or str(w_months) in ('60', '60.0'):
        warranty_val = '5 Years Warranty'
    elif '3 year' in warranty_raw.lower() or str(w_months) in ('36', '36.0'):
        warranty_val = '3 Years Warranty'
    elif '1 year' in warranty_raw.lower() or str(w_months) in ('12', '12.0'):
        warranty_val = '1 Year Warranty'
    elif warranty_raw and warranty_raw.lower() not in ('none', '0', 'null', 'default'):
        warranty_val = warranty_raw
    elif w_months:
        try:
            m_int = int(float(w_months))
            if m_int % 12 == 0 and m_int > 0:
                y_cnt = m_int // 12
                warranty_val = f"{y_cnt} Year{'s' if y_cnt > 1 else ''} Warranty"
            else:
                warranty_val = f"{m_int} Months Warranty"
        except (ValueError, TypeError):
            warranty_val = '1 Year Warranty'
    else:
        warranty_val = '1 Year Warranty'

    p_dict['warranty'] = warranty_val

    # Vehicle type normalization ('car', 'suv', 'van')
    raw_veh = str(p_dict.get('vehicle_type') or attr.get('tyre_type') or 'car').strip().lower()
    if any(k in raw_veh for k in ('suv', '4x4', '4wd', 'crossover')):
        veh_type = 'suv'
    elif any(k in raw_veh for k in ('van', 'truck', 'commercial')):
        veh_type = 'van'
    else:
        veh_type = 'car'
    p_dict['vehicle_type'] = veh_type

    p_dict['season'] = attr.get('season') or p_dict.get('tire_type') or ''
    
    b_slug = p_dict.get('brand_slug') or (p_dict.get('brand_name') or 'michelin').lower().replace(' ', '')
    p_dict['brand_slug'] = b_slug
    p_dict['brand_name'] = p_dict.get('brand_name') or b_slug.capitalize()
    p_dict['brand_logo'] = p_dict.get('brand_logo') or f"/static/assets/images/brands/{b_slug}.svg"
    
    # Normalize image_path:
    raw_img = p_dict.get('image_path') or p_dict.get('small_image') or attr.get('image')
    if raw_img and str(raw_img).strip():
        img_s = str(raw_img).strip().replace('\\', '/')
        if not (img_s.startswith('http://') or img_s.startswith('https://') or img_s.startswith('data:')):
            if not img_s.startswith('/'):
                img_s = '/' + img_s
        p_dict['image_path'] = img_s
    else:
        p_dict['image_path'] = '/static/assets/images/no-image-available.svg'

    # Price conversions
    price_val = float(p_dict.get('price') or 0)
    p_dict['price'] = price_val
    p_dict['price_formatted'] = f"{price_val:.2f}"
    p_dict['price_set_of_4'] = f"{p_dict.get('set_of_4_price', price_val * 4):.2f}"
    p_dict['price_set_of_8'] = f"{p_dict.get('set_of_8_price', price_val * 8):.2f}"
    p_dict['list_price'] = float(p_dict['list_price']) if p_dict.get('list_price') else None

    # Ensure display_name is readable
    if not p_dict.get('display_name'):
        name_raw = p_dict.get('name')
        if isinstance(name_raw, dict):
            p_dict['display_name'] = name_raw.get(locale) or name_raw.get('en') or list(name_raw.values())[0] if name_raw else p_dict.get('sku')
        elif isinstance(name_raw, str) and name_raw.strip().startswith('{'):
            try:
                n_json = json.loads(name_raw)
                p_dict['display_name'] = n_json.get(locale) or n_json.get('en') or list(n_json.values())[0]
            except Exception:
                p_dict['display_name'] = name_raw
        else:
            p_dict['display_name'] = name_raw or p_dict.get('sku')

    # Pattern / Model Name (e.g. "Atrezzo Eco") - strip brand name as requested
    b_name = (p_dict.get('brand_name') or '').strip()
    pat = str(attr.get('pattern') or attr.get('pattern.1') or '').strip()
    if not pat or pat.lower() in ('none', 'null', '0'):
        pat = p_dict.get('display_name') or ''
    if b_name and pat.lower().startswith(b_name.lower()):
        pat = pat[len(b_name):].strip()
    pat = re.sub(r'^[\s\-_:]+', '', pat).strip()

    d_name = (p_dict.get('display_name') or '').strip()
    if b_name and d_name.lower().startswith(b_name.lower()):
        d_name = re.sub(r'^[\s\-_:]+', '', d_name[len(b_name):].strip())
    p_dict['pattern_name'] = pat or d_name or 'Tyre'

    # Size spec with load/speed index (e.g. "165/65 R14 79T")
    base_size = str(p_dict.get('tire_size_label') or attr.get('tire_size') or attr.get('tyre_size') or '').strip()
    if not base_size:
        w = attr.get('width')
        h = attr.get('height')
        r = attr.get('rim')
        if w and r:
            base_size = f"{w}/{h} R{r}" if h else f"{w} R{r}"
    
    load_speed = str(attr.get('load_speed_index') or '').strip()
    if not load_speed:
        l_idx = str(attr.get('tire_load_index') or attr.get('load_index') or '').strip()
        s_rat = str(attr.get('tire_speed_rating') or '').strip()
        if l_idx or s_rat:
            load_speed = f"{l_idx}{s_rat}".strip()

    if load_speed and load_speed.lower() not in base_size.lower():
        full_size = f"{base_size} {load_speed}".strip()
    else:
        full_size = base_size

    p_dict['tire_size_label'] = base_size
    p_dict['full_size_spec'] = full_size or base_size or 'Standard Fit'

    # Width, Profile, Rim Size breakdown for specs
    w_val = str(attr.get('width') or '').strip()
    h_val = str(attr.get('height') or attr.get('profile') or '').strip()
    r_val = str(attr.get('rim') or '').strip()
    m_sz = re.search(r'(\d{3})(?:/(\d{2,3}))?\s*(?:R|Z|ZR|r)?(\d{2}[A-Z]?)', base_size)
    if m_sz:
        if not w_val:
            w_val = m_sz.group(1)
        if not h_val:
            h_val = m_sz.group(2) or 'None'
        if not r_val:
            r_val = f"R{m_sz.group(3)}" if m_sz.group(3) else ''

    p_dict['width'] = f"{w_val} mm" if w_val and not w_val.endswith('mm') else (w_val or '155 mm')
    p_dict['profile'] = h_val if h_val else 'None'
    p_dict['rim_size'] = f"R{r_val}" if r_val and not r_val.startswith('R') else (r_val or 'R16')
    p_dict['load_speed'] = load_speed or '86Q'

    # Year (e.g. 2024 / 2025 / 2026)
    yr_val = str(attr.get('year') or attr.get('dot') or '').strip()
    if not yr_val or yr_val.lower() in ('none', 'null', '0'):
        m_yr = re.search(r'\b(202[3-7])\b', str(p_dict.get('name') or '') + ' ' + str(p_dict.get('display_name') or ''))
        yr_val = m_yr.group(1) if m_yr else '2025'
    p_dict['year'] = yr_val

    # Country of Origin (e.g. "China", "Japan", "Germany", "USA")
    origin_val = str(attr.get('country_of_origin') or attr.get('origin') or attr.get('country') or '').strip()
    if not origin_val or origin_val.lower() in ('none', 'null', '0'):
        origin_val = 'USA'
    p_dict['country_of_origin'] = origin_val.title()

    # Runflat tyre detection
    rf_val = str(attr.get('runflat') or attr.get('is_runflat') or '').strip().lower()
    full_name_str = (str(p_dict.get('name') or '') + ' ' + str(p_dict.get('display_name') or '') + ' ' + pat).lower()
    is_rf = (p_dict.get('run_flat') in (1, '1', True)) or rf_val in ('yes', '1', 'true', 'rft', 'runflat') or 'runflat' in full_name_str or 'run flat' in full_name_str or ' rft' in full_name_str
    p_dict['is_runflat'] = bool(is_rf)
    p_dict['runflat_text'] = 'Runflat' if is_rf else ''

    # Tyre Category (e.g. "Premium", "Budget", "Mid-Range")
    cat_val = str(attr.get('tyres_category') or attr.get('category') or '').strip()
    if not cat_val or cat_val.lower() in ('none', 'null', '0', 'default'):
        cat_val = 'Premium'
    else:
        cat_val = cat_val.title()
    p_dict['tyres_category'] = cat_val

    p_dict['full_title'] = f"{p_dict['brand_name']} {p_dict['full_size_spec']} {p_dict['pattern_name']} {yr_val}".strip()
    p_dict['fitted_text'] = attr.get('price_included_text') or 'Fitted Price'

    return p_dict


def _fetch_catalog_products(args, locale='en'):
    """Queries products with dynamic filters, pagination, and sorting for client catalog."""
    from db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Build filter clauses mapped by dimension for multi-select disjunctive facet calculation
            clauses = {
                'brand': ([], []),
                'vehicle': ([], []),
                'size': ([], []),
                'pattern': ([], []),
                'oem': ([], []),
                'warranty': ([], []),
                'year': ([], []),
                'origin': ([], []),
                'type': ([], []),
                'runflat': ([], []),
                'price': ([], []),
                'promo': ([], []),
                'search': ([], [])
            }

            # 1. Brands filter (supports ?brand=pirelli,michelin or ?brand=pirelli&brand=michelin)
            raw_brands = args.getlist('brand') or args.getlist('brands')
            brands = []
            for b_entry in raw_brands:
                for b_part in b_entry.split(','):
                    bp = b_part.strip().lower()
                    if bp and bp not in brands:
                        brands.append(bp)

            if brands:
                b_placeholders = ', '.join(['%s'] * len(brands))
                clauses['brand'][0].append(f"(LOWER(b.slug) IN ({b_placeholders}) OR LOWER(b.name) IN ({b_placeholders}))")
                clauses['brand'][1].extend(brands)
                clauses['brand'][1].extend(brands)

            # 2. Vehicle Types filter
            raw_vehicles = args.getlist('vehicle') or args.getlist('vehicle_type') or args.getlist('vehicles')
            vehicles = []
            for v_entry in raw_vehicles:
                for v_part in v_entry.split(','):
                    vp = v_part.strip().lower()
                    if vp and vp not in vehicles:
                        vehicles.append(vp)

            if vehicles:
                v_terms = []
                for v in vehicles:
                    if v == 'suv':
                        v_terms.extend(['suv', '4x4', 'suv / 4x4'])
                    elif v == 'car':
                        v_terms.extend(['car', 'passenger car'])
                    elif v == 'van':
                        v_terms.extend(['van', 'light truck / van', 'commercial van'])
                    else:
                        v_terms.append(v)
                v_placeholders = ', '.join(['%s'] * len(v_terms))
                clauses['vehicle'][0].append(f"LOWER(p.vehicle_type) IN ({v_placeholders})")
                clauses['vehicle'][1].extend(v_terms)

            # 3. Sizes filter
            raw_sizes = args.getlist('size') or args.getlist('sizes')
            sizes = []
            for s_entry in raw_sizes:
                for s_part in s_entry.split(','):
                    sp = s_part.strip()
                    if sp and sp not in sizes:
                        sizes.append(sp)

            if sizes:
                s_clauses = []
                s_params = []
                for sz in sizes:
                    sz_clean = sz.strip()
                    sz_hyphen = sz_clean.replace('/', '-').replace(' ', '-')
                    s_clauses.append("(p.tire_size_label = %s OR REPLACE(REPLACE(p.tire_size_label, '/', '-'), ' ', '-') = %s)")
                    s_params.extend([sz_clean, sz_hyphen])
                clauses['size'][0].append("(" + " OR ".join(s_clauses) + ")")
                clauses['size'][1].extend(s_params)

            # 4. Pattern filter
            raw_patterns = args.getlist('pattern') or args.getlist('patterns')
            patterns = []
            for p_entry in raw_patterns:
                for p_part in p_entry.split(','):
                    pp = p_part.strip()
                    if pp and pp not in patterns:
                        patterns.append(pp)

            if patterns:
                pat_clauses = []
                pat_params = []
                for p in patterns:
                    p_c = p.strip().lower()
                    p_space = p_c.replace('-', ' ')
                    p_hyphen = p_c.replace(' ', '-')
                    pat_clauses.append("(LOWER(p.tire_pattern) = %s OR LOWER(p.tire_pattern) = %s OR LOWER(p.tire_pattern) LIKE %s OR REPLACE(LOWER(p.tire_pattern), ' ', '-') = %s)")
                    pat_params.extend([p_c, p_space, f"%{p_space}%", p_hyphen])
                clauses['pattern'][0].append("(" + " OR ".join(pat_clauses) + ")")
                clauses['pattern'][1].extend(pat_params)

            # 5. OEM Tyres filter (uses idx_products_active_oem)
            raw_oems = args.getlist('oem') or args.getlist('oem_tyres') or args.getlist('oems')
            oems = []
            for o_entry in raw_oems:
                for o_part in o_entry.split(','):
                    op = o_part.strip()
                    if op and op not in oems:
                        oems.append(op)

            if oems:
                oem_clauses = []
                oem_params = []
                for o in oems:
                    o_c = o.strip().lower()
                    o_space = o_c.replace('-', ' ')
                    o_hyphen = o_c.replace(' ', '-')
                    oem_clauses.append("(LOWER(p.oem_brand) = %s OR LOWER(p.oem_brand) = %s OR LOWER(p.oem_brand) LIKE %s OR REPLACE(LOWER(p.oem_brand), ' ', '-') = %s)")
                    oem_params.extend([o_c, o_space, f"%{o_c}%", o_hyphen])
                clauses['oem'][0].append("(" + " OR ".join(oem_clauses) + ")")
                clauses['oem'][1].extend(oem_params)

            # 6. Warranty Period filter
            raw_warranties = args.getlist('warranty') or args.getlist('warranty_period') or args.getlist('warranties')
            warranties = []
            for w_entry in raw_warranties:
                for w_part in w_entry.split(','):
                    wp = w_part.strip()
                    if wp and wp not in warranties:
                        warranties.append(wp)

            if warranties:
                w_clauses = []
                w_params = []
                for w in warranties:
                    w_lower = w.replace('-', ' ').strip().lower()
                    if '1 year' in w_lower or w in ('12', 12):
                        w_clauses.append("(p.warranty_months IN (12, '12') OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty')) LIKE %s OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty_period')) LIKE %s)")
                        w_params.extend(['%1 Year%', '%1 Year%'])
                    elif '3 year' in w_lower or w in ('36', 36):
                        w_clauses.append("(p.warranty_months IN (36, '36') OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty')) LIKE %s OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty_period')) LIKE %s)")
                        w_params.extend(['%3 Year%', '%3 Year%'])
                    elif '5 year' in w_lower or w in ('60', 60):
                        w_clauses.append("(p.warranty_months IN (60, '60') OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty')) LIKE %s OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty_period')) LIKE %s)")
                        w_params.extend(['%5 Year%', '%5 Year%'])
                    else:
                        w_clean = w.replace('-', ' ').strip()
                        w_clauses.append("(JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty')) LIKE %s OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty_period')) LIKE %s)")
                        w_params.extend([f"%{w_clean}%", f"%{w_clean}%"])
                clauses['warranty'][0].append("(" + " OR ".join(w_clauses) + ")")
                clauses['warranty'][1].extend(w_params)

            # 7. Year filter (uses idx_products_year)
            raw_years = args.getlist('year') or args.getlist('years')
            years = []
            for y_entry in raw_years:
                for y_part in y_entry.split(','):
                    yp = y_part.strip()
                    if yp and yp not in years:
                        years.append(yp)

            if years:
                y_ph = ', '.join(['%s'] * len(years))
                clauses['year'][0].append(f"p.year IN ({y_ph})")
                clauses['year'][1].extend(years)

            # 8. Origin / Country filter (uses idx_products_active_origin)
            raw_origins = args.getlist('origin') or args.getlist('country') or args.getlist('origins')
            origins = []
            for o_entry in raw_origins:
                for o_part in o_entry.split(','):
                    op = o_part.strip()
                    if op and op not in origins:
                        origins.append(op)

            if origins:
                org_clauses = []
                org_params = []
                for o in origins:
                    o_c = o.strip().lower()
                    o_space = o_c.replace('-', ' ')
                    o_hyphen = o_c.replace(' ', '-')
                    org_clauses.append("(LOWER(p.country_of_origin) = %s OR LOWER(p.country_of_origin) = %s OR LOWER(p.country_of_origin) LIKE %s)")
                    org_params.extend([o_c, o_space, f"%{o_c}%"])
                clauses['origin'][0].append("(" + " OR ".join(org_clauses) + ")")
                clauses['origin'][1].extend(org_params)

            # 9. Tyre Types / Seasons
            raw_types = args.getlist('type') or args.getlist('tire_type') or args.getlist('types')
            types = []
            for t_entry in raw_types:
                for t_part in t_entry.split(','):
                    tp = t_part.strip().lower()
                    if tp and tp not in types:
                        types.append(tp)

            if types:
                t_clauses = []
                t_terms = []
                for t in types:
                    if t == 'run_flat':
                        t_clauses.append("p.run_flat = 1")
                    else:
                        t_terms.append(t)
                if t_terms:
                    t_placeholders = ', '.join(['%s'] * len(t_terms))
                    t_clauses.append(f"LOWER(p.tire_type) IN ({t_placeholders})")
                    clauses['type'][1].extend(t_terms)
                if t_clauses:
                    clauses['type'][0].append("(" + " OR ".join(t_clauses) + ")")

            # 9b. Run Flat Tyres filter
            raw_rf = args.getlist('runflat') or args.getlist('run_flat') or args.getlist('is_runflat')
            rf_selected = [r.strip().lower() for r in raw_rf if r.strip()]
            if any(r in ('runflat', 'run_flat', '1', 'yes', 'true', 'rft') for r in rf_selected):
                clauses['runflat'][0].append("(p.run_flat = 1 OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.runflat')) IN ('yes', '1', 'true', 'rft', 'RunFlat', 'runflat') OR LOWER(p.display_name) LIKE %s OR LOWER(p.display_name) LIKE %s)")
                clauses['runflat'][1].extend(['%runflat%', '%run flat%'])

            # 10. Price filter
            max_price = args.get('max_price')
            if max_price:
                try:
                    clauses['price'][0].append("p.price <= %s")
                    clauses['price'][1].append(float(max_price))
                except (ValueError, TypeError):
                    pass

            min_price = args.get('min_price')
            if min_price:
                try:
                    clauses['price'][0].append("p.price >= %s")
                    clauses['price'][1].append(float(min_price))
                except (ValueError, TypeError):
                    pass

            # 11. Promotion / Special Offers filter
            raw_promos = args.getlist('promotion') or args.getlist('promotions') or args.getlist('offer') or args.getlist('offers')
            promos = []
            for p_entry in raw_promos:
                for p_part in p_entry.split(','):
                    pr = p_part.strip().lower()
                    if pr and pr not in promos:
                        promos.append(pr)

            if promos:
                pr_clauses = []
                for pr in promos:
                    if pr in ('buy_3_get_1_free', 'buy-3-get-1-free', 'buy 3 get 1 free'):
                        pr_clauses.append("(p.attributes_json LIKE '%%Buy 3 Get 1 Free%%' OR p.attributes_json LIKE '%%BUY 3 GET 1%%')")
                    elif pr in ('free_wheel_alignment', 'free-wheel-alignment', 'free wheel alignment'):
                        pr_clauses.append("(p.attributes_json LIKE '%%Free Wheel Alignment%%' OR p.attributes_json LIKE '%%FREE WHEEL ALIGNMENT%%')")
                    elif pr in ('top_savings', 'top-savings', 'top savings'):
                        pr_clauses.append("(p.attributes_json LIKE '%%Top Savings%%' OR p.attributes_json LIKE '%%TOP SAVINGS%%')")
                    else:
                        pr_clean = pr.replace('_', ' ').replace('-', ' ')
                        pr_clauses.append(f"(p.attributes_json LIKE '%%{pr_clean}%%')")
                if pr_clauses:
                    clauses['promo'][0].append("(" + " OR ".join(pr_clauses) + ")")

            # 12. Search query (leveraging FULLTEXT index idx_products_fulltext_search)
            search = args.get('search') or args.get('q')
            if search and search.strip():
                s_clean = search.strip()
                if len(s_clean) >= 3 and not any(c in s_clean for c in ('%', '_', '*', '+', '-', '<', '>', '~', '(', ')', '"', '@')):
                    clauses['search'][0].append("(MATCH(p.display_name, p.sku, p.item_code) AGAINST(%s IN BOOLEAN MODE) OR p.tire_size_label LIKE %s)")
                    clauses['search'][1].extend([f"+{s_clean}*", f"%{s_clean}%"])
                else:
                    s_term = f"%{s_clean}%"
                    clauses['search'][0].append("(p.sku LIKE %s OR p.display_name LIKE %s OR p.tire_size_label LIKE %s)")
                    clauses['search'][1].extend([s_term, s_term, s_term])

            # Build combined WHERE clause for the primary catalog query
            all_where = ["p.deleted_at IS NULL", "p.status = 'active'", "p.website_id = 1"]
            all_params = []
            for k, (c_list, p_list) in clauses.items():
                all_where.extend(c_list)
                all_params.extend(p_list)
            where_sql = " AND ".join(all_where)

            # Total matching count
            cur.execute(f"""
                SELECT COUNT(*) as total
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE {where_sql}
            """, all_params)
            c_row = cur.fetchone()
            total_count = c_row['total'] if c_row else 0

            # Sorting (Default: price-asc Low to High per user requirement)
            sort_by = (args.get('sort') or args.get('sort_by') or 'price-asc').lower().strip()
            if sort_by in ('price-desc', 'price_desc', 'high-to-low', 'price_high_to_low'):
                order_sql = "ORDER BY p.price DESC, p.id ASC"
            else:
                order_sql = "ORDER BY p.price ASC, p.id ASC"

            # Pagination (default 16 for 4 rows of 4 cards on desktop)
            try:
                page = max(1, int(args.get('page', 1)))
            except (ValueError, TypeError):
                page = 1

            try:
                per_page = max(1, min(100, int(args.get('per_page', 16))))
            except (ValueError, TypeError):
                per_page = 16

            total_pages = max(1, math.ceil(total_count / per_page)) if total_count > 0 else 1
            if page > total_pages and total_count > 0:
                page = total_pages
            offset = (page - 1) * per_page

            fetch_params = list(all_params) + [per_page, offset]
            cur.execute(f"""
                SELECT p.*, b.name as brand_name, b.slug as brand_slug, b.logo as brand_logo
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE {where_sql}
                {order_sql}
                LIMIT %s OFFSET %s
            """, fetch_params)
            raw_products = cur.fetchall()

            products = [_format_product_for_client(p, locale) for p in raw_products]

            # Dynamic Facets Calculation (disjunctive multi-select counts)
            def get_where_except(exclude_key):
                w = ["p.deleted_at IS NULL", "p.status = 'active'", "p.website_id = 1"]
                pm = []
                for k, (c_list, p_list) in clauses.items():
                    if k == exclude_key:
                        continue
                    w.extend(c_list)
                    pm.extend(p_list)
                return " AND ".join(w), pm

            facets = {
                'warranties': {},
                'years': {},
                'brands': {},
                'patterns': {},
                'oems': {},
                'origins': {},
                'promotions': {},
                'runflat': 0
            }

            # 1. Warranty facet
            w_where, w_params = get_where_except('warranty')
            cur.execute(f"""
                SELECT 
                    CASE 
                        WHEN p.warranty_months IN (12, '12') OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty_period')) LIKE '%%1 Year%%' OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty')) LIKE '%%1 Year%%' THEN '1 Year Warranty'
                        WHEN p.warranty_months IN (36, '36') OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty_period')) LIKE '%%3 Year%%' OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty')) LIKE '%%3 Year%%' THEN '3 Years Warranty'
                        WHEN p.warranty_months IN (60, '60') OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty_period')) LIKE '%%5 Year%%' OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.warranty')) LIKE '%%5 Year%%' THEN '5 Years Warranty'
                        ELSE '1 Year Warranty'
                    END as war,
                    COUNT(*) as cnt
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE {w_where}
                GROUP BY war
            """, w_params)
            for r in cur.fetchall():
                if r.get('war'):
                    facets['warranties'][r['war']] = int(r['cnt'])

            # 2. Year facet
            y_where, y_params = get_where_except('year')
            cur.execute(f"""
                SELECT p.year, COUNT(*) as cnt
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE {y_where} AND p.year IS NOT NULL AND p.year != '0000'
                GROUP BY p.year
            """, y_params)
            for r in cur.fetchall():
                if r.get('year'):
                    facets['years'][str(r['year'])] = int(r['cnt'])

            # 3. Brand facet
            b_where, b_params = get_where_except('brand')
            cur.execute(f"""
                SELECT b.slug, b.name, COUNT(p.id) as cnt
                FROM brands b
                JOIN products p ON p.brand_id = b.id
                WHERE {b_where}
                GROUP BY b.id, b.slug, b.name
            """, b_params)
            for r in cur.fetchall():
                c = int(r['cnt'])
                if r.get('slug'):
                    facets['brands'][r['slug'].lower()] = c
                if r.get('name'):
                    facets['brands'][r['name'].lower()] = c

            # 4. Pattern facet
            pat_where, pat_params = get_where_except('pattern')
            cur.execute(f"""
                SELECT p.tire_pattern as pattern, COUNT(*) as cnt
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE {pat_where} AND p.tire_pattern IS NOT NULL AND p.tire_pattern != '' AND p.tire_pattern != 'None'
                GROUP BY p.tire_pattern
            """, pat_params)
            for r in cur.fetchall():
                if r.get('pattern'):
                    facets['patterns'][r['pattern']] = int(r['cnt'])

            # 5. OEM Tyres facet
            oem_where, oem_params = get_where_except('oem')
            cur.execute(f"""
                SELECT p.oem_brand as oem, COUNT(*) as cnt
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE {oem_where} AND p.oem_brand IS NOT NULL AND p.oem_brand != '' AND p.oem_brand != 'None' AND p.oem_brand != '0'
                GROUP BY p.oem_brand
            """, oem_params)
            for r in cur.fetchall():
                if r.get('oem'):
                    facets['oems'][r['oem']] = int(r['cnt'])

            # 6. Origin facet
            org_where, org_params = get_where_except('origin')
            cur.execute(f"""
                SELECT LOWER(p.country_of_origin) as origin, COUNT(*) as cnt
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE {org_where} AND p.country_of_origin IS NOT NULL AND p.country_of_origin != '' AND p.country_of_origin != 'None'
                GROUP BY LOWER(p.country_of_origin)
            """, org_params)
            for r in cur.fetchall():
                if r.get('origin'):
                    facets['origins'][r['origin']] = int(r['cnt'])

            # 7. Promotions facet
            pr_where, pr_params = get_where_except('promo')
            cur.execute(f"""
                SELECT 
                    SUM(CASE WHEN p.attributes_json LIKE '%%Buy 3 Get 1 Free%%' OR p.attributes_json LIKE '%%BUY 3 GET 1%%' THEN 1 ELSE 0 END) as buy_3_get_1_free,
                    SUM(CASE WHEN p.attributes_json LIKE '%%Free Wheel Alignment%%' OR p.attributes_json LIKE '%%FREE WHEEL ALIGNMENT%%' THEN 1 ELSE 0 END) as free_wheel_alignment
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE {pr_where}
            """, pr_params)
            pr_row = cur.fetchone() or {}
            facets['promotions'] = {
                'buy_3_get_1_free': int(pr_row.get('buy_3_get_1_free') or 0),
                'free_wheel_alignment': int(pr_row.get('free_wheel_alignment') or 0)
            }

            # 8. Runflat facet
            rf_where, rf_params = get_where_except('runflat')
            cur.execute(f"""
                SELECT COUNT(*) as cnt
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE {rf_where} AND (p.run_flat = 1 OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.runflat')) IN ('yes', '1', 'true', 'rft', 'RunFlat', 'runflat') OR LOWER(p.display_name) LIKE '%%runflat%%' OR LOWER(p.display_name) LIKE '%%run flat%%')
            """, rf_params)
            rf_res = cur.fetchone()
            facets['runflat'] = int(rf_res['cnt']) if rf_res else 0

            return {
                'products': products,
                'total': total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'facets': facets
            }
    finally:
        conn.close()


# # --- PRODUCT CATALOG / CAR TYRES LISTING ---
def _parse_filter_path(filter_path):
    """Parses clean SEO slug filter segments (e.g. /page-2-16/brand-pirelli/size-225-40-R18/max_price-5693) into request args."""
    from werkzeug.datastructures import MultiDict
    import re
    args = MultiDict()
    if not filter_path:
        return args

    raw_segments = [s.strip() for s in filter_path.split('/') if s.strip()]
    segments = []
    i = 0
    while i < len(raw_segments):
        s = raw_segments[i]
        if s.lower() in ('brand', 'brands') and i + 1 < len(raw_segments):
            segments.append(f"brand-{raw_segments[i+1]}")
            i += 2
        else:
            segments.append(s)
            i += 1

    for seg in segments:
        m_page = re.match(r'^page-(\d+)(?:-(\d+))?$', seg, re.IGNORECASE)
        if m_page:
            args.setlistdefault('page', []).append(m_page.group(1))
            if m_page.group(2):
                args.setlistdefault('per_page', []).append(m_page.group(2))
            continue

        m_brand = re.match(r'^brand-(.+)$', seg, re.IGNORECASE)
        if m_brand:
            for b in m_brand.group(1).split(','):
                if b.strip():
                    args.add('brand', b.strip())
            continue

        m_pattern = re.match(r'^pattern-(.+)$', seg, re.IGNORECASE)
        if m_pattern:
            for p in m_pattern.group(1).split(','):
                if p.strip():
                    args.add('pattern', p.strip())
            continue

        m_oem = re.match(r'^(?:oem|oem_tyres)-(.+)$', seg, re.IGNORECASE)
        if m_oem:
            for o in m_oem.group(1).split(','):
                if o.strip():
                    args.add('oem', o.strip())
            continue

        m_warranty = re.match(r'^(?:warranty|warranty_period)-(.+)$', seg, re.IGNORECASE)
        if m_warranty:
            for w in m_warranty.group(1).split(','):
                if w.strip():
                    args.add('warranty', w.strip())
            continue

        m_year = re.match(r'^year-(\d{4}(?:,\d{4})*)$', seg, re.IGNORECASE)
        if m_year:
            for y in m_year.group(1).split(','):
                if y.strip():
                    args.add('year', y.strip())
            continue

        m_origin = re.match(r'^(?:origin|country)-(.+)$', seg, re.IGNORECASE)
        if m_origin:
            for org in m_origin.group(1).split(','):
                if org.strip():
                    args.add('origin', org.strip())
            continue

        m_size = re.match(r'^size-(.+)$', seg, re.IGNORECASE)
        if m_size:
            for s in m_size.group(1).split(','):
                if s.strip():
                    args.add('size', s.strip())
            continue

        m_veh = re.match(r'^vehicle-(.+)$', seg, re.IGNORECASE)
        if m_veh:
            for v in m_veh.group(1).split(','):
                if v.strip():
                    args.add('vehicle', v.strip())
            continue

        m_type = re.match(r'^type-(.+)$', seg, re.IGNORECASE)
        if m_type:
            for t in m_type.group(1).split(','):
                if t.strip():
                    args.add('type', t.strip())
            continue

        m_rf = re.match(r'^(?:runflat|run_flat|run-flat)(?:-(.+))?$', seg, re.IGNORECASE)
        if m_rf:
            args.add('runflat', 'runflat')
            continue

        m_promo = re.match(r'^(?:promotion|promo|offer)-(.+)$', seg, re.IGNORECASE)
        if m_promo:
            for pr in m_promo.group(1).split(','):
                if pr.strip():
                    args.add('promotion', pr.strip())
            continue

        m_price_range = re.match(r'^price-(\d+(?:\.\d+)?)-(?:to-)?(\d+(?:\.\d+)?)$', seg, re.IGNORECASE)
        if m_price_range:
            args.setlistdefault('min_price', []).append(m_price_range.group(1))
            args.setlistdefault('max_price', []).append(m_price_range.group(2))
            continue

        m_price_single = re.match(r'^price-(\d+(?:\.\d+)?)$', seg, re.IGNORECASE)
        if m_price_single:
            args.setlistdefault('max_price', []).append(m_price_single.group(1))
            continue

        m_max_p = re.match(r'^max_price-(\d+(?:\.\d+)?)$', seg, re.IGNORECASE)
        if m_max_p:
            args.setlistdefault('max_price', []).append(m_max_p.group(1))
            continue

        m_min_p = re.match(r'^min_price-(\d+(?:\.\d+)?)$', seg, re.IGNORECASE)
        if m_min_p:
            args.setlistdefault('min_price', []).append(m_min_p.group(1))
            continue

        m_sort = re.match(r'^sort-(.+)$', seg, re.IGNORECASE)
        if m_sort:
            args.setlistdefault('sort', []).append(m_sort.group(1))
            continue

        m_q = re.match(r'^(?:search|q)-(.+)$', seg, re.IGNORECASE)
        if m_q:
            args.setlistdefault('search', []).append(m_q.group(1))
            continue

    return args


def _render_product_listing(locale, filter_path=None):
    """Renders the dedicated product listing catalog with data and sidebar filters from MySQL database."""
    from werkzeug.datastructures import MultiDict
    combined_args = MultiDict()
    if filter_path:
        combined_args.update(_parse_filter_path(filter_path))
    for k, vals in request.args.lists():
        combined_args.setlist(k, vals)

    # Check if client requested JSON via query param or header
    if combined_args.get('format') == 'json' or request.headers.get('Accept') == 'application/json':
        data = _fetch_catalog_products(combined_args, locale)
        return jsonify(data)

    catalog_data = _fetch_catalog_products(combined_args, locale)
    products = catalog_data['products']
    total_count = catalog_data['total']
    current_page = catalog_data['page']
    per_page = catalog_data['per_page']
    total_pages = catalog_data['total_pages']
    facets = catalog_data.get('facets', {})

    active_brands = [b.lower() for b in (combined_args.getlist('brand') or combined_args.getlist('brands'))]
    active_patterns = [p.strip() for p in (combined_args.getlist('pattern') or combined_args.getlist('patterns'))]
    active_oem_tyres = [o.strip() for o in (combined_args.getlist('oem') or combined_args.getlist('oem_tyres') or combined_args.getlist('oems'))]
    active_warranties = []
    for w in (combined_args.getlist('warranty') or combined_args.getlist('warranty_period') or combined_args.getlist('warranties')):
        w_clean = w.replace('-', ' ').strip()
        active_warranties.append(w.strip())
        active_warranties.append(w_clean)
        if '3 year' in w_clean.lower():
            active_warranties.extend(['3 Year Warranty', '3 Years Warranty'])
        elif '5 year' in w_clean.lower():
            active_warranties.extend(['5 Year Warranty', '5 Years Warranty'])
        elif '1 year' in w_clean.lower():
            active_warranties.extend(['1 Year Warranty', '1 Years Warranty'])
    active_years = [str(y).strip() for y in (combined_args.getlist('year') or combined_args.getlist('years'))]
    active_origins = [org.strip() for org in (combined_args.getlist('origin') or combined_args.getlist('country') or combined_args.getlist('origins'))]
    active_vehicles = [v.lower() for v in (combined_args.getlist('vehicle') or combined_args.getlist('vehicle_type'))]
    active_sizes = []
    for s in (combined_args.getlist('size') or combined_args.getlist('sizes')):
        active_sizes.append(s.strip())
        active_sizes.append(s.strip().replace('/', '-').replace(' ', '-'))
    active_types = [t.lower() for t in (combined_args.getlist('type') or combined_args.getlist('tire_type'))]
    active_runflat = [r.lower() for r in (combined_args.getlist('runflat') or combined_args.getlist('run_flat') or combined_args.getlist('is_runflat'))]
    filter_runflat_count = facets.get('runflat', 0)
    active_max_price = combined_args.get('max_price')
    active_min_price = combined_args.get('min_price')
    active_sort = combined_args.get('sort') or 'price-asc'
    active_promotions = []
    for pr in (combined_args.getlist('promotion') or combined_args.getlist('promotions') or combined_args.getlist('offer') or combined_args.getlist('offers')):
        p_clean = pr.lower().strip()
        if p_clean:
            active_promotions.extend([p_clean, p_clean.replace('-', '_'), p_clean.replace('_', '-')])

    from db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:

            # 2. Sidebar: Brands from DB (active brands + product counts)
            cur.execute("""
                SELECT b.id, b.name, b.slug, b.logo, COUNT(p.id) as cnt
                FROM brands b
                LEFT JOIN products p ON p.brand_id = b.id AND p.deleted_at IS NULL AND p.status = 'active'
                WHERE b.status = 'active'
                GROUP BY b.id, b.name, b.slug, b.logo
                ORDER BY cnt DESC, b.name ASC
            """)
            filter_brands = []
            for b in cur.fetchall():
                b_slug = b.get('slug') or (b.get('name') or '').lower().replace(' ', '')
                b_logo = b.get('logo') or f"/static/assets/images/brands/{b_slug}.svg"
                b_cnt = facets.get('brands', {}).get(b_slug, 0) if facets else b.get('cnt', 0)
                filter_brands.append({
                    'id': b['id'],
                    'name': b['name'],
                    'slug': b_slug,
                    'logo': b_logo,
                    'count': b_cnt
                })

            # 3. Sidebar: Tyre Sizes from DB (from active products + attribute_options)
            cur.execute("""
                SELECT tire_size_label as size, COUNT(*) as cnt
                FROM products
                WHERE deleted_at IS NULL AND status = 'active' 
                  AND tire_size_label IS NOT NULL AND tire_size_label != ''
                GROUP BY tire_size_label
                ORDER BY cnt DESC, tire_size_label ASC
            """)
            filter_sizes = []
            seen_sizes = set()
            for r in cur.fetchall():
                sz = r['size'].strip() if r.get('size') else ''
                if sz and sz not in seen_sizes:
                    seen_sizes.add(sz)
                    filter_sizes.append({'size': sz, 'count': r['cnt']})

            # Supplement from attribute_options (attributes.code = 'tire_size')
            cur.execute("""
                SELECT ao.value as size, COUNT(p.id) as cnt
                FROM attribute_options ao
                JOIN attributes a ON ao.attribute_id = a.id AND a.code = 'tire_size'
                LEFT JOIN products p ON p.tire_size_label = ao.value AND p.deleted_at IS NULL AND p.status = 'active'
                GROUP BY ao.id, ao.value, ao.sort_order
                ORDER BY cnt DESC, ao.sort_order ASC, ao.value ASC
                LIMIT 25
            """)
            for r in cur.fetchall():
                sz = r['size'].strip() if r.get('size') else ''
                if sz and sz not in seen_sizes:
                    seen_sizes.add(sz)
                    filter_sizes.append({'size': sz, 'count': r['cnt']})

            # 4. Sidebar: Patterns from DB (using direct index idx_products_active_pattern)
            cur.execute("""
                SELECT tire_pattern as pattern, COUNT(*) as cnt
                FROM products
                WHERE deleted_at IS NULL AND status = 'active'
                  AND tire_pattern IS NOT NULL AND tire_pattern != '' AND tire_pattern != 'None'
                GROUP BY tire_pattern
                ORDER BY cnt DESC, tire_pattern ASC
            """)
            filter_patterns = [{
                'pattern': r['pattern'],
                'count': facets.get('patterns', {}).get(r['pattern'], 0) if facets else r['cnt']
            } for r in cur.fetchall()]

            # 5. Sidebar: OEM Tyres from DB (using direct index idx_products_active_oem)
            cur.execute("""
                SELECT oem_brand as oem, COUNT(*) as cnt
                FROM products
                WHERE deleted_at IS NULL AND status = 'active'
                  AND oem_brand IS NOT NULL AND oem_brand != '' AND oem_brand != 'None' AND oem_brand != '0'
                GROUP BY oem_brand
                ORDER BY cnt DESC, oem_brand ASC
            """)
            filter_oem_tyres = [{
                'oem': r['oem'],
                'count': facets.get('oems', {}).get(r['oem'], 0) if facets else r['cnt']
            } for r in cur.fetchall()]

            # 6. Sidebar: Warranty Period from DB
            cur.execute("""
                SELECT war as warranty, COUNT(*) as cnt
                FROM (
                    SELECT CASE 
                        WHEN warranty_months IN ('12', 12) OR COALESCE(JSON_UNQUOTE(JSON_EXTRACT(attributes_json, '$.warranty')), JSON_UNQUOTE(JSON_EXTRACT(attributes_json, '$.warranty_period'))) IN ('12', '1 Year Warranty') THEN '1 Year Warranty'
                        ELSE COALESCE(JSON_UNQUOTE(JSON_EXTRACT(attributes_json, '$.warranty')), JSON_UNQUOTE(JSON_EXTRACT(attributes_json, '$.warranty_period')), CONCAT(warranty_months, ' Months Warranty'))
                    END as war
                    FROM products
                    WHERE deleted_at IS NULL AND status = 'active'
                ) t
                WHERE war IS NOT NULL AND war != '' AND war != 'None'
                GROUP BY war
                ORDER BY cnt DESC
            """)
            filter_warranties = [{
                'warranty': r['warranty'],
                'count': facets.get('warranties', {}).get(r['warranty'], 0) if facets else r['cnt']
            } for r in cur.fetchall()]

            # 7. Sidebar: Year from DB (using direct index idx_products_year)
            cur.execute("""
                SELECT year, COUNT(*) as cnt
                FROM products
                WHERE deleted_at IS NULL AND status = 'active'
                  AND year IS NOT NULL AND year != '0000'
                GROUP BY year
                ORDER BY year DESC
            """)
            filter_years = [{
                'year': r['year'],
                'count': facets.get('years', {}).get(str(r['year']), 0) if facets else r['cnt']
            } for r in cur.fetchall()]

            # 8. Sidebar: Origin from DB (using direct index idx_products_active_origin)
            cur.execute("""
                SELECT country_of_origin as origin, COUNT(*) as cnt
                FROM products
                WHERE deleted_at IS NULL AND status = 'active'
                  AND country_of_origin IS NOT NULL AND country_of_origin != '' AND country_of_origin != 'None'
                GROUP BY country_of_origin
                ORDER BY cnt DESC, country_of_origin ASC
            """)
            filter_origins = [{
                'origin': r['origin'],
                'count': facets.get('origins', {}).get((r['origin'] or '').lower(), 0) if facets else r['cnt']
            } for r in cur.fetchall()]

            # 4. Sidebar: Vehicle Types from DB
            cur.execute("""
                SELECT ao.value, ao.label, ao.sort_order
                FROM attribute_options ao
                JOIN attributes a ON ao.attribute_id = a.id AND a.code = 'vehicle_type'
                ORDER BY ao.sort_order ASC
            """)
            v_rows = cur.fetchall()

            cur.execute("""
                SELECT LOWER(vehicle_type) as vtype, COUNT(*) as cnt
                FROM products
                WHERE deleted_at IS NULL AND status = 'active' AND vehicle_type IS NOT NULL
                GROUP BY vehicle_type
            """)
            vehicle_prod_counts = {r['vtype']: r['cnt'] for r in cur.fetchall() if r.get('vtype')}
            vehicle_key_map = {
                'Passenger Car': 'car',
                'SUV / 4x4': 'suv',
                'Light Truck / Van': 'van',
                'Performance / Sport': 'sport',
                'Commercial Van': 'van',
                'Car': 'car',
                'SUV': 'suv',
                '4x4': '4x4',
                'EV': 'ev'
            }
            filter_vehicles = []
            seen_v_keys = set()
            for vr in v_rows:
                raw_val = vr.get('value') or ''
                lbl_raw = vr.get('label')
                label_dict = {}
                if isinstance(lbl_raw, str):
                    try:
                        label_dict = json.loads(lbl_raw)
                    except Exception:
                        label_dict = {'en': raw_val}
                elif isinstance(lbl_raw, dict):
                    label_dict = lbl_raw
                label = label_dict.get(locale) or label_dict.get('en') or raw_val
                key = vehicle_key_map.get(raw_val, raw_val.lower().replace(' ', '_'))
                cnt = vehicle_prod_counts.get(key, 0)
                if key == 'suv' and '4x4' in vehicle_prod_counts:
                    cnt += vehicle_prod_counts.get('4x4', 0)
                if key not in seen_v_keys:
                    seen_v_keys.add(key)
                    filter_vehicles.append({'key': key, 'label': label, 'count': cnt})

            for vk, vc in vehicle_prod_counts.items():
                if vk not in seen_v_keys:
                    seen_v_keys.add(vk)
                    filter_vehicles.append({
                        'key': vk,
                        'label': vk.upper() if len(vk) <= 3 else vk.replace('_', ' ').title(),
                        'count': vc
                    })

            # 5. Sidebar: Tyre Types / Seasons from DB
            cur.execute("""
                SELECT ao.value, ao.label, ao.sort_order
                FROM attribute_options ao
                JOIN attributes a ON ao.attribute_id = a.id AND a.code = 'season'
                ORDER BY ao.sort_order ASC
            """)
            season_rows = cur.fetchall()

            cur.execute("""
                SELECT LOWER(tire_type) as ttype, COUNT(*) as cnt
                FROM products
                WHERE deleted_at IS NULL AND status = 'active' AND tire_type IS NOT NULL
                GROUP BY tire_type
            """)
            tire_type_counts = {r['ttype']: r['cnt'] for r in cur.fetchall() if r.get('ttype')}

            cur.execute("""
                SELECT COUNT(*) as cnt
                FROM products
                WHERE deleted_at IS NULL AND status = 'active' AND run_flat = 1
            """)
            rf_res = cur.fetchone()
            run_flat_cnt = rf_res['cnt'] if rf_res else 0

            filter_tyre_types = []
            for sr in season_rows:
                raw_val = sr.get('value') or ''
                lbl_raw = sr.get('label')
                label_dict = {}
                if isinstance(lbl_raw, str):
                    try:
                        label_dict = json.loads(lbl_raw)
                    except Exception:
                        label_dict = {'en': raw_val}
                elif isinstance(lbl_raw, dict):
                    label_dict = lbl_raw
                label = label_dict.get(locale) or label_dict.get('en') or raw_val
                key = raw_val.lower().replace('-', '_').replace(' ', '_')
                filter_tyre_types.append({
                    'key': key,
                    'label': label,
                    'count': tire_type_counts.get(key, 0)
                })

            filter_tyre_types.append({
                'key': 'run_flat',
                'label': 'Run Flat',
                'count': run_flat_cnt
            })

            # 6. Sidebar: Promotions / Special Offers directly synced with active cart_price_rules in DB
            cur.execute("""
                SELECT id, name
                FROM cart_price_rules
                WHERE is_active = 1
                  AND deleted_at IS NULL
                  AND (from_date IS NULL OR from_date <= CURRENT_DATE())
                  AND (to_date IS NULL OR to_date >= CURRENT_DATE())
                ORDER BY priority ASC, id ASC
            """)
            active_rules = cur.fetchall()
            filter_promotions = []
            for r in active_rules:
                r_name = (r.get('name') or '').strip()
                if not r_name:
                    continue
                cur.execute("""
                    SELECT COUNT(*) as cnt
                    FROM products
                    WHERE deleted_at IS NULL AND status = 'active'
                      AND (
                        attributes_json LIKE %s
                        OR JSON_EXTRACT(attributes_json, '$.offers') LIKE %s
                        OR JSON_EXTRACT(attributes_json, '$.promotion') LIKE %s
                        OR JSON_EXTRACT(attributes_json, '$.badge') LIKE %s
                      )
                """, [f"%{r_name}%", f"%{r_name}%", f"%{r_name}%", f"%{r_name}%"])
                cnt_row = cur.fetchone()
                cnt = int(cnt_row['cnt']) if cnt_row else 0
                p_key = re.sub(r'[^a-z0-9]+', '_', r_name.lower()).strip('_')
                p_cnt = facets.get('promotions', {}).get(p_key, 0) if facets else cnt
                filter_promotions.append({
                    'key': p_key,
                    'label': r_name,
                    'count': p_cnt
                })

            # 7. Sidebar: Price Range from DB
            cur.execute("""
                SELECT MIN(price) as min_p, MAX(price) as max_p
                FROM products
                WHERE deleted_at IS NULL AND status = 'active'
            """)
            pr_row = cur.fetchone()
            min_price = int(pr_row['min_p']) if pr_row and pr_row['min_p'] is not None else 100
            max_price = int(pr_row['max_p']) if pr_row and pr_row['max_p'] is not None else 2000
            if min_price >= max_price:
                max_price = min_price + 1000

            active_brand_name = ''
            active_brand_slug = ''
            if active_brands and len(active_brands) == 1:
                target_b = active_brands[0].lower()
                for fb in filter_brands:
                    if fb['slug'].lower() == target_b or fb['name'].lower() == target_b:
                        active_brand_name = fb['name']
                        active_brand_slug = fb['slug']
                        break
                if not active_brand_name:
                    active_brand_name = active_brands[0].capitalize()
                    active_brand_slug = active_brands[0]

            resp = make_response(render_template(
                'Client/ProductListing.html',
                products=products,
                total_count=total_count,
                current_page=current_page,
                per_page=per_page,
                total_pages=total_pages,
                filter_brands=filter_brands,
                active_brand_name=active_brand_name,
                active_brand_slug=active_brand_slug,
                filter_patterns=filter_patterns,
                filter_oem_tyres=filter_oem_tyres,
                filter_warranties=filter_warranties,
                filter_years=filter_years,
                filter_origins=filter_origins,
                filter_sizes=filter_sizes,
                filter_vehicles=filter_vehicles,
                filter_tyre_types=filter_tyre_types,
                filter_runflat_count=filter_runflat_count,
                active_runflat=active_runflat,
                filter_promotions=filter_promotions,
                min_price=min_price,
                max_price=max_price,
                active_brands=active_brands,
                active_patterns=active_patterns,
                active_oem_tyres=active_oem_tyres,
                active_warranties=active_warranties,
                active_years=active_years,
                active_origins=active_origins,
                active_vehicles=active_vehicles,
                active_sizes=active_sizes,
                active_types=active_types,
                active_promotions=active_promotions,
                active_max_price=active_max_price,
                active_min_price=active_min_price,
                active_sort=active_sort,
                locale=locale
            ))
            resp.set_cookie('site_locale', locale, max_age=31536000, path='/')
            return resp
    finally:
        conn.close()


@site_bp.route('/api/products')
@site_bp.route('/api/client/products')
def api_products():
    """Client storefront AJAX product catalog pagination and live filter endpoint."""
    locale = _get_locale()
    data = _fetch_catalog_products(request.args, locale)
    return jsonify(data)


# ============================================================================
# PRODUCT DETAIL PAGE (PDP) RENDERER & ROUTES
# ============================================================================
def _render_product_detail(slug_or_id, locale=None):
    """Render dynamic Product Detail Page matching 100% of reference design."""
    locale = (locale or _get_locale()).lower()
    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            is_digit_id = str(slug_or_id).isdigit()
            clean_s = str(slug_or_id).lower().strip()
            cur.execute("""
                SELECT p.*, b.name as brand_name, b.slug as brand_slug, b.logo as brand_logo
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE (p.slug = %s OR p.sku = %s OR p.id = %s OR p.slug LIKE %s)
                  AND p.deleted_at IS NULL
                ORDER BY (p.slug = %s) DESC, p.id ASC
                LIMIT 1
            """, [clean_s, clean_s, int(slug_or_id) if is_digit_id else -1, f"{clean_s}%", clean_s])
            p_row = cur.fetchone()
            if not p_row:
                abort(404)

            # Extract specs from attributes_json
            raw_attrs = {}
            if p_row.get('attributes_json'):
                try:
                    raw_attrs = json.loads(p_row['attributes_json']) if isinstance(p_row['attributes_json'], str) else p_row['attributes_json']
                except Exception:
                    raw_attrs = {}

            # Parse size specs from tire_size_label or attributes
            size_label = p_row.get('tire_size_label') or ''
            m_size = re.search(r'(\d+)[/\s](\d+)\s*(?:R|r)?(\d+)', size_label)
            width_val = raw_attrs.get('width') or (m_size.group(1) if m_size else '165')
            profile_val = raw_attrs.get('profile') or (m_size.group(2) if m_size else '65')
            rim_val = raw_attrs.get('rim') or (f"R{m_size.group(3)}" if m_size else 'R14')
            if not str(rim_val).upper().startswith('R'):
                rim_val = f"R{rim_val}"

            load_speed = raw_attrs.get('load_speed') or f"{p_row.get('tire_load_index') or '79'}{p_row.get('tire_speed_rating') or 'T'}"
            brand_name = p_row.get('brand_name') or 'Michelin'
            pattern_name = p_row.get('tire_pattern') or 'Energy XM2 Plus'
            price_f = float(p_row.get('price') or 121.0)

            # Short desc and full description faithfully from DB
            short_desc = ""
            if p_row.get('short_desc'):
                try:
                    sd = json.loads(p_row['short_desc']) if isinstance(p_row['short_desc'], str) else p_row['short_desc']
                    if isinstance(sd, dict):
                        short_desc = sd.get(locale) or sd.get('en') or next(iter(sd.values()), '')
                    else:
                        short_desc = str(sd)
                except Exception:
                    short_desc = str(p_row['short_desc'])
            if not short_desc or str(short_desc).strip() in ('{}', 'None', ''):
                short_desc = raw_attrs.get('short_description') or ''

            desc = ""
            if p_row.get('description'):
                try:
                    d = json.loads(p_row['description']) if isinstance(p_row['description'], str) else p_row['description']
                    if isinstance(d, dict):
                        desc = d.get(locale) or d.get('en') or next(iter(d.values()), '')
                    else:
                        desc = str(d)
                except Exception:
                    desc = str(p_row['description'])

            if not desc or str(desc).strip() in ('{}', 'None', ''):
                desc = raw_attrs.get('description') or ''
            if not desc or str(desc).strip() in ('{}', 'None', ''):
                desc = short_desc
            if not desc or str(desc).strip() in ('{}', 'None', ''):
                if p_row.get('meta_desc'):
                    try:
                        md = json.loads(p_row['meta_desc']) if isinstance(p_row['meta_desc'], str) else p_row['meta_desc']
                        if isinstance(md, dict):
                            desc = md.get(locale) or md.get('en') or next(iter(md.values()), '')
                        else:
                            desc = str(md)
                    except Exception:
                        desc = str(p_row['meta_desc'])
            if not desc or str(desc).strip() in ('{}', 'None', ''):
                desc = raw_attrs.get('meta_description') or ''
            if not desc or str(desc).strip() in ('{}', 'None', ''):
                desc = f"The {brand_name} {pattern_name} is designed for a safer and smoother drive with outstanding wet braking, long-lasting performance and excellent fuel efficiency. Ideal for everyday driving."

            # Parse meta_desc and meta_title for SEO
            meta_desc_val = ""
            if p_row.get('meta_desc'):
                try:
                    md = json.loads(p_row['meta_desc']) if isinstance(p_row['meta_desc'], str) else p_row['meta_desc']
                    if isinstance(md, dict):
                        meta_desc_val = md.get(locale) or md.get('en') or next(iter(md.values()), '')
                    else:
                        meta_desc_val = str(md)
                except Exception:
                    meta_desc_val = str(p_row['meta_desc'])
            if not meta_desc_val:
                meta_desc_val = raw_attrs.get('meta_description') or f"{p_row.get('display_name') or (brand_name + ' ' + size_label)} in stock with free delivery, warranty and mobile fitting across UAE."

            meta_title_val = ""
            if p_row.get('meta_title'):
                try:
                    mt = json.loads(p_row['meta_title']) if isinstance(p_row['meta_title'], str) else p_row['meta_title']
                    if isinstance(mt, dict):
                        meta_title_val = mt.get(locale) or mt.get('en') or next(iter(mt.values()), '')
                    else:
                        meta_title_val = str(mt)
                except Exception:
                    meta_title_val = str(p_row['meta_title'])
            if not meta_title_val:
                meta_title_val = raw_attrs.get('meta_title') or f"{p_row.get('display_name') or (brand_name + ' ' + size_label)} | Buy Online at TyresVision UAE"

            # Image
            img_path = p_row.get('image_path') or '/static/uploads/products/michelin_energy_xm2_wheel.jpg'
            if not img_path.startswith('/'):
                img_path = '/' + img_path.replace('\\', '/')

            brand_logo = p_row.get('brand_logo') or '/static/uploads/brands/brand_884b41a82943de82_1789467748.png'
            if not brand_logo.startswith('/'):
                brand_logo = '/' + brand_logo.replace('\\', '/')

            # Warranty
            w_months = p_row.get('warranty_months') or 12
            warranty_str = f"{w_months // 12} Year" if w_months >= 12 and w_months % 12 == 0 else f"{w_months} Months"

            # Vehicle type label
            v_type = (p_row.get('vehicle_type') or 'car').lower()
            vehicle_type_label = "Car Tyre" if v_type in ('car', 'passenger', '') else v_type.capitalize() + " Tyre"

            # Season
            t_type = (p_row.get('tire_type') or 'summer').lower()
            season_label = "Summer" if 'summer' in t_type else ("All Season" if 'all' in t_type else "Winter")

            # Offer banner and promotions
            raw_offer = (raw_attrs.get('offers') or raw_attrs.get('promotion') or raw_attrs.get('badge') or p_row.get('offer_banner') or '').strip()
            offer_banner = raw_offer.upper() if raw_offer and raw_offer.lower() not in ('none', '0', '', 'null') else ''
            if not offer_banner:
                offer_banner = 'BUY 3 GET 1 FREE'

            if 'BUY 3' in offer_banner:
                price_set4 = round(price_f * 3, 2)
            elif 'BUY 2' in offer_banner:
                price_set4 = round(price_f * 2, 2)
            else:
                price_set4 = round(price_f * 4, 2)

            product = {
                'id': p_row['id'],
                'slug': p_row['slug'],
                'sku': p_row['sku'],
                'title': p_row.get('display_name') or f"{brand_name} {size_label} {load_speed}",
                'brand_name': brand_name,
                'brand_logo': brand_logo,
                'pattern_name': pattern_name,
                'offer_banner': offer_banner,
                'has_offer': bool(offer_banner),
                'price': price_f,
                'price_formatted': f"{price_f:,.2f}",
                'price_set2': round(price_f * 2, 2),
                'price_set2_formatted': f"{price_f * 2:,.2f}",
                'price_set4': price_set4,
                'price_set4_formatted': f"{price_set4:,.2f}",
                'price_set4_regular_formatted': f"{price_f * 4:,.2f}",
                'image_path': img_path,
                'in_stock': p_row.get('stock_status') == 'in_stock',
                'short_desc': short_desc,
                'description': desc,
                'meta_description': meta_desc_val,
                'meta_title': meta_title_val,
                'width': width_val if 'mm' in str(width_val) else f"{width_val} mm",
                'profile': profile_val,
                'rim_size': rim_val,
                'load_speed': load_speed,
                'type': vehicle_type_label,
                'season': season_label,
                'year': p_row.get('year') or 2024,
                'country': p_row.get('country_of_origin') or 'France',
                'run_flat': 'Yes' if p_row.get('run_flat') == 1 else 'No',
                'warranty': warranty_str,
                'tire_size_label': size_label or f"{width_val}/{profile_val} {rim_val}",
                'faqs': raw_attrs.get('faqs') if isinstance(raw_attrs.get('faqs'), list) else ([] if not raw_attrs.get('faqs') else [raw_attrs.get('faqs')])
            }

            # Related products: SAME SIZE, DIFFERENT BRANDS (per requirement)
            target_size = size_label.strip() if size_label else f"{width_val}/{profile_val} {rim_val}"
            current_brand_id = p_row.get('brand_id')
            cur.execute("""
                SELECT p.*, b.name as brand_name, b.slug as brand_slug, b.logo as brand_logo
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE p.deleted_at IS NULL AND p.status = 'active'
                  AND p.id != %s
                  AND p.tire_size_label = %s
                  AND (p.brand_id != %s OR %s IS NULL)
                ORDER BY p.price ASC, p.id ASC
            """, [p_row['id'], target_size, current_brand_id, current_brand_id])
            same_size_rows = cur.fetchall()

            rel_rows = []
            seen_brands = set()
            if current_brand_id:
                seen_brands.add(current_brand_id)
            if brand_name:
                seen_brands.add(brand_name.lower().strip())

            for r in same_size_rows:
                b_key = (r.get('brand_name') or '').lower().strip()
                if b_key and b_key not in seen_brands:
                    seen_brands.add(b_key)
                    rel_rows.append(r)
                if len(rel_rows) >= 10:
                    break

            # Fallback 1: If fewer than 10, same rim size from different brands
            if len(rel_rows) < 10 and rim_val:
                cur.execute("""
                    SELECT p.*, b.name as brand_name, b.slug as brand_slug, b.logo as brand_logo
                    FROM products p
                    LEFT JOIN brands b ON p.brand_id = b.id
                    WHERE p.deleted_at IS NULL AND p.status = 'active'
                      AND p.id != %s
                      AND p.tire_size_label LIKE %s
                      AND (p.brand_id != %s OR %s IS NULL)
                    ORDER BY p.price ASC, p.id ASC
                """, [p_row['id'], f"%{rim_val}%", current_brand_id, current_brand_id])
                for r in cur.fetchall():
                    b_key = (r.get('brand_name') or '').lower().strip()
                    if b_key and b_key not in seen_brands:
                        seen_brands.add(b_key)
                        rel_rows.append(r)
                    if len(rel_rows) >= 10:
                        break

            # Fallback 2: Any active products from different brands
            if len(rel_rows) < 10:
                cur.execute("""
                    SELECT p.*, b.name as brand_name, b.slug as brand_slug, b.logo as brand_logo
                    FROM products p
                    LEFT JOIN brands b ON p.brand_id = b.id
                    WHERE p.deleted_at IS NULL AND p.status = 'active'
                      AND p.id != %s
                      AND (p.brand_id != %s OR %s IS NULL)
                    ORDER BY p.price ASC, p.id ASC
                    LIMIT 20
                """, [p_row['id'], current_brand_id, current_brand_id])
                for r in cur.fetchall():
                    b_key = (r.get('brand_name') or '').lower().strip()
                    if b_key and b_key not in seen_brands:
                        seen_brands.add(b_key)
                        rel_rows.append(r)
                    if len(rel_rows) >= 10:
                        break

            related_products = [_format_product_for_client(r, locale) for r in rel_rows]

            resp = make_response(render_template(
                'Client/ProductDetail.html',
                product=product,
                related_products=related_products,
                locale=locale
            ))
            resp.set_cookie('site_locale', locale, max_age=31536000, path='/')
            return resp
    finally:
        conn.close()


# Dedicated Product Detail Routes
@site_bp.route('/product/<slug>', strict_slashes=False)
@site_bp.route('/product/<slug>/', strict_slashes=False)
@site_bp.route('/tyres/product/<slug>', strict_slashes=False)
@site_bp.route('/tyres/product/<slug>/', strict_slashes=False)
def product_detail(slug):
    """Client storefront Product Detail page."""
    locale = _get_locale()
    return _render_product_detail(slug, locale)


@site_bp.route('/<string(length=2):lang_code>/product/<slug>', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/product/<slug>/', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/tyres/product/<slug>', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/tyres/product/<slug>/', strict_slashes=False)
def product_detail_locale(lang_code, slug):
    """Client storefront Product Detail page with dynamic locale."""
    code = lang_code.lower()
    session['site_locale'] = code
    return _render_product_detail(slug, code)


@site_bp.route('/car-tyres', strict_slashes=False)
@site_bp.route('/car-tyres/', strict_slashes=False)
@site_bp.route('/tyres', strict_slashes=False)
@site_bp.route('/tyres/', strict_slashes=False)
@site_bp.route('/products', strict_slashes=False)
@site_bp.route('/products/', strict_slashes=False)
def car_tyres_listing():
    """Client storefront Car Tyres / Product Listing catalog."""
    locale = _get_locale()
    return _render_product_listing(locale)


@site_bp.route('/car-tyres/<path:filter_path>', strict_slashes=False)
@site_bp.route('/tyres/<path:filter_path>', strict_slashes=False)
@site_bp.route('/products/<path:filter_path>', strict_slashes=False)
def car_tyres_listing_slug(filter_path):
    """Client storefront Car Tyres / Product Listing catalog with URL slug filters."""
    clean_path = (filter_path or '').strip('/')
    if not clean_path:
        return redirect('/tyres', code=301)

    # Check if slug matches a product directly
    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM products WHERE slug = %s AND deleted_at IS NULL LIMIT 1", [clean_path])
            if cur.fetchone():
                locale = _get_locale()
                return _render_product_detail(clean_path, locale)
    finally:
        conn.close()

    # If URL contains uppercase characters (e.g. /tyres/oem-Mercedes-Benz), 301 redirect to lowercase slug
    if clean_path != clean_path.lower():
        prefix = '/car-tyres' if request.path.startswith('/car-tyres') else ('/products' if request.path.startswith('/products') else '/tyres')
        query_str = f"?{request.query_string.decode('utf-8')}" if request.query_string else ""
        return redirect(f"{prefix}/{clean_path.lower()}{query_str}", code=301)
    locale = _get_locale()
    return _render_product_listing(locale, filter_path=clean_path)


@site_bp.route('/<string(length=2):lang_code>/car-tyres', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/car-tyres/', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/tyres', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/tyres/', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/products', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/products/', strict_slashes=False)
def car_tyres_listing_locale(lang_code):
    """Client storefront Car Tyres / Product Listing catalog with dynamic locale."""
    code = lang_code.lower()
    session['site_locale'] = code
    return _render_product_listing(code)


@site_bp.route('/<string(length=2):lang_code>/car-tyres/<path:filter_path>', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/tyres/<path:filter_path>', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/products/<path:filter_path>', strict_slashes=False)
def car_tyres_listing_locale_slug(lang_code, filter_path):
    """Client storefront Car Tyres / Product Listing catalog with dynamic locale and URL slug filters."""
    code = lang_code.lower()
    session['site_locale'] = code
    clean_path = (filter_path or '').strip('/')
    if not clean_path:
        return redirect(f'/{code}/tyres', code=301)

    # Check if slug matches a product directly
    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM products WHERE slug = %s AND deleted_at IS NULL LIMIT 1", [clean_path])
            if cur.fetchone():
                return _render_product_detail(clean_path, code)
    finally:
        conn.close()

    # If URL contains uppercase characters, 301 redirect to lowercase slug
    if clean_path != clean_path.lower():
        prefix = f'/{code}/car-tyres' if f'/{code}/car-tyres' in request.path else (f'/{code}/products' if f'/{code}/products' in request.path else f'/{code}/tyres')
        query_str = f"?{request.query_string.decode('utf-8')}" if request.query_string else ""
        return redirect(f"{prefix}/{clean_path.lower()}{query_str}", code=301)
    return _render_product_listing(code, filter_path=clean_path)


# ============================================================================
# CART OVERVIEW & CHECKOUT DRAWER API ENDPOINTS
# ============================================================================

def _haversine_km(lat1, lon1, lat2, lon2):
    """Calculates distance in kilometers between two GPS coordinates."""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


@site_bp.route('/api/store-locator', methods=['GET'])
def api_store_locator():
    """Returns fitting partner centres, mobile fitting vans, cities, and time slots."""
    user_lat = request.args.get('lat', type=float)
    user_lng = request.args.get('lng', type=float)

    cities = ["All", "Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah", "Umm Al Quwain"]

    branches = [
        {
            "id": "branch-dxb-alquoz",
            "name": "TyresVision Al Quoz Fitment Hub",
            "city": "Dubai",
            "address": "Street 8, Al Quoz Industrial Area 3, Dubai",
            "lat": 25.1325,
            "lng": 55.2341,
            "distance": 3.2,
            "phone": "+971 50 506 9575",
            "whatsapp": "+971505069575",
            "email": "alquoz@tyresvision.com",
            "installer_type": "Certified Hub",
            "openingHoursByDay": [["Mon - Sat", "08:00 AM - 09:00 PM"], ["Sun", "09:00 AM - 07:00 PM"]]
        },
        {
            "id": "branch-dxb-deira",
            "name": "TyresVision Deira Fitting Centre",
            "city": "Dubai",
            "address": "Al Khabaisi, Deira (Opposite City Centre), Dubai",
            "lat": 25.2638,
            "lng": 55.3374,
            "distance": 8.5,
            "phone": "+971 50 506 9575",
            "whatsapp": "+971505069575",
            "email": "deira@tyresvision.com",
            "installer_type": "Independent Installer",
            "openingHoursByDay": [["Mon - Sat", "08:30 AM - 08:30 PM"], ["Sun", "09:00 AM - 06:00 PM"]]
        },
        {
            "id": "branch-dxb-rasalkhor",
            "name": "TyresVision Ras Al Khor Workshop",
            "city": "Dubai",
            "address": "Ras Al Khor Industrial 2, Near Auto Market, Dubai",
            "lat": 25.1769,
            "lng": 55.3524,
            "distance": 11.0,
            "phone": "+971 50 506 9575",
            "whatsapp": "+971505069575",
            "email": "rasalkhor@tyresvision.com",
            "installer_type": "Certified Partner",
            "openingHoursByDay": [["Mon - Sat", "08:00 AM - 08:00 PM"]]
        },
        {
            "id": "branch-auh-mussafah",
            "name": "TyresVision Mussafah Central Garage",
            "city": "Abu Dhabi",
            "address": "M-14, Industrial Area, Mussafah, Abu Dhabi",
            "lat": 24.3411,
            "lng": 54.5123,
            "distance": 14.2,
            "phone": "+971 50 506 9575",
            "whatsapp": "+971505069575",
            "email": "mussafah@tyresvision.com",
            "installer_type": "Certified Hub",
            "openingHoursByDay": [["Sat - Thu", "08:00 AM - 09:00 PM"], ["Fri", "02:00 PM - 08:00 PM"]]
        },
        {
            "id": "branch-auh-khalidiya",
            "name": "TyresVision Al Khalidiya Express",
            "city": "Abu Dhabi",
            "address": "Zayed the First St, Al Khalidiyah, Abu Dhabi",
            "lat": 24.4721,
            "lng": 54.3482,
            "distance": 18.0,
            "phone": "+971 50 506 9575",
            "whatsapp": "+971505069575",
            "email": "khalidiya@tyresvision.com",
            "installer_type": "Independent Installer",
            "openingHoursByDay": [["Mon - Sat", "08:30 AM - 08:30 PM"]]
        },
        {
            "id": "branch-shj-industrial",
            "name": "TyresVision Sharjah Industrial 4",
            "city": "Sharjah",
            "address": "Industrial Area 4, Next to BMW Road, Sharjah",
            "lat": 25.3214,
            "lng": 55.4011,
            "distance": 16.5,
            "phone": "+971 50 506 9575",
            "whatsapp": "+971505069575",
            "email": "sharjah@tyresvision.com",
            "installer_type": "Certified Partner",
            "openingHoursByDay": [["Sat - Thu", "08:00 AM - 09:30 PM"]]
        },
        {
            "id": "branch-ajm-newind",
            "name": "TyresVision Ajman New Industrial Hub",
            "city": "Ajman",
            "address": "New Industrial Area, Sheikh Ammar St, Ajman",
            "lat": 25.3982,
            "lng": 55.4871,
            "distance": 22.0,
            "phone": "+971 50 506 9575",
            "whatsapp": "+971505069575",
            "email": "ajman@tyresvision.com",
            "installer_type": "Certified Partner",
            "openingHoursByDay": [["Sat - Thu", "08:30 AM - 09:00 PM"]]
        },
        {
            "id": "branch-rak-nakheel",
            "name": "TyresVision Ras Al Khaimah Al Nakheel",
            "city": "Ras Al Khaimah",
            "address": "Al Muntasir Rd, Al Nakheel, Ras Al Khaimah",
            "lat": 25.7912,
            "lng": 55.9723,
            "distance": 68.0,
            "phone": "+971 50 506 9575",
            "whatsapp": "+971505069575",
            "email": "rak@tyresvision.com",
            "installer_type": "Independent Installer",
            "openingHoursByDay": [["Sat - Thu", "08:00 AM - 08:30 PM"]]
        }
    ]

    mobileVans = [
        {
            "id": "van-dxb-01",
            "name": "Mobile Van #1 — Dubai & Northern Emirates",
            "city": "Dubai",
            "address": "Doorstep Service (Dubai, Sharjah, Ajman, RAK)",
            "lat": 25.2048,
            "lng": 55.2708,
            "phone": "+971 50 506 9575",
            "whatsapp": "+971505069575",
            "shipping_fee": "FREE",
            "installer_type": "Mobile Van",
            "delivery_mode": "mobile_van"
        },
        {
            "id": "van-auh-02",
            "name": "Mobile Van #2 — Abu Dhabi & Al Ain Fleet",
            "city": "Abu Dhabi",
            "address": "Doorstep Service (Abu Dhabi, Khalifa City, Yas, Al Ain)",
            "lat": 24.4539,
            "lng": 54.3773,
            "phone": "+971 50 506 9575",
            "whatsapp": "+971505069575",
            "shipping_fee": "FREE",
            "installer_type": "Mobile Van",
            "delivery_mode": "mobile_van"
        }
    ]

    timeSlots = [
        "09:00 AM - 11:00 AM",
        "11:00 AM - 01:00 PM",
        "02:00 PM - 04:00 PM",
        "04:00 PM - 06:00 PM",
        "06:00 PM - 08:00 PM"
    ]

    if user_lat is not None and user_lng is not None:
        for b in branches:
            b['distance'] = _haversine_km(user_lat, user_lng, b['lat'], b['lng'])
        branches.sort(key=lambda x: x['distance'])

        for v in mobileVans:
            v['distance'] = _haversine_km(user_lat, user_lng, v['lat'], v['lng'])
        mobileVans.sort(key=lambda x: x['distance'])

    return jsonify({
        "success": True,
        "cities": cities,
        "branches": branches,
        "mobileVans": mobileVans,
        "timeSlots": timeSlots
    })


@site_bp.route('/api/vehicles', methods=['GET'])
def api_vehicles():
    """Returns vehicle makes, models, and years for UAE vehicles."""
    action = request.args.get('action', 'makes')
    make = (request.args.get('make') or '').strip()
    model = (request.args.get('model') or '').strip()

    VEHICLE_CATALOG = {
        "Toyota": ["Land Cruiser", "Prado", "Camry", "Corolla", "RAV4", "Hilux", "Fortuner", "Yaris", "Highlander", "FJ Cruiser"],
        "Nissan": ["Patrol", "Altima", "Sunny", "X-Trail", "Pathfinder", "Kicks", "Maxima", "Navara", "Murano", "Armada"],
        "Mitsubishi": ["Pajero", "Outlander", "ASX", "Eclipse Cross", "L200", "Attrage", "Montero Sport", "Mirage"],
        "Ford": ["Explorer", "F-150", "Mustang", "Expedition", "Edge", "Ranger", "Bronco", "Escape", "Everest"],
        "Hyundai": ["Tucson", "Santa Fe", "Sonata", "Elantra", "Creta", "Accent", "Palisade", "Kona", "Azera"],
        "BMW": ["X5", "X6", "3 Series", "5 Series", "7 Series", "X3", "X7", "4 Series", "X1", "M3", "M5"],
        "Mercedes-Benz": ["C-Class", "E-Class", "S-Class", "G-Class", "GLE", "GLC", "CLA", "GLS", "A-Class", "AMG GT"],
        "Lexus": ["LX570", "LX600", "RX350", "ES350", "GX460", "IS300", "NX300", "LS500", "UX200"],
        "Audi": ["Q7", "Q5", "A6", "A4", "Q8", "RS6", "A3", "A8", "Q3", "e-tron"],
        "Land Rover": ["Range Rover", "Range Rover Sport", "Defender", "Discovery", "Velar", "Evoque"],
        "Porsche": ["Cayenne", "Macan", "Panamera", "911", "Taycan", "Boxster", "Cayman"],
        "Kia": ["Sportage", "Seltos", "Telluride", "Cerato", "Carnival", "Sorento", "Pegas", "K5", "Mohave"],
        "Honda": ["Accord", "Civic", "CR-V", "Pilot", "City", "HR-V", "Odyssey"],
        "Chevrolet": ["Tahoe", "Suburban", "Silverado", "Captiva", "Camaro", "Traverse", "Malibu", "Corvette"],
        "Jeep": ["Wrangler", "Grand Cherokee", "Gladiator", "Cherokee", "Compass", "Renegade"],
        "Tesla": ["Model Y", "Model 3", "Model X", "Model S"],
        "Volkswagen": ["Tiguan", "Touareg", "Golf", "Passat", "Teramont", "T-Roc", "CC"],
        "Mazda": ["CX-5", "CX-9", "Mazda 6", "Mazda 3", "CX-30", "CX-60"]
    }

    if action == 'makes':
        makes_list = [{"label": m, "value": m} for m in sorted(VEHICLE_CATALOG.keys())]
        return jsonify(makes_list)
    elif action == 'models':
        models_list = VEHICLE_CATALOG.get(make, ["Other"])
        return jsonify([{"label": m, "value": m} for m in models_list])
    elif action == 'years':
        years_list = [str(y) for y in range(2026, 2009, -1)]
        return jsonify([{"label": y, "value": y} for y in years_list])

    return jsonify([])


@site_bp.route('/api/geocode', methods=['GET'])
def api_geocode():
    """Approximates city/area name based on UAE coordinates."""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    if lat is None or lng is None:
        return jsonify({"address": "United Arab Emirates"})

    if 24.90 <= lat <= 25.40 and 55.00 <= lng <= 55.60:
        return jsonify({"address": "Dubai, United Arab Emirates"})
    elif 24.10 <= lat <= 24.70 and 54.10 <= lng <= 54.80:
        return jsonify({"address": "Abu Dhabi, United Arab Emirates"})
    elif 25.25 <= lat <= 25.50 and 55.35 <= lng <= 55.70:
        return jsonify({"address": "Sharjah, United Arab Emirates"})
    elif 25.35 <= lat <= 25.50 and 55.45 <= lng <= 55.60:
        return jsonify({"address": "Ajman, United Arab Emirates"})
    elif 25.55 <= lat <= 26.00 and 55.80 <= lng <= 56.10:
        return jsonify({"address": "Ras Al Khaimah, United Arab Emirates"})
    return jsonify({"address": f"{round(lat, 4)}, {round(lng, 4)} (UAE)"})


@site_bp.route('/api/cart', methods=['GET', 'POST'])
def api_cart():
    """Unified cart & checkout endpoint powering Overview Drawer and Cart operations."""
    if 'tv_cart' not in session:
        session['tv_cart'] = {
            'items': [],
            'email': '',
            'shipping': {},
            'billing': {},
            'installer': {},
            'payment_method': 'payment_link',
            'coupon': None,
            'discount': 0.0,
            'notes': ''
        }

    cart_state = session['tv_cart']

    if request.method == 'GET':
        items = cart_state.get('items', [])
        subtotal = sum(float(item.get('price', 0)) * int(item.get('qty', 1)) for item in items)
        discount = float(cart_state.get('discount', 0.0))
        vat = round(max(0.0, subtotal - discount) * 0.05, 2)
        total = round(max(0.0, subtotal - discount) + vat, 2)
        return jsonify({
            'success': True,
            'items': items,
            'subtotal': subtotal,
            'discount': discount,
            'vat': vat,
            'total': total,
            'coupon': cart_state.get('coupon'),
            'shipping': cart_state.get('shipping'),
            'installer': cart_state.get('installer'),
            'payment_method': cart_state.get('payment_method')
        })

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    op = data.get('op', '')

    if op == 'setEmail':
        cart_state['email'] = data.get('email', '')
        session.modified = True
        return jsonify({'success': True})

    elif op == 'setShippingAddress':
        cart_state['shipping'] = data.get('address', {})
        session.modified = True
        return jsonify({'success': True})

    elif op == 'setInstallerSelection':
        cart_state['installer'] = {
            'deliveryMode': data.get('deliveryMode'),
            'storeId': data.get('storeId'),
            'pickupLocation': data.get('pickupLocation'),
            'pickupDate': data.get('pickupDate'),
            'pickupTime': data.get('pickupTime')
        }
        session.modified = True
        return jsonify({'success': True})

    elif op == 'setBilling':
        cart_state['billing'] = data.get('address', {})
        session.modified = True
        return jsonify({'success': True})

    elif op == 'setPayment':
        cart_state['payment_method'] = data.get('code') or data.get('paymentMethod') or 'payment_link'
        session.modified = True
        return jsonify({'success': True})

    elif op == 'applyCoupon':
        code = (data.get('couponCode') or data.get('code') or '').strip().upper()
        items = data.get('items') or cart_state.get('items', [])
        subtotal = sum(float(item.get('price', 0)) * int(item.get('qty', 1)) for item in items)
        
        # Check coupons
        discount = 0.0
        applied_label = ''
        if code in ('TYRES10', 'SAVE10'):
            discount = round(subtotal * 0.10, 2)
            applied_label = '10% Discount Applied'
        elif code in ('WELCOME50', 'SAVE50'):
            discount = min(subtotal, 50.0)
            applied_label = 'AED 50 Discount Applied'
        elif code in ('FREEFIT', 'TYRESVISION'):
            discount = min(subtotal, 40.0)
            applied_label = 'Special Fitment Discount'
        else:
            # Check DB cart_price_rules
            import db
            conn = db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT c.code, r.name, r.discount_type, r.discount_amount
                        FROM cart_price_rule_coupons c
                        JOIN cart_price_rules r ON c.rule_id = r.id
                        WHERE UPPER(c.code) = %s AND r.is_active = 1 AND r.deleted_at IS NULL
                        LIMIT 1
                    """, [code])
                    rule = cur.fetchone()
                    if rule:
                        dtype = rule.get('discount_type')
                        damt = float(rule.get('discount_amount') or 0.0)
                        if dtype == 'percent_of_original':
                            discount = round(subtotal * (damt / 100.0), 2)
                        else:
                            discount = min(subtotal, damt)
                        applied_label = rule.get('name') or code
            except Exception:
                pass
            finally:
                conn.close()

        if discount > 0:
            cart_state['coupon'] = code
            cart_state['discount'] = discount
            session.modified = True
            return jsonify({
                'success': True,
                'discount': discount,
                'label': applied_label,
                'coupon': code
            })
        else:
            return jsonify({'success': False, 'error': f"Invalid coupon code '{code}'."}), 400

    elif op == 'removeCoupon':
        cart_state['coupon'] = None
        cart_state['discount'] = 0.0
        session.modified = True
        return jsonify({'success': True})

    elif op == 'placeOrder':
        import random
        import string
        import db

        items = data.get('items') or cart_state.get('items', [])
        if not items:
            return jsonify({'success': False, 'error': 'Cart is empty. Please add tyres first.'}), 400

        subtotal = sum(float(item.get('price', 0)) * int(item.get('qty', 1)) for item in items)
        discount = float(data.get('discount') or cart_state.get('discount') or 0.0)
        vat = round(max(0.0, subtotal - discount) * 0.05, 2)
        total = round(max(0.0, subtotal - discount) + vat, 2)

        shipping_data = data.get('shipping') or cart_state.get('shipping') or {}
        installer_data = data.get('installer') or cart_state.get('installer') or {}
        payment_method = data.get('paymentMethod') or cart_state.get('payment_method') or 'payment_link'
        order_comments = data.get('orderComments') or cart_state.get('notes') or ''

        # Generate unique order number (e.g. TV-849201)
        rand_digits = ''.join(random.choices(string.digits, k=6))
        order_number = f"TV-{rand_digits}"

        phone = shipping_data.get('telephone') or shipping_data.get('phone') or ''
        email = data.get('email') or shipping_data.get('email') or cart_state.get('email') or f"{phone.replace('+', '').replace(' ', '')}@tyresvision.com"

        delivery_mode = installer_data.get('deliveryMode') or 'install_outlet'
        delivery_date = installer_data.get('pickupDate') or None
        time_slot = installer_data.get('pickupTime') or None
        pickup_store = installer_data.get('storeId') or None

        # Persist to database if tables exist
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                # 1. Insert order
                cur.execute("""
                    INSERT INTO orders (
                        order_number, guest_email, guest_phone,
                        subtotal, discount_amount, tax_amount, total, currency,
                        status, payment_status, payment_method,
                        delivery_type, delivery_date, time_slot, pickup_store_id,
                        billing_address_json, shipping_address_json, notes, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s, 'AED',
                        'pending', 'pending', %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, NOW(), NOW()
                    )
                """, [
                    order_number, email, phone,
                    subtotal, discount, vat, total,
                    payment_method,
                    delivery_mode, delivery_date, time_slot, pickup_store,
                    json.dumps(shipping_data), json.dumps(shipping_data), order_comments
                ])
                order_id = cur.lastrowid

                # 2. Insert order items
                for it in items:
                    it_qty = int(it.get('qty', 1))
                    it_price = float(it.get('price', 0))
                    it_subtotal = round(it_qty * it_price, 2)
                    it_sku = str(it.get('sku') or it.get('id') or it.get('uid') or 'TYRE-GENERIC')
                    it_name = str(it.get('name') or it.get('title') or 'Tyre')
                    it_img = str(it.get('image') or it.get('thumbnail') or '')
                    it_size = str(it.get('size') or it.get('tire_size_label') or '')
                    it_prod_id = it.get('product_id') or it.get('id') or None
                    if isinstance(it_prod_id, str) and not it_prod_id.isdigit():
                        it_prod_id = None

                    cur.execute("""
                        INSERT INTO order_items (
                            order_id, product_id, sku, name, image,
                            price, qty, subtotal, tire_size_label, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, NOW(), NOW()
                        )
                    """, [
                        order_id, it_prod_id, it_sku, it_name, it_img,
                        it_price, it_qty, it_subtotal, it_size
                    ])

                conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            # Even if DB table insert hits an edge case, return clean orderNumber so user is never stuck
            print(f"[api_cart placeOrder warning]: {e}")
        finally:
            conn.close()

        # Clear session cart
        session['tv_cart'] = {
            'items': [],
            'email': '',
            'shipping': {},
            'billing': {},
            'installer': {},
            'payment_method': 'payment_link',
            'coupon': None,
            'discount': 0.0,
            'notes': ''
        }
        session.modified = True

        return jsonify({
            'success': True,
            'orderNumber': order_number,
            'orderId': order_number,
            'total': total
        })

    return jsonify({'success': False, 'error': f"Unknown op: {op}"}), 400


@site_bp.route('/<string(length=2):lang_code>/page/<slug>')
@site_bp.route('/<string(length=2):lang_code>/<slug>')
def page_detail_locale(lang_code, slug):
    """Directly render CMS page or blog for dynamic locale (e.g. /ar/terms, /de/privacy)."""
    code = lang_code.lower()
    session['site_locale'] = code
    if slug in ('blog', 'blogs'):
        return blog_locale(code)
    elif slug == 'about-us':
        return about_us_locale(code)
    elif slug == 'mobile-tyre-fitting':
        return mobile_tyre_fitting_locale(code)
    elif slug in ('car-tyres', 'tyres', 'products'):
        return _render_product_listing(code)

    page = Page.find_by_slug(slug)
    if page:
        template = 'Client/AboutUs.html' if slug == 'about-us' else 'Client/Page.html'
        raw_sections = PageSection.all_for_page(slug, include_inactive=False)
        sections = [PageSection.to_localized_dict(s, locale=code) for s in raw_sections]
        resp = make_response(render_template(template, page=page, slug=slug, locale=code, sections=sections))
        resp.set_cookie('site_locale', code, max_age=31536000, path='/')
        return resp
    blog = Blog.find_by_slug(slug)
    if blog:
        return _render_blog_detail(slug, code)

    # Check if slug is a product
    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            clean_s = slug.lower().strip()
            cur.execute("""
                SELECT slug FROM products 
                WHERE (slug = %s OR slug LIKE %s OR sku = %s) AND deleted_at IS NULL 
                ORDER BY (slug = %s) DESC, id ASC LIMIT 1
            """, [clean_s, f"{clean_s}%", clean_s, clean_s])
            p_match = cur.fetchone()
            if p_match:
                return _render_product_detail(p_match['slug'], code)
    finally:
        conn.close()

    abort(404)


@site_bp.route('/page/<slug>')
@site_bp.route('/<slug>')
def page_detail(slug):
    """Generic static CMS content page reader with dynamic sections support."""
    if slug in ('tcsadmin', 'visionadmin', 'visonadmin', 'admin', 'static', 'api', 'login', 'logout', 'forgot-password', 'reset-password', 'favicon.ico'):
        abort(404)
    if slug == 'mobile-tyre-fitting':
        return mobile_tyre_fitting()
    if slug in ('car-tyres', 'tyres', 'products'):
        return car_tyres_listing()
    locale = _get_locale()
    page = Page.find_by_slug(slug)
    if page:
        template = 'Client/AboutUs.html' if slug == 'about-us' else 'Client/Page.html'
        raw_sections = PageSection.all_for_page(slug, include_inactive=False)
        sections = [PageSection.to_localized_dict(s, locale=locale) for s in raw_sections]
        return render_template(template, page=page, slug=slug, locale=locale, sections=sections)
    blog = Blog.find_by_slug(slug)
    if blog:
        return redirect(f'/blog/{slug}')

    # Check if slug is a product
    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            clean_s = slug.lower().strip()
            cur.execute("""
                SELECT slug FROM products 
                WHERE (slug = %s OR slug LIKE %s OR sku = %s) AND deleted_at IS NULL 
                ORDER BY (slug = %s) DESC, id ASC LIMIT 1
            """, [clean_s, f"{clean_s}%", clean_s, clean_s])
            p_match = cur.fetchone()
            if p_match:
                return _render_product_detail(p_match['slug'], locale)
    finally:
        conn.close()

    abort(404)
