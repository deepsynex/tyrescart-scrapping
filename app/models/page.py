"""
app/models/page.py - Page Model & ORM Helpers
Table: pages
Schema:
  - id: bigint UNSIGNED PRIMARY KEY AUTO_INCREMENT
  - title: json NOT NULL
  - slug: varchar(255) NOT NULL UNIQUE
  - content: json DEFAULT NULL
  - banner_image: varchar(500) DEFAULT NULL
  - seo_title: json DEFAULT NULL
  - meta_description: json DEFAULT NULL
  - is_active: tinyint(1) NOT NULL DEFAULT '1'
  - created_by: bigint UNSIGNED DEFAULT NULL
  - updated_by: bigint UNSIGNED DEFAULT NULL
  - created_at: timestamp NULL DEFAULT CURRENT_TIMESTAMP
  - updated_at: timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  - deleted_at: timestamp NULL DEFAULT NULL
"""

import json
import re
from datetime import datetime, timezone
from db import get_connection


# ============================================================================
# MIXINS
# ============================================================================

class SlugMixin:
    """Provides slug generation, normalization, and uniqueness checking."""
    
    @staticmethod
    def slugify(text: str) -> str:
        """Converts a raw string into a clean URL slug."""
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '-', text)
        return text.strip('-')

    @classmethod
    def is_slug_available(cls, slug: str, exclude_id: int = None) -> bool:
        """Checks if a given slug is unique in the pages table."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT id FROM pages WHERE slug = %s"
                params = [slug]
                if exclude_id:
                    sql += " AND id != %s"
                    params.append(exclude_id)
                cursor.execute(sql, tuple(params))
                return cursor.fetchone() is None
        finally:
            conn.close()


class SoftDeleteMixin:
    """Provides soft-delete capabilities and unique slug prefix management."""

    @classmethod
    def soft_delete(cls, page_id: int) -> bool:
        """Marks a page as deleted and s its slug for new pages."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT slug FROM pages WHERE id = %s AND deleted_at IS NULL", (page_id,))
                row = cursor.fetchone()
                if not row:
                    return False
                old_slug = row.get('slug') or ''
                ts = int(datetime.now(timezone.utc).timestamp())
                new_slug = f"__del_{page_id}_{ts}_{old_slug}"[:250]
                cursor.execute(
                    "UPDATE pages SET deleted_at = CURRENT_TIMESTAMP, slug = %s WHERE id = %s",
                    (new_slug, page_id)
                )
                return cursor.rowcount > 0
        finally:
            conn.close()

    @classmethod
    def restore(cls, page_id: int) -> bool:
        """Restores a soft-deleted page, restoring original slug if available."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT slug FROM pages WHERE id = %s AND deleted_at IS NOT NULL", (page_id,))
                row = cursor.fetchone()
                if not row:
                    return False
                cur_slug = row.get('slug') or ''
                clean_slug = re.sub(r'^__del_\d+_\d+_', '', cur_slug)
                target_slug = clean_slug

                cursor.execute("SELECT id FROM pages WHERE slug = %s AND id != %s", (target_slug, page_id))
                if cursor.fetchone() is not None:
                    target_slug = f"{clean_slug}-restored-{page_id}"

                cursor.execute(
                    "UPDATE pages SET deleted_at = NULL, slug = %s WHERE id = %s",
                    (target_slug, page_id)
                )
                return cursor.rowcount > 0
        finally:
            conn.close()

    @classmethod
    def hard_delete(cls, page_id: int) -> bool:
        """Permanently deletes a page record from the MySQL database."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM pages WHERE id = %s", (page_id,))
                return cursor.rowcount > 0
        finally:
            conn.close()


class SearchableMixin:
    """Provides fulltext/JSON search across title and content."""

    @classmethod
    def search(cls, query: str, locale: str = 'en', limit: int = 20):
        """Searches active published pages by title or content snippet."""
        if not query:
            return []
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                term = f"%{query.strip()}%"
                sql = """
                    SELECT * FROM pages 
                    WHERE deleted_at IS NULL 
                      AND is_active = 1
                      AND (
                        JSON_UNQUOTE(JSON_EXTRACT(title, %s)) LIKE %s
                        OR JSON_UNQUOTE(JSON_EXTRACT(content, %s)) LIKE %s
                      )
                    ORDER BY id DESC
                    LIMIT %s
                """
                loc_key = f"$.{locale}"
                cursor.execute(sql, (loc_key, term, loc_key, term, limit))
                rows = cursor.fetchall()
                return [cls(r) for r in rows]
        finally:
            conn.close()


# ============================================================================
# PAGE MODEL
# ============================================================================

class Page(SlugMixin, SoftDeleteMixin, SearchableMixin):
    """
    Page model for managing static content pages (About Us, Terms, Privacy Policy, etc.).
    Supports localized JSON payloads for title, content, seo_title, and meta_description.
    """

    TABLE = 'pages'
    COLUMNS = (
        'id', 'title', 'slug', 'content', 'banner_image', 'seo_title',
        'meta_description', 'is_active', 'created_by', 'updated_by',
        'created_at', 'updated_at', 'deleted_at'
    )

    def __init__(self, data: dict):
        self.id = data.get('id')
        self.title = self._parse_json(data.get('title'))
        
        # Display clean slug for soft-deleted items
        raw_slug = data.get('slug') or ''
        self.raw_slug = raw_slug
        self.slug = re.sub(r'^__del_\d+_\d+_', '', raw_slug)

        self.content = self._parse_json(data.get('content'))
        self.banner_image = data.get('banner_image')
        self.seo_title = self._parse_json(data.get('seo_title'))
        self.meta_description = self._parse_json(data.get('meta_description'))
        self.is_active = bool(data.get('is_active', 1))
        self.created_by = data.get('created_by')
        self.updated_by = data.get('updated_by')
        self.created_at = data.get('created_at')
        self.updated_at = data.get('updated_at')
        self.deleted_at = data.get('deleted_at')

    @staticmethod
    def _parse_json(val):
        if val is None:
            return {}
        if isinstance(val, (dict, list)):
            return val
        if isinstance(val, str):
            val_str = val.strip()
            if val_str.startswith('{') or val_str.startswith('['):
                try:
                    res = json.loads(val_str)
                    return res if isinstance(res, (dict, list)) else {'en': str(res)}
                except Exception:
                    pass
            return {'en': val}
        return {'en': str(val)}

    @staticmethod
    def _dump_json(val):
        if val is None:
            return None
        if isinstance(val, (dict, list)):
            return json.dumps(val, ensure_ascii=False)
        if isinstance(val, str):
            val_strip = val.strip()
            if val_strip.startswith('{') or val_strip.startswith('['):
                try:
                    json.loads(val_strip)
                    return val_strip
                except Exception:
                    pass
            return json.dumps({'en': val}, ensure_ascii=False)
        return json.dumps(val, ensure_ascii=False)

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # Localized Property Accessors
    # -------------------------------------------------------------------------
    def get_title(self, locale: str = None) -> str:
        """Returns the localized title string for any dynamic language."""
        from i18n import get_translated_value
        return get_translated_value(self.title, language_code=locale)

    def get_content(self, locale: str = None) -> str:
        """Returns the localized HTML body content for any dynamic language."""
        from i18n import get_translated_value
        return get_translated_value(self.content, language_code=locale)

    def get_seo_title(self, locale: str = None) -> str:
        """Returns the localized SEO title (defaults to title if not specified)."""
        from i18n import get_translated_value
        if isinstance(self.seo_title, dict) and self.seo_title:
            loc_seo = get_translated_value(self.seo_title, language_code=locale)
            if loc_seo:
                return loc_seo
        return self.get_title(locale)

    def get_meta_title(self, locale: str = None) -> str:
        """Alias for get_seo_title."""
        return self.get_seo_title(locale)

    def get_meta_desc(self, locale: str = None) -> str:
        """Returns the localized meta description for any dynamic language."""
        from i18n import get_translated_value
        return get_translated_value(self.meta_description, language_code=locale)

    def to_dict(self, locale: str = None) -> dict:
        """Serializes page record for API responses or template context."""
        from services.store_context import StoreContext
        loc = locale or StoreContext.get_current_language()
        return {
            'id': self.id,
            'slug': self.slug,
            'banner_image': self.banner_image,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'display_title': self.get_title(loc),
            'title_raw': self.title,
            'content_raw': self.content,
            'seo_title_raw': self.seo_title,
            'meta_description_raw': self.meta_description,
            'title': self.get_title(loc) if locale else self.title,
            'content': self.get_content(loc) if locale else self.content,
            'seo_title': self.get_seo_title(loc) if locale else self.seo_title,
            'meta_description': self.get_meta_desc(loc) if locale else self.meta_description,
        }

    # -------------------------------------------------------------------------
    # Query Helpers
    # -------------------------------------------------------------------------
    @classmethod
    def all(cls, include_deleted: bool = False):
        """Returns all pages ordered by id ASC."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT * FROM pages"
                if not include_deleted:
                    sql += " WHERE deleted_at IS NULL"
                sql += " ORDER BY id ASC"
                cursor.execute(sql)
                return [cls(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    @classmethod
    def published(cls):
        """Returns all active, non-deleted pages."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT * FROM pages WHERE deleted_at IS NULL AND is_active = 1 ORDER BY id ASC"
                cursor.execute(sql)
                return [cls(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    @classmethod
    def find_by_slug(cls, slug: str, include_inactive: bool = False):
        """Finds an active page by unique slug string."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                if include_inactive:
                    sql = "SELECT * FROM pages WHERE slug = %s AND deleted_at IS NULL LIMIT 1"
                else:
                    sql = "SELECT * FROM pages WHERE slug = %s AND deleted_at IS NULL AND is_active = 1 LIMIT 1"
                cursor.execute(sql, (slug,))
                row = cursor.fetchone()
                return cls(row) if row else None
        finally:
            conn.close()

    @classmethod
    def find_by_id(cls, page_id: int):
        """Finds a page by primary key id."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM pages WHERE id = %s LIMIT 1", (page_id,))
                row = cursor.fetchone()
                return cls(row) if row else None
        finally:
            conn.close()

    @classmethod
    def create(cls, **kwargs):
        """Creates and inserts a new Page row into MySQL."""
        from services.store_context import StoreContext
        curr_lang = StoreContext.get_current_language()

        slug = kwargs.get('slug')
        if not slug and kwargs.get('title'):
            t = kwargs['title']
            raw_title = t.get(curr_lang) or t.get('en') if isinstance(t, dict) else str(t)
            slug = cls.slugify(raw_title)

        def _prepare_multilingual_dict(raw_val, default_empty=""):
            if isinstance(raw_val, dict):
                d = dict(raw_val)
            elif isinstance(raw_val, str) and raw_val.strip().startswith('{'):
                try:
                    p = json.loads(raw_val.strip())
                    d = dict(p) if isinstance(p, dict) else {curr_lang: raw_val.strip()}
                except Exception:
                    d = {curr_lang: raw_val.strip()}
            elif raw_val is not None:
                d = {curr_lang: str(raw_val).strip()}
            else:
                d = {}
            if default_empty and curr_lang not in d:
                d[curr_lang] = default_empty
            return d

        title_dict = _prepare_multilingual_dict(kwargs.get('title'), default_empty="")
        content_dict = _prepare_multilingual_dict(kwargs.get('content'), default_empty="")
        seo_title_dict = _prepare_multilingual_dict(kwargs.get('seo_title'))
        meta_desc_dict = _prepare_multilingual_dict(kwargs.get('meta_description'))

        title_json = cls._dump_json(title_dict)
        content_json = cls._dump_json(content_dict)
        seo_title_json = cls._dump_json(seo_title_dict) if seo_title_dict else None
        meta_desc_json = cls._dump_json(meta_desc_dict) if meta_desc_dict else None
        is_active = 1 if kwargs.get('is_active', True) else 0

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO pages (
                        title, slug, content, banner_image,
                        seo_title, meta_description, is_active,
                        created_by, updated_by
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s
                    )
                """
                cursor.execute(sql, (
                    title_json,
                    slug,
                    content_json,
                    kwargs.get('banner_image'),
                    seo_title_json,
                    meta_desc_json,
                    is_active,
                    kwargs.get('created_by'),
                    kwargs.get('updated_by')
                ))
                page_id = cursor.lastrowid
                return cls.find_by_id(page_id)
        finally:
            conn.close()

    def update(self, **kwargs) -> bool:
        """Updates fields of this Page instance in MySQL, merging multilingual fields safely."""
        from services.store_context import StoreContext
        curr_lang = StoreContext.get_current_language()

        updates = []
        params = []

        multilingual_fields = [
            ('title', 'title'),
            ('content', 'content'),
            ('seo_title', 'seo_title'),
            ('meta_description', 'meta_description')
        ]

        for fld, attr in multilingual_fields:
            if fld in kwargs:
                input_val = kwargs[fld]
                existing_dict = dict(getattr(self, attr) or {})
                if isinstance(input_val, dict):
                    existing_dict.update(input_val)
                elif isinstance(input_val, str):
                    s = input_val.strip()
                    if s.startswith('{'):
                        try:
                            p = json.loads(s)
                            if isinstance(p, dict):
                                existing_dict.update(p)
                            else:
                                existing_dict[curr_lang] = s
                        except Exception:
                            existing_dict[curr_lang] = s
                    else:
                        existing_dict[curr_lang] = input_val.strip()
                elif input_val is None:
                    existing_dict = {}

                updates.append(f"{fld} = %s")
                params.append(self._dump_json(existing_dict))

        if 'slug' in kwargs:
            updates.append("slug = %s")
            params.append(kwargs['slug'])
        if 'banner_image' in kwargs:
            updates.append("banner_image = %s")
            params.append(kwargs['banner_image'])
        if 'is_active' in kwargs:
            updates.append("is_active = %s")
            params.append(1 if kwargs['is_active'] else 0)
        if 'updated_by' in kwargs:
            updates.append("updated_by = %s")
            params.append(kwargs['updated_by'])

        if not updates:
            return False

        params.append(self.id)
        cols_clause = ", ".join(updates)
        sql = f"UPDATE pages SET {cols_clause} WHERE id = %s"

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                return cursor.rowcount > 0
        finally:
            conn.close()
