"""
app/i18n.py - Central Dynamic Multi-Language & Locale Architecture

Eliminates hardcoded 'ar' / 'en' static constraints. Supports adding any
arbitrary language (e.g. German 'de', French 'fr', Spanish 'es', Arabic 'ar', etc.)
dynamically at runtime with translatable data persisted in DB in JSON format.
"""

import json
import re
from flask import request, session, has_request_context

DEFAULT_LOCALE = 'en'
RTL_LOCALES = {'ar', 'fa', 'ur', 'he', 'ps', 'sd'}

# Regex matching valid 2-letter or BCP 47 locale codes (e.g. 'en', 'de', 'ar', 'zh-CN')
LOCALE_REGEX = re.compile(r'^[a-z]{2}(?:-[a-zA-Z]{2})?$')


def is_rtl(locale: str) -> bool:
    """Returns True if the given locale code uses a Right-to-Left script."""
    if not locale:
        return False
    code = str(locale).strip().lower().split('-')[0]
    return code in RTL_LOCALES


def get_supported_locales() -> list:
    """
    Returns list of active supported locales configured in the database,
    falling back to system defaults.
    """
    try:
        from models.setting import Setting
        custom_langs = Setting.get('supported_languages')
        if isinstance(custom_langs, list) and custom_langs:
            codes = []
            for item in custom_langs:
                if isinstance(item, dict) and item.get('code'):
                    codes.append(item['code'].lower())
                elif isinstance(item, str) and item:
                    codes.append(item.lower())
            if codes:
                return codes
    except Exception:
        pass

    try:
        from services.store_context import StoreContext
        views = StoreContext.get_all_store_views()
        if views:
            codes = [v['locale'].lower() for v in views if v.get('locale')]
            if codes:
                return list(dict.fromkeys(codes))
    except Exception:
        pass

    return ['en', 'ar', 'de']


def get_locale() -> str:
    """
    Determines the current request locale dynamically.
    Checks:
      1. Store Context active language (Store View / Scope)
      2. Query param: ?locale=... or ?lang=...
      3. Flask session: session['site_locale']
      4. Cookie: request.cookies.get('site_locale')
      5. Default fallback ('en')
    Accepts any valid language code matching LOCALE_REGEX.
    """
    if not has_request_context():
        return DEFAULT_LOCALE

    try:
        from services.store_context import StoreContext
        ctx_lang = StoreContext.get_current_language(fallback="")
        if ctx_lang and LOCALE_REGEX.match(ctx_lang):
            return ctx_lang
    except Exception:
        pass

    req_locale = (request.args.get('locale') or request.args.get('lang') or '').strip().lower()
    if req_locale and LOCALE_REGEX.match(req_locale):
        session['site_locale'] = req_locale
        return req_locale

    if 'site_locale' in session:
        sess_locale = str(session['site_locale']).strip().lower()
        if LOCALE_REGEX.match(sess_locale):
            return sess_locale

    cookie_locale = (request.cookies.get('site_locale') or '').strip().lower()
    if cookie_locale and LOCALE_REGEX.match(cookie_locale):
        session['site_locale'] = cookie_locale
        return cookie_locale

    return DEFAULT_LOCALE


def parse_json_dict(val):
    """Parses a database value into a Python dict/list safely."""
    if val is None:
        return {}
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        s = val.strip()
        if s.startswith('{') or s.startswith('['):
            try:
                parsed = json.loads(s)
                return parsed if isinstance(parsed, (dict, list)) else {DEFAULT_LOCALE: str(parsed)}
            except Exception:
                pass
        return {DEFAULT_LOCALE: val} if val else {}
    return {DEFAULT_LOCALE: str(val)}


def dump_json_dict(val):
    """Converts a string or dict into a valid JSON string for MySQL storage."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, str):
        s = val.strip()
        if s.startswith('{') or s.startswith('['):
            try:
                json.loads(s)
                return s
            except Exception:
                pass
        return json.dumps({DEFAULT_LOCALE: val}, ensure_ascii=False)
    return json.dumps(val, ensure_ascii=False)


_MOJIBAKE_MAP = {
    '\u00d4\u00c7\u00f4': '–',
    'ÔÇô': '–',
    '\u00d4\u00c7\u00f6': '—',
    'ÔÇö': '—',
    'ÔÇÿ': '‘',
    'ÔÇÖ': '’',
    'ÔÇ£': '“',
    'ÔÇØ': '”',
    'ÔÇª': '…',
}


def clean_mojibake(text: str) -> str:
    """Cleans common CP437/OEM mojibake artifacts from corruptly decoded UTF-8 strings."""
    if not text or not isinstance(text, str):
        return text
    for bad, good in _MOJIBAKE_MAP.items():
        if bad in text:
            text = text.replace(bad, good)
    return text


def get_translated_value(value, language_code: str = None, fallback: str = DEFAULT_LOCALE) -> str:
    """
    Central Translation Helper for VisionAdmin and storefront.
    Safely retrieves the translated string from a multilingual field (JSON dict, JSON string, or scalar).
    
    Fallback Order:
      1. Target language: language_code, or StoreContext.get_current_language(fallback).
      2. Fallback language (default 'en').
      3. First available non-empty translation in the dict.
      4. Empty string ("") if no translation exists.
    """
    if value is None:
        return ""

    fb_lang = (fallback or DEFAULT_LOCALE).strip().lower()

    # Determine target language code
    if not language_code:
        try:
            from services.store_context import StoreContext
            target_lang = StoreContext.get_current_language(fallback=fb_lang)
        except Exception:
            target_lang = get_locale()
    else:
        target_lang = str(language_code).strip().lower()

    # If it's a dict (e.g. {"en": "Tire", "ar": "إطار"})
    if isinstance(value, dict):
        if target_lang in value and value[target_lang] is not None and str(value[target_lang]).strip() != "":
            return clean_mojibake(str(value[target_lang]))
        if fb_lang in value and value[fb_lang] is not None and str(value[fb_lang]).strip() != "":
            return clean_mojibake(str(value[fb_lang]))
        # First non-empty value
        for v in value.values():
            if v is not None and str(v).strip() != "":
                return clean_mojibake(str(v))
        return ""

    # If it's a string, attempt JSON parse if it looks like JSON
    if isinstance(value, str):
        s = value.strip()
        if (s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']')):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, dict):
                    return clean_mojibake(get_translated_value(parsed, language_code=target_lang, fallback=fb_lang))
            except Exception:
                pass
        return clean_mojibake(value)

    # Scalars (int, float, bool)
    return clean_mojibake(str(value))


def localize_value(val, locale: str = None, default_locale: str = DEFAULT_LOCALE) -> str:
    """
    Wrapper for get_translated_value to maintain full backward compatibility across all modules.
    """
    return get_translated_value(val, language_code=locale, fallback=default_locale)


def translate(text: str, locale: str = None) -> str:
    """
    Translates UI strings dynamically from DB setting 'i18n_translations'.
    Stores translations as:
      {
        "ar": { "Home": "الرئيسية", "Blog": "المدونة", ... },
        "de": { "Home": "Startseite", "Blog": "Blog", ... },
        ...
      }
    If no translation is found in DB for the target locale, returns original text.
    """
    if not text:
        return ""
    target_locale = (locale or get_locale()).strip().lower()
    if target_locale == DEFAULT_LOCALE:
        return text

    try:
        from models.setting import Setting
        all_trans = Setting.get('i18n_translations', {})
        if isinstance(all_trans, dict):
            loc_dict = all_trans.get(target_locale)
            if isinstance(loc_dict, dict) and text in loc_dict:
                return loc_dict[text]
    except Exception:
        pass

    return text
