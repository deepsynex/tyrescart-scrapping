"""app/services/seo_builder.py - Central SEO builder.

Single source of truth for every page's JSON-LD schema, Open Graph tags and
Twitter Card tags. Routes in siteapp/clientroute.py call one `build_*_seo()`
function per page type and pass the result straight into `render_template`;
templates never hand-write `<script type="application/ld+json">` or `og:*`
tags themselves -- `templates/Client/layout.html` is the only place those are
printed, driven entirely by the dict this module returns.

Each `build_*_seo()` function returns a dict shaped like:
    {
        'canonical_url': str,
        'page_og_tags': {...},
        'page_twitter_tags': {...},
        'page_schema_json': str,  # json.dumps() of {"@context":..., "@graph": [...]}
    }
which a route can pass directly via `**seo` into `render_template(...)`.
"""
import functools
import json
import os

# ----------------------------------------------------------------------------
# CONFIG (from the TyresVision SEO brief)
# ----------------------------------------------------------------------------
BRAND_NAME = "TyresVision"
LEGAL_NAME = "DSP Trade Hub FZ-LLC"
SITE_URL = "https://www.tyresvision.com"
PHONE = "+971505069575"
WHATSAPP_URL = "https://wa.me/971505069575"
EMAIL = ""  # not supplied
REGISTERED_ADDRESS = ""  # not supplied
LOGO_URL = f"{SITE_URL}/static/assets/images/logo/tyresvision-logo-clean.webp"
DEFAULT_OG_IMAGE = f"{SITE_URL}/static/assets/images/og-tyresvision-1200x630.jpg"
DEFAULT_OG_IMAGE_ALT = "TyresVision – buy tyres online with fitting in Dubai, Abu Dhabi and across the UAE"
DEFAULT_OG_IMAGE_WIDTH = 1200
DEFAULT_OG_IMAGE_HEIGHT = 630
DEFAULT_OG_IMAGE_TYPE = "image/jpeg"

ORG_ID = f"{SITE_URL}/#organization"
WEBSITE_ID = f"{SITE_URL}/#website"

EMIRATES = ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah", "Umm Al Quwain"]

_BRAND_NAMES = [
    "Michelin", "Bridgestone", "Goodyear", "Continental", "Pirelli", "Dunlop",
    "Hankook", "Yokohama", "Toyo", "Falken", "Nexen", "Kumho", "BFGoodrich",
    "Cooper", "Nitto", "Vredestein", "Giti", "Laufenn", "Sumitomo", "Zeetex",
]

_KNOWS_ABOUT = [
    "Car tyres", "Tyre fitting", "Mobile tyre fitting", "Wheel balancing",
    "Wheel alignment", "Puncture repair", "Tyre sizes", "Fleet tyre supply",
]

# Service pages that exist only as generic `pages` table rows (no dedicated
# Flask route) -- keyed by slug so the catch-all page_detail() route can
# still build a correct Service node for them. name/description must only
# state facts the page itself shows -- see `templates/Client/Page.html`.
SERVICE_PAGE_SLUGS = {
    "mobile-tyre-fitting": {
        "name": "Mobile Tyre Fitting in Dubai and Abu Dhabi",
        "service_type": "Mobile tyre fitting",
        "description": "Our mobile vans fit your tyres at your home, office or roadside across Dubai and Abu Dhabi. The call-out fee is quoted on WhatsApp before we dispatch a van.",
        "area_served": ["Dubai", "Abu Dhabi", "Sharjah", "Ajman"],
    },
    "wheel-alignment": {
        "name": "Wheel Alignment",
        "service_type": "Wheel alignment",
        "description": "Wheel alignment service for cars and SUVs across the UAE.",
        "area_served": EMIRATES,
    },
    "wheel-balancing": {
        "name": "Wheel Balancing",
        "service_type": "Wheel balancing",
        "description": "Wheel balancing service for cars and SUVs across the UAE.",
        "area_served": EMIRATES,
    },
    "car-battery-replacement": {
        "name": "Car Battery Replacement",
        "service_type": "Car battery replacement",
        "description": "Car battery replacement service across the UAE.",
        "area_served": EMIRATES,
    },
    "oil-change": {
        "name": "Oil Change",
        "service_type": "Oil change",
        "description": "Engine oil change service for cars and SUVs across the UAE.",
        "area_served": EMIRATES,
    },
    "fleet-tyre-services": {
        "name": "Fleet Tyre Services",
        "service_type": "Fleet tyre supply and fitting",
        "description": "Fleet tyre supply, fitting and scheduled on-site visits for company vehicles across the UAE.",
        "area_served": EMIRATES,
    },
}

# FAQ text below is copied verbatim from the Q&A already rendered in each
# page's own server HTML (templates/Client/MobileTyreFitting.html and
# templates/Client/AboutUs.html), so the FAQPage schema matches the visible
# page exactly per the brief's rule 6 -- including the pre-existing "is 100%
# ." / missing-word blemish in two MobileTyreFitting answers, which is a
# content issue in that template, not something this SEO pass changes.
MOBILE_TYRE_FITTING_FAQS = [
    {
        'question': 'How long does mobile tyre fitting take?',
        'answer_html': 'Most single-tyre jobs take 20–30 minutes once the van arrives. A full set of four tyres, including mounting, computerised dynamic balancing, and final torque checks, usually takes 45 to 60 minutes.',
    },
    {
        'question': 'Do I need to be there when the van arrives?',
        'answer_html': 'You do not need to stand by the car throughout the entire service. You only need to be reachable to unlock the vehicle, provide wheel lock keys if needed, and confirm the completed installation. Many customers leave the key with building security while working.',
    },
    {
        'question': "Can you fit tyres in my building's car park?",
        'answer_html': 'Yes, as long as building security grants commercial van access and the ceiling height clears our vehicle (minimum 2.2m). If your basement has low height clearance, check with us on WhatsApp first and we will confirm clearance immediately.',
    },
    {
        'question': 'Is wheel balancing included in mobile fitting?',
        'answer_html': 'Yes. Every TyresVision mobile van carries an on-site computerised wheel balancer. High-speed dynamic wheel balancing is completed at your location as a standard part of the fitting — it is never skipped.',
    },
    {
        'question': 'Do you take away my old tyres?',
        'answer_html': 'Yes. We remove your old tyres and take them away with us for environmentally compliant recycling at no extra charge, saving you storage and disposal hassle.',
    },
    {
        'question': 'How much does mobile tyre fitting cost in Dubai?',
        'answer_html': 'Tyre fitting at one of our partner centres is 100% . Mobile tyre fitting at your own location has a transparent call-out fee on top, which is always confirmed on WhatsApp before our van is dispatched.',
    },
    {
        'question': 'Can your van fit an EV or a 4x4 at my home?',
        'answer_html': 'Yes. Our technicians use EV-dedicated rubber jacking pucks to lift electric vehicles strictly by manufacturer points without touching battery casings. Our vans also carry heavy-duty bead breakers for run-flat and 4x4 tyres.',
    },
]

ABOUT_US_FAQS = [
    {
        'question': 'Who is TyresVision?',
        'answer_html': 'TyresVision is an online tyre shop serving drivers across the UAE. We supply genuine tyres from 60+ brands and arrange fitting at a partner centre near you or at your location with our mobile vans. TyresVision is operated by DSP Trade Hub FZ-LLC.',
    },
    {
        'question': 'Are all tyres supplied by TyresVision genuine and brand new?',
        'answer_html': 'Yes. All tyres are sourced through authorised UAE channels and come with manufacturer-backed warranty on eligible tyres. We supply fresh date codes, never old stock, and you can always verify the DOT date code before fitting.',
    },
    {
        'question': 'What is included in your tyre price?',
        'answer_html': 'Our fitted price at a partner centre includes delivery, mounting, computerised dynamic wheel balancing, new valves and environmentally responsible disposal of your old tyres. There are no hidden fees.',
    },
    {
        'question': 'Can you fit tyres at my home, office or building car park?',
        'answer_html': 'Yes. Our mobile vans fit tyres in villa driveways, office car parks, apartment basements (subject to height clearance) and mall parking across Dubai, Abu Dhabi, Sharjah and Ajman.',
    },
    {
        'question': 'Which areas across the UAE do you cover?',
        'answer_html': 'We deliver and fit tyres across all seven Emirates: Dubai, Abu Dhabi, Sharjah, Ajman, Ras Al Khaimah, Fujairah and Umm Al Quwain.',
    },
    {
        'question': 'Do you supply and fit tyres for electric vehicles (EVs) and luxury SUVs?',
        'answer_html': 'Yes. We offer specialized high-load, low-rolling-resistance EV tyres for Tesla, BYD, Porsche, and other electric vehicles. Our technicians carry EV jacking pucks to ensure safe battery protection.',
    },
    {
        'question': 'How do I get a tyre price or book a fitting?',
        'answer_html': 'Send your tyre size (for example 245/45 R19) or vehicle make and model on WhatsApp to +971 50 506 9575. Our tyre advisors reply with budget, mid-range and premium options within minutes.',
    },
]

# Location (city) pages -- same mechanism as SERVICE_PAGE_SLUGS above.
LOCATION_PAGE_SLUGS = {
    "tyre-shop-dubai": "Dubai",
    "tyre-shop-abu-dhabi": "Abu Dhabi",
    "tyre-shop-sharjah": "Sharjah",
    "tyre-shop-ajman": "Ajman",
    "tyre-shop-ras-al-khaimah": "Ras Al Khaimah",
    "tyre-shop-fujairah": "Fujairah",
    "tyre-shop-umm-al-quwain": "Umm Al Quwain",
}

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ----------------------------------------------------------------------------
# Low-level helpers
# ----------------------------------------------------------------------------
def _abs_url(path_or_url):
    """Turns a possibly-relative path into an absolute https://www.tyresvision.com/... URL."""
    if not path_or_url:
        return DEFAULT_OG_IMAGE
    if path_or_url.startswith('http://') or path_or_url.startswith('https://'):
        return path_or_url
    if not path_or_url.startswith('/'):
        path_or_url = '/' + path_or_url
    return f"{SITE_URL}{path_or_url}"


@functools.lru_cache(maxsize=512)
def get_image_dimensions(image_url_or_path):
    """Reads real (width, height) off disk for a /static/... image. Returns
    (None, None) if the file can't be found or Pillow isn't available --
    callers must omit width/height meta rather than invent a number."""
    try:
        from PIL import Image
    except ImportError:
        return (None, None)

    path = image_url_or_path or ''
    if path.startswith(SITE_URL):
        path = path[len(SITE_URL):]
    if path.startswith('http://') or path.startswith('https://'):
        return (None, None)
    if not path.startswith('/'):
        return (None, None)

    fp = os.path.join(_BASE_DIR, path.lstrip('/'))
    if not os.path.isfile(fp):
        return (None, None)
    try:
        with Image.open(fp) as img:
            return img.size
    except Exception:
        return (None, None)


def jsonld_dumps(graph):
    """Serializes a JSON-LD @graph dict, escaping '</' so embedded content
    (FAQ answers, descriptions, etc.) can never prematurely close the
    surrounding <script> tag."""
    raw = json.dumps(graph, ensure_ascii=False)
    return raw.replace('</', '<\\/')


def build_graph(nodes):
    """Wraps a list of schema nodes in the single @graph JSON-LD document a
    page should emit, and returns it pre-serialized for page_schema_json."""
    return jsonld_dumps({
        "@context": "https://schema.org",
        "@graph": [n for n in nodes if n],
    })


def build_breadcrumb_list(page_id_fragment, items):
    """items: list of {'label': str, 'url': str|None} in order, Home first.
    The last item may omit 'url' (current page)."""
    elements = []
    for i, item in enumerate(items, start=1):
        entry = {
            "@type": "ListItem",
            "position": i,
            "name": item.get('label') or item.get('name'),
        }
        url = item.get('url')
        if url and i != len(items):
            entry["item"] = _abs_url(url)
        elements.append(entry)
    return {
        "@type": "BreadcrumbList",
        "@id": f"{page_id_fragment}#breadcrumb",
        "itemListElement": elements,
    }


def get_image_mime_type(image_url_or_path):
    """Determines image MIME type (image/jpeg, image/png, image/webp) from path or URL."""
    path = (image_url_or_path or '').lower().split('?')[0]
    if path.endswith('.png'):
        return 'image/png'
    elif path.endswith('.webp'):
        return 'image/webp'
    elif path.endswith('.svg'):
        return 'image/svg+xml'
    return 'image/jpeg'


def build_og_twitter_tags(og_type, canonical_url, title, description, image=None,
                           image_alt=None, extra_og=None):
    """Builds page_og_tags/page_twitter_tags for layout.html's existing
    fallback chain. `image` may be relative; dimensions are read from disk."""
    image_url = _abs_url(image) if image else DEFAULT_OG_IMAGE
    width, height = get_image_dimensions(image_url)
    if not width and image_url == DEFAULT_OG_IMAGE:
        width, height = DEFAULT_OG_IMAGE_WIDTH, DEFAULT_OG_IMAGE_HEIGHT

    alt_text = image_alt or DEFAULT_OG_IMAGE_ALT
    mime_type = get_image_mime_type(image_url)

    og_tags = {
        'og_type': og_type,
        'og_url': canonical_url,
        'og_title': title,
        'og_description': description,
        'og_image': image_url,
        'og_image_secure_url': image_url,
        'og_image_type': mime_type,
        'og_image_alt': alt_text,
        'og_locale': 'en_AE',
    }
    if width and height:
        og_tags['og_image_width'] = width
        og_tags['og_image_height'] = height
    if extra_og:
        og_tags.update(extra_og)

    twitter_tags = {
        'twitter_card': 'summary_large_image',
        'twitter_title': title,
        'twitter_description': description,
        'twitter_image': image_url,
        'twitter_image_alt': alt_text,
    }
    return og_tags, twitter_tags, alt_text


# ----------------------------------------------------------------------------
# Global nodes (Organization + WebSite) -- included on every page's @graph
# ----------------------------------------------------------------------------
def build_organization_node():
    try:
        from models.setting import Setting
        _ci = Setting.get_company_info()
    except Exception:
        _ci = {}
    current_phone = _ci.get("phone_call_number") or _ci.get("phone_number") or PHONE

    node = {
        "@type": ["Organization", "OnlineStore"],
        "@id": ORG_ID,
        "name": _ci.get("company_name") or BRAND_NAME,
        "legalName": LEGAL_NAME,
        "alternateName": ["Tyres Vision", "TyresVision UAE"],
        "url": SITE_URL,
        "telephone": current_phone,
        "image": DEFAULT_OG_IMAGE,
        "description": (
            "TyresVision is an online tyre shop in the UAE, operated by DSP Trade Hub FZ-LLC, "
            "selling genuine car, SUV and 4x4 tyres from top global brands with free fitting at "
            "partner outlets and paid mobile van fitting."
        ),
        "contactPoint": [
            {
                "@type": "ContactPoint",
                "telephone": current_phone,
                "contactType": "sales",
                "availableLanguage": ["English", "Arabic"],
                "areaServed": "AE",
            },
            {
                "@type": "ContactPoint",
                "telephone": current_phone,
                "contactType": "customer support",
                "availableLanguage": ["English", "Arabic"],
                "areaServed": "AE",
            },
        ],
        "areaServed": [{"@type": "City", "name": n} for n in EMIRATES] + [
            {"@type": "Country", "name": "United Arab Emirates"}
        ],
        "knowsAbout": _KNOWS_ABOUT,
        "brand": [{"@type": "Brand", "name": n} for n in _BRAND_NAMES],
    }

    width, height = get_image_dimensions(LOGO_URL)
    logo = {"@type": "ImageObject", "@id": f"{SITE_URL}/#logo", "url": LOGO_URL}
    if width and height:
        logo["width"] = width
        logo["height"] = height
    node["logo"] = logo

    if EMAIL:
        node["email"] = EMAIL
    if REGISTERED_ADDRESS:
        node["address"] = {"@type": "PostalAddress", "streetAddress": REGISTERED_ADDRESS, "addressCountry": "AE"}

    return node


def build_website_node():
    return {
        "@type": "WebSite",
        "@id": WEBSITE_ID,
        "url": SITE_URL,
        "name": BRAND_NAME,
        "alternateName": ["Tyres Vision", "TyresVision UAE"],
        "publisher": {"@id": ORG_ID},
        "inLanguage": "en-AE",
    }


def _base_nodes():
    return [build_organization_node(), build_website_node()]


# ----------------------------------------------------------------------------
# Per page-type builders
# ----------------------------------------------------------------------------
def build_homepage_seo(title, description, faqs):
    """faqs: list of {'question': str, 'answer_html': str} already localized,
    identical to what Home.html renders server-side, so FAQPage matches the
    visible page per the brief's rule 6."""
    canonical_url = f"{SITE_URL}/"
    og_tags, twitter_tags, _alt = build_og_twitter_tags('website', canonical_url, title, description)

    webpage = {
        "@type": "WebPage",
        "@id": f"{canonical_url}#webpage",
        "url": canonical_url,
        "name": title,
        "description": description,
        "isPartOf": {"@id": WEBSITE_ID},
        "primaryImageOfPage": {"@type": "ImageObject", "url": DEFAULT_OG_IMAGE},
        "inLanguage": "en-AE",
    }

    service_centre = {
        "@type": "Service",
        "@id": f"{canonical_url}#service-centre-fitting",
        "serviceType": "Tyre delivery and fitting",
        "name": "Free tyre fitting at a partner outlet",
        "description": "We deliver your tyres to a partner fitting centre near you across the UAE, and arrange the fitting for you at no extra charge.",
        "provider": {"@id": ORG_ID},
        "areaServed": [{"@type": "City", "name": n} for n in EMIRATES],
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "AED"},
    }

    service_mobile = {
        "@type": "Service",
        "@id": f"{canonical_url}#service-mobile-fitting",
        "serviceType": "Mobile tyre fitting",
        "name": "Mobile tyre fitting at your location",
        "description": "Our mobile vans fit your tyres at your home, office or roadside across the UAE. The call-out fee is confirmed on WhatsApp before we dispatch a van.",
        "provider": {"@id": ORG_ID},
        "areaServed": [{"@type": "City", "name": n} for n in EMIRATES],
    }

    faq_node = None
    if faqs:
        faq_node = {
            "@type": "FAQPage",
            "@id": f"{canonical_url}#faq",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f['question'],
                    "acceptedAnswer": {"@type": "Answer", "text": f['answer_html']},
                } for f in faqs
            ],
        }

    graph = _base_nodes() + [webpage, service_centre, service_mobile, faq_node]
    return {
        'canonical_url': canonical_url,
        'page_og_tags': og_tags,
        'page_twitter_tags': twitter_tags,
        'page_schema_json': build_graph(graph),
    }


def build_collection_page_seo(canonical_url, title, description, breadcrumb_items,
                               list_items, og_type='website', image=None):
    """Generic CollectionPage + BreadcrumbList + ItemList builder, used for
    the tyre listing, brand directory, car directory and vehicle fitment
    pages. `list_items`: [{'name':..., 'url':...}, ...] for the items
    actually shown on this page (respects pagination -- caller passes only
    the current page's items)."""
    og_tags, twitter_tags, _alt = build_og_twitter_tags(og_type, canonical_url, title, description, image=image)

    page_id = canonical_url
    breadcrumb = build_breadcrumb_list(page_id, breadcrumb_items)
    item_list = {
        "@type": "ItemList",
        "@id": f"{page_id}#itemlist",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": it['name'], "url": _abs_url(it['url'])}
            for i, it in enumerate(list_items, start=1)
        ],
    }
    collection = {
        "@type": "CollectionPage",
        "@id": f"{page_id}#webpage",
        "url": canonical_url,
        "name": title,
        "description": description,
        "isPartOf": {"@id": WEBSITE_ID},
        "breadcrumb": {"@id": f"{page_id}#breadcrumb"},
        "mainEntity": {"@id": f"{page_id}#itemlist"},
        "inLanguage": "en-AE",
    }

    graph = _base_nodes() + [collection, breadcrumb, item_list]
    return {
        'canonical_url': canonical_url,
        'page_og_tags': og_tags,
        'page_twitter_tags': twitter_tags,
        'page_schema_json': build_graph(graph),
    }


def build_brand_detail_seo(canonical_url, title, description, brand_name, brand_logo,
                            breadcrumb_items, list_items):
    og_tags, twitter_tags, _alt = build_og_twitter_tags(
        'website', canonical_url, title, description,
        image=brand_logo or DEFAULT_OG_IMAGE,
    )
    page_id = canonical_url
    breadcrumb = build_breadcrumb_list(page_id, breadcrumb_items)
    item_list = {
        "@type": "ItemList",
        "@id": f"{page_id}#itemlist",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": it['name'], "url": _abs_url(it['url'])}
            for i, it in enumerate(list_items, start=1)
        ],
    }
    brand_node = {
        "@type": "Brand",
        "@id": f"{page_id}#brand",
        "name": brand_name,
    }
    if brand_logo:
        brand_node["logo"] = _abs_url(brand_logo)
    brand_node["url"] = canonical_url

    collection = {
        "@type": "CollectionPage",
        "@id": f"{page_id}#webpage",
        "url": canonical_url,
        "name": title,
        "description": description,
        "isPartOf": {"@id": WEBSITE_ID},
        "about": {"@id": f"{page_id}#brand"},
        "breadcrumb": {"@id": f"{page_id}#breadcrumb"},
        "mainEntity": {"@id": f"{page_id}#itemlist"},
        "inLanguage": "en-AE",
    }

    graph = _base_nodes() + [collection, brand_node, breadcrumb, item_list]
    return {
        'canonical_url': canonical_url,
        'page_og_tags': og_tags,
        'page_twitter_tags': twitter_tags,
        'page_schema_json': build_graph(graph),
    }


def build_vehicle_seo(canonical_url, title, description, breadcrumb_items,
                       list_items, car_about=None):
    """car_about: {'make':..., 'model':...} when this is a make+model page,
    used for the `about: Car` node -- omitted on make-only/directory pages."""
    og_tags, twitter_tags, _alt = build_og_twitter_tags('website', canonical_url, title, description)
    page_id = canonical_url
    breadcrumb = build_breadcrumb_list(page_id, breadcrumb_items)
    item_list = {
        "@type": "ItemList",
        "@id": f"{page_id}#itemlist",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": it['name'], "url": _abs_url(it['url'])}
            for i, it in enumerate(list_items, start=1)
        ],
    }

    collection = {
        "@type": "CollectionPage",
        "@id": f"{page_id}#webpage",
        "url": canonical_url,
        "name": title,
        "description": description,
        "isPartOf": {"@id": WEBSITE_ID},
        "breadcrumb": {"@id": f"{page_id}#breadcrumb"},
        "mainEntity": {"@id": f"{page_id}#itemlist"},
        "inLanguage": "en-AE",
    }

    car_node = None
    if car_about and car_about.get('make'):
        car_name = car_about['make']
        if car_about.get('model'):
            car_name = f"{car_about['make']} {car_about['model']}"
        car_node = {
            "@type": "Car",
            "@id": f"{page_id}#car",
            "name": car_name,
            "manufacturer": {"@type": "Organization", "name": car_about['make']},
        }
        collection["about"] = {"@id": f"{page_id}#car"}

    graph = _base_nodes() + [collection, car_node, breadcrumb, item_list]
    return {
        'canonical_url': canonical_url,
        'page_og_tags': og_tags,
        'page_twitter_tags': twitter_tags,
        'page_schema_json': build_graph(graph),
    }


def build_product_seo(canonical_url, title, description, image, brand_name,
                       sku, price, in_stock, additional_properties=None,
                       breadcrumb_items=None, gtin=None, mpn=None,
                       price_valid_until=None, image_alt=None):
    """additional_properties: [(name, value), ...] -- e.g. Tyre size, Load
    index, Speed rating, Manufacture year, Origin, Warranty -- only include
    pairs whose value is real product data."""
    image_url = _abs_url(image)
    if not image_alt:
        props = dict(additional_properties or [])
        size_str = props.get('Tyre size') or ''
        clean_title = (title or '').strip()
        if brand_name and clean_title.lower().startswith(brand_name.lower()):
            alt_base = f"{clean_title} {size_str}".strip()
        else:
            alt_base = f"{brand_name} {clean_title} {size_str}".strip()
        image_alt = f"{alt_base} tyre" if not alt_base.lower().endswith('tyre') else alt_base
        image_alt = ' '.join(image_alt.split())

    og_tags, twitter_tags, _alt = build_og_twitter_tags(
        'product', canonical_url, title, description, image=image_url,
        image_alt=image_alt,
        extra_og={
            'product_price_amount': f"{price:.2f}" if price is not None else None,
            'product_price_currency': 'AED',
            'product_availability': 'instock' if in_stock else 'oos',
            'product_brand': brand_name,
        },
    )
    og_tags = {k: v for k, v in og_tags.items() if v is not None}

    page_id = canonical_url
    offers = {
        "@type": "Offer",
        "url": canonical_url,
        "priceCurrency": "AED",
        "price": f"{price:.2f}" if price is not None else "0.00",
        "availability": "https://schema.org/InStock" if in_stock else "https://schema.org/OutOfStock",
        "itemCondition": "https://schema.org/NewCondition",
        "seller": {"@id": ORG_ID},
    }
    if price_valid_until:
        offers["priceValidUntil"] = price_valid_until

    product_node = {
        "@type": "Product",
        "@id": f"{page_id}#product",
        "name": title,
        "image": [image_url],
        "description": description,
        "sku": sku,
        "brand": {"@type": "Brand", "name": brand_name},
        "offers": offers,
    }
    if gtin:
        product_node["gtin13"] = gtin
    if mpn:
        product_node["mpn"] = mpn
    if additional_properties:
        product_node["additionalProperty"] = [
            {"@type": "PropertyValue", "name": name, "value": value}
            for name, value in additional_properties if value
        ]

    nodes = _base_nodes() + [product_node]
    if breadcrumb_items:
        nodes.append(build_breadcrumb_list(page_id, breadcrumb_items))

    return {
        'canonical_url': canonical_url,
        'page_og_tags': og_tags,
        'page_twitter_tags': twitter_tags,
        'page_schema_json': build_graph(nodes),
    }


def build_service_seo(canonical_url, title, description, service_name, service_type,
                       area_served, breadcrumb_items, faqs=None, price=None):
    """Used for both service pages and location pages -- a location page is
    just a Service whose areaServed is a single city."""
    og_tags, twitter_tags, _alt = build_og_twitter_tags('website', canonical_url, title, description)
    page_id = canonical_url

    webpage = {
        "@type": "WebPage",
        "@id": f"{page_id}#webpage",
        "url": canonical_url,
        "name": title,
        "description": description,
        "isPartOf": {"@id": WEBSITE_ID},
        "breadcrumb": {"@id": f"{page_id}#breadcrumb"},
        "inLanguage": "en-AE",
    }

    service = {
        "@type": "Service",
        "@id": f"{page_id}#service",
        "name": service_name,
        "serviceType": service_type,
        "description": description,
        "provider": {"@id": ORG_ID},
        "areaServed": [{"@type": "City", "name": n} for n in area_served] if isinstance(area_served, (list, tuple)) else {"@type": "City", "name": area_served},
        "url": canonical_url,
    }
    if price is not None:
        service["offers"] = {"@type": "Offer", "price": f"{price:.2f}", "priceCurrency": "AED"}

    breadcrumb = build_breadcrumb_list(page_id, breadcrumb_items)

    faq_node = None
    if faqs:
        faq_node = {
            "@type": "FAQPage",
            "@id": f"{page_id}#faq",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f['question'],
                    "acceptedAnswer": {"@type": "Answer", "text": f['answer_html']},
                } for f in faqs
            ],
        }

    graph = _base_nodes() + [webpage, service, breadcrumb, faq_node]
    return {
        'canonical_url': canonical_url,
        'page_og_tags': og_tags,
        'page_twitter_tags': twitter_tags,
        'page_schema_json': build_graph(graph),
    }


def build_blog_index_seo(canonical_url, title, description, posts, image=None):
    og_tags, twitter_tags, _alt = build_og_twitter_tags('website', canonical_url, title, description, image=image)
    page_id = canonical_url
    breadcrumb = build_breadcrumb_list(page_id, [
        {"label": "Home", "url": "/"},
        {"label": "Blog"},
    ])
    item_list = {
        "@type": "ItemList",
        "@id": f"{page_id}#itemlist",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": p['name'], "url": _abs_url(p['url'])}
            for i, p in enumerate(posts, start=1)
        ],
    }
    collection = {
        "@type": "CollectionPage",
        "@id": f"{page_id}#webpage",
        "url": canonical_url,
        "name": title,
        "description": description,
        "isPartOf": {"@id": WEBSITE_ID},
        "breadcrumb": {"@id": f"{page_id}#breadcrumb"},
        "mainEntity": {"@id": f"{page_id}#itemlist"},
        "inLanguage": "en-AE",
    }
    graph = _base_nodes() + [collection, breadcrumb, item_list]
    return {
        'canonical_url': canonical_url,
        'page_og_tags': og_tags,
        'page_twitter_tags': twitter_tags,
        'page_schema_json': build_graph(graph),
    }


def build_blog_post_seo(canonical_url, title, description, image, date_published,
                         date_modified, author_name, is_person_author, faqs=None):
    og_tags, twitter_tags, _alt = build_og_twitter_tags(
        'article', canonical_url, title, description, image=image,
        image_alt=title,
        extra_og={
            'article_published_time': date_published,
            'article_modified_time': date_modified,
            'article_section': 'Tyre Care & Buying Guides',
        },
    )
    og_tags = {k: v for k, v in og_tags.items() if v is not None}
    page_id = canonical_url

    author_node = (
        {"@type": "Person", "name": author_name} if (is_person_author and author_name)
        else {"@id": ORG_ID}
    )

    posting = {
        "@type": "BlogPosting",
        "@id": f"{page_id}#article",
        "headline": title,
        "description": description,
        "image": [_abs_url(image)],
        "mainEntityOfPage": {"@id": f"{page_id}#webpage"},
        "publisher": {"@id": ORG_ID},
        "author": author_node,
        "inLanguage": "en-AE",
    }
    if date_published:
        posting["datePublished"] = date_published
    if date_modified:
        posting["dateModified"] = date_modified

    webpage = {
        "@type": "WebPage",
        "@id": f"{page_id}#webpage",
        "url": canonical_url,
        "name": title,
        "isPartOf": {"@id": WEBSITE_ID},
        "breadcrumb": {"@id": f"{page_id}#breadcrumb"},
        "inLanguage": "en-AE",
    }
    breadcrumb = build_breadcrumb_list(page_id, [
        {"label": "Home", "url": "/"},
        {"label": "Blog", "url": "/blog"},
        {"label": title},
    ])

    faq_node = None
    if faqs:
        faq_node = {
            "@type": "FAQPage",
            "@id": f"{page_id}#faq",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f['question'],
                    "acceptedAnswer": {"@type": "Answer", "text": f['answer_html']},
                } for f in faqs
            ],
        }

    graph = _base_nodes() + [webpage, posting, breadcrumb, faq_node]
    return {
        'canonical_url': canonical_url,
        'page_og_tags': og_tags,
        'page_twitter_tags': twitter_tags,
        'page_schema_json': build_graph(graph),
    }


def build_about_seo(canonical_url, title, description, faqs=None):
    og_tags, twitter_tags, _alt = build_og_twitter_tags('website', canonical_url, title, description)
    page_id = canonical_url
    breadcrumb = build_breadcrumb_list(page_id, [
        {"label": "Home", "url": "/"},
        {"label": "About Us"},
    ])
    about_page = {
        "@type": "AboutPage",
        "@id": f"{page_id}#webpage",
        "url": canonical_url,
        "name": title,
        "about": {"@id": ORG_ID},
        "isPartOf": {"@id": WEBSITE_ID},
        "breadcrumb": {"@id": f"{page_id}#breadcrumb"},
        "inLanguage": "en-AE",
    }

    faq_node = None
    if faqs:
        faq_node = {
            "@type": "FAQPage",
            "@id": f"{page_id}#faq",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f['question'],
                    "acceptedAnswer": {"@type": "Answer", "text": f['answer_html']},
                } for f in faqs
            ],
        }

    graph = _base_nodes() + [about_page, breadcrumb, faq_node]
    return {
        'canonical_url': canonical_url,
        'page_og_tags': og_tags,
        'page_twitter_tags': twitter_tags,
        'page_schema_json': build_graph(graph),
    }


def build_generic_page_seo(canonical_url, title, description, breadcrumb_items):
    """Fallback for CMS pages that aren't a recognized service/location
    slug -- just a WebPage + BreadcrumbList, no invented Service/FAQ."""
    og_tags, twitter_tags, _alt = build_og_twitter_tags('website', canonical_url, title, description)
    page_id = canonical_url
    webpage = {
        "@type": "WebPage",
        "@id": f"{page_id}#webpage",
        "url": canonical_url,
        "name": title,
        "description": description,
        "isPartOf": {"@id": WEBSITE_ID},
        "breadcrumb": {"@id": f"{page_id}#breadcrumb"},
        "inLanguage": "en-AE",
    }
    breadcrumb = build_breadcrumb_list(page_id, breadcrumb_items)
    graph = _base_nodes() + [webpage, breadcrumb]
    return {
        'canonical_url': canonical_url,
        'page_og_tags': og_tags,
        'page_twitter_tags': twitter_tags,
        'page_schema_json': build_graph(graph),
    }


def page_has_manual_seo(slug):
    """True if a `pages` row for this slug already has a complete,
    admin-authored schema graph (set via VisionAdmin -> SEO Manager) worth
    keeping -- e.g. the tyre-shop-<city> pages and mobile-tyre-fitting
    already carry a proper multi-node @graph (WebPage + ImageObject +
    Service + FAQPage, correctly @id-linked to #organization/#website) with
    real, page-specific content this pass can't reconstruct from scratch.

    Deliberately narrower than "has any row": a handful of pages (e.g.
    wheel-alignment, wheel-balancing, oil-change, car-battery-replacement,
    fleet-tyre-services) only ever got a thin single-node Service placeholder
    with no @graph and an inline `provider` object instead of an
    `{"@id": ".../#organization"}` reference -- those still need the
    central-builder upgrade, so they return False here on purpose.
    """
    import db
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT schema_json FROM pages WHERE slug = %s AND deleted_at IS NULL AND is_active = 1",
                (slug,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return False
    schema = row.get('schema_json') if isinstance(row, dict) else row[0]
    return bool(schema) and '"@graph"' in schema


def noindex_seo(canonical_url):
    """Cart/checkout/internal-search style pages: no schema, robots noindex."""
    return {
        'canonical_url': canonical_url,
        'page_og_tags': {},
        'page_twitter_tags': {},
        'page_schema_json': '',
        'robots_noindex': True,
    }
