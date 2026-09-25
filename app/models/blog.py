"""
app/models/blog.py - Blog Model & ORM Layer
Table: blogs
Schema:
  - id: bigint UNSIGNED PRIMARY KEY AUTO_INCREMENT
  - title: json NOT NULL
  - slug: varchar(255) NOT NULL UNIQUE
  - content: json NOT NULL
  - short_description: json DEFAULT NULL
  - image: varchar(255) DEFAULT NULL
  - blog_category_id: bigint UNSIGNED DEFAULT NULL
  - author_id: bigint UNSIGNED DEFAULT NULL
  - status: enum('draft','published','archived') NOT NULL DEFAULT 'draft'
  - published_at: timestamp NULL DEFAULT NULL
  - meta_title: json DEFAULT NULL
  - meta_desc: json DEFAULT NULL
  - created_at: timestamp NULL DEFAULT CURRENT_TIMESTAMP
  - updated_at: timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  - deleted_at: timestamp NULL DEFAULT NULL
  - created_by: bigint UNSIGNED DEFAULT NULL
  - updated_by: bigint UNSIGNED DEFAULT NULL
"""

import json
import re
from datetime import datetime, timezone
from db import get_connection
from i18n import localize_value, dump_json_dict, parse_json_dict, DEFAULT_LOCALE


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
        """Checks if a given slug is unique in the blogs table."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT id FROM blogs WHERE slug = %s"
                params = [slug]
                if exclude_id:
                    sql += " AND id != %s"
                    params.append(exclude_id)
                cursor.execute(sql, tuple(params))
                return cursor.fetchone() is None
        finally:
            conn.close()


class SoftDeleteMixin:
    """Provides soft-delete capabilities and unique slug collision handling."""

    @classmethod
    def soft_delete(cls, blog_id: int) -> bool:
        """Marks a blog as deleted and prefixes slug to free it for reuse."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT slug FROM blogs WHERE id = %s AND deleted_at IS NULL", (blog_id,))
                row = cursor.fetchone()
                if not row:
                    return False
                old_slug = row.get('slug') or ''
                ts = int(datetime.now(timezone.utc).timestamp())
                new_slug = f"__del_{blog_id}_{ts}_{old_slug}"[:250]
                cursor.execute(
                    "UPDATE blogs SET deleted_at = CURRENT_TIMESTAMP, slug = %s WHERE id = %s",
                    (new_slug, blog_id)
                )
                return cursor.rowcount > 0
        finally:
            conn.close()

    @classmethod
    def restore(cls, blog_id: int) -> bool:
        """Restores a soft-deleted blog, reclaiming original slug if available."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT slug FROM blogs WHERE id = %s AND deleted_at IS NOT NULL", (blog_id,))
                row = cursor.fetchone()
                if not row:
                    return False
                cur_slug = row.get('slug') or ''
                clean_slug = re.sub(r'^__del_\d+_\d+_', '', cur_slug)
                target_slug = clean_slug

                cursor.execute("SELECT id FROM blogs WHERE slug = %s AND id != %s", (target_slug, blog_id))
                if cursor.fetchone() is not None:
                    target_slug = f"{clean_slug}-restored-{blog_id}"

                cursor.execute(
                    "UPDATE blogs SET deleted_at = NULL, slug = %s WHERE id = %s",
                    (target_slug, blog_id)
                )
                return cursor.rowcount > 0
        finally:
            conn.close()

    @classmethod
    def hard_delete(cls, blog_id: int) -> bool:
        """Permanently deletes a blog record from the MySQL database."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM blogs WHERE id = %s", (blog_id,))
                return cursor.rowcount > 0
        finally:
            conn.close()


class SearchableMixin:
    """Provides fulltext/JSON search across title, short_description, and content."""

    @classmethod
    def search(cls, query: str, locale: str = 'en', limit: int = 20):
        """Searches active published blogs by title or content snippet."""
        if not query:
            return []
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                term = f"%{query.strip()}%"
                sql = """
                    SELECT * FROM blogs 
                    WHERE deleted_at IS NULL 
                      AND status = 'published'
                      AND (
                        JSON_UNQUOTE(JSON_EXTRACT(title, %s)) LIKE %s
                        OR JSON_UNQUOTE(JSON_EXTRACT(content, %s)) LIKE %s
                        OR JSON_UNQUOTE(JSON_EXTRACT(short_description, %s)) LIKE %s
                      )
                    ORDER BY published_at DESC, id DESC
                    LIMIT %s
                """
                loc_key = f"$.{locale}"
                cursor.execute(sql, (loc_key, term, loc_key, term, loc_key, term, limit))
                rows = cursor.fetchall()
                return [cls(r) for r in rows]
        finally:
            conn.close()


# ============================================================================
# BLOG MODEL
# ============================================================================

class Blog(SlugMixin, SoftDeleteMixin, SearchableMixin):
    """
    Blog ORM model for managing articles, posts, and announcements.
    Supports localized JSON payloads for title, content, short_description, meta_title, and meta_desc.
    """

    TABLE = 'blogs'
    COLUMNS = (
        'id', 'title', 'slug', 'content', 'short_description', 'image',
        'category_id', 'author_id', 'status', 'published_at',
        'meta_title', 'meta_desc', 'faqs', 'created_at', 'updated_at', 'deleted_at',
        'created_by', 'updated_by'
    )

    VALID_STATUSES = ('draft', 'published', 'archived')

    def __init__(self, data: dict):
        self.id = data.get('id')
        self.title = self._parse_json(data.get('title'))
        
        # Display clean slug for soft-deleted items
        raw_slug = data.get('slug') or ''
        self.raw_slug = raw_slug
        self.slug = re.sub(r'^__del_\d+_\d+_', '', raw_slug)

        self.content = self._parse_json(data.get('content'))
        self.short_description = self._parse_json(data.get('short_description'))
        self.image = data.get('image')
        self.category_id = data.get('category_id')
        cat_raw = data.get('category_name')
        if isinstance(cat_raw, (dict, list)):
            self.category_name = cat_raw
        elif isinstance(cat_raw, str) and cat_raw.strip().startswith('{'):
            try:
                self.category_name = json.loads(cat_raw)
            except Exception:
                self.category_name = cat_raw or ''
        else:
            self.category_name = cat_raw or ''
        self.category_slug = data.get('category_slug') or ''
        self.author_id = data.get('author_id')
        self.status = data.get('status') or 'draft'
        self.published_at = data.get('published_at')
        self.meta_title = self._parse_json(data.get('meta_title'))
        self.meta_desc = self._parse_json(data.get('meta_desc'))
        self.faqs = self._parse_json(data.get('faqs'))
        self.created_at = data.get('created_at')
        self.updated_at = data.get('updated_at')
        self.deleted_at = data.get('deleted_at')
        self.created_by = data.get('created_by')
        self.updated_by = data.get('updated_by')

    @property
    def blog_category_id(self):
        """Backward-compatible alias for category_id."""
        return self.category_id

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
        """Returns the localized title string."""
        from i18n import get_translated_value
        return get_translated_value(self.title, language_code=locale)

    def get_content(self, locale: str = None) -> str:
        """Returns the localized HTML body content."""
        from i18n import get_translated_value
        return get_translated_value(self.content, language_code=locale)

    def get_short_desc(self, locale: str = None) -> str:
        """Returns the localized short summary description."""
        from i18n import get_translated_value
        return get_translated_value(self.short_description, language_code=locale)

    def get_meta_title(self, locale: str = None) -> str:
        """Returns the localized meta title (fallback to title)."""
        from i18n import get_translated_value
        loc_mt = get_translated_value(self.meta_title, language_code=locale) if self.meta_title else ""
        return loc_mt or self.get_title(locale)

    def get_meta_desc(self, locale: str = None) -> str:
        """Returns the localized meta description (fallback to short_description)."""
        from i18n import get_translated_value
        loc_md = get_translated_value(self.meta_desc, language_code=locale) if self.meta_desc else ""
        return loc_md or self.get_short_desc(locale)

    def get_faqs(self, locale: str = None) -> list:
        """
        Returns localized list of FAQ objects [{'question': '...', 'answer': '...'}].
        """
        if not self.faqs:
            return []
        from services.store_context import StoreContext
        from i18n import get_translated_value
        loc = locale or StoreContext.get_current_language()

        if isinstance(self.faqs, dict):
            items = self.faqs.get(loc) or self.faqs.get('en') or []
            if isinstance(items, list):
                return [
                    {
                        'question': it.get('question') if isinstance(it, dict) else str(it),
                        'answer': it.get('answer') if isinstance(it, dict) else ''
                    }
                    for it in items if isinstance(it, dict) and it.get('question')
                ]
        if isinstance(self.faqs, list):
            result = []
            for item in self.faqs:
                if not isinstance(item, dict):
                    continue
                q = item.get('question')
                a = item.get('answer')
                q_text = get_translated_value(q, language_code=loc) if isinstance(q, dict) else str(q or '')
                a_text = get_translated_value(a, language_code=loc) if isinstance(a, dict) else str(a or '')
                if q_text:
                    result.append({'question': q_text, 'answer': a_text})
            return result
        return []

    def get_category_name(self, locale: str = None) -> str:
        """Returns the localized category name string for any dynamic language."""
        if not self.category_name:
            return ""
        from i18n import get_translated_value
        if isinstance(self.category_name, dict):
            return get_translated_value(self.category_name, language_code=locale)
        return str(self.category_name or "")

    @property
    def category_name_ar(self):
        """Backward-compatible alias returning Arabic translation if available."""
        return self.get_category_name('ar')

    @property
    def is_published(self) -> bool:
        """Checks if blog post is published and not deleted."""
        return self.status == 'published' and self.deleted_at is None

    def to_dict(self, locale: str = None) -> dict:
        """Serializes blog record for API responses or template rendering."""
        from services.store_context import StoreContext
        loc = locale or StoreContext.get_current_language()
        cat_display = self.get_category_name(loc)
        base = {
            'id': self.id,
            'slug': self.slug,
            'image': self.image,
            'category_id': self.category_id,
            'category_name': cat_display or '',
            'category_slug': self.category_slug or '',
            'blog_category_id': self.category_id,
            'author_id': self.author_id,
            'status': self.status,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'display_title': self.get_title(loc),
            'title_raw': self.title,
            'content_raw': self.content,
            'short_description_raw': self.short_description,
            'meta_title_raw': self.meta_title,
            'meta_desc_raw': self.meta_desc,
            'title': self.get_title(loc) if locale else self.title,
            'content': self.get_content(loc) if locale else self.content,
            'short_description': self.get_short_desc(loc) if locale else self.short_description,
            'meta_title': self.get_meta_title(loc) if locale else self.meta_title,
            'meta_desc': self.get_meta_desc(loc) if locale else self.meta_desc,
            'faqs': self.get_faqs(loc) if locale else (self.faqs if isinstance(self.faqs, (list, dict)) else []),
        }
        return base

    # -------------------------------------------------------------------------
    # Query Helpers
    # -------------------------------------------------------------------------
    @classmethod
    def get_all_categories(cls, locale: str = None) -> list:
        """Returns all active categories from blog_categories table with blog counts."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT c.id, c.name, c.slug, c.sort_order, c.status, c.meta_title, c.meta_keywords, c.meta_description,
                           c.created_at, c.updated_at,
                           COUNT(b.id) AS blogs_count
                    FROM blog_categories c
                    LEFT JOIN blogs b ON b.category_id = c.id AND b.deleted_at IS NULL
                    WHERE c.deleted_at IS NULL
                    GROUP BY c.id, c.name, c.slug, c.sort_order, c.status, c.meta_title, c.meta_keywords, c.meta_description,
                             c.created_at, c.updated_at
                    ORDER BY c.sort_order ASC, c.id ASC
                """)
                rows = cursor.fetchall() or []
                from services.store_context import StoreContext
                from i18n import get_translated_value
                loc = locale or StoreContext.get_current_language()
                for r in rows:
                    name_parsed = cls._parse_json(r.get('name'))
                    r['name'] = name_parsed
                    r['title'] = name_parsed
                    r['meta_title'] = cls._parse_json(r.get('meta_title'))
                    r['meta_keywords'] = cls._parse_json(r.get('meta_keywords'))
                    r['meta_description'] = cls._parse_json(r.get('meta_description'))
                    r['status'] = r.get('status') or 'enabled'
                    r['sort_order'] = r.get('sort_order') if r.get('sort_order') is not None else 0
                    r['display_name'] = get_translated_value(name_parsed, loc)
                    r['name_en'] = get_translated_value(name_parsed, 'en')
                    r['name_ar'] = get_translated_value(name_parsed, 'ar')
                return rows
        finally:
            conn.close()

    @classmethod
    def get_category_by_id(cls, cat_id: int, locale: str = None) -> dict:
        """Returns a single category by id with localized fields and blog counts."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT c.id, c.name, c.slug, c.sort_order, c.status, c.meta_title, c.meta_keywords, c.meta_description,
                           c.created_at, c.updated_at,
                           COUNT(b.id) AS blogs_count
                    FROM blog_categories c
                    LEFT JOIN blogs b ON b.category_id = c.id AND b.deleted_at IS NULL
                    WHERE c.id = %s AND c.deleted_at IS NULL
                    GROUP BY c.id, c.name, c.slug, c.sort_order, c.status, c.meta_title, c.meta_keywords, c.meta_description,
                             c.created_at, c.updated_at
                """, (cat_id,))
                r = cursor.fetchone()
                if not r:
                    return None
                from services.store_context import StoreContext
                from i18n import get_translated_value
                loc = locale or StoreContext.get_current_language()

                name_parsed = cls._parse_json(r.get('name'))
                meta_title_parsed = cls._parse_json(r.get('meta_title'))
                meta_keywords_parsed = cls._parse_json(r.get('meta_keywords'))
                meta_description_parsed = cls._parse_json(r.get('meta_description'))

                r['name'] = name_parsed
                r['title'] = name_parsed
                r['meta_title'] = meta_title_parsed
                r['meta_keywords'] = meta_keywords_parsed
                r['meta_description'] = meta_description_parsed
                r['status'] = r.get('status') or 'enabled'
                r['sort_order'] = r.get('sort_order') if r.get('sort_order') is not None else 0

                r['display_name'] = get_translated_value(name_parsed, loc)
                r['name_en'] = get_translated_value(name_parsed, 'en')
                r['name_ar'] = get_translated_value(name_parsed, 'ar')

                return r
        finally:
            conn.close()

    @classmethod
    def create_category(cls, data: dict, user_id: int = None) -> dict:
        """Creates a new category in blog_categories table with full Magento-style fields."""
        data = data or {}
        raw_name = data.get('name') or data.get('title') or data.get('name_en')
        name_dict = raw_name if isinstance(raw_name, dict) else cls._parse_json(raw_name)
        if not isinstance(name_dict, dict) or not name_dict:
            name_dict = {DEFAULT_LOCALE: str(raw_name or '').strip()}

        if data.get('name_en'):
            name_dict['en'] = str(data['name_en']).strip()
        if data.get('name_ar'):
            name_dict['ar'] = str(data['name_ar']).strip()

        slug_seed = name_dict.get('en') or next(iter(name_dict.values()), '')
        custom_slug = (data.get('slug') or '').strip()
        slug = SlugMixin.slugify(custom_slug) if custom_slug else SlugMixin.slugify(slug_seed)
        if not slug:
            slug = f"category-{int(datetime.now(timezone.utc).timestamp())}"

        status = data.get('status') or 'enabled'
        if status not in ('enabled', 'disabled'):
            status = 'enabled'

        try:
            sort_order = int(data.get('sort_order', 0))
        except (ValueError, TypeError):
            sort_order = 0

        # Parse meta fields
        def _normalize_meta(val, fallback_key='meta_en'):
            if isinstance(val, dict):
                return val
            parsed = cls._parse_json(val)
            if isinstance(parsed, dict) and parsed:
                return parsed
            if val is not None and str(val).strip():
                return {'en': str(val).strip()}
            return {}

        meta_title_dict = _normalize_meta(data.get('meta_title'))
        if data.get('meta_title_en'):
            meta_title_dict['en'] = str(data['meta_title_en']).strip()
        if data.get('meta_title_ar'):
            meta_title_dict['ar'] = str(data['meta_title_ar']).strip()

        meta_keywords_dict = _normalize_meta(data.get('meta_keywords'))
        if data.get('meta_keywords_en'):
            meta_keywords_dict['en'] = str(data['meta_keywords_en']).strip()
        if data.get('meta_keywords_ar'):
            meta_keywords_dict['ar'] = str(data['meta_keywords_ar']).strip()

        meta_description_dict = _normalize_meta(data.get('meta_description'))
        if data.get('meta_description_en'):
            meta_description_dict['en'] = str(data['meta_description_en']).strip()
        if data.get('meta_description_ar'):
            meta_description_dict['ar'] = str(data['meta_description_ar']).strip()

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # Check slug uniqueness among active categories
                cursor.execute("SELECT id FROM blog_categories WHERE slug = %s AND deleted_at IS NULL", (slug,))
                if cursor.fetchone() is not None:
                    slug = f"{slug}-{int(datetime.now(timezone.utc).timestamp()) % 10000}"

                cursor.execute("""
                    INSERT INTO blog_categories (
                        name, slug, sort_order, status, meta_title, meta_keywords, meta_description,
                        created_at, updated_at, created_by, updated_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s)
                """, (
                    dump_json_dict(name_dict),
                    slug,
                    sort_order,
                    status,
                    dump_json_dict(meta_title_dict) if meta_title_dict else None,
                    dump_json_dict(meta_keywords_dict) if meta_keywords_dict else None,
                    dump_json_dict(meta_description_dict) if meta_description_dict else None,
                    user_id,
                    user_id
                ))
                conn.commit()
                cat_id = cursor.lastrowid
                return cls.get_category_by_id(cat_id)
        finally:
            conn.close()

    @classmethod
    def update_category(cls, cat_id: int, name=None, slug: str = None, user_id: int = None, **kwargs) -> dict:
        """Updates an existing category in blog_categories storing name as JSON, preserving other languages."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM blog_categories WHERE id = %s AND deleted_at IS NULL", (cat_id,))
                existing = cursor.fetchone()
                if not existing:
                    return None

                from services.store_context import StoreContext
                curr_lang = StoreContext.get_current_language()

                name_dict = cls._parse_json(existing.get('name')) if existing.get('name') else {}
                if not isinstance(name_dict, dict):
                    name_dict = {}

                # Name / Title handling
                raw_name = name if name is not None else kwargs.get('title')
                if isinstance(raw_name, dict):
                    name_dict.update(raw_name)
                elif isinstance(raw_name, str) and raw_name.strip().startswith('{'):
                    parsed = cls._parse_json(raw_name)
                    if isinstance(parsed, dict):
                        name_dict.update(parsed)
                    else:
                        name_dict[curr_lang] = raw_name.strip()
                elif raw_name is not None and str(raw_name).strip():
                    name_dict[curr_lang] = str(raw_name).strip()

                if kwargs.get('name_en'):
                    name_dict['en'] = str(kwargs['name_en']).strip()
                if kwargs.get('name_ar'):
                    name_dict['ar'] = str(kwargs['name_ar']).strip()

                name_json = dump_json_dict(name_dict)

                # Slug handling
                slug_val = slug if slug is not None else kwargs.get('slug')
                if slug_val:
                    clean_slug = SlugMixin.slugify(slug_val)
                else:
                    slug_seed = name_dict.get('en') or next(iter(name_dict.values()), '')
                    clean_slug = SlugMixin.slugify(slug_seed) or existing.get('slug')

                # Status handling
                status = kwargs.get('status', existing.get('status', 'enabled'))
                if status not in ('enabled', 'disabled'):
                    status = 'enabled'

                # Sort order handling
                try:
                    sort_order = int(kwargs.get('sort_order', existing.get('sort_order', 0)))
                except (ValueError, TypeError):
                    sort_order = existing.get('sort_order', 0)

                # Meta fields handling
                def _update_meta_dict(field_name, direct_val, en_key, ar_key):
                    existing_val = cls._parse_json(existing.get(field_name)) if existing.get(field_name) else {}
                    if not isinstance(existing_val, dict):
                        existing_val = {}
                    if isinstance(direct_val, dict):
                        existing_val.update(direct_val)
                    elif isinstance(direct_val, str) and direct_val.strip().startswith('{'):
                        p = cls._parse_json(direct_val)
                        if isinstance(p, dict):
                            existing_val.update(p)
                        else:
                            existing_val[curr_lang] = direct_val.strip()
                    elif direct_val is not None:
                        existing_val[curr_lang] = str(direct_val).strip()

                    if kwargs.get(en_key) is not None:
                        existing_val['en'] = str(kwargs[en_key]).strip()
                    if kwargs.get(ar_key) is not None:
                        existing_val['ar'] = str(kwargs[ar_key]).strip()
                    return existing_val

                meta_title_dict = _update_meta_dict('meta_title', kwargs.get('meta_title'), 'meta_title_en', 'meta_title_ar')
                meta_keywords_dict = _update_meta_dict('meta_keywords', kwargs.get('meta_keywords'), 'meta_keywords_en', 'meta_keywords_ar')
                meta_description_dict = _update_meta_dict('meta_description', kwargs.get('meta_description'), 'meta_description_en', 'meta_description_ar')

                cursor.execute("""
                    UPDATE blog_categories
                    SET name = %s, slug = %s, status = %s, sort_order = %s,
                        meta_title = %s, meta_keywords = %s, meta_description = %s,
                        updated_at = NOW(), updated_by = %s
                    WHERE id = %s AND deleted_at IS NULL
                """, (
                    name_json,
                    clean_slug,
                    status,
                    sort_order,
                    dump_json_dict(meta_title_dict) if meta_title_dict else None,
                    dump_json_dict(meta_keywords_dict) if meta_keywords_dict else None,
                    dump_json_dict(meta_description_dict) if meta_description_dict else None,
                    user_id,
                    cat_id
                ))
                conn.commit()
                return cls.get_category_by_id(cat_id)
        finally:
            conn.close()

    @classmethod
    def delete_category(cls, cat_id: int, user_id: int = None) -> bool:
        """Soft-deletes a category in blog_categories."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE blog_categories
                    SET deleted_at = NOW(), updated_by = %s
                    WHERE id = %s AND deleted_at IS NULL
                """, (user_id, cat_id))
                affected = cursor.rowcount
                cursor.execute("""
                    UPDATE blogs
                    SET category_id = NULL
                    WHERE category_id = %s
                """, (cat_id,))
                conn.commit()
                return affected > 0
        finally:
            conn.close()

    @classmethod
    def get_or_create_category(cls, name, user_id: int = None, **kwargs) -> dict:
        """Finds existing or creates a new category record in blog_categories table using JSON storage."""
        if not name:
            return None
        name_dict = name if isinstance(name, dict) else cls._parse_json(name)
        if not isinstance(name_dict, dict) or not name_dict:
            name_dict = {DEFAULT_LOCALE: str(name).strip()}

        if kwargs.get('name_en'):
            name_dict['en'] = kwargs['name_en'].strip()
        if kwargs.get('name_ar'):
            name_dict['ar'] = kwargs['name_ar'].strip()

        slug_seed = name_dict.get('en') or next(iter(name_dict.values()), '')
        slug = SlugMixin.slugify(slug_seed)
        name_json = dump_json_dict(name_dict)

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, name, slug, sort_order, status
                    FROM blog_categories
                    WHERE slug = %s AND deleted_at IS NULL
                    LIMIT 1
                """, (slug,))
                row = cursor.fetchone()
                if row:
                    row['name'] = cls._parse_json(row.get('name'))
                    if isinstance(row['name'], dict) and any(k not in row['name'] for k in name_dict):
                        row['name'].update(name_dict)
                        cursor.execute("UPDATE blog_categories SET name = %s, updated_at = NOW() WHERE id = %s", (dump_json_dict(row['name']), row['id']))
                        conn.commit()
                    row['display_name'] = localize_value(row['name'])
                    row['name_en'] = localize_value(row['name'], 'en')
                    row['name_ar'] = localize_value(row['name'], 'ar')
                    return row

                status = kwargs.get('status', 'enabled')
                cursor.execute("""
                    INSERT INTO blog_categories (name, slug, sort_order, status, created_at, updated_at, created_by, updated_by)
                    VALUES (%s, %s, 0, %s, NOW(), NOW(), %s, %s)
                """, (name_json, slug, status, user_id, user_id))
                conn.commit()
                cat_id = cursor.lastrowid
                return cls.get_category_by_id(cat_id)
        finally:
            conn.close()

    @classmethod
    def distinct_categories(cls, locale: str = None) -> list:
        """Returns distinct category names stored in blog_categories table, localized for any requested locale."""
        cats = cls.get_all_categories(locale=locale)
        if cats:
            return [c.get('display_name') or localize_value(c.get('name'), locale) for c in cats if c.get('name')]

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT category_name 
                    FROM blogs 
                    WHERE category_name IS NOT NULL 
                      AND category_name != '' 
                      AND deleted_at IS NULL
                    ORDER BY category_name ASC
                """)
                rows = cursor.fetchall()
                found = []
                for r in rows:
                    c_val = r.get('category_name')
                    if c_val:
                        if isinstance(c_val, str) and c_val.strip().startswith('{'):
                            found.append(localize_value(cls._parse_json(c_val), locale))
                        else:
                            found.append(str(c_val).strip())
                return found
        finally:
            conn.close()

    @classmethod
    def all(cls, include_deleted: bool = False, status: str = None):
        """Returns all blogs with optional status/trash filtering, joining category details."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT b.*,
                           c.name AS category_name,
                           c.slug AS category_slug
                    FROM blogs b
                    LEFT JOIN blog_categories c ON b.category_id = c.id
                    WHERE 1=1
                """
                params = []
                if not include_deleted:
                    sql += " AND b.deleted_at IS NULL"
                if status:
                    sql += " AND b.status = %s"
                    params.append(status)
                sql += " ORDER BY b.id DESC"
                cursor.execute(sql, tuple(params))
                return [cls(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    @classmethod
    def published(cls, limit: int = None):
        """Returns all published non-deleted blogs ordered by published_at DESC."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT b.*,
                           c.name AS category_name,
                           c.slug AS category_slug
                    FROM blogs b
                    LEFT JOIN blog_categories c ON b.category_id = c.id
                    WHERE b.deleted_at IS NULL 
                      AND b.status = 'published' 
                    ORDER BY COALESCE(b.published_at, b.created_at) DESC, b.id DESC
                """
                if limit:
                    sql += f" LIMIT {int(limit)}"
                cursor.execute(sql)
                return [cls(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    @classmethod
    def find_by_slug(cls, slug: str, include_drafts: bool = False):
        """Finds a blog post by unique slug string."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                if include_drafts:
                    sql = """
                        SELECT b.*,
                               c.name AS category_name,
                               c.slug AS category_slug
                        FROM blogs b
                        LEFT JOIN blog_categories c ON b.category_id = c.id
                        WHERE b.slug = %s AND b.deleted_at IS NULL LIMIT 1
                    """
                else:
                    sql = """
                        SELECT b.*,
                               c.name AS category_name,
                               c.slug AS category_slug
                        FROM blogs b
                        LEFT JOIN blog_categories c ON b.category_id = c.id
                        WHERE b.slug = %s AND b.deleted_at IS NULL AND b.status = 'published' LIMIT 1
                    """
                cursor.execute(sql, (slug,))
                row = cursor.fetchone()
                return cls(row) if row else None
        finally:
            conn.close()

    @classmethod
    def find_by_id(cls, blog_id: int):
        """Finds a blog post by primary key id."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT b.*,
                           c.name AS category_name,
                           c.slug AS category_slug
                    FROM blogs b
                    LEFT JOIN blog_categories c ON b.category_id = c.id
                    WHERE b.id = %s LIMIT 1
                """, (blog_id,))
                row = cursor.fetchone()
                return cls(row) if row else None
        finally:
            conn.close()

    @classmethod
    def create(cls, **kwargs):
        """Creates and inserts a new Blog row into MySQL using category_id."""
        slug = kwargs.get('slug')
        if not slug and kwargs.get('title'):
            t = kwargs['title']
            raw_title = t.get('en') if isinstance(t, dict) else str(t)
            slug = cls.slugify(raw_title)

        title_json = cls._dump_json(kwargs.get('title', {"en": ""}))
        content_json = cls._dump_json(kwargs.get('content', {"en": "", "ar": ""}))
        short_desc_json = cls._dump_json(kwargs.get('short_description'))
        meta_title_json = cls._dump_json(kwargs.get('meta_title'))
        meta_desc_json = cls._dump_json(kwargs.get('meta_desc'))
        faqs_json = cls._dump_json(kwargs.get('faqs', []))
        status = kwargs.get('status', 'draft')
        if status not in cls.VALID_STATUSES:
            status = 'draft'

        published_at = kwargs.get('published_at')
        if status == 'published' and not published_at:
            published_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cat_id = kwargs.get('category_id') or kwargs.get('blog_category_id')
                cat_name = kwargs.get('category_name') or kwargs.get('category')
                if not cat_id and cat_name:
                    cat_rec = cls.get_or_create_category(cat_name, user_id=kwargs.get('created_by'))
                    if cat_rec:
                        cat_id = cat_rec['id']

                sql = """
                    INSERT INTO blogs (
                        title, slug, content, short_description, image,
                        category_id, author_id, status, published_at,
                        meta_title, meta_desc, faqs, created_by, updated_by
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                """
                cursor.execute(sql, (
                    title_json,
                    slug,
                    content_json,
                    short_desc_json,
                    kwargs.get('image'),
                    cat_id,
                    kwargs.get('author_id', 1),
                    status,
                    published_at,
                    meta_title_json,
                    meta_desc_json,
                    faqs_json,
                    kwargs.get('created_by'),
                    kwargs.get('updated_by')
                ))
                blog_id = cursor.lastrowid
                return cls.find_by_id(blog_id)
        finally:
            conn.close()

    def update(self, **kwargs) -> bool:
        """Updates fields of this Blog instance in MySQL, merging multilingual fields safely."""
        from services.store_context import StoreContext
        curr_lang = StoreContext.get_current_language()

        updates = []
        params = []

        multilingual_fields = [
            ('title', 'title'),
            ('content', 'content'),
            ('short_description', 'short_description'),
            ('meta_title', 'meta_title'),
            ('meta_desc', 'meta_desc')
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
        if 'image' in kwargs:
            updates.append("image = %s")
            params.append(kwargs['image'])
        if 'category_id' in kwargs:
            updates.append("category_id = %s")
            params.append(kwargs['category_id'] if kwargs['category_id'] else None)
        elif 'blog_category_id' in kwargs:
            updates.append("category_id = %s")
            params.append(kwargs['blog_category_id'] if kwargs['blog_category_id'] else None)
        elif 'category_name' in kwargs:
            cat_name = kwargs['category_name']
            if cat_name:
                cat_rec = self.get_or_create_category(cat_name, user_id=kwargs.get('updated_by'))
                cat_id = cat_rec['id'] if cat_rec else None
            else:
                cat_id = None
            updates.append("category_id = %s")
            params.append(cat_id)
        if 'author_id' in kwargs:
            updates.append("author_id = %s")
            params.append(kwargs['author_id'])
        if 'status' in kwargs:
            new_status = kwargs['status']
            if new_status in self.VALID_STATUSES:
                updates.append("status = %s")
                params.append(new_status)
        if 'published_at' in kwargs:
            updates.append("published_at = %s")
            params.append(kwargs['published_at'])
        if 'faqs' in kwargs:
            updates.append("faqs = %s")
            params.append(self._dump_json(kwargs['faqs']))
        if 'updated_by' in kwargs:
            updates.append("updated_by = %s")
            params.append(kwargs['updated_by'])

        if not updates:
            return False

        params.append(self.id)
        cols_clause = ", ".join(updates)
        sql = f"UPDATE blogs SET {cols_clause} WHERE id = %s"

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                return cursor.rowcount > 0
        finally:
            conn.close()
