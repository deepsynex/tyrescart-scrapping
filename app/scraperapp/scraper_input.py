"""Normalizes the three supported scraper-start inputs (CSV upload, JSON upload,
pasted URL text) into one shape, and validates/classifies every URL before a
scraper ever runs.

This module never decides *which* scraper script to run on its own -- it only
classifies URLs via `detect_scraper_type` (imported from scrapers/scraper_config.py,
the single source of truth for that mapping) and reports what it found. The
caller (app.py) is responsible for actually launching a script, and it only
ever launches scripts named in SCRIPT_MAP -- never a name supplied by the
request -- so a browser can never choose which scraper runs.
"""

import csv
import io
import json
import re
from urllib.parse import urlparse

from scraper_config import SCRIPT_MAP, detect_scraper_type

URL_RE = re.compile(r'^https?://', re.IGNORECASE)


class InputError(Exception):
    """Raised with an end-user-facing message when the request itself is unusable
    (empty file, unsupported extension, unparseable JSON, no input at all) --
    as opposed to individual bad URLs, which are collected and reported instead
    of raising.
    """


def _clean_token(raw):
    """Strips whitespace, surrounding quotes, and stray commas from one URL token,
    e.g. turns "  'https://example.com/x',  " into "https://example.com/x".
    """
    if raw is None:
        return ''
    token = str(raw).strip().strip(',').strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ('"', "'"):
        token = token[1:-1].strip()
    return token.strip(',').strip()


def _is_valid_url(url):
    if not url or not URL_RE.match(url):
        return False
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)


def parse_text_urls(text):
    """Splits -form pasted text into cleaned URL tokens -- one per line,
    also splitting each line on commas so "url1, url2" on one line still works.
    """
    tokens = []
    for line in (text or '').splitlines():
        for piece in line.split(','):
            cleaned = _clean_token(piece)
            if cleaned:
                tokens.append(cleaned)
    return tokens


def parse_csv_urls(file_bytes):
    """Returns [(raw_url, declared_type_or_None), ...] from CSV bytes.

    Supports a bare `url` column or `type,url` columns, with or without a
    header row. The declared type (when present) is carried through only for
    visibility -- build_entries() always re-detects the type itself rather
    than trusting it.
    """
    text = file_bytes.decode('utf-8-sig', errors='replace')
    rows = [row for row in csv.reader(io.StringIO(text)) if any((cell or '').strip() for cell in row)]
    if not rows:
        return []

    header = [(cell or '').strip().lower() for cell in rows[0]]
    if 'url' in header:
        url_col = header.index('url')
        type_col = header.index('type') if 'type' in header else None
        data_rows = rows[1:]
    else:
        url_col = 0
        type_col = 1 if len(header) > 1 else None
        data_rows = rows

    entries = []
    for row in data_rows:
        raw_url = row[url_col] if url_col < len(row) else ''
        declared_type = row[type_col].strip().lower() if type_col is not None and type_col < len(row) else None
        cleaned = _clean_token(raw_url)
        if cleaned:
            entries.append((cleaned, declared_type or None))
    return entries


def parse_json_urls(file_bytes):
    """Returns cleaned URL strings from JSON bytes -- accepts a bare array of
    strings, {"urls": [...]}, or an array of {"url": "..."} objects. Used for
    both an uploaded .json file and JSON text pasted directly into the UI.
    """
    try:
        data = json.loads(file_bytes.decode('utf-8-sig'))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InputError(f'Invalid JSON: {exc}')

    if isinstance(data, dict) and 'urls' in data:
        data = data['urls']

    if not isinstance(data, list):
        raise InputError('JSON input must be an array of URLs, {"urls": [...]}, or an array of {"url": "..."} objects.')

    urls = []
    for item in data:
        if isinstance(item, str):
            urls.append(_clean_token(item))
        elif isinstance(item, dict) and 'url' in item:
            urls.append(_clean_token(item['url']))
        else:
            raise InputError(f'Unrecognized entry in JSON input: {item!r}')
    return urls


def extract_input_source(req):
    """Given a Flask request, returns [(raw_url, declared_type_or_None), ...]
    from whichever of the three input methods the client used:
      - multipart file upload, field name "file", extension .csv or .json
      - JSON body {"urls": [...]} or {"text": "..."}
      - form field "text" (paste-URL tab submitted as regular form data)
      - JSON body {"json": "..."} -- raw JSON *text* pasted into the Upload
        JSON tab's textarea (as opposed to {"urls": [...]}, which is already
        a parsed list), parsed the same way an uploaded .json file would be
    Raises InputError with a user-facing message if the request can't be read.
    """
    if req.files and 'file' in req.files:
        upload = req.files['file']
        filename = (upload.filename or '').lower()
        if not filename:
            raise InputError('No file was selected.')

        raw_bytes = upload.read()
        if not raw_bytes:
            raise InputError('The uploaded file is empty.')

        if filename.endswith('.csv'):
            return parse_csv_urls(raw_bytes)
        if filename.endswith('.json'):
            return [(u, None) for u in parse_json_urls(raw_bytes)]
        raise InputError('Unsupported file type. Please upload a .csv or .json file.')

    data = req.get_json(silent=True)
    if isinstance(data, dict):
        if isinstance(data.get('urls'), list):
            return [(_clean_token(u), None) for u in data['urls']]
        if isinstance(data.get('json'), str):
            if not data['json'].strip():
                raise InputError('Paste some JSON first.')
            return [(u, None) for u in parse_json_urls(data['json'].encode('utf-8'))]
        if isinstance(data.get('text'), str):
            return [(u, None) for u in parse_text_urls(data['text'])]
        raise InputError('JSON body must be {"urls": [...]}, {"json": "..."}, or {"text": "..."}.')

    text = (req.form.get('text') or '').strip() if req.form else ''
    if text:
        return [(u, None) for u in parse_text_urls(text)]

    raise InputError('No input provided. Upload a CSV/JSON file, or paste one or more URLs.')


def build_entries(raw_items):
    """raw_items: [(raw_url, declared_type_or_None), ...]

    Returns (entries, errors, unsupported):
      entries     = [{"url", "type", "scraper"}, ...] -- valid, supported, deduped
      errors      = [{"row", "value", "reason"}, ...] -- malformed/non-http(s) URLs
      unsupported = [{"row", "url"}, ...]              -- well-formed but detect_scraper_type == "unknown"

    Rows are 1-indexed in the order they were supplied. Duplicate URLs (case/
    trailing-slash insensitive) are silently dropped after the first occurrence.
    A declared `type` is never trusted for routing -- detect_scraper_type()
    always makes the final call, independent of anything the input claimed.
    """
    entries = []
    errors = []
    unsupported = []
    seen = set()

    for row, item in enumerate(raw_items, start=1):
        raw_url = item[0] if isinstance(item, tuple) else item
        if not raw_url:
            continue

        if not _is_valid_url(raw_url):
            errors.append({'row': row, 'value': raw_url, 'reason': 'Invalid URL'})
            continue

        detected_type = detect_scraper_type(raw_url)
        if detected_type == 'unknown':
            unsupported.append({'row': row, 'url': raw_url})
            continue

        key = raw_url.rstrip('/').lower()
        if key in seen:
            continue
        seen.add(key)

        entries.append({'url': raw_url, 'type': detected_type, 'scraper': SCRIPT_MAP[detected_type]})

    return entries, errors, unsupported


def format_invalid_url_message(errors):
    if not errors:
        return ''
    lines = [f"Invalid URL on row {e['row']}: {e['value']}" for e in errors]
    return '\n'.join(lines) + '\n\nPlease provide a valid HTTP/HTTPS URL.'


def format_unsupported_message(unsupported):
    if not unsupported:
        return ''
    return '\n\n'.join(
        f"Unsupported URL\n\nUnable to determine a supported scraper for:\n{u['url']}" for u in unsupported
    )


def validate_url_list(raw_urls):
    """Generic (non-pitstoparabia-typed) URL list validation for fileTbl's
    registered scrapers -- unlike build_entries(), this never classifies a
    URL by scraper type or rejects it as "unsupported"; it only checks each
    one is a well-formed http(s) URL and dedupes them.

    raw_urls: an iterable of strings (already split into individual tokens,
    e.g. by parse_text_urls() or parse_csv_urls()).

    Returns (urls, errors):
      urls   = [str, ...]                       -- valid, deduped, in order
      errors = [{"row", "value", "reason"}, ...] -- malformed/non-http(s) URLs
    """
    urls = []
    errors = []
    seen = set()

    for row, raw in enumerate(raw_urls, start=1):
        cleaned = _clean_token(raw)
        if not cleaned:
            continue
        if not _is_valid_url(cleaned):
            errors.append({'row': row, 'value': cleaned, 'reason': 'Invalid URL'})
            continue
        key = cleaned.rstrip('/').lower()
        if key in seen:
            continue
        seen.add(key)
        urls.append(cleaned)

    return urls, errors
