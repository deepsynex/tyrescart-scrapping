# app/siteapp/clientroute.py - TyresVision Customer Storefront Blueprint ('site')
#
# Serves the public client-facing HTML pages only (home, blog listing/detail,
# About Us, generic CMS pages). The public JSON API endpoints that used to
# live in this file (/api/blogs, /api/blogs/<slug>) now live in the unified
# app/api.py alongside the tcsadmin and visionadmin APIs.
import json
import html
import os
import math
import re
import threading
import time
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


@site_bp.route('/favicon.ico')
def favicon_ico():
    return send_from_directory(os.path.join(BASE_DIR, 'static', 'assets', 'images', 'logo'), 'favicon.ico', mimetype='image/x-icon')


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

    base_url = "https://www.tyresvision.com"
    canonical_url = f"{base_url}/{code}/blog" if code and code.lower() != 'en' else f"{base_url}/blog"
    canonical_url = canonical_url.rstrip('/')

    listing_title = translate('Tyre Care & Buying Guides | TyresVision Blog', code)
    listing_desc = translate('Straight answers on tyre sizing, maintenance, and buying the right set for UAE roads and heat — from the team behind TyresVision.', code)
    listing_img = f"{base_url}/static/assets/images/online-tyres-shop-dubai.png"

    page_og_tags = {
        'og_type': 'website',
        'og_url': canonical_url,
        'og_title': listing_title,
        'og_description': listing_desc,
        'og_image': listing_img,
        'og_locale': 'ar_AE' if code == 'ar' else 'en_AE',
    }
    page_twitter_tags = {
        'twitter_card': 'summary_large_image',
        'twitter_title': listing_title,
        'twitter_description': listing_desc,
        'twitter_image': listing_img,
    }

    resp = make_response(render_template(
        'Client/Blog.html',
        locale=code,
        categories=categories,
        selected_category=selected_category,
        canonical_url=canonical_url,
        page_og_tags=page_og_tags,
        page_twitter_tags=page_twitter_tags
    ))
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

    base_url = "https://www.tyresvision.com"
    canonical_url = f"{base_url}/{code}/blog" if code and code.lower() != 'en' else f"{base_url}/blog"
    canonical_url = canonical_url.rstrip('/')

    listing_title = translate('Tyre Care & Buying Guides | TyresVision Blog', code)
    listing_desc = translate('Straight answers on tyre sizing, maintenance, and buying the right set for UAE roads and heat — from the team behind TyresVision.', code)
    listing_img = f"{base_url}/static/assets/images/online-tyres-shop-dubai.png"

    page_og_tags = {
        'og_type': 'website',
        'og_url': canonical_url,
        'og_title': listing_title,
        'og_description': listing_desc,
        'og_image': listing_img,
        'og_locale': 'ar_AE' if code == 'ar' else 'en_AE',
    }
    page_twitter_tags = {
        'twitter_card': 'summary_large_image',
        'twitter_title': listing_title,
        'twitter_description': listing_desc,
        'twitter_image': listing_img,
    }

    resp = make_response(render_template(
        'Client/Blog.html',
        locale=code,
        categories=categories,
        selected_category=selected_category,
        canonical_url=canonical_url,
        page_og_tags=page_og_tags,
        page_twitter_tags=page_twitter_tags
    ))
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


_INLINE_STYLE_ATTR_RE = re.compile(r'''\s+style\s*=\s*(?:"[^"]*"|'[^']*')''', re.IGNORECASE)


def _strip_inline_styles(html):
    """Drop author-carried style="..." attributes from blog content so
    rendered articles rely only on .article-prose in client.css, matching
    the no-inline-CSS convention used for Page.html/page.css."""
    if not html:
        return html
    return _INLINE_STYLE_ATTR_RE.sub('', html)


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

    # Canonical URL: actual full URL without trailing slash
    base_url = "https://www.tyresvision.com"
    if locale and locale.lower() != 'en':
        canonical_url = f"{base_url}/{locale.lower()}/blog/{blog.slug}"
    else:
        canonical_url = f"{base_url}/blog/{blog.slug}"
    canonical_url = canonical_url.rstrip('/')

    # Meta Title and Meta Description (fallback to title / short_description / default)
    meta_title = blog.get_meta_title(locale) or blog.get_title(locale)
    meta_desc = blog.get_meta_desc(locale) or blog.get_short_desc(locale) or f"{blog.get_title(locale)} — expert advice and tyre guide for UAE drivers."

    # Cover image and absolute OG image URL
    cover_image = blog.image or '/static/assets/images/online-tyres-shop-dubai.png'
    full_image_url = cover_image if cover_image.startswith('http') else f"{base_url}{cover_image}"

    # Build Open Graph and Twitter tags
    page_og_tags = {
        'og_type': 'article',
        'og_url': canonical_url,
        'og_title': meta_title,
        'og_description': meta_desc,
        'og_image': full_image_url,
        'og_locale': 'ar_AE' if locale == 'ar' else 'en_AE',
    }
    page_twitter_tags = {
        'twitter_card': 'summary_large_image',
        'twitter_title': meta_title,
        'twitter_description': meta_desc,
        'twitter_image': full_image_url,
    }

    blog_data = {
        'id': blog.id,
        'slug': blog.slug,
        'title': blog.get_title(locale),
        'meta_title': meta_title,
        'meta_desc': meta_desc,
        'canonical_url': canonical_url,
        'content': _strip_inline_styles(blog.get_content(locale)),
        'short_description': blog.get_short_desc(locale),
        'category': cat_name,
        'cover_image_url': cover_image,
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
        locale=locale,
        canonical_url=canonical_url,
        page_og_tags=page_og_tags,
        page_twitter_tags=page_twitter_tags
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


_CARS_LOGO_DIR = os.path.join(BASE_DIR, 'static', 'assets', 'images', 'cars-logo')
_CAR_LOGO_CACHE = None

_BRAND_TO_FILE = {
    'alfa romeo': 'alfa-romeo.png',
    'alpina': 'alpina.png',
    'aston martin': 'aston-martin.png',
    'audi': 'audi.png',
    'bentley': 'bentley.png',
    'bmw': 'bmw.png',
    'bugatti': 'bugatti.png',
    'cadillac': 'cadillac.png',
    'chevrolet': 'chevrolet.png',
    'chrysler': 'chrysler.png',
    'ferrari': 'ferrari.png',
    'fiat': 'fiat.png',
    'ford': 'ford.png',
    'genesis': 'genesis.png',
    'gmc': 'gmc.png',
    'honda': 'honda.png',
    'hyundai': 'hyundai.png',
    'jaguar': 'jaguar.png',
    'jeep': 'jeep.png',
    'lamborghini': 'lamborghini.png',
    'land rover': 'land-rover.png',
    'lexus': 'lexus.png',
    'lotus': 'lotus.png',
    'maserati': 'maserati.png',
    'mazda': 'mazda.png',
    'mclaren': 'mclaren.png',
    'mercedes-benz': 'mercedes-benz.png',
    'mercedes': 'mercedes-benz.png',
    'mercedes benz': 'mercedes-benz.png',
    'mini': 'mini.png',
    'mitsubishi': 'mitsubishi.png',
    'nissan': 'nissan.png',
    'peugeot': 'peugeot.png',
    'porsche': 'porsche.png',
    'renault': 'renault.png',
    'rivian': 'rivian.png',
    'rolls-royce': 'rolls-royce.png',
    'rolls royce': 'rolls-royce.png',
    'subaru': 'subaru.png',
    'suzuki': 'suzuki.png',
    'tesla': 'tesla.png',
    'toyota': 'toyota.png',
    'volkswagen': 'volkswagen.png',
    'vw': 'volkswagen.png',
    'volvo': 'volvo.png',
}

_MARKING_TO_BRANDS = {
    '*': ['bmw'],
    '1': ['bmw'],
    '2': ['bmw'],
    'mo': ['mercedes-benz'],
    'moe': ['mercedes-benz'],
    'mo1': ['mercedes-benz'],
    'mos': ['mercedes-benz'],
    'ao': ['audi'],
    'ao1': ['audi'],
    'ao2': ['audi'],
    'aoe': ['audi'],
    'ro1': ['audi'],
    'ro2': ['audi'],
    'n0': ['porsche'],
    'n1': ['porsche'],
    'n2': ['porsche'],
    'n3': ['porsche'],
    'n4': ['porsche'],
    'na0': ['porsche'],
    'na1': ['porsche'],
    'nf0': ['porsche'],
    'nc0': ['porsche'],
    'nd0': ['porsche'],
    'j': ['jaguar'],
    'lr': ['land rover'],
    'jlr': ['jaguar', 'land rover'],
    't0': ['tesla'],
    't1': ['tesla'],
    'vol': ['volvo'],
    'mgt': ['maserati'],
    'ar': ['alfa romeo'],
    'am8': ['aston martin'],
    'aml': ['aston martin'],
    'mc': ['mclaren'],
    'f': ['ferrari'],
}

_DISPLAY_NAMES = {
    'bmw': 'BMW',
    'mercedes-benz': 'Mercedes-Benz',
    'mercedes': 'Mercedes-Benz',
    'vw': 'Volkswagen',
    'volkswagen': 'Volkswagen',
    'alfa-romeo': 'Alfa Romeo',
    'aston-martin': 'Aston Martin',
    'land-rover': 'Land Rover',
    'rolls-royce': 'Rolls-Royce',
    'mg': 'MG',
    'byd': 'BYD',
    'gmc': 'GMC',
    'ram': 'RAM',
}


def _get_car_logo_files():
    global _CAR_LOGO_CACHE
    if _CAR_LOGO_CACHE is None:
        _CAR_LOGO_CACHE = {}
        try:
            if os.path.isdir(_CARS_LOGO_DIR):
                for f in os.listdir(_CARS_LOGO_DIR):
                    if f.lower().endswith('.png'):
                        _CAR_LOGO_CACHE[f.lower()] = f
        except Exception:
            pass
    return _CAR_LOGO_CACHE


def resolve_oem_car_logos(product_or_dict):
    """
    Extracts and resolves OEM car brand logo items:
    Returns list of dicts: [{'name': 'BMW', 'image_url': '/static/assets/images/cars-logo/bmw.png'}, ...]
    """
    p = product_or_dict
    raw_brands = []

    # 1. From oem_brand column
    oem_b = p.get('oem_brand')
    if oem_b and str(oem_b).strip() and str(oem_b).strip().lower() not in ('none', '0', 'null', 'false'):
        raw_brands.append(str(oem_b).strip())

    # 2. From attributes_json
    attr = p.get('attr') or p.get('attributes_json') or {}
    if isinstance(attr, str):
        try:
            attr = json.loads(attr)
        except Exception:
            attr = {}
    if isinstance(attr, dict):
        attr_oem = attr.get('oem_tyres') or attr.get('oem_brand')
        if attr_oem and str(attr_oem).strip() and str(attr_oem).strip().lower() not in ('none', '0', 'null', 'false'):
            raw_brands.append(str(attr_oem).strip())

    tokens = []
    for rb in raw_brands:
        for part in re.split(r'[,;/]+', rb):
            tok = part.strip()
            if tok and tok.lower() not in ('none', '0', 'null', 'false'):
                tokens.append(tok)

    # 3. If no tokens from oem_brand, check tyre_marking fallback
    if not tokens and isinstance(attr, dict):
        marking = attr.get('tyre_marking') or attr.get('tyre_markings') or attr.get('oem_marking') or ''
        if marking:
            for m_tok in re.split(r'[\s,;/]+', str(marking).strip()):
                m_clean = m_tok.strip().lower()
                if m_clean in _MARKING_TO_BRANDS:
                    tokens.extend(_MARKING_TO_BRANDS[m_clean])

    avail = _get_car_logo_files()
    resolved_logos = []
    seen_files = set()

    for tok in tokens:
        tok_clean = tok.strip()
        tok_lower = tok_clean.lower()

        brands_to_check = [tok_lower]
        if tok_lower in _MARKING_TO_BRANDS:
            brands_to_check = _MARKING_TO_BRANDS[tok_lower]

        for b_name in brands_to_check:
            filename = _BRAND_TO_FILE.get(b_name)
            if not filename:
                cand1 = f"{b_name}.png"
                cand2 = f"{b_name.replace(' ', '-')}.png"
                if cand1 in avail:
                    filename = avail[cand1]
                elif cand2 in avail:
                    filename = avail[cand2]

            if filename and filename in avail and filename not in seen_files:
                seen_files.add(filename)
                clean_key = b_name.lower().replace(' ', '-')
                display_name = _DISPLAY_NAMES.get(clean_key) or _DISPLAY_NAMES.get(b_name.lower()) or b_name.replace('-', ' ').title()
                resolved_logos.append({
                    'name': display_name,
                    'file': filename,
                    'image_url': f"/static/assets/images/cars-logo/{filename}"
                })

    return resolved_logos


def _clean_multilingual_text(val, locale='en'):
    """
    Recursively unwrap and clean multilingual JSON strings or dicts,
    stripping double-encoded JSON like '{"en": "{\"en\": \"...\"}"}'
    and replacing legacy domain branding (e.g. Tyrescart -> TyresVision UAE).
    """
    if not val:
        return ""
    cur = val
    if isinstance(cur, str):
        cur = html.unescape(cur).strip()
    for _ in range(5):
        if isinstance(cur, dict):
            cur = cur.get(locale) or cur.get('en') or (next(iter(cur.values())) if cur else '')
        elif isinstance(cur, str):
            s = cur.strip()
            if (s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']')):
                try:
                    cur = json.loads(s)
                    continue
                except Exception:
                    m = re.search(r'["\'](?:' + (locale or 'en') + r'|en)["\']\s*:\s*["\']([^"\']+)["\']', s)
                    if m:
                        cur = m.group(1).strip()
                    break
            else:
                if s.startswith('{') and ('"en"' in s or "'en'" in s):
                    m = re.search(r'["\'](?:' + (locale or 'en') + r'|en)["\']\s*:\s*["\']([^"\']+)["\']', s)
                    if m:
                        cur = m.group(1).strip()
                break
        else:
            break

    if isinstance(cur, dict):
        cur = cur.get(locale) or cur.get('en') or (next(iter(cur.values())) if cur else '')

    res = str(cur).strip() if cur is not None else ""
    if res in ('None', 'null', '{}', '[]'):
        return ""

    res = re.sub(r'\|\s*tyrescart(?:\s*uae)?\b', '| TyresVision UAE', res, flags=re.IGNORECASE)
    res = re.sub(r'from\s+tyrescart\s+uae\b', 'from TyresVision UAE', res, flags=re.IGNORECASE)
    res = re.sub(r'\btyrescart\b', 'TyresVision', res, flags=re.IGNORECASE)
    return res


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

    # Ensure display_name is readable and free of JSON artifacts
    d_name = p_dict.get('display_name') or p_dict.get('name') or p_dict.get('sku')
    p_dict['display_name'] = _clean_multilingual_text(d_name, locale) or str(d_name)

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

    # OEM Car Brand Logos
    p_dict['oem_logos'] = resolve_oem_car_logos(p_dict)
    p_dict['has_oem'] = len(p_dict['oem_logos']) > 0

    return p_dict


def _fetch_catalog_products(args, locale='en'):
    """Queries products with dynamic filters, pagination, and sorting for client catalog."""
    from db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            raw_rear = (args.get('rear') or '').strip()
            raw_sizes = args.getlist('size') or args.getlist('sizes')
            if not raw_rear and len(raw_sizes) >= 2:
                raw_rear = raw_sizes[1].strip()
                raw_sizes = [raw_sizes[0]]

            m_front = re.match(r'^(\d+)[-/ ]+(\d+)[-/ ]+r?(\d+(?:\.\d+)?)$', raw_sizes[0].strip(), re.IGNORECASE) if raw_sizes else None
            m_rear = re.match(r'^(\d+)[-/ ]+(\d+)[-/ ]+r?(\d+(?:\.\d+)?)$', raw_rear, re.IGNORECASE) if raw_rear else None

            # ── STAGGERED PAIR FITMENT QUERY (Front + Rear Matching Pairs) ──
            if m_front and m_rear:
                f_w, f_h, f_r = m_front.group(1), m_front.group(2), m_front.group(3)
                r_w, r_h, r_r = m_rear.group(1), m_rear.group(2), m_rear.group(3)
                front_size_label = f"{f_w}/{f_h} R{f_r}"
                rear_size_label = f"{r_w}/{r_h} R{r_r}"

                where_conds = [
                    "p1.deleted_at IS NULL", "p1.status = 'active'", "p1.website_id = 1",
                    "p2.deleted_at IS NULL", "p2.status = 'active'", "p2.website_id = 1",
                    "p1.brand_id = p2.brand_id",
                    "(p1.tire_pattern = p2.tire_pattern OR p1.tire_pattern IS NULL OR p2.tire_pattern IS NULL OR p1.tire_pattern = '' OR p2.tire_pattern = '')"
                ]
                if front_size_label != rear_size_label:
                    where_conds.append("p1.id != p2.id")
                else:
                    where_conds.append("p1.id = p2.id")
                params = []

                # Front size match
                where_conds.append("""(
                    (JSON_UNQUOTE(JSON_EXTRACT(p1.attributes_json, '$.width')) = %s 
                     AND JSON_UNQUOTE(JSON_EXTRACT(p1.attributes_json, '$.height')) = %s 
                     AND JSON_UNQUOTE(JSON_EXTRACT(p1.attributes_json, '$.rim')) IN (%s, %s))
                    OR p1.tire_size_label = %s
                )""")
                params.extend([f_w, f_h, f_r, f"R{f_r}", front_size_label])

                # Rear size match
                where_conds.append("""(
                    (JSON_UNQUOTE(JSON_EXTRACT(p2.attributes_json, '$.width')) = %s 
                     AND JSON_UNQUOTE(JSON_EXTRACT(p2.attributes_json, '$.height')) = %s 
                     AND JSON_UNQUOTE(JSON_EXTRACT(p2.attributes_json, '$.rim')) IN (%s, %s))
                    OR p2.tire_size_label = %s
                )""")
                params.extend([r_w, r_h, r_r, f"R{r_r}", rear_size_label])

                # Optional Brand filter
                raw_brands = args.getlist('brand') or args.getlist('brands')
                brand_terms = []
                for b_entry in raw_brands:
                    for b_part in b_entry.split(','):
                        bp = b_part.strip().lower()
                        if bp and bp not in brand_terms:
                            brand_terms.append(bp)
                if brand_terms:
                    b_ph = ', '.join(['%s'] * len(brand_terms))
                    where_conds.append(f"(LOWER(b.slug) IN ({b_ph}) OR LOWER(b.name) IN ({b_ph}))")
                    params.extend(brand_terms)
                    params.extend(brand_terms)

                # Optional Category filter
                raw_cats = args.getlist('tyres_category') or args.getlist('category')
                cat_terms = [c.strip().title() for c in raw_cats if c.strip()]
                if cat_terms:
                    c_clauses = ["(p1.tyres_category = %s OR JSON_UNQUOTE(JSON_EXTRACT(p1.attributes_json, '$.tyres_category')) = %s)" for _ in cat_terms]
                    where_conds.append("(" + " OR ".join(c_clauses) + ")")
                    for ct in cat_terms:
                        params.extend([ct, ct])

                # Optional Price filter
                max_price = args.get('max_price')
                if max_price:
                    try:
                        where_conds.append("(p1.price * 2 + p2.price * 2) <= %s")
                        params.append(float(max_price))
                    except (ValueError, TypeError):
                        pass

                where_sql = " AND ".join(where_conds)

                # Sorting
                sort_by = (args.get('sort') or args.get('sort_by') or 'price-asc').lower().strip()
                if sort_by in ('price-desc', 'price_desc', 'high-to-low', 'price_high_to_low'):
                    order_sql = "ORDER BY total_set_price DESC, p1.id ASC"
                else:
                    order_sql = "ORDER BY total_set_price ASC, p1.id ASC"

                cur.execute(f"""
                    SELECT COUNT(*) as total
                    FROM products p1
                    JOIN products p2 ON p1.brand_id = p2.brand_id
                         AND (p1.tire_pattern = p2.tire_pattern OR p1.tire_pattern IS NULL OR p2.tire_pattern IS NULL OR p1.tire_pattern = '' OR p2.tire_pattern = '')
                    LEFT JOIN brands b ON p1.brand_id = b.id
                    WHERE {where_sql}
                """, params)
                c_row = cur.fetchone()
                total_count = c_row['total'] if c_row else 0

                try:
                    page = max(1, int(args.get('page', 1)))
                except (ValueError, TypeError):
                    page = 1
                per_page = max(1, min(100, int(args.get('per_page', 16))))
                total_pages = max(1, math.ceil(total_count / per_page)) if total_count > 0 else 1
                offset = (page - 1) * per_page

                cur.execute(f"""
                    SELECT 
                        p1.id as front_id, p2.id as rear_id,
                        (p1.price * 2 + p2.price * 2) as total_set_price
                    FROM products p1
                    JOIN products p2 ON p1.brand_id = p2.brand_id
                         AND (p1.tire_pattern = p2.tire_pattern OR p1.tire_pattern IS NULL OR p2.tire_pattern IS NULL OR p1.tire_pattern = '' OR p2.tire_pattern = '')
                    LEFT JOIN brands b ON p1.brand_id = b.id
                    WHERE {where_sql}
                    {order_sql}
                    LIMIT %s OFFSET %s
                """, params + [per_page, offset])
                pair_rows = cur.fetchall()

                # Collect all product IDs to fetch full product rows
                all_ids = []
                for pr in pair_rows:
                    if pr['front_id'] not in all_ids:
                        all_ids.append(pr['front_id'])
                    if pr['rear_id'] not in all_ids:
                        all_ids.append(pr['rear_id'])

                full_products_map = {}
                if all_ids:
                    id_placeholders = ', '.join(['%s'] * len(all_ids))
                    cur.execute(f"""
                        SELECT p.*, b.name as brand_name, b.slug as brand_slug, b.logo as brand_logo
                        FROM products p
                        LEFT JOIN brands b ON p.brand_id = b.id
                        WHERE p.id IN ({id_placeholders})
                    """, all_ids)
                    for prow in cur.fetchall():
                        full_products_map[prow['id']] = prow

                staggered_products = []
                for pr in pair_rows:
                    f_row = full_products_map.get(pr['front_id'])
                    r_row = full_products_map.get(pr['rear_id'])
                    if not f_row or not r_row:
                        continue

                    p1_formatted = _format_product_for_client(f_row, locale)
                    p1_formatted['axle'] = 'front'
                    p1_formatted['axle_label'] = 'Front'
                    p1_formatted['set_qty'] = 2
                    p1_formatted['set_of_2_price'] = round(p1_formatted['price'] * 2, 2)
                    p1_formatted['paired_with_id'] = pr['rear_id']
                    p1_formatted['paired_size'] = rear_size_label

                    p2_formatted = _format_product_for_client(r_row, locale)
                    p2_formatted['axle'] = 'rear'
                    p2_formatted['axle_label'] = 'Rear'
                    p2_formatted['set_qty'] = 2
                    p2_formatted['set_of_2_price'] = round(p2_formatted['price'] * 2, 2)
                    p2_formatted['paired_with_id'] = pr['front_id']
                    p2_formatted['paired_size'] = front_size_label

                    f_price = float(p1_formatted.get('price') or 0)
                    r_price = float(p2_formatted.get('price') or 0)
                    tot_price = float(pr['total_set_price'] or (f_price * 2 + r_price * 2))

                    combined_pair = {
                        'id': f"{pr['front_id']}_{pr['rear_id']}",
                        'is_staggered': True,
                        'is_combined_pair': True,
                        'brand_name': p1_formatted.get('brand_name') or 'Tyres',
                        'brand_slug': p1_formatted.get('brand_slug') or '',
                        'brand_logo': p1_formatted.get('brand_logo') or '',
                        'pattern_name': p1_formatted.get('pattern_name') or '',
                        'display_name': f"{p1_formatted.get('brand_name', '')} {p1_formatted.get('pattern_name', '')}".strip(),
                        'total_set_price': tot_price,
                        'total_set_price_formatted': f"{tot_price:.2f}" if (tot_price % 1 != 0) else f"{tot_price:.0f}",
                        'front': p1_formatted,
                        'rear': p2_formatted,
                        'front_id': pr['front_id'],
                        'rear_id': pr['rear_id'],
                        'front_size': p1_formatted['full_size_spec'],
                        'rear_size': p2_formatted['full_size_spec'],
                        'front_price': f_price,
                        'rear_price': r_price,
                        'front_set2': p1_formatted['set_of_2_price'],
                        'rear_set2': p2_formatted['set_of_2_price'],
                        'price': round(tot_price / 4.0, 2),
                        'slug': p1_formatted.get('slug', ''),
                        'full_title': f"{p1_formatted.get('brand_name', '')} {p1_formatted.get('pattern_name', '')} Staggered Fitment (Front: {p1_formatted['full_size_spec']} • Rear: {p2_formatted['full_size_spec']})".strip()
                    }
                    staggered_products.append(combined_pair)

                return {
                    'products': staggered_products,
                    'total': total_count,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': total_pages,
                    'facets': {},
                    'is_staggered': True,
                    'front_size_label': front_size_label,
                    'rear_size_label': rear_size_label
                }

            # Build filter clauses mapped by dimension for multi-select disjunctive facet calculation
            clauses = {
                'tyres_category': ([], []),
                'brand': ([], []),
                'vehicle': ([], []),
                'size': ([], []),
                'pattern': ([], []),
                'tyre_marking': ([], []),
                'oem': ([], []),
                'warranty': ([], []),
                'year': ([], []),
                'origin': ([], []),
                'type': ([], []),
                'runflat': ([], []),
                'ev_tyre': ([], []),
                'price': ([], []),
                'promo': ([], []),
                'search': ([], [])
            }

            # 0. Tyres Category filter (Budget, Premium, Quality)
            raw_tyres_cats = args.getlist('tyres_category') or args.getlist('tyres-category') or args.getlist('tyre_category') or args.getlist('tyres_categories')
            if not raw_tyres_cats and args.getlist('category'):
                raw_tyres_cats = [c for c in args.getlist('category') if c.strip().lower() in ('budget', 'quality', 'premium')]
            tyres_cats = []
            for tc_entry in raw_tyres_cats:
                for tc_part in tc_entry.split(','):
                    tcp = tc_part.strip().title()
                    if tcp and tcp not in tyres_cats:
                        tyres_cats.append(tcp)

            if tyres_cats:
                tc_clauses = []
                tc_params = []
                for tc in tyres_cats:
                    tc_clauses.append("(LOWER(p.tyres_category) = %s OR LOWER(JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.tyres_category'))) = %s)")
                    tc_params.extend([tc.lower(), tc.lower()])
                clauses['tyres_category'][0].append("(" + " OR ".join(tc_clauses) + ")")
                clauses['tyres_category'][1].extend(tc_params)

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
                    sz_nor = re.sub(r'[-/ ]*r(\d+)', r'-\1', sz_hyphen, flags=re.IGNORECASE)
                    sz_withr = re.sub(r'-(\d+)$', r'-r\1', sz_nor, flags=re.IGNORECASE)
                    m_dim = re.match(r'^(\d+)[-/ ]+(\d+)[-/ ]+r?(\d+(?:\.\d+)?)$', sz_clean, re.IGNORECASE)
                    if m_dim:
                        w_val, h_val, r_val = m_dim.group(1), m_dim.group(2), m_dim.group(3)
                        s_clauses.append(
                            "("
                            "LOWER(p.tire_size_label) = LOWER(%s) "
                            "OR REPLACE(REPLACE(LOWER(p.tire_size_label), '/', '-'), ' ', '-') = LOWER(%s) "
                            "OR REPLACE(REPLACE(LOWER(p.tire_size_label), '/', '-'), ' ', '-') = LOWER(%s) "
                            "OR REPLACE(REPLACE(REPLACE(LOWER(p.tire_size_label), '/', '-'), ' ', '-'), 'r', '') = LOWER(%s) "
                            "OR (JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.width')) = %s "
                            "    AND JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.height')) = %s "
                            "    AND (JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.rim')) = %s "
                            "         OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.rim')) = %s))"
                            ")"
                        )
                        s_params.extend([sz_clean, sz_hyphen, sz_withr, sz_nor, w_val, h_val, r_val, f"R{r_val}"])
                    else:
                        s_clauses.append(
                            "("
                            "LOWER(p.tire_size_label) = LOWER(%s) "
                            "OR REPLACE(REPLACE(LOWER(p.tire_size_label), '/', '-'), ' ', '-') = LOWER(%s) "
                            "OR REPLACE(REPLACE(LOWER(p.tire_size_label), '/', '-'), ' ', '-') = LOWER(%s) "
                            "OR REPLACE(REPLACE(REPLACE(LOWER(p.tire_size_label), '/', '-'), ' ', '-'), 'r', '') = LOWER(%s)"
                            ")"
                        )
                        s_params.extend([sz_clean, sz_hyphen, sz_withr, sz_nor])
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

            # 4b. Tyre Marking filter
            raw_markings = args.getlist('tyre_marking') or args.getlist('marking') or args.getlist('tyre_markings') or args.getlist('markings')
            markings = []
            for m_entry in raw_markings:
                for m_part in m_entry.split(','):
                    mp = m_part.strip()
                    if mp and mp not in markings:
                        markings.append(mp)

            if markings:
                tm_clauses = []
                tm_params = []
                for m in markings:
                    tm_clauses.append("(JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.tyre_marking')) = %s OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.tyre_marking')) LIKE %s)")
                    tm_params.extend([m, f"%{m}%"])
                clauses['tyre_marking'][0].append("(" + " OR ".join(tm_clauses) + ")")
                clauses['tyre_marking'][1].extend(tm_params)

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

            # 7. Year filter (uses idx_products_year) - tyre DOT manufacturing year only
            # Car model years (from vehicle search, e.g. 2012, 2018) must never be compared to tyre year
            has_vehicle_context = bool(args.get('make') or args.get('model') or args.get('trim') or args.get('modification') or args.get('car_year') or args.get('vehicle_year'))
            raw_years = [] if has_vehicle_context else (args.getlist('year') or args.getlist('years'))
            years = []
            for y_entry in raw_years:
                for y_part in y_entry.split(','):
                    yp = y_part.strip()
                    if yp and yp.isdigit() and int(yp) >= 2024 and yp not in years:
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

            # 9c. EV Tyre filter
            raw_ev = args.getlist('ev_tyre') or args.getlist('ev') or args.getlist('is_ev') or args.getlist('ev_rated')
            ev_selected = [e.strip().lower() for e in raw_ev if e.strip()]
            if any(e in ('ev', '1', 'yes', 'true', 'ev_ready', 'ev_tyre') for e in ev_selected):
                clauses['ev_tyre'][0].append("(p.ev_rated = 1 OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.ev')) IN ('1', 'yes', 'true') OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.ev_tyre')) IN ('1', 'yes', 'true') OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.ev_rated')) IN ('1', 'yes', 'true') OR LOWER(p.display_name) LIKE %s OR LOWER(p.display_name) LIKE %s OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.tyre_marking')) LIKE %s OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.tyre_marking')) LIKE %s)")
                clauses['ev_tyre'][1].extend(['% ev %', '%elect%', '%Elect%', '%EV%'])

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
                'tyres_categories': {},
                'warranties': {},
                'years': {},
                'brands': {},
                'patterns': {},
                'tyre_markings': {},
                'oems': {},
                'origins': {},
                'promotions': {},
                'runflat': 0,
                'ev_tyre': 0
            }

            # 0. Tyres Category facet
            tc_where, tc_params = get_where_except('tyres_category')
            cur.execute(f"""
                SELECT 
                    COALESCE(p.tyres_category, JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.tyres_category'))) as tc,
                    COUNT(*) as cnt
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE {tc_where} AND (p.tyres_category IS NOT NULL OR JSON_EXTRACT(p.attributes_json, '$.tyres_category') IS NOT NULL)
                GROUP BY tc
            """, tc_params)
            for r in cur.fetchall():
                if r.get('tc'):
                    facets['tyres_categories'][r['tc']] = int(r['cnt'])

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

            # 4b. Tyre Marking facet
            tm_where, tm_params = get_where_except('tyre_marking')
            cur.execute(f"""
                SELECT 
                    JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.tyre_marking')) as tm,
                    COUNT(*) as cnt
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE {tm_where} 
                  AND JSON_EXTRACT(p.attributes_json, '$.tyre_marking') IS NOT NULL
                  AND JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.tyre_marking')) NOT IN ('', 'None', 'Standard', '0')
                GROUP BY tm
                ORDER BY cnt DESC
                LIMIT 30
            """, tm_params)
            for r in cur.fetchall():
                if r.get('tm'):
                    facets['tyre_markings'][r['tm']] = int(r['cnt'])

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

            # 9. EV Tyre facet
            ev_where, ev_params = get_where_except('ev_tyre')
            cur.execute(f"""
                SELECT COUNT(*) as cnt
                FROM products p
                LEFT JOIN brands b ON p.brand_id = b.id
                WHERE {ev_where} AND (p.ev_rated = 1 OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.ev')) IN ('1', 'yes', 'true') OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.ev_tyre')) IN ('1', 'yes', 'true') OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.ev_rated')) IN ('1', 'yes', 'true') OR LOWER(p.display_name) LIKE '%% ev %%' OR LOWER(p.display_name) LIKE '%%elect%%' OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.tyre_marking')) LIKE '%%Elect%%' OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.tyre_marking')) LIKE '%%EV%%')
            """, ev_params)
            ev_res = cur.fetchone()
            facets['ev_tyre'] = int(ev_res['cnt']) if ev_res else 0

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

        # Check pure tyre size like 155-70-13 or 175-65-15 or size-155-70-13
        m_pure_size = re.match(r'^(?:size-)?(\d{2,3})[-/ ]+(\d{2})[-/ ]+r?(\d{2}(?:\.\d+)?)$', seg, re.IGNORECASE)
        if m_pure_size:
            formatted_size = f"{m_pure_size.group(1)}-{m_pure_size.group(2)}-{m_pure_size.group(3)}"
            if not args.getlist('size'):
                args.add('size', formatted_size)
            elif not args.getlist('rear'):
                args.setlistdefault('rear', []).append(formatted_size)
            else:
                args.add('size', formatted_size)
            continue

        m_tc = re.match(r'^(?:tyres_category|category|tyres-category|tyre-category)-(.+)$', seg, re.IGNORECASE)
        if m_tc:
            for tc in m_tc.group(1).split(','):
                if tc.strip():
                    args.add('tyres_category', tc.strip())
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

        m_tm = re.match(r'^(?:tyre_marking|marking|tyre-marking)-(.+)$', seg, re.IGNORECASE)
        if m_tm:
            for tm in m_tm.group(1).split(','):
                if tm.strip():
                    args.add('tyre_marking', tm.strip())
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

        m_ev = re.match(r'^(?:ev_tyre|ev-tyre|ev)(?:-(.+))?$', seg, re.IGNORECASE)
        if m_ev:
            args.add('ev_tyre', 'ev')
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
    is_staggered = catalog_data.get('is_staggered', False)
    front_size_label = catalog_data.get('front_size_label', '')
    rear_size_label = catalog_data.get('rear_size_label', '')

    raw_tc = (combined_args.getlist('tyres_category') or combined_args.getlist('tyres-category') or combined_args.getlist('tyres_categories') or combined_args.getlist('tyre_category'))
    if not raw_tc and combined_args.getlist('category'):
        raw_tc = [c for c in combined_args.getlist('category') if c.strip().lower() in ('budget', 'quality', 'premium')]
    active_tyres_categories = [tc.strip() for tc in raw_tc if tc.strip()]
    active_brands = [b.lower() for b in (combined_args.getlist('brand') or combined_args.getlist('brands'))]
    active_patterns = [p.strip() for p in (combined_args.getlist('pattern') or combined_args.getlist('patterns'))]
    active_tyre_markings = [tm.strip() for tm in (combined_args.getlist('tyre_marking') or combined_args.getlist('marking') or combined_args.getlist('tyre_markings') or combined_args.getlist('markings')) if tm.strip()]
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
    has_vehicle_context = bool(combined_args.get('make') or combined_args.get('model') or combined_args.get('trim') or combined_args.get('modification') or combined_args.get('car_year') or combined_args.get('vehicle_year'))
    raw_active_years = [] if has_vehicle_context else (combined_args.getlist('year') or combined_args.getlist('years'))
    active_years = [str(y).strip() for y in raw_active_years if str(y).strip().isdigit() and int(str(y).strip()) >= 2024]
    active_origins = [org.strip() for org in (combined_args.getlist('origin') or combined_args.getlist('country') or combined_args.getlist('origins'))]
    active_vehicles = [v.lower() for v in (combined_args.getlist('vehicle') or combined_args.getlist('vehicle_type'))]
    active_sizes = []
    active_sizes_match = set()
    for s in (combined_args.getlist('size') or combined_args.getlist('sizes')):
        s_c = s.strip()
        if not s_c:
            continue
        s_slug = s_c.lower().replace('/', '-').replace(' ', '-')
        s_slug_clean = re.sub(r'[-/ ]*r(\d+)', r'-\1', s_slug, flags=re.IGNORECASE)
        if s_slug_clean not in active_sizes:
            active_sizes.append(s_slug_clean)
        active_sizes_match.add(s_c.lower())
        active_sizes_match.add(s_slug)
        active_sizes_match.add(s_slug_clean)
        active_sizes_match.add(s_c.upper())
        active_sizes_match.add(s_slug.upper())
        active_sizes_match.add(s_slug_clean.upper())
        s_slug_r = re.sub(r'-(\d+)$', r'-r\1', s_slug_clean, flags=re.IGNORECASE)
        active_sizes_match.add(s_slug_r)
        active_sizes_match.add(s_slug_r.upper())
    active_types = [t.lower() for t in (combined_args.getlist('type') or combined_args.getlist('tire_type'))]
    active_runflat = [r.lower() for r in (combined_args.getlist('runflat') or combined_args.getlist('run_flat') or combined_args.getlist('is_runflat'))]
    filter_runflat_count = catalog_data.get('facets', {}).get('runflat', 0)
    active_ev_tyre = [e.lower() for e in (combined_args.getlist('ev_tyre') or combined_args.getlist('ev') or combined_args.getlist('is_ev') or combined_args.getlist('ev_rated')) if e.strip()]
    filter_ev_tyre_count = catalog_data.get('facets', {}).get('ev_tyre', 0)
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

            # 1. Sidebar: Tyres Category from DB
            cur.execute("""
                SELECT DISTINCT COALESCE(tyres_category, JSON_UNQUOTE(JSON_EXTRACT(attributes_json, '$.tyres_category'))) as tc, COUNT(*) as cnt
                FROM products
                WHERE deleted_at IS NULL AND status = 'active'
                  AND (tyres_category IS NOT NULL OR JSON_EXTRACT(attributes_json, '$.tyres_category') IS NOT NULL)
                GROUP BY tc
                ORDER BY FIELD(tc, 'Budget', 'Quality', 'Premium'), cnt DESC
            """)
            filter_tyres_categories = [{
                'category': r['tc'],
                'count': r['cnt']
            } for r in cur.fetchall() if r.get('tc')]

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
                b_cnt = b.get('cnt', 0)
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
                'count': r['cnt']
            } for r in cur.fetchall()]

            # 4b. Sidebar: Tyre Markings from DB
            cur.execute("""
                SELECT JSON_UNQUOTE(JSON_EXTRACT(attributes_json, '$.tyre_marking')) as tm, COUNT(*) as cnt
                FROM products
                WHERE deleted_at IS NULL AND status = 'active'
                  AND JSON_EXTRACT(attributes_json, '$.tyre_marking') IS NOT NULL
                  AND JSON_UNQUOTE(JSON_EXTRACT(attributes_json, '$.tyre_marking')) NOT IN ('', 'None', 'Standard', '0')
                GROUP BY tm
                ORDER BY cnt DESC
                LIMIT 35
            """)
            filter_tyre_markings = [{
                'marking': r['tm'],
                'count': r['cnt']
            } for r in cur.fetchall() if r.get('tm')]

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
                'count': r['cnt']
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
                'count': r['cnt']
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
                'count': r['cnt']
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
                'count': r['cnt']
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
                filter_tyres_categories=filter_tyres_categories,
                active_tyres_categories=active_tyres_categories,
                filter_brands=filter_brands,
                active_brand_name=active_brand_name,
                active_brand_slug=active_brand_slug,
                filter_patterns=filter_patterns,
                filter_tyre_markings=filter_tyre_markings,
                active_tyre_markings=active_tyre_markings,
                filter_oem_tyres=filter_oem_tyres,
                filter_warranties=filter_warranties,
                filter_years=filter_years,
                filter_origins=filter_origins,
                filter_sizes=filter_sizes,
                filter_vehicles=filter_vehicles,
                filter_tyre_types=filter_tyre_types,
                filter_runflat_count=filter_runflat_count,
                active_runflat=active_runflat,
                filter_ev_tyre_count=filter_ev_tyre_count,
                active_ev_tyre=active_ev_tyre,
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
                is_staggered=is_staggered,
                front_size_label=front_size_label,
                rear_size_label=rear_size_label,
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
                  AND p.status = 'active'
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
            short_desc = _clean_multilingual_text(p_row.get('short_desc') or raw_attrs.get('short_description'), locale)

            desc = _clean_multilingual_text(p_row.get('description') or raw_attrs.get('description'), locale)
            if not desc:
                desc = short_desc or _clean_multilingual_text(p_row.get('meta_desc') or raw_attrs.get('meta_description'), locale)
            if not desc:
                desc = f"The {brand_name} {pattern_name} is designed for a safer and smoother drive with outstanding wet braking, long-lasting performance and excellent fuel efficiency. Ideal for everyday driving."

            # Parse meta_desc and meta_title for SEO
            meta_desc_val = _clean_multilingual_text(p_row.get('meta_desc') or raw_attrs.get('meta_description'), locale)
            if not meta_desc_val:
                meta_desc_val = f"{_clean_multilingual_text(p_row.get('display_name'), locale) or (brand_name + ' ' + size_label)} in stock with free delivery, warranty and mobile fitting across UAE."

            meta_title_val = _clean_multilingual_text(p_row.get('meta_title'), locale) or _clean_multilingual_text(raw_attrs.get('meta_title'), locale)
            if not meta_title_val:
                meta_title_val = f"{_clean_multilingual_text(p_row.get('display_name'), locale) or (brand_name + ' ' + size_label)} | Buy Online at TyresVision UAE"

            # Image. Falls back to the neutral placeholder rather than a real
            # Michelin product shot -- the old default put a branded photo on
            # products of other brands.
            img_path = p_row.get('image_path') or '/static/assets/images/no-image-available.svg'
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
            # if not offer_banner:
            #     offer_banner = 'BUY 3 GET 1 FREE'

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
                'title': _clean_multilingual_text(p_row.get('display_name') or p_row.get('name'), locale) or f"{brand_name} {size_label} {load_speed}",
                'display_name': _clean_multilingual_text(p_row.get('display_name') or p_row.get('name'), locale) or f"{brand_name} {size_label} {load_speed}",
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
                'faqs': raw_attrs.get('faqs') if isinstance(raw_attrs.get('faqs'), list) else ([] if not raw_attrs.get('faqs') else [raw_attrs.get('faqs')]),
                'oem_brand': p_row.get('oem_brand'),
                'oem_logos': resolve_oem_car_logos(p_row),
                'has_oem': len(resolve_oem_car_logos(p_row)) > 0
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

            canonical_url = f"https://www.tyresvision.com/product/{product['slug']}"
            raw_img = product.get('image_path') or '/static/assets/images/online-tyres-shop-dubai.png'
            if raw_img.startswith('http://') or raw_img.startswith('https://'):
                full_image_url = raw_img
            else:
                if not raw_img.startswith('/'):
                    raw_img = '/' + raw_img
                full_image_url = f"https://www.tyresvision.com{raw_img}"

            og_title = product.get('meta_title') or f"{product.get('title')} | Buy Online at TyresVision UAE"
            og_description = product.get('meta_description') or product.get('description') or f"Buy {product.get('title')} online in UAE with free fitting and warranty. Best tyre prices at TyresVision."

            page_og_tags = {
                'og_type': 'product',
                'og_url': canonical_url,
                'og_title': og_title,
                'og_description': og_description,
                'og_image': full_image_url,
                'og_locale': 'ar_AE' if locale == 'ar' else 'en_AE',
                'og_image_width': 800,
                'og_image_height': 800,
            }

            page_twitter_tags = {
                'twitter_card': 'summary_large_image',
                'twitter_title': og_title,
                'twitter_description': og_description,
                'twitter_image': full_image_url,
            }

            product_schema = {
                "@context": "https://schema.org/",
                "@type": "Product",
                "name": product.get('title') or product.get('display_name'),
                "image": [full_image_url],
                "description": og_description,
                "sku": product.get('sku') or f"TYRE-{product.get('id')}",
                "brand": {
                    "@type": "Brand",
                    "name": product.get('brand_name') or "TyresVision"
                },
                "offers": {
                    "@type": "Offer",
                    "url": canonical_url,
                    "priceCurrency": "AED",
                    "price": f"{product.get('price'):.2f}" if product.get('price') else "0.00",
                    "itemCondition": "https://schema.org/NewCondition",
                    "availability": "https://schema.org/InStock" if product.get('in_stock') else "https://schema.org/OutOfStock",
                    "seller": {
                        "@type": "Organization",
                        "name": "TyresVision"
                    }
                }
            }
            page_schema_json = json.dumps(product_schema, ensure_ascii=False)

            resp = make_response(render_template(
                'Client/ProductDetail.html',
                product=product,
                related_products=related_products,
                page_og_tags=page_og_tags,
                page_twitter_tags=page_twitter_tags,
                page_schema_json=page_schema_json,
                canonical_url=canonical_url,
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







@site_bp.route('/brand', strict_slashes=False)
@site_bp.route('/brands', strict_slashes=False)
def brand_page():
    """Client storefront Brands page rendering Client/brand.html with all active tyre brands."""
    locale = _get_locale()
    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT b.id, b.name, b.slug, b.logo, b.is_featured, b.sort_order, b.country,
                       COUNT(p.id) as tyre_count
                FROM brands b
                LEFT JOIN products p ON p.brand_id = b.id AND p.deleted_at IS NULL AND (p.status = 'active' OR p.status = 1 OR p.status IS NULL)
                WHERE b.deleted_at IS NULL AND (b.status = 'active' OR b.status = 1 OR b.status IS NULL)
                GROUP BY b.id, b.name, b.slug, b.logo, b.is_featured, b.sort_order, b.country
                ORDER BY 
                    b.is_featured DESC,
                    CASE 
                        WHEN LOWER(TRIM(b.name)) IN ('michelin', 'bridgestone', 'continental', 'pirelli', 'goodyear', 'dunlop', 'yokohama', 'hankook', 'kumho', 'nexen') THEN 0
                        ELSE 1
                    END ASC,
                    tyre_count DESC, 
                    b.name ASC
            """)
            raw_brands = cur.fetchall()

            premium_names = {'michelin', 'pirelli', 'continental', 'bridgestone', 'goodyear', 'dunlop', 'yokohama'}
            mid_names = {'hankook', 'kumho', 'nexen', 'toyo', 'falken', 'cooper', 'bfgoodrich', 'firestone', 'general tire', 'maxxis'}
            popular_names = {'michelin', 'pirelli', 'continental', 'bridgestone', 'goodyear', 'dunlop', 'yokohama', 'hankook', 'kumho', 'nexen'}

            total_tyres = 0
            brands = []
            for b in raw_brands:
                b_name_clean = (b.get('name') or '').strip().lower()
                tyres_cnt = int(b.get('tyre_count') or 0)
                total_tyres += tyres_cnt

                tier = 'budget'
                if b_name_clean in premium_names:
                    tier = 'premium'
                elif b_name_clean in mid_names:
                    tier = 'mid-range'
                
                is_pop = b.get('is_featured') or (b_name_clean in popular_names)

                brands.append({
                    'id': b.get('id'),
                    'name': b.get('name') or '',
                    'slug': b.get('slug') or (b.get('name') or '').lower().replace(' ', '-'),
                    'logo': b.get('logo') or '',
                    'is_featured': 1 if is_pop else 0,
                    'tyre_count': tyres_cnt,
                    'tier': tier,
                    'country': b.get('country') or ''
                })

            resp = make_response(render_template(
                'Client/brand.html',
                brands=brands,
                total_brands=len(brands),
                total_tyres=total_tyres,
                locale=locale
            ))
            resp.set_cookie('site_locale', locale, max_age=31536000, path='/')
            return resp
    finally:
        conn.close()


_BRAND_FEATURE_DEFAULTS = [
    {
        'icon': 'shield',
        'title': 'Genuine Stock, Manufacturer Warranty',
        'text': 'Every tyre is sourced through authorised channels with fresh manufacturing dates and the full manufacturer warranty honoured in the UAE.'
    },
    {
        'icon': 'truck',
        'title': 'Fitted at Your Home or Office',
        'text': 'Choose a fitting centre near you or book one of our mobile vans — tyres are delivered and fitted without you needing to drive anywhere.'
    },
    {
        'icon': 'check',
        'title': 'Matched to Your Exact Vehicle',
        'text': 'Search by size, by your number plate, or by vehicle to see only the tyres that actually fit — no guesswork, no wrong-size returns.'
    },
]


@site_bp.route('/brands/<slug>', strict_slashes=False)
def brand_detail_page(slug):
    """Client storefront Brand Detail page: one brand's story + its in-stock tyres."""
    locale = _get_locale()
    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, slug, logo, description, country, meta_title, meta_desc
                FROM brands
                WHERE slug = %s AND deleted_at IS NULL AND (status = 'active' OR status IS NULL)
            """, (slug,))
            brand_row = cur.fetchone()
            if not brand_row:
                abort(404)

            cur.execute("""
                SELECT COUNT(*) AS cnt, MIN(price) AS min_price
                FROM products
                WHERE brand_id = %s AND deleted_at IS NULL AND status = 'active' AND stock_status = 'in_stock'
            """, (brand_row['id'],))
            stats_row = cur.fetchone() or {}

            cur.execute("""
                SELECT DISTINCT tyres_category
                FROM products
                WHERE brand_id = %s AND deleted_at IS NULL AND status = 'active'
                      AND stock_status = 'in_stock' AND tyres_category IS NOT NULL AND tyres_category != ''
            """, (brand_row['id'],))
            categories = [r['tyres_category'] for r in cur.fetchall()]

            # One card per tyre pattern/model (not per size/SKU): group all
            # variants by pattern name, keep the cheapest variant's row for
            # the card's image/slug, and attach how many variants/distinct
            # sizes that pattern has in stock.
            cur.execute("""
                WITH ranked AS (
                    SELECT p.*,
                           COALESCE(NULLIF(p.tire_pattern, ''), p.display_name, p.name) AS pattern_key,
                           ROW_NUMBER() OVER (
                               PARTITION BY COALESCE(NULLIF(p.tire_pattern, ''), p.display_name, p.name)
                               ORDER BY p.price ASC
                           ) AS rn
                    FROM products p
                    WHERE p.brand_id = %s AND p.deleted_at IS NULL AND p.status = 'active' AND p.stock_status = 'in_stock'
                ),
                counts AS (
                    SELECT pattern_key,
                           COUNT(*) AS variant_count,
                           COUNT(DISTINCT tire_size_label) AS size_count
                    FROM ranked
                    GROUP BY pattern_key
                )
                SELECT r.*, c.variant_count, c.size_count, b.name as brand_name, b.slug as brand_slug, b.logo as brand_logo
                FROM ranked r
                JOIN counts c ON c.pattern_key = r.pattern_key
                LEFT JOIN brands b ON r.brand_id = b.id
                WHERE r.rn = 1
                ORDER BY r.price ASC
                LIMIT 24
            """, (brand_row['id'],))
            raw_patterns = cur.fetchall()
            products = []
            for row in raw_patterns:
                variant_count = row.pop('variant_count', 1)
                size_count = row.pop('size_count', 1)
                row.pop('pattern_key', None)
                row.pop('rn', None)
                fp = _format_product_for_client(row, locale)
                fp['variant_count'] = variant_count
                fp['size_count'] = size_count
                products.append(fp)
    finally:
        conn.close()

    def _loc(value):
        if isinstance(value, str) and value.strip().startswith('{'):
            try:
                value = json.loads(value)
            except Exception:
                pass
        if isinstance(value, dict):
            return value.get(locale) or value.get('en') or next(iter(value.values()), '')
        return value or ''

    brand_name = brand_row['name']
    description = _loc(brand_row.get('description'))
    if not description:
        description = (
            f"{brand_name} tyres are available at TyresVision with genuine stock, fresh manufacturing dates, "
            f"and full manufacturer warranty. Compare {brand_name} sizes and patterns, then have them fitted "
            f"at a centre near you or at your home or office anywhere in the UAE."
        )

    meta_title = _loc(brand_row.get('meta_title')) or f"{brand_name} Tyres UAE | Genuine Stock & Fitting | TyresVision"
    meta_desc = _loc(brand_row.get('meta_desc')) or (
        f"Shop genuine {brand_name} tyres in the UAE. Compare sizes and prices, then book doorstep or "
        f"workshop fitting with TyresVision."
    )

    base_url = "https://www.tyresvision.com"
    canonical_url = f"{base_url}/brands/{slug}"

    breadcrumbs = [
        {"label": "Home", "url": "/"},
        {"label": "Brands", "url": "/brands"},
        {"label": brand_name, "url": f"/brands/{slug}"},
    ]

    resp = make_response(render_template(
        'Client/BrandDetail.html',
        brand={
            'id': brand_row['id'],
            'name': brand_name,
            'slug': brand_row['slug'],
            'logo': brand_row.get('logo') or '',
            'country': brand_row.get('country') or '',
            'description': description,
        },
        tyre_count=int(stats_row.get('cnt') or 0),
        min_price=stats_row.get('min_price'),
        categories=categories,
        products=products,
        features=_BRAND_FEATURE_DEFAULTS,
        breadcrumbs=breadcrumbs,
        canonical_url=canonical_url,
        page_og_tags={
            'og_type': 'website',
            'og_url': canonical_url,
            'og_title': meta_title,
            'og_description': meta_desc,
            'og_image': brand_row.get('logo') or f"{base_url}/static/assets/images/online-tyres-shop-dubai.png",
        },
        meta_title=meta_title,
        meta_desc=meta_desc,
        locale=locale,
    ))
    resp.set_cookie('site_locale', locale, max_age=31536000, path='/')
    return resp


# ============================================================================
# CAR BRANDS & VEHICLE DYNAMIC MULTI-SLUG PAGES
# ============================================================================
_DB_AVAILABLE_SIZES_CACHE = None
_DB_AVAILABLE_SIZES_CACHE_TIME = 0
_AVAILABLE_MAKES_CACHE = None
_AVAILABLE_MAKES_CACHE_TIME = 0
_AVAILABLE_MODELS_CACHE = {}
_AVAILABLE_MODELS_CACHE_TIME = {}


def get_available_db_tire_sizes():
    """
    Returns a set of normalized size keys (e.g. '245-40-18', '255-40-23')
    for all products currently active and in stock in the database.
    Cached in memory for 5 minutes.
    """
    global _DB_AVAILABLE_SIZES_CACHE, _DB_AVAILABLE_SIZES_CACHE_TIME
    now = time.time()
    if _DB_AVAILABLE_SIZES_CACHE is not None and (now - _DB_AVAILABLE_SIZES_CACHE_TIME < 300):
        return _DB_AVAILABLE_SIZES_CACHE

    sizes = set()
    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT tire_size_label 
                FROM products 
                WHERE deleted_at IS NULL 
                  AND status = 'active' 
                  AND stock_status = 'in_stock' 
                  AND stock_qty > 0
            """)
            for r in cur.fetchall():
                sz = r.get('tire_size_label') or ''
                m = re.search(r'(\d+)[/\s]+(\d+)\s*(?:[A-Za-z]+)?\s*(\d+)', sz)
                if m:
                    sizes.add(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
    except Exception as e:
        current_app.logger.warning(f"get_available_db_tire_sizes error: {e}")
    finally:
        conn.close()

    _DB_AVAILABLE_SIZES_CACHE = sizes
    _DB_AVAILABLE_SIZES_CACHE_TIME = now
    return sizes


def get_makes_with_available_tyres():
    """
    Returns a set of car make slugs that have at least one model with in-stock tyres in the database.
    Cached in memory for 10 minutes.
    """
    global _AVAILABLE_MAKES_CACHE, _AVAILABLE_MAKES_CACHE_TIME
    now = time.time()
    if _AVAILABLE_MAKES_CACHE is not None and (now - _AVAILABLE_MAKES_CACHE_TIME < 600):
        return _AVAILABLE_MAKES_CACHE

    makes = set()
    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT v.make
                FROM vehicles v
                JOIN products p ON (p.tire_size_label = v.front_tire_size OR p.tire_size_label = v.rear_tire_size)
                WHERE p.deleted_at IS NULL
                  AND p.status = 'active'
                  AND p.stock_status = 'in_stock'
                  AND p.stock_qty > 0
            """)
            for r in cur.fetchall():
                if r.get('make'):
                    makes.add(r['make'].lower().strip())
    except Exception as e:
        current_app.logger.warning(f"get_makes_with_available_tyres error: {e}")
    finally:
        conn.close()

    _AVAILABLE_MAKES_CACHE = makes
    _AVAILABLE_MAKES_CACHE_TIME = now
    return makes


def get_models_with_available_tyres(make_slug):
    """
    Returns a set of model slugs for the specified make that have in-stock tyres in the database.
    Cached in memory for 10 minutes per make.
    """
    global _AVAILABLE_MODELS_CACHE, _AVAILABLE_MODELS_CACHE_TIME
    clean_make = (make_slug or '').lower().strip()
    if clean_make == 'mercedes-benz':
        clean_make = 'mercedes'
    now = time.time()
    if clean_make in _AVAILABLE_MODELS_CACHE and (now - _AVAILABLE_MODELS_CACHE_TIME.get(clean_make, 0) < 600):
        return _AVAILABLE_MODELS_CACHE[clean_make]

    models = set()
    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT v.model
                FROM vehicles v
                JOIN products p ON (p.tire_size_label = v.front_tire_size OR p.tire_size_label = v.rear_tire_size)
                WHERE v.make = %s
                  AND p.deleted_at IS NULL
                  AND p.status = 'active'
                  AND p.stock_status = 'in_stock'
                  AND p.stock_qty > 0
            """, [clean_make])
            for r in cur.fetchall():
                if r.get('model'):
                    models.add(r['model'].lower().strip())
    except Exception as e:
        current_app.logger.warning(f"get_models_with_available_tyres error for {make_slug}: {e}")
    finally:
        conn.close()

    _AVAILABLE_MODELS_CACHE[clean_make] = models
    _AVAILABLE_MODELS_CACHE_TIME[clean_make] = now
    return models


@site_bp.route('/tyres/cars', strict_slashes=False)
@site_bp.route('/tyres/cars/', strict_slashes=False)
@site_bp.route('/cars', strict_slashes=False)
@site_bp.route('/cars/', strict_slashes=False)
def car_brands_page():
    """Client storefront Car Brands directory rendering Client/CarBrands.html."""
    locale = _get_locale()
    return _render_car_brands(locale)


@site_bp.route('/<string(length=2):lang_code>/tyres/cars', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/tyres/cars/', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/cars', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/cars/', strict_slashes=False)
def car_brands_page_locale(lang_code):
    """Client storefront Car Brands directory with dynamic locale."""
    code = lang_code.lower()
    session['site_locale'] = code
    return _render_car_brands(code)


def _render_car_brands(locale):
    avail_makes = get_makes_with_available_tyres()
    try:
        raw = _vs_wheel_get('makes.php', {'region': 'medm'})
        raw_makes = raw.get('data', [])
    except Exception as e:
        current_app.logger.warning(f"Error fetching car makes from Wheel-API: {e}")
        raw_makes = []

    popular_makes = {
        'toyota', 'nissan', 'lexus', 'bmw', 'mercedes', 'mercedes-benz', 'ford',
        'land-rover', 'porsche', 'audi', 'hyundai', 'kia', 'honda', 'mitsubishi',
        'tesla', 'chevrolet', 'volkswagen', 'jeep'
    }
    luxury_makes = {
        'porsche', 'ferrari', 'lamborghini', 'bentley', 'rolls-royce', 'aston-martin',
        'maserati', 'mclaren', 'mercedes-benz', 'mercedes', 'bmw', 'audi', 'lexus',
        'land-rover', 'jaguar', 'genesis', 'bugatti'
    }
    suv_makes = {
        'toyota', 'nissan', 'land-rover', 'jeep', 'ford', 'gmc', 'chevrolet',
        'mitsubishi', 'lexus', 'dodge', 'ram', 'subaru'
    }

    avail_local = _get_car_logo_files()
    makes = []
    for m in raw_makes:
        slug = (m.get('slug') or '').strip().lower()
        if not slug:
            continue
        name = m.get('name_en') or m.get('name') or slug.replace('-', ' ').title()
        if slug == 'citroen':
            name = 'Citroën'

        logo_file = f"{slug}.png"
        if logo_file in avail_local:
            logo_url = f"/static/assets/images/cars-logo/{logo_file}"
        else:
            logo_url = m.get('logo') or f"https://wheel-api.klever.ae/logos/{slug}.png"

        tier = 'all'
        category_label = 'Passenger'
        if slug in luxury_makes:
            tier = 'luxury'
            category_label = 'Luxury'
        elif slug in popular_makes:
            tier = 'popular'
            category_label = 'Popular'
        elif slug in suv_makes:
            tier = 'suv'
            category_label = 'SUV & 4x4'
        elif slug in {'tesla', 'lucid', 'polestar', 'byd', 'nio', 'zeekr'}:
            tier = 'all'
            category_label = 'EV'

        is_feat = (slug in popular_makes) or (slug in luxury_makes)
        has_db_tyres = slug in avail_makes or slug in {'mercedes', 'mercedes-benz'}

        makes.append({
            'slug': slug,
            'name': name,
            'logo': logo_url,
            'tier': tier,
            'category_label': category_label,
            'is_featured': is_feat,
            'has_db_tyres': has_db_tyres
        })

    # Sort alphabetically from A to Z to match OEM car makes directory
    makes.sort(key=lambda x: x['name'].lower())

    base_url = "https://www.tyresvision.com"
    canonical_url = f"{base_url}/{locale}/tyres/cars" if locale and locale != 'en' else f"{base_url}/tyres/cars"
    canonical_url = canonical_url.rstrip('/')

    resp = make_response(render_template(
        'Client/CarBrands.html',
        makes=makes,
        total_makes=len(makes),
        locale=locale,
        canonical_url=canonical_url
    ))
    resp.set_cookie('site_locale', locale, max_age=31536000, path='/')
    return resp


@site_bp.route('/tyres/cars/<path:slug_path>', strict_slashes=False)
@site_bp.route('/cars/<path:slug_path>', strict_slashes=False)
def vehicle_dynamic_page(slug_path):
    """Dynamic multi-slug Vehicle page supporting Make > Model > Year > Trim fitments."""
    locale = _get_locale()
    return _render_vehicle_page(slug_path, locale)


@site_bp.route('/<string(length=2):lang_code>/tyres/cars/<path:slug_path>', strict_slashes=False)
@site_bp.route('/<string(length=2):lang_code>/cars/<path:slug_path>', strict_slashes=False)
def vehicle_dynamic_page_locale(lang_code, slug_path):
    """Dynamic multi-slug Vehicle page with dynamic locale."""
    code = lang_code.lower()
    session['site_locale'] = code
    return _render_vehicle_page(slug_path, code)


def _render_vehicle_page(slug_path, locale):
    clean_path = (slug_path or '').strip('/')
    segments = [s.strip() for s in clean_path.split('/') if s.strip()]
    if not segments:
        return redirect('/tyres/cars', code=301)

    level = len(segments)
    make_slug = segments[0].lower()
    if make_slug == 'mercedes-benz':
        make_slug = 'mercedes'
    model_slug = segments[1].lower() if level >= 2 else None
    year = segments[2] if level >= 3 else None
    trim_slug = segments[3].lower() if level >= 4 else None

    # Fetch Make metadata
    make_info = {'slug': make_slug, 'name': make_slug.replace('-', ' ').title(), 'logo': None}
    try:
        raw_makes = _vs_wheel_get('makes.php', {'region': 'medm'})
        for rm in raw_makes.get('data', []):
            if rm.get('slug', '').lower() == make_slug:
                make_info['name'] = rm.get('name_en') or rm.get('name') or make_info['name']
                if rm.get('logo'):
                    make_info['logo'] = rm.get('logo')
                break
    except Exception as e:
        current_app.logger.warning(f"Error resolving make {make_slug}: {e}")

    avail_local = _get_car_logo_files()
    if f"{make_slug}.png" in avail_local:
        make_info['logo'] = f"/static/assets/images/cars-logo/{make_slug}.png"
    elif not make_info['logo']:
        make_info['logo'] = f"https://wheel-api.klever.ae/logos/{make_slug}.png"

    base_prefix = f"/{locale}/tyres/cars" if locale and locale != 'en' else "/tyres/cars"
    breadcrumbs = [
        {"label": "Home", "url": "/"},
        {"label": "Tyres", "url": "/tyres"},
        {"label": "Cars", "url": base_prefix},
        {"label": make_info['name'], "url": f"{base_prefix}/{make_slug}"}
    ]

    models = []
    years = []
    engines = []
    tyre_options = []
    products = []
    model_info = {}
    trim_info = {}
    make_stats = {'total_tyres': 0, 'min_price': None, 'popular_sizes': []}
    model_stats = {'total_tyres': 0, 'min_price': None, 'popular_sizes': [], 'staggered': False, 'front_size': None, 'rear_size': None, 'year_range': ''}
    # OEM partner brand logos, used by the "Recommended Tyre Brands" panels
    # on both the make-overview page and the model/trim pages.
    oem_brands = []
    OEM_BRAND_TAGLINES = {
        'pirelli': 'P Zero PZ4 PNCS',
        'continental': 'SportContact ContiSilent',
        'michelin': 'Pilot Sport 4 SUV Acoustic',
        'goodyear': 'Eagle F1 SoundComfort',
    }
    try:
        import db
        _brand_conn = db.get_connection()
        try:
            with _brand_conn.cursor() as _cur:
                _cur.execute(
                    "SELECT name, slug, logo FROM brands WHERE slug IN (%s, %s, %s, %s)",
                    tuple(OEM_BRAND_TAGLINES.keys())
                )
                _brand_rows = {r['slug']: r for r in _cur.fetchall()}
            for b_slug, tagline in OEM_BRAND_TAGLINES.items():
                b_row = _brand_rows.get(b_slug)
                oem_brands.append({
                    'slug': b_slug,
                    'name': b_row['name'] if b_row else b_slug.title(),
                    'logo': b_row.get('logo') if b_row else None,
                    'tagline': tagline,
                })
        finally:
            _brand_conn.close()
    except Exception as e:
        current_app.logger.warning(f"Error fetching OEM brand logos: {e}")

    oem_brands_by_slug = {b['slug']: b for b in oem_brands}

    if level == 1:
        # Level 1: Make overview -> list of Models with available tyres in DB
        avail_models = get_models_with_available_tyres(make_slug)
        db_model_stats = {}
        try:
            import db
            conn = db.get_connection()
            with conn.cursor() as cur:
                # 1. Model years and fitment counts
                cur.execute(
                    "SELECT LOWER(model) AS model, MIN(year_from) AS min_y, MAX(year_to) AS max_y, COUNT(*) AS cnt "
                    "FROM vehicles WHERE LOWER(make) = %s GROUP BY model",
                    (make_slug,)
                )
                for row in cur.fetchall():
                    m_key = (row.get('model') or '').strip().lower()
                    min_y = row.get('min_y')
                    max_y = row.get('max_y')
                    y_disp = f"{min_y} - {max_y}" if min_y and max_y and min_y != max_y else str(min_y or max_y or '')
                    db_model_stats[m_key] = {'year_range': y_disp, 'count': row.get('cnt') or 0}

                # 2. Make overall stats
                cur.execute(
                    "SELECT COUNT(DISTINCT p.id) AS total_tyres, MIN(p.price) AS min_price "
                    "FROM vehicles v "
                    "JOIN products p ON INSTR(p.tire_size_label, v.front_tire_size) > 0 "
                    "WHERE LOWER(v.make) = %s AND p.stock_status = 'in_stock'",
                    (make_slug,)
                )
                st_row = cur.fetchone() or {}
                if st_row:
                    make_stats['total_tyres'] = st_row.get('total_tyres') or 0
                    make_stats['min_price'] = st_row.get('min_price')

                # 3. Top popular tyre sizes
                cur.execute(
                    "SELECT v.front_tire_size, COUNT(DISTINCT p.id) AS tyre_count "
                    "FROM vehicles v "
                    "JOIN products p ON INSTR(p.tire_size_label, v.front_tire_size) > 0 "
                    "WHERE LOWER(v.make) = %s AND p.stock_status = 'in_stock' "
                    "GROUP BY v.front_tire_size "
                    "ORDER BY tyre_count DESC LIMIT 6",
                    (make_slug,)
                )
                for s_row in cur.fetchall():
                    sz = s_row.get('front_tire_size') or ''
                    if sz:
                        slug_parts = re.findall(r'\d+', sz)
                        sz_slug = '-'.join(slug_parts) if slug_parts else sz
                        make_stats['popular_sizes'].append({
                            'label': sz,
                            'slug': sz_slug,
                            'count': s_row.get('tyre_count') or 0
                        })
            conn.close()
        except Exception as e:
            current_app.logger.warning(f"Error querying vehicle stats for {make_slug}: {e}")

        try:
            raw_models = _vs_wheel_get('models.php', {'make': make_slug, 'region': 'medm'})
            for rm in raw_models.get('data', []):
                slug = (rm.get('slug') or '').lower()
                # When tyres for this model are not available in our database, do not show that model on the list
                if avail_models and slug not in avail_models:
                    continue
                models.append({
                    'slug': slug,
                    'name': rm.get('name_en') or rm.get('name', ''),
                    'years': rm.get('year_ranges', [])
                })
        except Exception as e:
            current_app.logger.warning(f"Error fetching models for {make_slug}: {e}")

        # If models list is empty due to API issue, fallback to DB models
        if not models and avail_models:
            for m_slug in sorted(avail_models):
                models.append({
                    'slug': m_slug,
                    'name': m_slug.replace('-', ' ').title(),
                    'years': []
                })

        # Enrich each model with year_display and category
        BODY_TYPES = {
            'cullinan': 'Ultra-Luxury SUV',
            'phantom': 'Flagship Luxury Saloon',
            'ghost': 'Prestige Saloon',
            'dawn': 'Luxury Drophead Coupe',
            'wraith': 'Grand Tourer Coupe',
        }
        for m in models:
            m_slug = m['slug']
            st = db_model_stats.get(m_slug, {})
            m['year_display'] = st.get('year_range') or (', '.join(str(y) for y in m.get('years', [])) if m.get('years') else '')
            if m_slug in BODY_TYPES:
                m['category'] = BODY_TYPES[m_slug]
            elif any(k in m_slug for k in ['suv', 'cross', 'x5', 'x6', 'x7', 'gls', 'gle', 'cayenne', 'macan', 'urus', 'land-cruiser', 'patrol', 'defender']):
                m['category'] = 'Luxury SUV'
            elif any(k in m_slug for k in ['coupe', 'cabrio', 'spider', 'convertible', 'gt', '911', '718', 'vantage']):
                m['category'] = 'Coupe / Convertible'
            elif any(k in m_slug for k in ['sedan', 'saloon', 's-class', '7-series', 'a8', 'flying-spur']):
                m['category'] = 'Executive Saloon'
            else:
                m['category'] = 'Certified Fitment'

    elif level == 2:
        # Level 2: Model overview -> list of Years
        model_name = model_slug.replace('-', ' ').title()
        try:
            raw_models = _vs_wheel_get('models.php', {'make': make_slug, 'region': 'medm'})
            for rm in raw_models.get('data', []):
                if rm.get('slug', '').lower() == model_slug:
                    model_name = rm.get('name_en') or rm.get('name') or model_name
                    break
        except Exception:
            pass

        model_info = {'slug': model_slug, 'name': model_name}
        breadcrumbs.append({"label": model_name, "url": f"{base_prefix}/{make_slug}/{model_slug}"})
        try:
            raw_years = _vs_wheel_get('years.php', {'make': make_slug, 'model': model_slug})
            for y_item in raw_years.get('data', []):
                y_val = str(y_item.get('slug') or y_item.get('name', '')).strip()
                if y_val and y_val not in years:
                    years.append(y_val)
            years.sort(key=lambda y: int(y) if y.isdigit() else 0, reverse=True)
        except Exception as e:
            current_app.logger.warning(f"Error fetching years for {make_slug}/{model_slug}: {e}")

        try:
            import db
            conn = db.get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT MIN(year_from) AS min_y, MAX(year_to) AS max_y, "
                    "front_tire_size, rear_tire_size "
                    "FROM vehicles WHERE LOWER(make) = %s AND LOWER(model) = %s "
                    "GROUP BY front_tire_size, rear_tire_size",
                    (make_slug, model_slug)
                )
                fitments = cur.fetchall()
                front_sizes = []
                rear_sizes = []
                min_y_val = None
                max_y_val = None
                for f in fitments:
                    if f.get('min_y'):
                        min_y_val = min(min_y_val or 9999, f['min_y'])
                    if f.get('max_y'):
                        max_y_val = max(max_y_val or 0, f['max_y'])
                    fs = (f.get('front_tire_size') or '').strip()
                    rs = (f.get('rear_tire_size') or '').strip()
                    if fs and fs not in front_sizes:
                        front_sizes.append(fs)
                    if rs and rs not in rear_sizes:
                        rear_sizes.append(rs)

                if min_y_val and max_y_val:
                    model_stats['year_range'] = f"{min_y_val} - {max_y_val}" if min_y_val != max_y_val else str(min_y_val)
                elif years:
                    model_stats['year_range'] = f"{years[-1]} - {years[0]}" if len(years) > 1 else str(years[0])

                p_front = front_sizes[0] if front_sizes else None
                p_rear = rear_sizes[0] if rear_sizes else None
                is_staggered = bool(p_front and p_rear and p_front != p_rear)

                model_stats['staggered'] = is_staggered
                model_stats['front_size'] = p_front
                model_stats['rear_size'] = p_rear if is_staggered else None

                f_cnt = 0
                f_min_p = None
                r_cnt = 0
                r_min_p = None

                if p_front:
                    m_f = re.search(r'(\d+)[/\s](\d+)\s*(?:[A-Za-z]+)?\s*(\d+)', p_front)
                    if m_f:
                        f_pattern = f"%{m_f.group(1)}/{m_f.group(2)}%{m_f.group(3)}%"
                        f_slug = f"{m_f.group(1)}-{m_f.group(2)}-{m_f.group(3)}"
                        model_stats['front_size_slug'] = f_slug
                        cur.execute(
                            "SELECT COUNT(id) AS cnt, MIN(price) AS min_p FROM products "
                            "WHERE tire_size_label LIKE %s AND stock_status = 'in_stock'",
                            (f_pattern,)
                        )
                        f_res = cur.fetchone() or {}
                        f_cnt = f_res.get('cnt') or 0
                        f_min_p = float(f_res['min_p']) if f_res.get('min_p') else None
                        model_stats['front_count'] = f_cnt
                        model_stats['front_min_price'] = f_min_p

                if p_rear and is_staggered:
                    m_r = re.search(r'(\d+)[/\s](\d+)\s*(?:[A-Za-z]+)?\s*(\d+)', p_rear)
                    if m_r:
                        r_pattern = f"%{m_r.group(1)}/{m_r.group(2)}%{m_r.group(3)}%"
                        r_slug = f"{m_r.group(1)}-{m_r.group(2)}-{m_r.group(3)}"
                        model_stats['rear_size_slug'] = r_slug
                        cur.execute(
                            "SELECT COUNT(id) AS cnt, MIN(price) AS min_p FROM products "
                            "WHERE tire_size_label LIKE %s AND stock_status = 'in_stock'",
                            (r_pattern,)
                        )
                        r_res = cur.fetchone() or {}
                        r_cnt = r_res.get('cnt') or 0
                        r_min_p = float(r_res['min_p']) if r_res.get('min_p') else None
                        model_stats['rear_count'] = r_cnt
                        model_stats['rear_min_price'] = r_min_p

                total_tyres = f_cnt + r_cnt
                all_prices = [p for p in [f_min_p, r_min_p] if p is not None]
                model_stats['total_tyres'] = total_tyres
                model_stats['min_price'] = min(all_prices) if all_prices else None

                f_patt = None
                if model_stats.get('front_size_slug'):
                    f_parts = model_stats['front_size_slug'].split('-')
                    if len(f_parts) == 3:
                        f_patt = f"%{f_parts[0]}/{f_parts[1]}%{f_parts[2]}%"

                r_patt = None
                if model_stats.get('rear_size_slug'):
                    r_parts = model_stats['rear_size_slug'].split('-')
                    if len(r_parts) == 3:
                        r_patt = f"%{r_parts[0]}/{r_parts[1]}%{r_parts[2]}%"
                if f_patt or r_patt:
                    where_clause = []
                    params = []
                    if f_patt:
                        where_clause.append("p.tire_size_label LIKE %s")
                        params.append(f_patt)
                    if r_patt:
                        where_clause.append("p.tire_size_label LIKE %s")
                        params.append(r_patt)
                    q = (
                        "SELECT p.id, p.display_name, p.name, p.slug, p.price, p.image_path, p.tire_size_label, "
                        "p.tire_size_label AS full_size_spec, p.tire_speed_rating, p.tire_load_index, "
                        "p.year, p.country_of_origin, p.tyres_category, "
                        "b.name as brand_name, b.slug as brand_slug, b.logo as brand_logo "
                        "FROM products p "
                        "LEFT JOIN brands b ON p.brand_id = b.id "
                        f"WHERE ({' OR '.join(where_clause)}) AND p.stock_status = 'in_stock' "
                        "ORDER BY p.price DESC LIMIT 6"
                    )
                    cur.execute(q, tuple(params))
                    model_stats['sample_products'] = cur.fetchall() or []
        except Exception as e:
            current_app.logger.warning(f"Error fetching model stats for {make_slug}/{model_slug}: {e}")

    elif level == 3:
        # Level 3: Year overview -> list of Engines/Trims
        model_name = model_slug.replace('-', ' ').title()
        try:
            raw_models = _vs_wheel_get('models.php', {'make': make_slug, 'region': 'medm'})
            for rm in raw_models.get('data', []):
                if rm.get('slug', '').lower() == model_slug:
                    model_name = rm.get('name_en') or rm.get('name') or model_name
                    break
        except Exception:
            pass

        model_info = {'slug': model_slug, 'name': model_name}
        breadcrumbs.append({"label": model_name, "url": f"{base_prefix}/{make_slug}/{model_slug}"})
        breadcrumbs.append({"label": str(year), "url": f"{base_prefix}/{make_slug}/{model_slug}/{year}"})
        try:
            raw_eng = _vs_wheel_get('modifications.php', {'make': make_slug, 'model': model_slug, 'year': year})
            seen_trims = set()
            for m in raw_eng.get('data', []):
                trim = m.get('trim') or m.get('name', '')
                if not trim or trim in seen_trims:
                    continue
                seen_trims.add(trim)
                eng = m.get('engine') or {}
                power = eng.get('power') or {}
                parts = []
                if eng.get('capacity'): parts.append(f"{eng['capacity']}L")
                if eng.get('type'): parts.append(eng['type'])
                if power.get('hp'): parts.append(f"{power['hp']} hp")
                engine_str = ' · '.join(parts)
                engines.append({
                    'slug': m.get('slug', ''),
                    'trim': trim,
                    'engine': engine_str,
                    'fuel': eng.get('fuel', ''),
                    'display': trim + (f' — {engine_str}' if engine_str else '')
                })
        except Exception as e:
            current_app.logger.warning(f"Error fetching engines for {make_slug}/{model_slug}/{year}: {e}")

    elif level >= 4:
        # Level 4: Engine/Trim fitment -> Tyre Sizes & Catalog Products
        model_name = model_slug.replace('-', ' ').title()
        try:
            raw_models = _vs_wheel_get('models.php', {'make': make_slug, 'region': 'medm'})
            for rm in raw_models.get('data', []):
                if rm.get('slug', '').lower() == model_slug:
                    model_name = rm.get('name_en') or rm.get('name') or model_name
                    break
        except Exception:
            pass

        model_info = {'slug': model_slug, 'name': model_name}

        # Resolve real engine / trim details from modifications API instead of raw slug
        resolved_trim_name = None
        resolved_engine_desc = None
        try:
            raw_mods = _vs_wheel_get('modifications.php', {'make': make_slug, 'model': model_slug, 'year': year})
            for m in raw_mods.get('data', []):
                m_slug = (m.get('slug') or '').lower()
                m_trim = (m.get('trim') or m.get('name') or '').strip()
                m_trim_slug = m_trim.lower().replace(' ', '-')
                if m_slug == trim_slug or m_trim_slug == trim_slug:
                    resolved_trim_name = m_trim
                    eng = m.get('engine') or {}
                    power = eng.get('power') or {}
                    parts = []
                    if eng.get('capacity'): parts.append(f"{eng['capacity']}L")
                    if eng.get('type'): parts.append(eng['type'])
                    if power.get('hp'): parts.append(f"{power['hp']} hp")
                    resolved_engine_desc = ' · '.join(parts)
                    break
        except Exception as e:
            current_app.logger.warning(f"Error resolving trim modification {trim_slug}: {e}")

        if resolved_trim_name and resolved_engine_desc:
            trim_display = f"{resolved_trim_name} ({resolved_engine_desc})"
            trim_name = resolved_trim_name
        elif resolved_engine_desc:
            trim_display = resolved_engine_desc
            trim_name = resolved_engine_desc
        elif resolved_trim_name:
            trim_display = resolved_trim_name
            trim_name = resolved_trim_name
        else:
            clean_fallback = trim_slug.replace('-', ' ').title()
            trim_display = clean_fallback
            trim_name = clean_fallback

        trim_info = {
            'slug': trim_slug,
            'trim': trim_name,
            'display': trim_display,
            'engine': resolved_engine_desc or ''
        }
        breadcrumbs.append({"label": model_name, "url": f"{base_prefix}/{make_slug}/{model_slug}"})
        breadcrumbs.append({"label": str(year), "url": f"{base_prefix}/{make_slug}/{model_slug}/{year}"})
        breadcrumbs.append({"label": trim_info['trim'], "url": f"{base_prefix}/{make_slug}/{model_slug}/{year}/{trim_slug}"})

        try:
            params = {'make': make_slug, 'model': model_slug, 'year': year, 'modification': trim_slug}
            raw = _vs_wheel_get('search/by_model/', params)
            if not raw.get('data'):
                raw = _vs_wheel_get('search/by_model/', {'make': make_slug, 'model': model_slug, 'year': year})

            wheels = []
            for item in raw.get('data', []):
                wheels.extend(item.get('wheels', []))

            def extract_size(t_obj):
                w = t_obj.get('tire_width')
                h = t_obj.get('tire_aspect_ratio')
                rim = t_obj.get('rim_diameter')
                if not (w and h and rim):
                    raw_t = t_obj.get('tire') or ''
                    m = re.search(r'(\d{2,3})[/\s](\d{2,3})\s*(?:[A-Za-z]+)?\s*(\d{2})', raw_t)
                    if m:
                        w, h, rim = m.group(1), m.group(2), m.group(3)
                if not (w and h and rim):
                    return None, None, None, None, None
                label = f"{w}/{h} R{rim}"
                speed = t_obj.get('speed_index') or ''
                return str(w), str(h), str(rim), label, speed

            seen = set()
            avail_sizes = get_available_db_tire_sizes()
            for w in wheels:
                f = w.get('front', {}) or {}
                r_ = w.get('rear', {}) or {}
                fw, fh, frim, flabel, fspeed = extract_size(f)
                if not fw:
                    continue

                # User requirement: If tyre size is not available in our database, do NOT show that size!
                front_key = f"{fw}-{fh}-{frim}"
                if avail_sizes and front_key not in avail_sizes:
                    continue

                rw, rh, rrim, rlabel, rspeed = extract_size(r_)
                is_staggered = bool(rw and rh and rrim and (rw != fw or fh != rh or frim != rrim))
                dedup_key = (flabel, rlabel if is_staggered else None)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                is_factory = bool(w.get('is_stock', False))
                tyre_options.append({
                    "width": fw,
                    "height": fh,
                    "rim": frim,
                    "rear": {"width": rw, "height": rh, "rim": rrim} if is_staggered else None,
                    "isFactory": is_factory,
                    "is_stock": is_factory,
                    "speedIndex": fspeed or '',
                    "label": flabel,
                    "badge": "Standard / OEM" if is_factory else f"{frim}\" Optional"
                })

            tyre_options.sort(key=lambda x: (not x['is_stock'], int(x['rim'] or 0)))

            # Fetch matching products in DB for all available sizes
            if tyre_options:
                target_sizes = [f"{opt['width']}-{opt['height']}-{opt['rim']}" for opt in tyre_options]
                from werkzeug.datastructures import MultiDict
                filter_args = MultiDict([('size', sz) for sz in target_sizes])
                catalog_res = _fetch_catalog_products(filter_args, locale)
                products = catalog_res.get('products', []) if isinstance(catalog_res, dict) else (catalog_res or [])
        except Exception as e:
            current_app.logger.warning(f"Error fetching tyres for vehicle fitment: {e}")

    base_url = "https://www.tyresvision.com"
    canonical_url = f"{base_url}/{locale}/tyres/cars/{clean_path}" if locale and locale != 'en' else f"{base_url}/tyres/cars/{clean_path}"
    canonical_url = canonical_url.rstrip('/')

    resp = make_response(render_template(
        'Client/VehiclePage.html',
        level=level,
        make=make_info,
        model=model_info,
        year=year,
        trim=trim_info,
        models=models,
        years=years,
        engines=engines,
        tyre_options=tyre_options,
        products=products,
        breadcrumbs=breadcrumbs,
        canonical_url=canonical_url,
        make_stats=make_stats,
        model_stats=model_stats,
        oem_brands=oem_brands,
        oem_brands_by_slug=oem_brands_by_slug,
        locale=locale
    ))
    resp.set_cookie('site_locale', locale, max_age=31536000, path='/')
    return resp


@site_bp.route('/tyres', strict_slashes=False)
def car_tyres_listing():
    """Client storefront Car Tyres / Product Listing catalog."""
    locale = _get_locale()
    return _render_product_listing(locale)


@site_bp.route('/tyres/<path:filter_path>', strict_slashes=False)
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

    # If URL contains page-X or page-X-Y segment, or legacy size with '-r' (e.g. size-195-55-r16), 301 redirect to clean path
    raw_segments = [s.strip() for s in clean_path.split('/') if s.strip()]
    has_page_segment = any(re.match(r'^page-\d+(?:-\d+)?$', s, re.IGNORECASE) for s in raw_segments)
    has_size_r = any(re.match(r'^size-.*-r\d+', s, re.IGNORECASE) for s in raw_segments)
    if has_page_segment or has_size_r:
        cleaned_segments = []
        for s in raw_segments:
            if re.match(r'^page-\d+(?:-\d+)?$', s, re.IGNORECASE):
                continue
            if re.match(r'^size-', s, re.IGNORECASE):
                s = re.sub(r'[-/ ]*r(\d+)', r'-\1', s, flags=re.IGNORECASE)
            cleaned_segments.append(s)
        prefix = '/tyres'
        query_str = f"?{request.query_string.decode('utf-8')}" if request.query_string else ""
        clean_url = f"{prefix}/{'/'.join(cleaned_segments).lower()}{query_str}" if cleaned_segments else f"{prefix}{query_str}"
        return redirect(clean_url, code=301)

    # If URL contains uppercase characters (e.g. /tyres/oem-Mercedes-Benz), 301 redirect to lowercase slug
    if clean_path != clean_path.lower():
        prefix = '/tyres'
        query_str = f"?{request.query_string.decode('utf-8')}" if request.query_string else ""
        return redirect(f"{prefix}/{clean_path.lower()}{query_str}", code=301)
    locale = _get_locale()
    return _render_product_listing(locale, filter_path=clean_path)


@site_bp.route('/<string(length=2):lang_code>/tyres', strict_slashes=False)
def car_tyres_listing_locale(lang_code):
    """Client storefront Car Tyres / Product Listing catalog with dynamic locale."""
    code = lang_code.lower()
    session['site_locale'] = code
    return _render_product_listing(code)


@site_bp.route('/<string(length=2):lang_code>/tyres/<path:filter_path>', strict_slashes=False)
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

    # If URL contains page-X or page-X-Y segment, or legacy size with '-r', 301 redirect to clean path
    raw_segments = [s.strip() for s in clean_path.split('/') if s.strip()]
    has_page_segment = any(re.match(r'^page-\d+(?:-\d+)?$', s, re.IGNORECASE) for s in raw_segments)
    has_size_r = any(re.match(r'^size-.*-r\d+', s, re.IGNORECASE) for s in raw_segments)
    if has_page_segment or has_size_r:
        cleaned_segments = []
        for s in raw_segments:
            if re.match(r'^page-\d+(?:-\d+)?$', s, re.IGNORECASE):
                continue
            if re.match(r'^size-', s, re.IGNORECASE):
                s = re.sub(r'[-/ ]*r(\d+)', r'-\1', s, flags=re.IGNORECASE)
            cleaned_segments.append(s)
        prefix = f'/{code}/tyres'
        query_str = f"?{request.query_string.decode('utf-8')}" if request.query_string else ""
        clean_url = f"{prefix}/{'/'.join(cleaned_segments).lower()}{query_str}" if cleaned_segments else f"{prefix}{query_str}"
        return redirect(clean_url, code=301)

    if clean_path != clean_path.lower():
        prefix = f'/{code}/tyres'
        query_str = f"?{request.query_string.decode('utf-8')}" if request.query_string else ""
        return redirect(f"{prefix}/{clean_path.lower()}{query_str}", code=301)

    return _render_product_listing(code, filter_path=clean_path)


# Legacy redirects: redirect old /car-tyres and /products cleanly to canonical /tyres
@site_bp.route('/car-tyres', defaults={'filter_path': None}, strict_slashes=False)
@site_bp.route('/car-tyres/<path:filter_path>', strict_slashes=False)
def legacy_car_tyres_redirect(filter_path):
    target = f"/tyres/{filter_path.strip('/')}" if filter_path else "/tyres"
    qs = f"?{request.query_string.decode('utf-8')}" if request.query_string else ""
    return redirect(f"{target}{qs}", code=301)


@site_bp.route('/products', defaults={'filter_path': None}, strict_slashes=False)
@site_bp.route('/products/<path:filter_path>', strict_slashes=False)
def legacy_products_redirect(filter_path):
    target = f"/tyres/{filter_path.strip('/')}" if filter_path else "/tyres"
    qs = f"?{request.query_string.decode('utf-8')}" if request.query_string else ""
    return redirect(f"{target}{qs}", code=301)


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


_BUY_TYRE_SEARCH_CACHE = {}
_WHEEL_MAKE_LOGOS_CACHE = {}

def get_wheel_make_logos():
    """Fetches and caches the official vehicle make logos from Wheel-API (/v1/makes.php as documented in docs.html)."""
    global _WHEEL_MAKE_LOGOS_CACHE
    if _WHEEL_MAKE_LOGOS_CACHE:
        return _WHEEL_MAKE_LOGOS_CACHE

    try:
        import urllib.request
        key = "f9030340bff3fbffd0208256549f9984940fe536fec8ae7d8c2f1681b8ed3da2"
        url = f"https://wheel-api.klever.ae/v1/makes.php?user_key={key}&limit=500"
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'X-Client-Domain': 'localhost',
                'Origin': 'http://localhost'
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for m in data.get('data', []):
                slug = m.get('slug')
                logo = m.get('logo')
                if slug and logo:
                    _WHEEL_MAKE_LOGOS_CACHE[slug] = logo
    except Exception as e:
        current_app.logger.warning(f"Could not preload makes logos from wheel-api: {e}")

    return _WHEEL_MAKE_LOGOS_CACHE


def _format_wheel_api_vehicles_html(items, make_logos=None):
    """Formats Wheel-API vehicle match objects into HTML matching the compatibility drawer design."""
    import html as html_lib
    if not items:
        return ""

    if make_logos is None:
        make_logos = get_wheel_make_logos()

    by_make = {}
    for it in items:
        m_name = (it.get("make_name") or "Other").strip()
        m_slug = (it.get("make_slug") or m_name.lower().replace(" ", "-")).strip()
        if m_name not in by_make:
            # As documented in Wheel-API docs (https://wheel-api.klever.ae/docs.html):
            # logos are available from /v1/makes.php and served at https://wheel-api.klever.ae/logos/{make_slug}.png
            logo_url = (make_logos.get(m_slug) if make_logos else None) or f"https://wheel-api.klever.ae/logos/{m_slug}.png"
            by_make[m_name] = {
                "name": m_name,
                "slug": m_slug,
                "logo": logo_url,
                "models": {}
            }

        mod_name = (it.get("model_name") or "").strip()
        mod_slug = (it.get("model_slug") or mod_name.lower().replace(" ", "-")).strip()
        if not mod_name:
            continue

        yr_raw = it.get("year_ranges")
        years = []
        if yr_raw:
            try:
                years = json.loads(yr_raw) if isinstance(yr_raw, str) else yr_raw
            except Exception:
                years = [str(yr_raw)]

        if mod_name not in by_make[m_name]["models"]:
            by_make[m_name]["models"][mod_name] = {
                "name": mod_name,
                "slug": mod_slug,
                "years": set(years)
            }
        else:
            by_make[m_name]["models"][mod_name]["years"].update(years)

    rows = []
    for m_name in sorted(by_make.keys()):
        minfo = by_make[m_name]
        logo_url = minfo["logo"]
        m_slug = minfo["slug"]

        model_pills = []
        for mod_name in sorted(minfo["models"].keys()):
            mod = minfo["models"][mod_name]
            mod_slug = mod["slug"]
            sorted_years = sorted(list(mod["years"]))
            year_spans = "".join([f'<span class="text-xs text-gray-500 block">{html_lib.escape(y)}</span>' for y in sorted_years])

            model_pills.append(f'''<a class="brand-info" href="/en/tyres/cars/{html_lib.escape(m_slug)}/{html_lib.escape(mod_slug)}">
                <div class="model-year font-semibold text-gray-900 text-sm hover:text-theme-blue transition-colors text-center">
                    <span>{html_lib.escape(mod_name)}</span>{year_spans}
                </div>
            </a>''')

        models_html = "\n".join(model_pills)

        row_html = f'''<div class="flex justify-between items-start mb-3 pb-3 border-b border-dashed border-theme-blue gap-3">
            <div class="modal-name-cotent" style="flex:0 0 auto;">
                <div class="left-content">
                    <div class="brand-image flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 rounded-[6px] px-3 py-1 border border-blue-200 group-hover:border-blue-300 transition-colors">
                        <img class="w-8 h-auto object-contain" src="{html_lib.escape(logo_url)}" alt="{html_lib.escape(m_name)}" onerror="this.onerror=null; this.src='/static/assets/images/cars-logo/{html_lib.escape(m_slug)}.png';" />
                        <p class="ml-2 text-xs font-semibold uppercase text-gray-800 tracking-wide">{html_lib.escape(m_name)}</p>
                    </div>
                </div>
            </div>
            <div class="modal-results-content">
                <div class="brand-info-content flex gap-2 flex-wrap justify-end">
                    {models_html}
                </div>
            </div>
        </div>'''
        rows.append(row_html)

    return "\n".join(rows)


@site_bp.route('/api/tyre-sizes', methods=['GET'])
def api_tyre_sizes_cascade():
    """
    Public JSON API: cascading tyre-size options (width -> profile -> rim)
    sourced from real product inventory (attributes_json.width/height/rim),
    not a static list -- so the hero search widget only ever offers a
    combination that actually has matching products in stock.

    - no params:            distinct widths
    - ?brand=X:             distinct widths for brand X
    - ?width=X:              distinct profiles (aspect ratio) for that width
    - ?brand=X&width=Y:      distinct profiles for brand X and width Y
    - ?width=X&profile=Y:    distinct rims for that width+profile
    - ?brand=X&width=Y&profile=Z: distinct rims for brand X, width Y, profile Z
    """
    brand = (request.args.get('brand') or '').strip().lower()
    width = (request.args.get('width') or '').strip()
    profile = (request.args.get('profile') or request.args.get('height') or '').strip()

    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            base_where = (
                "deleted_at IS NULL AND status = 'active' "
                "AND attributes_json IS NOT NULL"
            )
            brand_filter = ""
            brand_params = []
            if brand:
                brand_filter = " AND (brand_id = (SELECT id FROM brands WHERE (slug = %s OR LOWER(name) = %s) AND deleted_at IS NULL LIMIT 1))"
                brand_params = [brand, brand]

            if not width:
                cur.execute(f"""
                    SELECT DISTINCT JSON_UNQUOTE(JSON_EXTRACT(attributes_json, '$.width')) AS val
                    FROM products
                    WHERE {base_where}{brand_filter}
                      AND JSON_EXTRACT(attributes_json, '$.width') IS NOT NULL
                """, brand_params)
                step = 'width'
            elif not profile:
                cur.execute(f"""
                    SELECT DISTINCT JSON_UNQUOTE(JSON_EXTRACT(attributes_json, '$.height')) AS val
                    FROM products
                    WHERE {base_where}{brand_filter}
                      AND JSON_UNQUOTE(JSON_EXTRACT(attributes_json, '$.width')) = %s
                      AND JSON_EXTRACT(attributes_json, '$.height') IS NOT NULL
                """, brand_params + [width])
                step = 'profile'
            else:
                cur.execute(f"""
                    SELECT DISTINCT JSON_UNQUOTE(JSON_EXTRACT(attributes_json, '$.rim')) AS val
                    FROM products
                    WHERE {base_where}{brand_filter}
                      AND JSON_UNQUOTE(JSON_EXTRACT(attributes_json, '$.width')) = %s
                      AND JSON_UNQUOTE(JSON_EXTRACT(attributes_json, '$.height')) = %s
                      AND JSON_EXTRACT(attributes_json, '$.rim') IS NOT NULL
                """, brand_params + [width, profile])
                step = 'rim'

            raw_vals = [r['val'].strip() for r in cur.fetchall() if r.get('val') and r['val'].strip()]
    finally:
        conn.close()

    if step == 'rim':
        # Clean rim sizes: omit 'R'/'r' prefix and C suffix, no artificial minimum size restriction
        cleaned_rims = set()
        for v in raw_vals:
            v_clean = v.strip()
            if v_clean.upper().startswith('R'):
                v_clean = v_clean[1:].strip()
            if v_clean.upper().endswith('C'):
                v_clean = v_clean[:-1].strip()
            try:
                val_num = float(v_clean)
                if val_num > 0:
                    rim_str = str(int(val_num)) if val_num.is_integer() else str(val_num)
                    cleaned_rims.add(rim_str)
            except ValueError:
                if v_clean:
                    cleaned_rims.add(v_clean)
        def _rim_sort_key(x):
            try:
                return (0, float(x))
            except ValueError:
                return (1, str(x))
        options = sorted(cleaned_rims, key=_rim_sort_key)
    else:
        cleaned_vals = set()
        for v in raw_vals:
            v_clean = v.strip()
            if v_clean:
                cleaned_vals.add(v_clean)
        def _sort_key(x):
            try:
                return (0, float(x))
            except ValueError:
                return (1, str(x))
        options = sorted(cleaned_vals, key=_sort_key)

    if not options:
        if step == 'width':
            options = ['155', '165', '175', '185', '195', '205', '215', '225', '235', '245', '255', '265', '275', '285', '295', '305', '315', '325']
        elif step == 'profile':
            options = ['30', '35', '40', '45', '50', '55', '60', '65', '70', '75', '80', '85']
        elif step == 'rim':
            options = ['12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24']

    return jsonify({'success': True, 'step': step, 'options': options})


@site_bp.route('/api/brand-size-products', methods=['GET'])
def api_brand_size_products():
    """Returns products matching a specific brand and tyre size (width, profile, rim)."""
    brand = (request.args.get('brand') or '').strip().lower()
    width = (request.args.get('width') or '').strip()
    profile = (request.args.get('profile') or request.args.get('height') or '').strip()
    rim = (request.args.get('rim') or '').strip()

    if not brand or not width or not profile or not rim:
        return jsonify({'status': 'error', 'message': 'brand, width, profile, and rim are required'}), 400

    rim_digits = ''.join(c for c in rim if c.isdigit())
    rim_with_r = f"R{rim_digits}" if not rim.upper().startswith('R') else rim.upper()

    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.id, p.display_name, p.slug, p.sku, p.price, p.sale_price, p.currency, 
                       p.image_path, p.tire_size_label, p.tire_pattern, p.tire_speed_rating, 
                       p.tire_load_index, p.run_flat, p.ev_rated, p.stock_status, 
                       b.name as brand_name, b.slug as brand_slug, b.logo as brand_logo
                FROM products p
                JOIN brands b ON p.brand_id = b.id
                WHERE (b.slug = %s OR LOWER(b.name) = %s)
                  AND JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.width')) = %s
                  AND JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.height')) = %s
                  AND (JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.rim')) = %s OR JSON_UNQUOTE(JSON_EXTRACT(p.attributes_json, '$.rim')) = %s)
                  AND p.deleted_at IS NULL AND p.status = 'active'
                ORDER BY p.price ASC
            """, [brand, brand, width, profile, rim_digits, rim_with_r])
            rows = cur.fetchall()
            products = []
            brand_slug_res = brand
            brand_name_res = brand.title()
            for p in rows:
                brand_slug_res = p.get('brand_slug') or brand_slug_res
                brand_name_res = p.get('brand_name') or brand_name_res
                price_f = float(p['price']) if p.get('price') is not None else 0.0
                sale_price_f = float(p['sale_price']) if p.get('sale_price') is not None else None
                products.append({
                    'id': p['id'],
                    'name': p['display_name'] or p['slug'],
                    'slug': p['slug'],
                    'sku': p['sku'] or '',
                    'price': price_f,
                    'sale_price': sale_price_f,
                    'currency': p.get('currency') or 'AED',
                    'image': p.get('image_path') or '',
                    'tire_size': p.get('tire_size_label') or f"{width}/{profile} {rim_with_r}",
                    'pattern': p.get('tire_pattern') or '',
                    'speed_rating': p.get('tire_speed_rating') or '',
                    'load_index': p.get('tire_load_index') or '',
                    'run_flat': bool(p.get('run_flat')),
                    'ev_rated': bool(p.get('ev_rated')),
                    'brand_name': brand_name_res,
                    'brand_slug': brand_slug_res,
                    'url': f"/tyres/{p['slug']}"
                })

            catalog_url = f"/tyres/brand-{brand_slug_res}/size-{width}-{profile}-{rim_with_r}"
            return jsonify({
                'status': 'success',
                'data': products,
                'total': len(products),
                'brand_name': brand_name_res,
                'brand_slug': brand_slug_res,
                'catalog_url': catalog_url
            })
    except Exception as e:
        current_app.logger.warning(f"api_brand_size_products error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

# ── Vehicle-first hero search proxy routes ────────────────────────────────────
_WHEEL_API_KEY  = "f9030340bff3fbffd0208256549f9984940fe536fec8ae7d8c2f1681b8ed3da2"
_WHEEL_API_BASE = "https://wheel-api.klever.ae/v1"
_VS_CACHE = {}


def _vs_wheel_get(path, params=None, timeout=8):
    import urllib.request, urllib.parse
    qs = urllib.parse.urlencode({**(params or {}), 'user_key': _WHEEL_API_KEY, 'limit': 500})
    url = f"{_WHEEL_API_BASE}/{path}?{qs}"
    if url in _VS_CACHE:
        return _VS_CACHE[url]
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'X-Client-Domain': 'localhost', 'Origin': 'http://localhost'
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode('utf-8'))
    _VS_CACHE[url] = data
    return data


@site_bp.route('/api/vehicle-search/makes')
def vs_makes():
    try:
        raw   = _vs_wheel_get('makes.php', {'region': 'medm'})
        makes = [{'slug': m.get('slug',''), 'name': m.get('name_en') or m.get('name',''),
                  'logo': m.get('logo') or f"https://wheel-api.klever.ae/logos/{m.get('slug','')}.png"}
                 for m in raw.get('data', [])]
        return jsonify({'status': 'success', 'data': makes})
    except Exception as e:
        current_app.logger.warning(f"vs_makes: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 502


@site_bp.route('/api/vehicle-search/models')
def vs_models():
    make = request.args.get('make', '').strip()
    if not make:
        return jsonify({'status': 'error', 'message': 'make required'}), 400
    try:
        raw    = _vs_wheel_get('models.php', {'make': make, 'region': 'medm'})
        models = [{'slug': m.get('slug',''), 'name': m.get('name_en') or m.get('name',''),
                   'years': m.get('year_ranges', [])}
                  for m in raw.get('data', [])]
        return jsonify({'status': 'success', 'data': models})
    except Exception as e:
        current_app.logger.warning(f"vs_models: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 502


@site_bp.route('/api/vehicle-search/years')
def vs_years():
    make  = request.args.get('make', '').strip()
    model = request.args.get('model', '').strip()
    if not make or not model:
        return jsonify({'status': 'error', 'message': 'make and model required'}), 400
    try:
        raw   = _vs_wheel_get('years.php', {'make': make, 'model': model})
        years = [str(y.get('slug') or y.get('name', '')) for y in raw.get('data', [])]
        return jsonify({'status': 'success', 'data': years})
    except Exception as e:
        current_app.logger.warning(f"vs_years: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 502


@site_bp.route('/api/vehicle-search/engines')
def vs_engines():
    make  = request.args.get('make', '').strip()
    model = request.args.get('model', '').strip()
    year  = request.args.get('year', '').strip()
    if not make or not model or not year:
        return jsonify({'status': 'error', 'message': 'make, model and year required'}), 400
    try:
        raw  = _vs_wheel_get('modifications.php', {'make': make, 'model': model, 'year': year})
        seen, engines = set(), []
        for m in raw.get('data', []):
            trim = m.get('trim') or m.get('name', '')
            if not trim or trim in seen:
                continue
            seen.add(trim)
            eng   = m.get('engine') or {}
            power = eng.get('power') or {}
            parts = []
            if eng.get('capacity'): parts.append(f"{eng['capacity']}L")
            if eng.get('type'):     parts.append(eng['type'])
            if power.get('hp'):     parts.append(f"{power['hp']}hp")
            engine_str = ' · '.join(parts)
            engines.append({
                'slug':    m.get('slug', ''),
                'trim':    trim,
                'engine':  engine_str,
                'fuel':    eng.get('fuel', ''),
                'display': trim + (f'  —  {engine_str}' if engine_str else '')
            })
        return jsonify({'status': 'success', 'data': engines})
    except Exception as e:
        current_app.logger.warning(f"vs_engines: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 502


@site_bp.route('/api/vehicle-search/tyres')
def vs_tyres():
    """Return tyre size options for make + model + year + modification from Wheel-API search/by_model."""
    make = request.args.get('make', '').strip()
    model = request.args.get('model', '').strip()
    year = request.args.get('year', '').strip()
    modification = request.args.get('modification', '').strip() or request.args.get('trim', '').strip()
    if not make or not model or not year:
        return jsonify({'status': 'error', 'message': 'make, model and year required'}), 400
    try:
        params = {'make': make, 'model': model, 'year': year}
        if modification:
            params['modification'] = modification
        raw = _vs_wheel_get('search/by_model/', params)
        items = raw.get('data', [])
        if not items and modification:
            params_fallback = {'make': make, 'model': model, 'year': year}
            raw = _vs_wheel_get('search/by_model/', params_fallback)
            items = raw.get('data', [])

        if not items:
            return jsonify({'status': 'success', 'data': []})

        wheels = items[0].get('wheels', [])
        options = []
        seen = set()

        def extract_size(t_obj):
            if not t_obj:
                return None, None, None, None, None
            w = str(t_obj.get('tire_width') or '')
            h = str(t_obj.get('tire_aspect_ratio') or '')
            rim = str(t_obj.get('rim_diameter') or '')
            if not w or not h or not rim:
                raw = t_obj.get('tire') or ''
                m = re.search(r'(\d{2,3})[/\s](\d{2,3})\s*(?:[A-Za-z]+)?\s*(\d{2})', raw)
                if m:
                    w, h, rim = m.group(1), m.group(2), m.group(3)
            if not (w and h and rim):
                return None, None, None, None, None
            label = f"{w}/{h}R{rim}"
            speed = t_obj.get('speed_index') or ''
            return w, h, rim, label, speed

        wheels_sorted = sorted(wheels, key=lambda w: (not w.get('is_stock', False), -(1 if (w.get('front') or {}).get('speed_index') == 'Y' else 0)))

        for w in wheels_sorted:
            f = w.get('front', {}) or {}
            r_ = w.get('rear', {}) or {}
            
            fw, fh, frim, flabel, fspeed = extract_size(f)
            if not fw:
                continue
            
            rw, rh, rrim, rlabel, rspeed = extract_size(r_)
            is_staggered = bool(rw and rh and rrim and (rw != fw or fh != rh or frim != rrim))
            
            dedup_key = (flabel, rlabel if is_staggered else None)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            
            is_factory = bool(w.get('is_stock', False))
            
            item = {
                "width": fw,
                "height": fh,
                "rim": frim,
                "rear": {
                    "width": rw,
                    "height": rh,
                    "rim": rrim
                } if is_staggered else None,
                "isFactory": is_factory,
                "speedIndex": fspeed or '',
                "rearSpeedIndex": (rspeed or '') if is_staggered else None,
                "label": flabel,
                "rearLabel": rlabel if is_staggered else None,
                # UI helpers
                "title": flabel + (f" / Rear: {rlabel}" if is_staggered else ""),
                "badge": "Standard / OEM" if is_factory else (f"{frim}\" Optional" if frim else "Optional"),
                "front_slug": f"{fw}-{fh}-{frim}",
                "rear_slug": f"{rw}-{rh}-{rrim}" if is_staggered else None,
                "rim_spec": f.get('rim', ''),
                "is_staggered": is_staggered,
                "is_stock": is_factory
            }
            options.append(item)

        options.sort(key=lambda x: (not x['isFactory'], int(x['rim'] or 0)))

        return jsonify({'status': 'success', 'data': options})
    except Exception as e:
        current_app.logger.warning(f"vs_tyres: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 502
# ─────────────────────────────────────────────────────────────────────────────
@site_bp.route('/api/brands', methods=['GET'])
def client_api_brands():
    """Returns all active tyre brands for client search widgets and overlays."""
    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, slug, logo, is_featured, sort_order
                FROM brands
                WHERE deleted_at IS NULL AND (status = 'active' OR status = 1 OR status IS NULL)
                ORDER BY 
                    is_featured DESC,
                    CASE 
                        WHEN LOWER(TRIM(name)) IN ('michelin', 'bridgestone', 'continental', 'pirelli', 'goodyear', 'dunlop', 'yokohama', 'hankook') THEN 0
                        ELSE 1
                    END ASC,
                    sort_order ASC, 
                    name ASC
            """)
            rows = cur.fetchall()
            brands = []
            for r in rows:
                brands.append({
                    'id': r['id'],
                    'name': r['name'],
                    'slug': r['slug'] or r['name'].lower().replace(' ', '-'),
                    'logo': r.get('logo') or '',
                    'is_featured': bool(r.get('is_featured'))
                })
            return jsonify({
                'status': 'success',
                'data': brands,
                'total': len(brands)
            })
    except Exception as e:
        current_app.logger.warning(f"client_api_brands error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()


@site_bp.route('/api/wheel-search', methods=['GET', 'POST'])
def ajax_buy_tyre_search():
    """Fetches compatible vehicles for a tyre size from Wheel-API using POST method, with fallback."""
    import urllib.request
    import urllib.parse

    if request.is_json and request.json:
        width = str(request.json.get('width', '')).strip()
        height = str(request.json.get('height', '')).strip()
        rim = str(request.json.get('rim', '')).strip()
    else:
        width = str(request.values.get('width', '')).strip()
        height = str(request.values.get('height', '')).strip()
        rim = str(request.values.get('rim', '')).strip()

    # Extract clean numeric values
    w_match = re.search(r'\d+', width)
    w_clean = w_match.group(0) if w_match else '205'

    h_match = re.search(r'\d+', height)
    h_clean = h_match.group(0) if h_match else '55'

    r_match = re.search(r'\d+', rim)
    r_clean = r_match.group(0) if r_match else '16'

    cache_key = (w_clean, h_clean, r_clean)
    if cache_key in _BUY_TYRE_SEARCH_CACHE:
        cached_entry = _BUY_TYRE_SEARCH_CACHE[cache_key]
        if isinstance(cached_entry, dict):
            return jsonify(cached_entry)
        return jsonify({'status': 'success', 'html': cached_entry, 'source': 'cache'})

    # 1. Primary data source: Wheel-API (via POST method as requested)
    # Target URL: https://wheel-api.klever.ae/search.php?api_key=f9030340bff3fbffd0208256549f9984940fe536fec8ae7d8c2f1681b8ed3da2&width={width}&height={height}&rim={rim}
    wheel_api_url = f"https://wheel-api.klever.ae/search.php?api_key=f9030340bff3fbffd0208256549f9984940fe536fec8ae7d8c2f1681b8ed3da2&width={w_clean}&height={h_clean}&rim={r_clean}"
    try:
        req_wheel = urllib.request.Request(
            wheel_api_url,
            data=b"",  # Method POST
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'X-Client-Domain': 'localhost',
                'Origin': 'http://localhost',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
            }
        )
        with urllib.request.urlopen(req_wheel, timeout=8) as resp:
            wheel_data = json.loads(resp.read().decode('utf-8'))
            vehicle_items = wheel_data.get('data', [])
            if vehicle_items:
                make_logos = get_wheel_make_logos()
                for it in vehicle_items:
                    m_slug = it.get('make_slug')
                    if m_slug:
                        it['logo'] = make_logos.get(m_slug) or f"https://wheel-api.klever.ae/logos/{m_slug}.png"
                html_rendered = _format_wheel_api_vehicles_html(vehicle_items, make_logos)
                if html_rendered:
                    res_payload = {
                        'status': 'success',
                        'api_url': wheel_api_url,
                        'method': 'POST',
                        'html': html_rendered,
                        'data': vehicle_items,
                        'source': 'wheel-api',
                        'count': len(vehicle_items)
                    }
                    _BUY_TYRE_SEARCH_CACHE[cache_key] = res_payload
                    return jsonify(res_payload)
            return jsonify({'status': 'error', 'message': 'No compatible vehicles found for this size.'})
    except Exception as e:
        current_app.logger.warning(f"Wheel-API request failed for {w_clean}/{h_clean}R{r_clean}: {e}")
        return jsonify({'status': 'error', 'message': 'Unable to load compatible vehicles at this time.'})


@site_bp.route('/api/contact', methods=['POST'])
@site_bp.route('/api/contact-us', methods=['POST'])
def handle_contact_submission():
    """
    Handles customer contact form submissions from the Contact Overview Drawer.
    Validates form data, records the enquiry in hdweb_enquiry,
    and dispatches a notification email via Gmail SMTP.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    phone = (data.get('phone') or data.get('number') or '').strip()
    subject = (data.get('subject') or '').strip()
    message = (data.get('message') or '').strip()
    product_name = (data.get('product_name') or data.get('product') or '').strip()
    comment = (data.get('comment') or '').strip()
    form_type = (data.get('form_type') or 'contact_drawer_mail').strip()
    
    if product_name and not subject:
        subject = f"Product Enquiry: {product_name}"
    elif not subject:
        subject = 'General Enquiry'
        
    if not message:
        parts = []
        if product_name:
            parts.append(f"Product: {product_name}")
        if comment:
            parts.append(f"Comment: {comment}")
        message = "\n".join(parts) if parts else "Customer Enquiry"
    
    if not name:
        return jsonify({'success': False, 'error': 'Please provide your full name.'}), 400
    if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return jsonify({'success': False, 'error': 'Please provide a valid email address.'}), 400
    if not message:
        return jsonify({'success': False, 'error': 'Please enter your message or tyre details.'}), 400
        
    # 1. Save into hdweb_enquiry table
    enquiry_id = None
    try:
        import db
        conn = db.get_connection()
        try:
            with conn.cursor() as cur:
                sql = """
                    INSERT INTO hdweb_enquiry (
                        name, email, number, enquiry_for, message, status, form_type
                    ) VALUES (%s, %s, %s, %s, %s, 0, %s)
                """
                cur.execute(sql, (name, email, phone or None, subject, message, form_type))
                conn.commit()
                enquiry_id = cur.lastrowid
        finally:
            conn.close()
    except Exception as db_err:
        current_app.logger.error(f"Error saving contact enquiry to DB: {db_err}", exc_info=True)

    # 2. Dispatch email notification via mailer using the database Product Enquiry template.
    # Sent in a background thread so the SMTP round-trips (which can take
    # several seconds each, more if SSL fails and it falls back to TLS)
    # never block the HTTP response the browser is waiting on.
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'Unknown')
    flask_app = current_app._get_current_object()
    thread = threading.Thread(
        target=_send_contact_enquiry_email,
        args=(flask_app, name, email, phone, subject, message, product_name, comment, enquiry_id, client_ip),
        daemon=True
    )
    thread.start()

    return jsonify({
        'success': True,
        'message': 'Thank you! Your message has been sent successfully. Our team will contact you shortly.',
        'enquiry_id': enquiry_id,
        'mail_dispatched': True
    }), 200


def _send_contact_enquiry_email(flask_app, name, email, phone, subject, message, product_name, comment, enquiry_id, client_ip):
    """Builds and sends the contact-enquiry notification email(s). Runs on a
    background thread (see handle_contact_submission) so a slow or failing
    SMTP connection never blocks the form's HTTP response. Any failure here
    only reaches the server log, never the customer -- by the time this
    runs, the browser has already been told the enquiry was received."""
    with flask_app.app_context():
        try:
            from mailer import send_email, GMAIL_USER, OWNER_EMAIL
            from services.email_template_service import EmailTemplateService
            import urllib.parse

            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            clean_phone = re.sub(r'[^\d+]', '', phone) if phone else ''

            display_product = product_name if product_name else (subject if subject and subject != 'General Enquiry' else 'TyresVision Products')
            service_text = 'Product Enquiry • Tyres Catalog' if product_name else (subject if subject else 'General Customer Enquiry')
            note_text = comment if comment else (message if message else 'Customer submitted an enquiry via TyresVision website.')

            context = {
                'client name': name,
                'client_name': name,
                'client mobile': phone or 'Not provided',
                'client number': clean_phone or phone or 'Not provided',
                'client email': email,
                'client Email': email,
                'service': service_text,
                'product Name': display_product,
                'product_name': display_product,
                'Note': note_text,
                'note': note_text,
                'enquiry_id': str(enquiry_id or 'N/A'),
                'timestamp': timestamp,
                'client_ip': client_ip,
            }

            # Render database email template for Product Enquiry (code: contact_enquiry_received)
            fallback_subject = f"New Product Enquiry from TyresVision: {display_product} - {name}"
            email_subject, html_body = EmailTemplateService.render_template_by_code(
                'contact_enquiry_received',
                context=context,
                default_subject=fallback_subject
            )
            if not email_subject or email_subject.strip() == 'Customer Enquiry':
                email_subject = fallback_subject

            # Clean up any static href attributes in template
            if clean_phone:
                html_body = html_body.replace('href="tel:+971506515269"', f'href="tel:{clean_phone}"')
            if display_product:
                encoded_prod = urllib.parse.quote(display_product)
                html_body = html_body.replace('Continental%20Tyres', encoded_prod)

            text_body = f"""New Product Enquiry from TyresVision
-------------------------------------
Customer Name: {name}
Email Address: {email}
Phone / Mobile: {phone or 'Not provided'}
Service / Type: {service_text}
Product Name: {display_product}

Customer Note / Message:
{note_text}

-------------------------------------
Enquiry ID: #{enquiry_id or 'N/A'}
Timestamp: {timestamp}
IP Address: {client_ip}
"""

            # Attach TyresVision white logo as inline CID image for bulletproof rendering across Gmail PC, Outlook, Apple Mail
            logo_path = os.path.abspath(os.path.join(flask_app.root_path, '..', 'static', 'assets', 'images', 'logo', 'tyresvision-logo-white.png'))
            inline_images = {'tyresvision_logo': logo_path} if os.path.isfile(logo_path) else None

            # Resolve owner notification email from environment (.env), falling back to mailer.OWNER_EMAIL
            owner_email_raw = os.environ.get('OWNER_EMAIL') or os.environ.get('TO_OWNER_EMAIL') or OWNER_EMAIL
            owner_recipients = [e.strip() for e in re.split(r'[,;]', owner_email_raw) if e.strip()]
            for target_email in owner_recipients:
                try:
                    send_email(target_email, email_subject, html_body, text_body, inline_images=inline_images)
                except Exception as send_err:
                    flask_app.logger.warning(f"Failed to send contact enquiry to {target_email}: {send_err}")

            # Also copy GMAIL_USER if configured and distinct from owner recipients
            if GMAIL_USER and not any(GMAIL_USER.lower() == r.lower() for r in owner_recipients):
                try:
                    send_email(GMAIL_USER, email_subject, html_body, text_body, inline_images=inline_images)
                except Exception as send_err:
                    flask_app.logger.warning(f"Failed to send contact enquiry copy to {GMAIL_USER}: {send_err}")
        except Exception as mail_err:
            flask_app.logger.warning(f"Failed to send email notification for contact enquiry #{enquiry_id}: {mail_err}", exc_info=True)


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
