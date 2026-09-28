from db import get_connection

CREATE_ADMIN_USERS_TBL = """
CREATE TABLE IF NOT EXISTS admin_users (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role ENUM('super_admin', 'manager', 'support') NOT NULL DEFAULT 'super_admin',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    last_login_at TIMESTAMP NULL DEFAULT NULL,
    remember_token VARCHAR(100) NULL DEFAULT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_admin_email (email),
    INDEX idx_admin_role (role),
    INDEX idx_admin_active (is_active)
)
"""

CREATE_PASSWORD_RESET_TOKENS_TBL = """
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    email VARCHAR(255) NOT NULL,
    token VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_reset_token (token),
    INDEX idx_reset_email (email)
)
"""

CREATE_USER_TBL = """
CREATE TABLE IF NOT EXISTS userTbl (
    userid INT AUTO_INCREMENT PRIMARY KEY,
    Name VARCHAR(50) NOT NULL,
    Email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    Status BIT(1) NOT NULL DEFAULT 1,
    IsDeleted BIT(1) NOT NULL DEFAULT 0,
    Role VARCHAR(50) NOT NULL,
    avatar VARCHAR(500) NULL,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_user_deleted_id (IsDeleted, userid),
    INDEX idx_user_role (Role)
)
"""

NEW_USER_COLUMNS = {
    "avatar": "ALTER TABLE userTbl ADD COLUMN avatar VARCHAR(500) NULL",
    "updated_at": "ALTER TABLE userTbl ADD COLUMN updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
    "created_at": "ALTER TABLE userTbl ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "deleted_at": "ALTER TABLE userTbl ADD COLUMN deleted_at TIMESTAMP NULL DEFAULT NULL",
}


CREATE_FILE_TBL = """
CREATE TABLE IF NOT EXISTS fileTbl (
    file_id INT AUTO_INCREMENT PRIMARY KEY,
    logo VARCHAR(500) NULL,
    site_name VARCHAR(255) NOT NULL,
    python_file_path VARCHAR(255) NOT NULL UNIQUE,
    urls_json TEXT NULL,
    working BIT(1) NOT NULL DEFAULT 0,
    is_deleted BIT(1) NOT NULL DEFAULT 0,
    deleted_at TIMESTAMP NULL DEFAULT NULL,
    created_by INT NULL,
    create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_file_deleted_id (is_deleted, file_id),
    INDEX idx_file_site_name (site_name),
    INDEX idx_file_working (working)
)
"""

NEW_FILE_COLUMNS = {
    "is_deleted": "ALTER TABLE fileTbl ADD COLUMN is_deleted BIT(1) NOT NULL DEFAULT 0",
    "deleted_at": "ALTER TABLE fileTbl ADD COLUMN deleted_at TIMESTAMP NULL DEFAULT NULL",
    "created_by": "ALTER TABLE fileTbl ADD COLUMN created_by INT NULL",
}


CREATE_LOG_TBL = """
CREATE TABLE IF NOT EXISTS logTbl (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id VARCHAR(32) NULL UNIQUE,
    scraper VARCHAR(255) NOT NULL,
    file_id INT NULL,
    user_id INT NOT NULL,
    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP NULL DEFAULT NULL,
    no_of_url_found INT NOT NULL DEFAULT 0,
    total_success_url INT NOT NULL DEFAULT 0,
    total_block_url INT NOT NULL DEFAULT 0,
    data_scraped INT NOT NULL DEFAULT 0,
    total_products INT NOT NULL DEFAULT 0,
    pending_urls INT NOT NULL DEFAULT 0,
    running_urls INT NOT NULL DEFAULT 0,
    completed_urls INT NOT NULL DEFAULT 0,
    blocked_urls INT NOT NULL DEFAULT 0,
    main_url_done INT NOT NULL DEFAULT 0,
    product_url_done INT NOT NULL DEFAULT 0,
    progress_percent FLOAT NOT NULL DEFAULT 0.0,
    status VARCHAR(50) NOT NULL DEFAULT 'RUNNING',
    output_file_path VARCHAR(500) NULL,
    error_message TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    process_id INT NULL,
    INDEX idx_log_user_id (user_id),
    INDEX idx_log_file_id (file_id),
    INDEX idx_log_start_time (start_time),
    INDEX idx_log_file_id_id (file_id, id),
    INDEX idx_log_status_id (status, id),
    INDEX idx_log_user_id_id (user_id, id),
    INDEX idx_log_scraper (scraper)
)
"""

NEW_LOG_COLUMNS = {
    "process_id": "ALTER TABLE logTbl ADD COLUMN process_id INT NULL",
    "job_id": "ALTER TABLE logTbl ADD COLUMN job_id VARCHAR(32) NULL UNIQUE",
    "progress_percent": "ALTER TABLE logTbl ADD COLUMN progress_percent FLOAT NOT NULL DEFAULT 0.0",
    "total_products": "ALTER TABLE logTbl ADD COLUMN total_products INT NOT NULL DEFAULT 0",
    "pending_urls": "ALTER TABLE logTbl ADD COLUMN pending_urls INT NOT NULL DEFAULT 0",
    "completed_urls": "ALTER TABLE logTbl ADD COLUMN completed_urls INT NOT NULL DEFAULT 0",
    "blocked_urls": "ALTER TABLE logTbl ADD COLUMN blocked_urls INT NOT NULL DEFAULT 0",
    "main_url_done": "ALTER TABLE logTbl ADD COLUMN main_url_done INT NOT NULL DEFAULT 0",
    "product_url_done": "ALTER TABLE logTbl ADD COLUMN product_url_done INT NOT NULL DEFAULT 0",
}

CREATE_PAGES_TBL = """
CREATE TABLE IF NOT EXISTS `pages` (
  `id` bigint UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `title` json NOT NULL,
  `slug` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` json DEFAULT NULL,
  `banner_image` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `seo_title` json DEFAULT NULL,
  `meta_description` json DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_by` bigint UNSIGNED DEFAULT NULL,
  `updated_by` bigint UNSIGNED DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted_at` timestamp NULL DEFAULT NULL,
  UNIQUE KEY `uq_pages_slug` (`slug`),
  KEY `idx_pages_is_active` (`is_active`),
  KEY `idx_pages_deleted_at` (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

CREATE_PAGE_SECTIONS_TBL = """
CREATE TABLE IF NOT EXISTS `page_sections` (
  `id` bigint UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `website_id` bigint UNSIGNED DEFAULT NULL,
  `store_id` bigint UNSIGNED DEFAULT NULL,
  `page_slug` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'home',
  `section_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `section_title` json NOT NULL,
  `section_subtitle` json DEFAULT NULL,
  `meta_title` json DEFAULT NULL,
  `meta_description` json DEFAULT NULL,
  `content` json DEFAULT NULL,
  `image` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `image_position` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'right',
  `button_text` json DEFAULT NULL,
  `button_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `section_data` json DEFAULT NULL,
  `sort_order` int NOT NULL DEFAULT 0,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_by` bigint UNSIGNED DEFAULT NULL,
  `updated_by` bigint UNSIGNED DEFAULT NULL,
  `deleted_by` bigint UNSIGNED DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted_at` timestamp NULL DEFAULT NULL,
  KEY `idx_sections_slug` (`page_slug`),
  KEY `idx_sections_active_order` (`page_slug`, `is_active`, `sort_order`),
  KEY `idx_sections_deleted_at` (`deleted_at`),
  KEY `idx_sections_website_id` (`website_id`),
  KEY `idx_sections_store_id` (`store_id`),
  KEY `idx_sections_created_by` (`created_by`),
  KEY `idx_sections_updated_by` (`updated_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

CREATE_BLOGS_TBL = """
CREATE TABLE IF NOT EXISTS `blogs` (
  `id` bigint UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `title` json NOT NULL,
  `slug` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` json NOT NULL,
  `short_description` json DEFAULT NULL,
  `image` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `category_id` bigint UNSIGNED DEFAULT NULL,
  `author_id` bigint UNSIGNED DEFAULT NULL,
  `status` enum('draft','published','archived') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'draft',
  `published_at` timestamp NULL DEFAULT NULL,
  `meta_title` json DEFAULT NULL,
  `meta_desc` json DEFAULT NULL,
  `faqs` json DEFAULT NULL,
  `reviewer_data` json DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted_at` timestamp NULL DEFAULT NULL,
  `created_by` bigint UNSIGNED DEFAULT NULL,
  `updated_by` bigint UNSIGNED DEFAULT NULL,
  `deleted_by` bigint UNSIGNED DEFAULT NULL,
  UNIQUE KEY `blogs_slug_unique` (`slug`),
  KEY `blogs_status_index` (`status`),
  KEY `blogs_published_at_index` (`published_at`),
  KEY `blogs_category_id_index` (`category_id`),
  KEY `blogs_created_by_foreign` (`created_by`),
  KEY `blogs_updated_by_foreign` (`updated_by`),
  KEY `idx_blogs_deleted_at` (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

CREATE_STORELOCATOR_TBL = """
CREATE TABLE IF NOT EXISTS `storelocator` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(255) NOT NULL,
  `name_ar` VARCHAR(255) NULL,
  `status` TINYINT(1) NOT NULL DEFAULT 1,
  `category` VARCHAR(100) NULL,
  `is_mobile_van` TINYINT(1) NOT NULL DEFAULT 0,
  `shipping_amount` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `installer_sort_order` INT NOT NULL DEFAULT 0,
  `skip_days` INT NOT NULL DEFAULT 0,
  `cutoff_time` VARCHAR(50) NULL,
  `skip_hours` VARCHAR(50) NULL,
  `coming_soon` TINYINT(1) NOT NULL DEFAULT 0,
  `opening_hours_one` VARCHAR(255) NULL,
  `opening_hours_two` VARCHAR(255) NULL,
  `longitude` VARCHAR(50) NOT NULL,
  `latitude` VARCHAR(50) NOT NULL,
  `address_ar` VARCHAR(500) NULL,
  `city_ar` VARCHAR(255) NULL,
  `postcode` VARCHAR(50) NULL,
  `country` VARCHAR(100) NOT NULL DEFAULT 'United Arab Emirates',
  `region` VARCHAR(255) NULL,
  `city` VARCHAR(255) NULL,
  `address` VARCHAR(500) NULL,
  `external_link` VARCHAR(500) NULL,
  `phone` VARCHAR(100) NULL,
  `email` VARCHAR(255) NULL,
  `google_map` TEXT NULL,
  `image` VARCHAR(500) NULL,
  `image_1` VARCHAR(500) NULL,
  `image_2` VARCHAR(500) NULL,
  `image_3` VARCHAR(500) NULL,
  `image_4` VARCHAR(500) NULL,
  `image_5` VARCHAR(500) NULL,
  `intro` TEXT NULL,
  `description` LONGTEXT NULL,
  `distance` VARCHAR(100) NULL,
  `nearest_station` VARCHAR(255) NULL,
  `url_key` VARCHAR(255) NULL,
  `store_details_image` VARCHAR(500) NULL,
  `service_included` LONGTEXT NULL,
  `meta_title` VARCHAR(255) NULL,
  `meta_description` TEXT NULL,
  `meta_title_ar` VARCHAR(255) NULL,
  `meta_description_ar` TEXT NULL,
  `store_views` JSON NULL,
  `schedule_json` JSON NULL,
  `is_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted_at` TIMESTAMP NULL DEFAULT NULL,
  KEY `idx_storelocator_status` (`status`),
  KEY `idx_storelocator_city` (`city`),
  KEY `idx_storelocator_url_key` (`url_key`),
  KEY `idx_storelocator_deleted` (`is_deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

NEW_BLOG_COLUMNS = {
    "category_id": "ALTER TABLE blogs ADD COLUMN category_id BIGINT UNSIGNED NULL AFTER image",
    "deleted_by": "ALTER TABLE blogs ADD COLUMN deleted_by BIGINT UNSIGNED NULL AFTER updated_by",
}

NEW_PAGE_SECTION_COLUMNS = {
    "website_id": "ALTER TABLE page_sections ADD COLUMN website_id BIGINT UNSIGNED NULL AFTER id",
    "store_id": "ALTER TABLE page_sections ADD COLUMN store_id BIGINT UNSIGNED NULL AFTER website_id",
    "created_by": "ALTER TABLE page_sections ADD COLUMN created_by BIGINT UNSIGNED NULL AFTER is_active",
    "updated_by": "ALTER TABLE page_sections ADD COLUMN updated_by BIGINT UNSIGNED NULL AFTER created_by",
    "deleted_by": "ALTER TABLE page_sections ADD COLUMN deleted_by BIGINT UNSIGNED NULL AFTER deleted_at",
}

NEW_PAGE_COLUMNS = {
    "deleted_by": "ALTER TABLE pages ADD COLUMN deleted_by BIGINT UNSIGNED NULL AFTER deleted_at",
    "website_id": "ALTER TABLE pages ADD COLUMN website_id BIGINT UNSIGNED NULL AFTER id",
    "store_id": "ALTER TABLE pages ADD COLUMN store_id BIGINT UNSIGNED NULL AFTER website_id",
}

PERFORMANCE_INDEXES = [
    # 0. logTbl & fileTbl
    ("logTbl", "idx_log_file_id_id", "(file_id, id)"),
    ("logTbl", "idx_log_status_id", "(status, id)"),
    ("logTbl", "idx_log_user_id_id", "(user_id, id)"),
    ("logTbl", "idx_log_scraper", "(scraper)"),
    ("fileTbl", "idx_file_deleted_id", "(is_deleted, file_id)"),
    ("fileTbl", "idx_file_site_name", "(site_name)"),
    ("fileTbl", "idx_file_working", "(working)"),

    # 1. stores
    ("stores", "idx_stores_website_id", "(website_id)"),
    ("stores", "idx_stores_code", "(code)"),
    ("stores", "idx_stores_is_active", "(is_active)"),
    ("stores", "idx_stores_deleted_at", "(deleted_at)"),
    ("stores", "idx_stores_emirate", "(emirate)"),
    ("stores", "idx_stores_active_lookup", "(website_id, is_active, deleted_at)"),

    # 2. blog_categories
    ("blog_categories", "idx_blog_cats_slug", "(slug)"),
    ("blog_categories", "idx_blog_cats_deleted_at", "(deleted_at)"),
    ("blog_categories", "idx_blog_cats_sort", "(sort_order, deleted_at)"),

    # 3. blogs
    ("blogs", "idx_blogs_category_status", "(category_id, status, deleted_at)"),
    ("blogs", "idx_blogs_published", "(status, deleted_at, published_at)"),
    ("blogs", "idx_blogs_created_at", "(created_at)"),

    # 4. products
    ("products", "idx_products_sku", "(sku)"),
    ("products", "idx_products_slug", "(slug)"),
    ("products", "idx_products_brand_id", "(brand_id)"),
    ("products", "idx_products_category_id", "(category_id)"),
    ("products", "idx_products_status", "(status)"),
    ("products", "idx_products_visibility", "(visibility)"),
    ("products", "idx_products_deleted_at", "(deleted_at)"),
    ("products", "idx_products_tire_size", "(tire_size_label)"),
    ("products", "idx_products_price", "(price)"),
    ("products", "idx_products_active_catalog", "(status, visibility, deleted_at, brand_id)"),

    # 5. categories
    ("categories", "idx_categories_slug", "(slug)"),
    ("categories", "idx_categories_parent_id", "(parent_id)"),
    ("categories", "idx_categories_status", "(status)"),
    ("categories", "idx_categories_deleted_at", "(deleted_at)"),
    ("categories", "idx_categories_sort", "(sort_order, status, deleted_at)"),

    # 6. brands
    ("brands", "idx_brands_slug", "(slug)"),
    ("brands", "idx_brands_status", "(status)"),
    ("brands", "idx_brands_is_featured", "(is_featured)"),
    ("brands", "idx_brands_deleted_at", "(deleted_at)"),

    # 7. enquiries
    ("enquiries", "idx_enquiries_email", "(email)"),
    ("enquiries", "idx_enquiries_phone", "(phone)"),
    ("enquiries", "idx_enquiries_status", "(status)"),
    ("enquiries", "idx_enquiries_form_type", "(form_type)"),
    ("enquiries", "idx_enquiries_store_id", "(store_id)"),
    ("enquiries", "idx_enquiries_created_at", "(created_at)"),
    ("enquiries", "idx_enquiries_deleted_at", "(deleted_at)"),

    # 8. hdweb_enquiry
    ("hdweb_enquiry", "idx_hdweb_email", "(email)"),
    ("hdweb_enquiry", "idx_hdweb_status", "(status)"),
    ("hdweb_enquiry", "idx_hdweb_created_at", "(created_at)"),
    ("hdweb_enquiry", "idx_hdweb_form_type", "(form_type)"),

    # 9. orders
    ("orders", "idx_orders_order_number", "(order_number)"),
    ("orders", "idx_orders_user_id", "(user_id)"),
    ("orders", "idx_orders_status", "(status)"),
    ("orders", "idx_orders_payment_status", "(payment_status)"),
    ("orders", "idx_orders_website_id", "(website_id)"),
    ("orders", "idx_orders_store_id", "(store_id)"),
    ("orders", "idx_orders_created_at", "(created_at)"),
    ("orders", "idx_orders_deleted_at", "(deleted_at)"),

    # 10. order_items
    ("order_items", "idx_order_items_order_id", "(order_id)"),
    ("order_items", "idx_order_items_product_id", "(product_id)"),
    ("order_items", "idx_order_items_sku", "(sku)"),

    # 11. carts
    ("carts", "idx_carts_session_id", "(session_id)"),
    ("carts", "idx_carts_user_id", "(user_id)"),
    ("carts", "idx_carts_expires_at", "(expires_at)"),
    ("carts", "idx_carts_deleted_at", "(deleted_at)"),

    # 12. cart_items
    ("cart_items", "idx_cart_items_cart_id", "(cart_id)"),
    ("cart_items", "idx_cart_items_product_id", "(product_id)"),

    # 13. users
    ("users", "idx_users_email", "(email)"),
    ("users", "idx_users_phone", "(phone)"),
    ("users", "idx_users_status", "(status)"),
    ("users", "idx_users_customer_group_id", "(customer_group_id)"),
    ("users", "idx_users_deleted_at", "(deleted_at)"),
    ("users", "idx_users_created_at", "(created_at)"),

    # 14. vehicles
    ("vehicles", "idx_vehicles_make", "(make)"),
    ("vehicles", "idx_vehicles_model", "(model)"),
    ("vehicles", "idx_vehicles_active", "(active)"),
    ("vehicles", "idx_vehicles_front_tire", "(front_tire_size)"),
    ("vehicles", "idx_vehicles_rear_tire", "(rear_tire_size)"),
    ("vehicles", "idx_vehicles_deleted_at", "(deleted_at)"),

    # 15. makes
    ("makes", "idx_makes_slug", "(make_slug)"),
    ("makes", "idx_makes_status", "(status)"),
    ("makes", "idx_makes_deleted_at", "(deleted_at)"),

    # 16. models
    ("models", "idx_models_make_id", "(make_id)"),
    ("models", "idx_models_slug", "(model_slug)"),
    ("models", "idx_models_deleted_at", "(deleted_at)"),

    # 17. banners
    ("banners", "idx_banners_position", "(position)"),
    ("banners", "idx_banners_is_active", "(is_active)"),
    ("banners", "idx_banners_sort", "(sort_order, is_active)"),
    ("banners", "idx_banners_deleted_at", "(deleted_at)"),

    # 18. faqs
    ("faqs", "idx_faqs_is_active", "(is_active)"),
    ("faqs", "idx_faqs_sort", "(sort_order, is_active)"),
    ("faqs", "idx_faqs_deleted_at", "(deleted_at)"),

    # 19. admin_users
    ("admin_users", "idx_admin_users_role", "(role)"),
    ("admin_users", "idx_admin_users_active", "(is_active)"),
    ("admin_users", "idx_admin_users_deleted", "(is_deleted, deleted_at)"),

    # 20. coupons
    ("coupons", "idx_coupons_code", "(code)"),
    ("coupons", "idx_coupons_active", "(is_active)"),
    ("coupons", "idx_coupons_dates", "(starts_at, expires_at)"),
    ("coupons", "idx_coupons_deleted_at", "(deleted_at)"),

    # 21. newsletter_subscribers
    ("newsletter_subscribers", "idx_newsletter_email", "(email)"),
    ("newsletter_subscribers", "idx_newsletter_status", "(status)"),
    ("newsletter_subscribers", "idx_newsletter_deleted_at", "(deleted_at)"),

    # 22. password_reset_tokens
    ("password_reset_tokens", "idx_reset_token", "(token)"),
    ("password_reset_tokens", "idx_reset_email", "(email)"),
    ("password_reset_tokens", "idx_reset_created_at", "(created_at)"),
]


def add_missing_columns(cursor):
    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'userTbl'"
    )
    existing_user = {row["COLUMN_NAME"] for row in cursor.fetchall()}
    for column, statement in NEW_USER_COLUMNS.items():
        if column not in existing_user:
            cursor.execute(statement)

    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'fileTbl'"
    )
    existing_file = {row["COLUMN_NAME"] for row in cursor.fetchall()}
    for column, statement in NEW_FILE_COLUMNS.items():
        if column not in existing_file:
            cursor.execute(statement)

    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'logTbl'"
    )
    existing_log = {row["COLUMN_NAME"] for row in cursor.fetchall()}
    for column, statement in NEW_LOG_COLUMNS.items():
        if column not in existing_log:
            try:
                cursor.execute(statement)
            except Exception:
                pass

    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'blogs'"
    )
    existing_blogs = {row["COLUMN_NAME"] for row in cursor.fetchall()}
    for column, statement in NEW_BLOG_COLUMNS.items():
        if column not in existing_blogs:
            try:
                cursor.execute(statement)
            except Exception:
                pass

    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'page_sections'"
    )
    existing_sections = {row["COLUMN_NAME"] for row in cursor.fetchall()}
    for column, statement in NEW_PAGE_SECTION_COLUMNS.items():
        if column not in existing_sections:
            try:
                cursor.execute(statement)
            except Exception:
                pass

    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pages'"
    )
    existing_pages = {row["COLUMN_NAME"] for row in cursor.fetchall()}
    for column, statement in NEW_PAGE_COLUMNS.items():
        if column not in existing_pages:
            try:
                cursor.execute(statement)
            except Exception:
                pass


def add_missing_indexes(cursor):
    """Ensures high-performance database indexes exist across all core tables."""
    for table, index_name, cols in PERFORMANCE_INDEXES:
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt 
            FROM information_schema.STATISTICS 
            WHERE TABLE_SCHEMA = DATABASE() 
              AND TABLE_NAME = %s 
              AND INDEX_NAME = %s
            """,
            (table, index_name),
        )
        if cursor.fetchone()["cnt"] == 0:
            try:
                cursor.execute(f"CREATE INDEX {index_name} ON {table} {cols}")
            except Exception:
                pass


def cleanup_deprecated_tables(cursor):
    """Drops deprecated tables and triggers per user requirement."""
    cursor.execute("DROP TRIGGER IF EXISTS before_scraper_job_insert")
    cursor.execute("DROP TRIGGER IF EXISTS after_scraper_job_update")
    cursor.execute("DROP TABLE IF EXISTS password_reset_tbl")
    cursor.execute("DROP TABLE IF EXISTS scraper_job_locks")
    cursor.execute("DROP TABLE IF EXISTS scraper_jobs")
    cursor.execute("DROP TABLE IF EXISTS scraperReportTbl")


def update_legacy_stopped_logs(cursor):
    """Backfills legacy logs where scraper was stopped by user to status='STOPPED'."""
    cursor.execute(
        """
        UPDATE logTbl 
        SET status = 'STOPPED' 
        WHERE status != 'STOPPED' 
          AND (
            LOWER(error_message) LIKE '%stopped by user%' 
            OR LOWER(error_message) LIKE '%status: stopped%'
            OR status = 'STOP'
          )
        """
    )


def seed_default_about_us_sections(cursor):
    """Populates default predefined sections for about-us if empty."""
    import json
    cursor.execute("SELECT COUNT(*) as cnt FROM page_sections WHERE page_slug = 'about-us' AND deleted_at IS NULL")
    if cursor.fetchone()["cnt"] > 0:
        return

    default_sections = [
        (
            "about-us",
            "hero",
            json.dumps({"en": "Driven by Confidence,\nBuilt for the Road.", "ar": "مدفوعون بالثقة،\nمصممون للطريق."}, ensure_ascii=False),
            json.dumps({"en": "ABOUT US", "ar": "من نحن"}, ensure_ascii=False),
            json.dumps({"en": "At TyresVision, we deliver premium tyres that combine cutting-edge technology, superior performance, and lasting reliability. Because every journey deserves confidence.", "ar": "في تايرز فيجن، نقدم إطارات فائقة الجودة تجمع بين أحدث التقنيات والأداء المتميز والاعتمادية الدائمة. لأن كل رحلة تستحق قيادة واثقة وآمنة."}, ensure_ascii=False),
            "/static/assets/about/hero-tyre-showroom.jpg",
            "right",
            json.dumps({"en": "Our Journey →", "ar": "استكشف مسيرتنا ←"}, ensure_ascii=False),
            "#our-story",
            json.dumps({
                "features": [
                    {"icon": "shield-check", "title": {"en": "Premium Quality", "ar": "جودة ممتازة"}, "sub": {"en": "Trusted brands and superior quality.", "ar": "علامات تجارية موثوقة وجودة فائقة."}},
                    {"icon": "dollar-sign", "title": {"en": "Best Prices", "ar": "أفضل الأسعار"}, "sub": {"en": "Competitive prices every day.", "ar": "أسعار تنافسية وشفافة كل يوم."}},
                    {"icon": "truck", "title": {"en": "Fast Delivery", "ar": "توصيل سريع"}, "sub": {"en": "Quick and reliable delivery.", "ar": "توصيل وتركيب سريع وموثوق."}},
                    {"icon": "headset", "title": {"en": "Expert Support", "ar": "دعم الخبراء"}, "sub": {"en": "We're here to help you anytime.", "ar": "نحن هنا لمساعدتك في أي وقت."}}
                ]
            }, ensure_ascii=False),
            1,
            1
        ),
        (
            "about-us",
            "content_image",
            json.dumps({"en": "The Road That Started Our Journey.", "ar": "الطريق الذي بدأ منه مشوارنا."}, ensure_ascii=False),
            json.dumps({"en": "OUR STORY", "ar": "قصتنا"}, ensure_ascii=False),
            json.dumps({"en": "TyresVision was built with a simple mission — to make high-quality tyres accessible to everyone. What started as a small idea is today a trusted name for thousands of customers.\n\nWe partner with world-class brands, use advanced technology, and maintain rigorous quality standards to ensure you get the best performance, every single time.\n\nFrom city streets to highway adventures, we're here to keep you moving forward with confidence.", "ar": "أُنشئت تايرز فيجن بمهمة واضحة وبسيطة — توفير إطارات سيارات عالية الجودة بأسعار عادلة ومتاحة للجميع. ما بدأ كفكرة رقمية مبتكرة أصبح اليوم اسماً موثوقاً لآلاف السائقين في دولة الإمارات.\n\nنتعاون مع كبرى الشركات المصنعة العالمية، ونستخدم أحدث التقنيات لضمان معايير جودة صارمة تمنحك الأداء الأفضل في كل مرة تنطلق فيها على الطريق.\n\nمن شوارع المدينة إلى الطرق السريعة الطويلة، نحن هنا لنضمن استمرار رحلتك بكل أمان وثقة."}, ensure_ascii=False),
            "/static/assets/about/warehouse-tyres.jpg",
            "left",
            json.dumps({"en": "Learn More About Us →", "ar": "تعرف أكثر على قصتنا ←"}, ensure_ascii=False),
            "/#why",
            json.dumps({
                "badge_title": {"en": "Customer First", "ar": "العميل أولاً"},
                "badge_sub": {"en": "Your safety and satisfaction are our priority.", "ar": "سلامتك ورضاك هما أولويتنا القصوى."},
                "badge_icon": "users"
            }, ensure_ascii=False),
            2,
            1
        ),
        (
            "about-us",
            "features",
            json.dumps({"en": "What Drives Us Forward", "ar": "ما يدفعنا دوماً إلى الأمام"}, ensure_ascii=False),
            json.dumps({"en": "OUR VALUES", "ar": "قيمنا ومبادئنا"}, ensure_ascii=False),
            json.dumps({"en": "Our values guide everything we do and help us build lasting relationships with our customers.", "ar": "ترشدنا قيمنا في كل خطوة نبني بها علاقات طويلة الأمد مع عملائنا وشركائنا."}, ensure_ascii=False),
            None,
            "right",
            None,
            None,
            json.dumps({
                "cards": [
                    {"icon": "shield", "title": {"en": "Integrity", "ar": "النزاهة والصدق"}, "desc": {"en": "Honest business practices and transparent relationships.", "ar": "ممارسات تجارية نزيهة وعلاقات واضحة وشفافة."}},
                    {"icon": "award", "title": {"en": "Quality", "ar": "أعلى معايير الجودة"}, "desc": {"en": "We never compromise on the quality of products and services.", "ar": "لا نساوم أبداً على جودة الإطارات والخدمات المقدمة."}},
                    {"icon": "heart", "title": {"en": "Customer Focus", "ar": "التركيز على العميل"}, "desc": {"en": "Your needs inspire us to deliver better every single day.", "ar": "احتياجاتك تلهمنا لتقديم خدمة أسرع وأفضل كل يوم."}},
                    {"icon": "zap", "title": {"en": "Innovation", "ar": "الابتكار المستمر"}, "desc": {"en": "Constantly improving through technology and smarter solutions.", "ar": "تطوير مستمر من خلال الحلول الرقمية والتقنيات الذكية."}},
                    {"icon": "globe", "title": {"en": "Sustainability", "ar": "الاستدامة والمسؤولية"}, "desc": {"en": "Responsible choices for a better tomorrow.", "ar": "خيارات مسؤولة وحلول بيئية لمستقبل أفضل."}}
                ]
            }, ensure_ascii=False),
            3,
            1
        ),
        (
            "about-us",
            "stats",
            json.dumps({"en": "Our Numbers Speak", "ar": "أرقامنا تتحدث"}, ensure_ascii=False),
            json.dumps({"en": "STATISTICS", "ar": "الإحصائيات"}, ensure_ascii=False),
            None,
            None,
            "right",
            None,
            None,
            json.dumps({
                "metrics": [
                    {"icon": "users", "number": "50K+", "heading": {"en": "Happy Customers", "ar": "عميل سعيد وموثوق"}, "subtext": {"en": "Trusted by drivers across the country.", "ar": "موثوق من آلاف السائقين عبر الدولة."}},
                    {"icon": "disc", "number": "20K+", "heading": {"en": "Tyres Sold", "ar": "إطار تم تركيبه"}, "subtext": {"en": "A wide range of tyres for every need.", "ar": "تشكيلة ضخمة تغطي كافة الاحتياجات."}},
                    {"icon": "globe", "number": "100+", "heading": {"en": "Top Brands", "ar": "علامة تجارية رائدة"}, "subtext": {"en": "Offering the world's most trusted tyre brands.", "ar": "نقدم أشهر الماركات العالمية المعتمدة."}},
                    {"icon": "award", "number": "10+", "heading": {"en": "Years of Experience", "ar": "سنوات من الخبرة"}, "subtext": {"en": "Decade of expertise in tyre industry.", "ar": "عقد من التميز والاحترافية في قطاع الإطارات."}}
                ]
            }, ensure_ascii=False),
            4,
            1
        ),
        (
            "about-us",
            "mission_vision",
            json.dumps({"en": "People Behind Our Performance", "ar": "الكوادر وراء تميز أدائنا"}, ensure_ascii=False),
            json.dumps({"en": "OUR TEAM", "ar": "فريق العمل"}, ensure_ascii=False),
            json.dumps({"en": "Our team is made up of passionate professionals who live and breathe automotive excellence.\n\nFrom product experts to customer support, we work together to ensure you get the best experience with every interaction.", "ar": "يتكون فريقنا من محترفين شغوفين يعيشون ويتنفسون التميز في عالم السيارات وخدمات الإطارات.\n\nمن خبراء المنتجات والمقاسات إلى مهندسي خدمة العملاء وفنيي التركيب المتنقل، نعمل معاً لضمان حصولك على أفضل تجربة مع كل تواصل."}, ensure_ascii=False),
            "/static/assets/about/team-specialists.jpg",
            "right",
            json.dumps({"en": "Meet Our Team →", "ar": "تعرف على فريقنا ←"}, ensure_ascii=False),
            "https://wa.me/971505069575?text=Hi%20TyresVision%20Team",
            json.dumps({}, ensure_ascii=False),
            5,
            1
        ),
        (
            "about-us",
            "features",
            json.dumps({"en": "Committed to Quality. Committed to You.", "ar": "ملتزمون بالجودة. ملتزمون برضاك."}, ensure_ascii=False),
            json.dumps({"en": "OUR COMMITMENT", "ar": "التزامنا الدائم"}, ensure_ascii=False),
            json.dumps({"en": "We are committed to providing premium quality tyres, exceptional service, and honest advice. Your trust is what drives us to keep raising the bar.", "ar": "نحن ملتزمون بتقديم إطارات سيارات فائقة الجودة، وخدمة استثنائية، ومشورة صادقة. ثقتكم هي دافعنا الدائم للارتقاء بالمعايير."}, ensure_ascii=False),
            None,
            "right",
            None,
            None,
            json.dumps({
                "cards": [
                    {"icon": "shield-check", "title": {"en": "Safe & Reliable", "ar": "أمان واعتمادية"}, "desc": {"en": "Tyres you can count on for every journey.", "ar": "إطارات يمكنك الاعتماد عليها في كل رحلة."}},
                    {"icon": "award", "title": {"en": "Tested & Trusted", "ar": "مختبرة وموثوقة"}, "desc": {"en": "Every product meets strict quality standards.", "ar": "كل منتج يطابق أعلى معايير الجودة الصارمة."}},
                    {"icon": "headset", "title": {"en": "Always Here", "ar": "دائماً بجانبك"}, "desc": {"en": "Support you can rely on, whenever you need.", "ar": "دعم يمكنك الاعتماد عليه كلما احتجت."}},
                    {"icon": "users", "title": {"en": "Long-Term Partnership", "ar": "شراكة طويلة الأمد"}, "desc": {"en": "Building relationships beyond just business.", "ar": "نبني علاقات ثقة تتجاوز مجرد المعاملات التجارية."}}
                ]
            }, ensure_ascii=False),
            6,
            1
        ),
        (
            "about-us",
            "cta",
            json.dumps({"en": "Let's Move Forward Together.", "ar": "دعنا ننطلق معاً إلى الأمام."}, ensure_ascii=False),
            json.dumps({"en": "GET STARTED", "ar": "ابدأ الآن"}, ensure_ascii=False),
            json.dumps({"en": "Explore our range of premium tyres and experience the difference with TyresVision.", "ar": "استكشف مجموعتنا من الإطارات الممتازة وجرّب الفارق مع تايرز فيجن."}, ensure_ascii=False),
            "/static/assets/about/wheel-rim.png",
            "left",
            json.dumps({"en": "Contact Us Today →", "ar": "تواصل معنا اليوم ←"}, ensure_ascii=False),
            "https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20would%20like%20to%20contact%20you%20today.",
            json.dumps({}, ensure_ascii=False),
            7,
            1
        )
    ]

    sql = """
        INSERT INTO page_sections (
            page_slug, section_type, section_title, section_subtitle,
            content, image, image_position, button_text, button_url,
            section_data, sort_order, is_active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    for sec in default_sections:
        cursor.execute(sql, sec)


def seed_default_home_sections(cursor):
    """Seed the default 9 home page sections if none exist."""
    cursor.execute("SELECT COUNT(*) as cnt FROM page_sections WHERE page_slug = 'home' AND deleted_at IS NULL")
    res = cursor.fetchone()
    cnt = res['cnt'] if isinstance(res, dict) else res[0]
    if cnt > 0:
        return

    home_sections = [
        (
            "home",
            "hero",
            json.dumps({"en": "Buy tyres online.\n<em>Fitted locally</em> across the UAE.", "ar": "اشترِ الإطارات عبر الإنترنت.\n<em>تركيب محلي</em> في جميع أنحاء الإمارات."}, ensure_ascii=False),
            json.dumps({"en": "Dubai · Abu Dhabi · Sharjah · Ajman", "ar": "دبي · أبوظبي · الشارقة · عجمان"}, ensure_ascii=False),
            json.dumps({"en": "TyresVision is an online tyre shop for the UAE. Genuine, date-fresh tyres from 60+ brands at the lowest prices — delivered free to a fitting centre near you, or fitted at your home or office by our mobile vans.", "ar": "تايرز فيجن هو متجر إطارات إلكتروني رائد في الإمارات. إطارات أصلية وتواريخ إنتاج حديثة من أكثر من 60 علامة تجارية بأقل الأسعار — توصيل مجاني إلى مركز تركيب قريب منك، أو تركيب متنقل عند باب منزلك أو مكتبك."}, ensure_ascii=False),
            None,
            "right",
            json.dumps({"en": "WhatsApp for a quote", "ar": "اطلب عرض سعر عبر واتساب"}, ensure_ascii=False),
            "https://wa.me/971505069575?text=Hi%20Online%20Tyres%20Shop%2C%20I%27d%20like%20a%20tyre%20quote.",
            json.dumps({
                "phone": "+971505069575",
                "phone_display": "+971 50 506 9575",
                "badges": [
                    {"icon": "dollar", "text": {"en": "Lowest price guaranteed", "ar": "أقل سعر مضمون"}},
                    {"icon": "shield", "text": {"en": "Warranty on eligible tyres", "ar": "ضمان على الإطارات المؤهلة"}},
                    {"icon": "truck", "text": {"en": "Free delivery to fitter", "ar": "توصيل مجاني لمركز التركيب"}}
                ]
            }, ensure_ascii=False),
            1,
            1
        ),
        (
            "home",
            "stats",
            json.dumps({"en": "Key Numbers", "ar": "أرقامنا المميزة"}, ensure_ascii=False),
            None,
            None,
            None,
            "right",
            None,
            None,
            json.dumps({
                "metrics": [
                    {"number": "60+", "label": {"en": "Tyre brands", "ar": "علامة تجارية للإطارات"}, "icon": "brand"},
                    {"number": "7,000+", "label": {"en": "Products in stock", "ar": "منتج متوفر في المخزون"}, "icon": "tyre"},
                    {"number": "25+", "label": {"en": "Fitting locations", "ar": "موقع تركيب معتمد"}, "icon": "globe"},
                    {"number": "10+", "label": {"en": "Mobile Van Fitting", "ar": "فانات تركيب متنقلة"}, "icon": "truck"}
                ]
            }, ensure_ascii=False),
            2,
            1
        ),
        (
            "home",
            "features",
            json.dumps({"en": "Everything a tyre shop should be — without the runaround", "ar": "كل ما يجب أن يقدمه متجر الإطارات — بدون تعقيدات"}, ensure_ascii=False),
            json.dumps({"en": "Why TyresVision?", "ar": "لماذا تايرز فيجن؟"}, ensure_ascii=False),
            json.dumps({"en": "No haggling, no upselling, no waiting around. Pick your tyres, pick where you want them fitted, and get on with your day.", "ar": "لا مساومة، لا بيع عشوائي، لا انتظار. اختر إطاراتك، وحدد موقع التركيب، وتابع يومك براحة تامة."}, ensure_ascii=False),
            None,
            "right",
            None,
            None,
            json.dumps({
                "cards": [
                    {
                        "icon": "shield",
                        "title": {"en": "Genuine tyres only", "ar": "إطارات أصلية 100%"},
                        "description": {"en": "Sourced through authorised channels with manufacturer-backed warranty on eligible tyres. Fresh manufacturing dates — never old stock.", "ar": "مستوردة عبر القنوات الرسمية المعتمدة مع ضمان الشركة المصنعة على الإطارات المؤهلة. تواريخ إنتاج حديثة — خالية تماماً من المخزون القديم."}
                    },
                    {
                        "icon": "dollar",
                        "title": {"en": "Lowest price, guaranteed", "ar": "أفضل وأقل سعر مضمون"},
                        "description": {"en": "Found the same tyre cheaper elsewhere in the UAE? Send us the quote on WhatsApp and we’ll match or beat it.", "ar": "هل وجدت نفس الإطار بسعر أرخص في الإمارات؟ أرسل لنا عرض السعر على واتساب وسنطابقه أو نمنحك سعراً أفضل."}
                    },
                    {
                        "icon": "truck",
                        "title": {"en": "We come to you", "ar": "نصل إليك أينما كنت"},
                        "description": {"en": "Mobile fitting vans across the UAE will change your tyres at home, at the office, or in the mall car park while you’re inside.", "ar": "فانات التركيب المتنقل في جميع أنحاء الإمارات تقوم بتبديل إطاراتك في المنزل، في المكتب، أو في مواقف المول أثناء تسوقك."}
                    },
                    {
                        "icon": "clock",
                        "title": {"en": "Fast turnaround", "ar": "سرعة استجابة وتركيب فوري"},
                        "description": {"en": "Most popular sizes are in stock and ready to go, so fitting can usually be arranged within the same day across Dubai and Sharjah.", "ar": "معظم المقاسات الشائعة متوفرة في المخزون وجاهزة، مما يتيح ترتيب التركيب في نفس اليوم عبر دبي والشارقة."}
                    },
                    {
                        "icon": "award",
                        "title": {"en": "Warranty handled for you", "ar": "إدارة الضمان بالكامل"},
                        "description": {"en": "Every purchase is logged against your vehicle, so warranty questions and claims come to us — no chasing the manufacturer yourself.", "ar": "يتم تسجيل كل عملية شراء برقم مركبتك، لنتولى نحن كافة إجراءات ومطالبات الضمان نيابة عنك."}
                    },
                    {
                        "icon": "zap",
                        "title": {"en": "Built for UAE roads", "ar": "مصممة لطرقات الإمارات"},
                        "description": {"en": "Advice tuned to Gulf heat and long highway runs — the right compound and load rating for how you actually drive.", "ar": "نصائح وإطارات ملائمة لحرارة الخليج والطرق السريعة — المركب المناسب ومعدل الحمولة المتوافق مع قيادتك."}
                    }
                ],
                "cta_row": {
                    "wa_text": {"en": "Chat on WhatsApp", "ar": "تحدث معنا عبر واتساب"},
                    "wa_url": "https://wa.me/971505069575?text=Hi%20Online%20Tyres%20Shop%2C%20I%27d%20like%20a%20tyre%20quote.",
                    "call_text": {"en": "Call +971 50 506 9575", "ar": "اتصل بنا: 9575 506 50 971+"},
                    "call_url": "tel:+971505069575"
                }
            }, ensure_ascii=False),
            3,
            1
        ),
        (
            "home",
            "price_table",
            json.dumps({"en": "Tyre Prices in Dubai and Abu Dhabi", "ar": "أسعار الإطارات في دبي وأبوظبي"}, ensure_ascii=False),
            json.dumps({"en": "TYRE PRICES", "ar": "أسعار الإطارات"}, ensure_ascii=False),
            json.dumps({"en": "Starting prices for the sizes UAE drivers buy most, fitted at a partner centre — delivery, mounting, balancing, valves and old-tyre disposal all included. Send your size on WhatsApp for an exact price on your vehicle.", "ar": "أسعار تبدأ للمقاسات الأكثر طلباً في الإمارات، مع التركيب في مركز شريك — يشمل التوصيل، التركيب، الترصيص، البلوف والتخلص من الإطارات القديمة. أرسل مقاس إطارك عبر واتساب للحصول على السعر الدقيق لسيارتك."}, ensure_ascii=False),
            None,
            "right",
            json.dumps({"en": "Send Size on WhatsApp", "ar": "أرسل المقاس عبر واتساب"}, ensure_ascii=False),
            "https://wa.me/971505065575?text=Hi%20TyresVision%2C%20I%27d%20like%20a%20price%20for%20my%20tyre%20size.",
            json.dumps({
                "value_cards": [
                    {
                        "icon": "truck",
                        "title": {"en": "FREE Delivery", "ar": "توصيل مجاني"},
                        "subtitle": {"en": "Across Dubai & Abu Dhabi", "ar": "في دبي وأبوظبي"}
                    },
                    {
                        "icon": "tool",
                        "title": {"en": "Fitting Included", "ar": "التركيب مشمول"},
                        "subtitle": {"en": "Mounting, Balancing & Valves", "ar": "فك وتركيب وترصيص وبلوف"}
                    },
                    {
                        "icon": "recycle",
                        "title": {"en": "Old Tyre Disposal", "ar": "التخلص من الإطارات القديمة"},
                        "subtitle": {"en": "Eco-friendly & included", "ar": "صديق للبيئة ومجاني"}
                    },
                    {
                        "icon": "shield",
                        "title": {"en": "Warranty Covered", "ar": "ضمان شامل"},
                        "subtitle": {"en": "Genuine products only", "ar": "منتجات أصلية 100%"}
                    }
                ],
                "rows": [
                    {
                        "size": "195/65 R15",
                        "common_on": {"en": "Corolla, Sunny, Elantra", "ar": "كورولا، صني، إلنترا"},
                        "budget": "AED —",
                        "mid_range": "AED —",
                        "premium": "AED —"
                    },
                    {
                        "size": "205/55 R16",
                        "common_on": {"en": "Civic, Jetta, Cerato", "ar": "سيفيك، جيتا، سيراتو"},
                        "budget": "AED —",
                        "mid_range": "AED —",
                        "premium": "AED —"
                    },
                    {
                        "size": "215/60 R17",
                        "common_on": {"en": "Camry, Accord, Sonata", "ar": "كامري، أكورد، سوناتا"},
                        "budget": "AED —",
                        "mid_range": "AED —",
                        "premium": "AED —"
                    },
                    {
                        "size": "225/65 R17",
                        "common_on": {"en": "RAV4, Tucson, Sportage", "ar": "راف 4، توسان، سبورتاج"},
                        "budget": "AED —",
                        "mid_range": "AED —",
                        "premium": "AED —"
                    },
                    {
                        "size": "235/55 R19",
                        "common_on": {"en": "Explorer, Edge, XC60", "ar": "إكسبلورر، إيدج، إكس سي 60"},
                        "budget": "AED —",
                        "mid_range": "AED —",
                        "premium": "AED —"
                    },
                    {
                        "size": "265/65 R17",
                        "common_on": {"en": "Prado, Fortuner, Hilux", "ar": "برادو، فورتشنر، هايلوكس"},
                        "budget": "AED —",
                        "mid_range": "AED —",
                        "premium": "AED —"
                    },
                    {
                        "size": "275/60 R20",
                        "common_on": {"en": "Land Cruiser, Tahoe", "ar": "لاندكروزر، تاهو"},
                        "budget": "AED —",
                        "mid_range": "AED —",
                        "premium": "AED —"
                    },
                    {
                        "size": "285/50 R20",
                        "common_on": {"en": "Patrol, Armada", "ar": "باترول، أرمادا"},
                        "budget": "AED —",
                        "mid_range": "AED —",
                        "premium": "AED —"
                    },
                    {
                        "size": "275/45 R20",
                        "common_on": {"en": "Range Rover, X5, GLE", "ar": "رينج روفر، إكس 5، جي إل إي"},
                        "budget": "AED —",
                        "mid_range": "AED —",
                        "premium": "AED —"
                    },
                    {
                        "size": "255/45 R19",
                        "common_on": {"en": "Tesla Model Y, EQC", "ar": "تسلا موديل واي، إي كيو سي"},
                        "budget": "AED —",
                        "mid_range": "AED —",
                        "premium": "AED —"
                    }
                ],
                "small_print": {
                    "en": "Prices are per tyre, fitted at a partner centre. Mobile van fitting at your own location is available for an additional call-out fee, confirmed before we dispatch. Updated September 2026. Stock and pricing change — WhatsApp for today’s price.",
                    "ar": "الأسعار للإطار الواحد مع التركيب في مركز شريك. تتوفر خدمة التركيب المتنقل عند موقعك مقابل رسوم إضافية يتم تأكيدها قبل التحرك. تم التحديث سبتمبر 2026. الأسعار والمخزون يتغيران — راسلنا عبر واتساب لمعرفة سعر اليوم."
                },
                "call_button": {
                    "text": "+971 50 506 5575",
                    "url": "tel:+971505065575"
                },
                "trust_text": {
                    "en": "Partner centres near you • Expert fitting",
                    "ar": "مراكز شركاء قريبة منك • تركيب احترافي"
                }
            }, ensure_ascii=False),
            4,
            1
        ),
        (
            "home",
            "services",
            json.dumps({"en": "More than tyres", "ar": "أكثر من مجرد إطارات"}, ensure_ascii=False),
            json.dumps({"en": "Full car care", "ar": "عناية متكاملة بسيارتك"}, ensure_ascii=False),
            json.dumps({"en": "Book any of these alongside your tyre fitting and save a second trip.", "ar": "احجز أي من هذه الخدمات الإضافية مع تركيب الإطارات ووفر على نفسك وقتاً وزيارة إضافية."}, ensure_ascii=False),
            None,
            "right",
            None,
            None,
            json.dumps({
                "services": [
                    {"name": {"en": "Tyre fitting", "ar": "تركيب الإطارات"}},
                    {"name": {"en": "Wheel alignment", "ar": "ميزان الإطارات (محاذاة)"}},
                    {"name": {"en": "Wheel balancing", "ar": "ترصيص العجلات"}},
                    {"name": {"en": "Tyre rotation", "ar": "تدوير الإطارات"}},
                    {"name": {"en": "Nitrogen fill", "ar": "تعبئة غاز النيتروجين"}},
                    {"name": {"en": "Car batteries", "ar": "بطاريات السيارات"}},
                    {"name": {"en": "Oil change", "ar": "تغيير الزيت والفلاتر"}},
                    {"name": {"en": "AC repair", "ar": "صيانة وتعبئة مكيف السيارة"}},
                    {"name": {"en": "Service & repair", "ar": "الصيانة الميكانيكية العامة"}},
                    {"name": {"en": "Car spa & detailing", "ar": "تلميع وتنظيف شامل (سبا)"}},
                    {"name": {"en": "Window tinting", "ar": "تظليل وتعتيم النوافذ"}},
                    {"name": {"en": "Car recovery", "ar": "خدمة ونش وسطحة الإنقاذ"}},
                    {"name": {"en": "Car insurance", "ar": "تأمين المركبات"}},
                    {"name": {"en": "Puncture repair", "ar": "إصلاح البنشر والثقوب"}},
                    {"name": {"en": "Fleet servicing", "ar": "خدمة وصيانة أساطيل الشركات"}},
                    {"name": {"en": "Mobile van visit", "ar": "زيارة الفان المتنقل"}}
                ]
            }, ensure_ascii=False),
            5,
            1
        ),
        (
            "home",
            "how_it_works",
            json.dumps({"en": "Four steps, one afternoon", "ar": "أربع خطوات بسيطة في وقت قياسي"}, ensure_ascii=False),
            json.dumps({"en": "How it works", "ar": "كيف تعمل الخدمة"}, ensure_ascii=False),
            None,
            None,
            "right",
            None,
            None,
            json.dumps({
                "steps": [
                    {
                        "step_number": 1,
                        "icon": "phone",
                        "title": {"en": "Send your size", "ar": "أرسل مقاس إطارك"},
                        "description": {"en": "WhatsApp us the numbers on your tyre sidewall, or just your car model and year.", "ar": "راسلنا على واتساب بالأرقام المكتوبة على جدار إطارك أو فقط موديل وسنة سيارتك."}
                    },
                    {
                        "step_number": 2,
                        "icon": "dollar",
                        "title": {"en": "Get options & prices", "ar": "استلم الخيارات والأسعار"},
                        "description": {"en": "We reply with best-value, mid-range and premium options — all in stock.", "ar": "نرد عليك بأفضل الخيارات الاقتصادية، المتوسطة، والممتازة — جميعها متوفرة فوراً."}
                    },
                    {
                        "step_number": 3,
                        "icon": "globe",
                        "title": {"en": "Pick your fitter", "ar": "اختر طريقة ومكان التركيب"},
                        "description": {"en": "Choose a centre near you, or book a mobile van to your address.", "ar": "اختر مركز تركيب معتمد قريب منك، أو اطلب فان الخدمة المتنقلة لعندك."}
                    },
                    {
                        "step_number": 4,
                        "icon": "truck",
                        "title": {"en": "Drive away", "ar": "انطلق بأمان"},
                        "description": {"en": "Fitting, balancing and disposal of the old tyres are handled. Warranty is logged for you.", "ar": "يتم إنجاز التركيب، الترصيص، والتخلص من الإطارات القديمة، مع تسجيل الضمان رسمياً."}
                    }
                ],
                "cta_row": {
                    "wa_text": {"en": "Start on WhatsApp", "ar": "ابدأ الآن عبر واتساب"},
                    "wa_url": "https://wa.me/971505069575?text=Hi%20Online%20Tyres%20Shop%2C%20I%27d%20like%20a%20tyre%20quote.",
                    "call_text": {"en": "Prefer to talk? Call us", "ar": "تفضل الاتصال؟ اتصل بنا مباشرة"},
                    "call_url": "tel:+971505069575"
                }
            }, ensure_ascii=False),
            6,
            1
        ),
        (
            "home",
            "shop_by",
            json.dumps({"en": "Find Your Tyres by Size, Vehicle or Brand"}, ensure_ascii=False),
            json.dumps({"en": "Shop by Size, Vehicle or Brand"}, ensure_ascii=False),
            json.dumps({"en": "Not sure what fits? Tap your size or your car below and we’ll come back with options and prices on WhatsApp."}, ensure_ascii=False),
            None,
            "right",
            None,
            None,
            json.dumps({
                "groups": [
                    {
                        "heading": "Popular tyre sizes in the UAE",
                        "type": "size",
                        "chips": [
                            "195/65 R15", "205/55 R16", "215/55 R17", "215/60 R17", "225/45 R17",
                            "225/65 R17", "235/55 R19", "235/60 R18", "245/45 R18", "245/70 R16",
                            "255/50 R20", "265/50 R20", "265/65 R17", "275/40 R20", "275/45 R20",
                            "275/60 R20", "285/50 R20", "285/60 R18", "305/40 R22"
                        ]
                    },
                    {
                        "heading": "Tyres by vehicle",
                        "type": "vehicle",
                        "chips": [
                            "Toyota Land Cruiser", "Nissan Patrol", "Toyota Prado", "Toyota Corolla",
                            "Toyota Camry", "Nissan Sunny", "Honda Civic", "Hyundai Elantra",
                            "Mitsubishi Pajero", "Ford Explorer", "Chevrolet Tahoe", "Kia Sportage",
                            "Range Rover", "Toyota Hilux", "Tesla Model 3 & Model Y", "Mercedes G-Class"
                        ]
                    },
                    {
                        "heading": "Tyres by brand — Premium",
                        "type": "brand",
                        "tier": "premium",
                        "chips": [
                            "Michelin", "Bridgestone", "Continental", "Pirelli", "Goodyear", "Dunlop"
                        ]
                    },
                    {
                        "heading": "Tyres by brand — Mid-range",
                        "type": "brand",
                        "tier": "mid-range",
                        "chips": [
                            "Hankook", "Yokohama", "Toyo", "Falken", "Kumho", "Nexen", "BFGoodrich",
                            "Cooper", "Nitto", "Vredestein"
                        ]
                    },
                    {
                        "heading": "Tyres by brand — Value",
                        "type": "brand",
                        "tier": "value",
                        "chips": [
                            "Laufenn", "Giti", "Sumitomo", "Zeetex", "Roadstone", "and 40+ more"
                        ]
                    }
                ]
            }, ensure_ascii=False),
            7,
            1
        ),
        (
            "home",
            "coverage",
            json.dumps({"en": "Delivery and Fitting Across Dubai and Abu Dhabi"}, ensure_ascii=False),
            json.dumps({"en": "Delivery & Fitting Coverage"}, ensure_ascii=False),
            json.dumps({"en": "Free delivery and free fitting at any of our 25+ partner centres across Dubai and Abu Dhabi. Prefer not to leave home? Our mobile vans come to you for a call-out fee, confirmed on WhatsApp before we dispatch. Not sure if we reach you? Send a location pin and we’ll confirm in a minute."}, ensure_ascii=False),
            None,
            "right",
            None,
            None,
            json.dumps({
                "options": [
                    {
                        "tag": "FREE Delivery & Fitting",
                        "heading": "Free fitting at a partner centre",
                        "description": "Choose any centre on our network and we deliver your tyres there free of charge. Fitting, balancing, new valves and disposal of your old tyres are all included at no extra cost — the price we quote on WhatsApp is the price you pay.",
                        "button_text": "Book at Partner Centre",
                        "wa_msg": "Hi TyresVision, I'd like to book free tyre fitting at a partner centre."
                    },
                    {
                        "tag": "Mobile Van Service",
                        "heading": "Mobile van fitting at your location — call-out fee applies",
                        "description": "Our fully equipped vans fit your tyres at your villa, apartment car park, office bay or roadside. The van service carries a call-out fee on top of the tyre price, which we always confirm before dispatch so there are no surprises. Mounting, balancing, valves and old-tyre disposal are included in the job.",
                        "button_text": "Book Mobile Van",
                        "wa_msg": "Hi TyresVision, I'd like to book mobile van fitting at my location."
                    }
                ],
                "areas": [
                    {
                        "heading": "Dubai coverage",
                        "emirate": "Dubai",
                        "chips": [
                            "Dubai Marina", "JLT", "JBR", "Palm Jumeirah", "Business Bay", "Downtown", "DIFC",
                            "Al Barsha", "Barsha Heights", "Jumeirah", "Umm Suqeim", "Al Quoz", "Deira", "Bur Dubai",
                            "Al Nahda", "Mirdif", "Al Qusais", "Silicon Oasis", "Dubai Hills", "Arabian Ranches",
                            "JVC", "Motor City", "Al Furjan", "Jebel Ali", "Dubai South", "Nad Al Sheba",
                            "Al Warqa", "Umm Ramool", "Festival City"
                        ]
                    },
                    {
                        "heading": "Abu Dhabi coverage",
                        "emirate": "Abu Dhabi",
                        "chips": [
                            "Corniche", "Al Khalidiyah", "Al Bateen", "Al Mushrif", "Al Nahyan", "Al Zahiyah",
                            "Al Reem Island", "Al Maryah Island", "Saadiyat Island", "Yas Island", "Khalifa City A & B",
                            "Al Raha Beach", "Mohammed Bin Zayed City", "Shakhbout City", "Al Shamkha", "Al Falah",
                            "Masdar City", "Musaffah", "ICAD", "Baniyas", "Between the Two Bridges"
                        ]
                    },
                    {
                        "heading": "Sharjah, Ajman and the Northern Emirates",
                        "emirate": "Northern Emirates",
                        "chips": [
                            "Al Nahda", "Al Majaz", "Al Khan", "Muwaileh", "Al Taawun", "Ajman",
                            "Umm Al Quwain", "Ras Al Khaimah", "Fujairah"
                        ]
                    }
                ]
            }, ensure_ascii=False),
            8,
            1
        ),
        (
            "home",
            "advice",
            json.dumps({"en": "How to Choose the Right Tyres in the UAE", "ar": "كيف تختار الإطارات المناسبة لسيارتك في الإمارات"}, ensure_ascii=False),
            json.dumps({"en": "Expert Tyre Advice", "ar": "نصائح وإرشادات الخبراء"}, ensure_ascii=False),
            json.dumps({"en": "Practical advice from UAE tyre specialists to help you choose the right tyre compound, rating and brand for our climate — without overpaying.", "ar": "إرشادات عملية من خبراء إطارات الإمارات لمساعدتك في اختيار التركيبة والتصنيف الأنسب لمناخنا دون دفع مبالغ إضافية غير ضرورية."}, ensure_ascii=False),
            None,
            "right",
            None,
            None,
            json.dumps({
                "cards": [
                    {
                        "icon": "clock",
                        "title": {
                            "en": "Check the manufacturing date, not just the tread",
                            "ar": "تحقق من تاريخ الصنع، وليس فقط عمق النقشة"
                        },
                        "description": {
                            "en": "The last four digits of the DOT code on the sidewall are the week and year of manufacture, so 1226 means week 12 of 2026. UAE heat ages rubber faster than tread wears down, so a tyre made three years ago is already partway through its life before you fit it. Always ask for the date code.",
                            "ar": "آخر أربعة أرقام من رمز DOT على جدار الإطار تشير إلى أسبوع وسنة الصنع (مثلاً 1226 تعني الأسبوع 12 من سنة 2026). حرارة الإمارات تؤدي لتقادم المطاط بسرعة حتى لو كان المداس سليماً. اطلب دائماً رمز تاريخ الصنع."
                        }
                    },
                    {
                        "icon": "shield",
                        "title": {
                            "en": "Match the load and speed rating to your car",
                            "ar": "طابق مؤشر الحمولة والسرعة مع مواصفات سيارتك"
                        },
                        "description": {
                            "en": "The 105W after your tyre size is the load index and speed rating. Fitting a lower rating to save money is the most common and most dangerous saving people make in this market, especially on heavy SUVs carrying a full family down the E11.",
                            "ar": "الرمز مثل 105W بعد مقاس الإطار هو مؤشر الحمولة ومعدل السرعة. اختيار تصنيف أقل لتوفير المال هو الخيار الأكثر خطورة في سوقنا، خاصة لسيارات الدفع الرباعي الثقيلة أثناء القيادة على الطرق السريعة مثل شارع الشيخ زايد E11."
                        }
                    },
                    {
                        "icon": "dollar",
                        "title": {
                            "en": "Premium isn’t always right, budget isn’t always wrong",
                            "ar": "الفئة الفاخرة ليست دائماً الأنسب، والاقتصادية ليست خاطئة دائماً"
                        },
                        "description": {
                            "en": "If you cover 30,000 km a year on the highway, premium compounds pay for themselves in wear and braking distance. If you do 8,000 km of city driving, a good mid-range tyre is the smarter buy. We’ll tell you honestly which one you are.",
                            "ar": "إذا كنت تقطع 30,000 كم سنوياً على الطرق السريعة، فإن الإطارات الفاخرة تستحق قيمتها في استدامة التآكل ومسافة الكبح. أما إذا كنت تقطع 8,000 كم داخل المدينة، فالإطار المتوسط هو الخيار الأذكى. سنخبرك بكل أمانة بالخيار الأنسب لك."
                        }
                    },
                    {
                        "icon": "zap",
                        "title": {
                            "en": "How UAE heat changes the maths",
                            "ar": "كيف تغير حرارة صيف الإمارات المعادلة"
                        },
                        "description": {
                            "en": "Sustained 45–50 °C tarmac means heat resistance matters more here than it does in Europe. Look for tyres rated for high ambient temperatures, and don’t choose on tread pattern alone.",
                            "ar": "تصل حرارة الإسفلت إلى 45-50 درجة مئوية، مما يجعل مقاومة الحرارة أهم بكثير مما هي عليه في أوروبا. ابحث دائماً عن إطارات مصممة لدرجات الحرارة المحيطة العالية ولا تكتفِ بالنظر إلى شكل النقشة فقط."
                        }
                    },
                    {
                        "icon": "award",
                        "title": {
                            "en": "When to replace your tyres",
                            "ar": "متى يجب تبديل إطاراتك"
                        },
                        "description": {
                            "en": "Replace at the 1.6 mm legal minimum, or sooner if you see sidewall cracking, bulges or uneven wear. Most UAE drivers should replace at 3–5 years regardless of how much tread is left.",
                            "ar": "استبدل الإطار عند وصول عمق المداس إلى الحد القانوني الأدنى 1.6 مم، أو قبل ذلك في حال ظهور تشققات في الجدار الجانبي أو انتفاخات أو تآكل غير منتظم. يُنصح معظم سائقي الإمارات باستبدال الإطارات كل 3 إلى 5 سنوات بغض النظر عن عمق المداس المتبقي."
                        }
                    },
                    {
                        "icon": "truck",
                        "title": {
                            "en": "What a “fully fitted” price should include",
                            "ar": "ما الذي يجب أن يشمله السعر \"الشامل للتركيب\""
                        },
                        "description": {
                            "en": "A real fitted price covers delivery, mounting, balancing, new valves and disposal of the old tyres. If a quote doesn’t say so, ask — that is where the surprise charges live.",
                            "ar": "السعر الحقيقي الشامل للتركيب يغطي التوصيل، التركيب، الترصيص، بلوف جديدة، والتخلص من الإطارات القديمة. إذا كان العرض لا يذكر ذلك صراحة، اسأل عنه — فهناك تكمن الرسوم المخفية غير المتوقعة."
                        }
                    }
                ]
            }, ensure_ascii=False),
            9,
            1
        ),
        (
            "home",
            "brands",
            json.dumps({"en": "The names you trust, the prices you don’t expect", "ar": "العلامات التي تثق بها، بالأسعار التي لا تتوقعها"}, ensure_ascii=False),
            json.dumps({"en": "60+ brands in stock", "ar": "+60 علامة تجارية في المخزون"}, ensure_ascii=False),
            None,
            None,
            "right",
            None,
            None,
            json.dumps({
                "brands": [
                    "Michelin", "Bridgestone", "Goodyear", "Continental", "Pirelli", "Dunlop",
                    "Hankook", "Yokohama", "Toyo", "Falken", "Nexen", "Kumho",
                    "BFGoodrich", "Cooper", "Nitto", "Vredestein", "Giti", "Laufenn",
                    "Sumitomo", "Zeetex", "+40 more"
                ]
            }, ensure_ascii=False),
            10,
            1
        ),
        (
            "home",
            "testimonials",
            json.dumps({"en": "What UAE drivers say", "ar": "ماذا يقول سائقو الإمارات"}, ensure_ascii=False),
            json.dumps({"en": "Customer reviews", "ar": "تقييمات وآراء العملاء"}, ensure_ascii=False),
            None,
            None,
            "right",
            None,
            None,
            json.dumps({
                "reviews": [
                    {
                        "rating": 5,
                        "quote": {
                            "en": "Sent my tyre size in the morning, had a price back in minutes and the car was done the same afternoon.",
                            "ar": "أرسلت مقاس إطاري صباحاً، وتلقيت السعر في دقائق وتم تركيب الإطارات في نفس بعد الظهر."
                        },
                        "author": {"en": "Verified customer", "ar": "عميل موثوق"},
                        "location": {"en": "Dubai", "ar": "دبي"}
                    },
                    {
                        "rating": 5,
                        "quote": {
                            "en": "Straight answers, no upselling, and the price was better than the two shops I’d already called.",
                            "ar": "إجابات واضحة ومباشرة بدون محاولات بيع إضافي، وكان السعر أفضل بكثير من المحلين اللذين اتصلت بهما مسبقاً."
                        },
                        "author": {"en": "Verified customer", "ar": "عميل موثوق"},
                        "location": {"en": "Sharjah", "ar": "الشارقة"}
                    },
                    {
                        "rating": 5,
                        "quote": {
                            "en": "The mobile van came to my building’s car park. I didn’t have to take time off work at all.",
                            "ar": "وصل الفان المتنقل إلى موقف بنايتي. لم أضطر لأخذ إجازة أو مغادرة العمل على الإطلاق."
                        },
                        "author": {"en": "Verified customer", "ar": "عميل موثوق"},
                        "location": {"en": "Abu Dhabi", "ar": "أبوظبي"}
                    }
                ]
            }, ensure_ascii=False),
            11,
            1
        ),
        (
            "home",
            "faq",
            json.dumps({"en": "Good to know", "ar": "معلومات تهمك"}, ensure_ascii=False),
            json.dumps({"en": "Questions", "ar": "الأسئلة الشائعة"}, ensure_ascii=False),
            None,
            None,
            "right",
            None,
            None,
            json.dumps({
                "faqs": [
                    {
                        "question": {"en": "How do I buy tyres online from TyresVision?"},
                        "answer": {"en": "Send your tyre size on WhatsApp and we reply within minutes with three in-stock options — budget, mid-range and premium — each with the fitted price. Choose one, tell us whether you want it fitted at a partner centre or at your own location, and pay when the job is done. No account, no card details online."}
                    },
                    {
                        "question": {"en": "How much do tyres cost in Dubai and Abu Dhabi?"},
                        "answer": {"en": "It depends on your size and brand tier. A common sedan size like 205/55 R16 costs less than a large SUV size like 285/50 R20, and budget, mid-range and premium differ within the same size. See our price table above, and WhatsApp your exact size for today’s price."}
                    },
                    {
                        "question": {"en": "Is fitting included in the price?"},
                        "answer": {"en": "Fitting at one of our partner centres is free and included, along with delivery, mounting, balancing, new valves and disposal of your old tyres. Mobile fitting at your own location is charged as a call-out fee on top of the tyre price, always confirmed on WhatsApp before we dispatch a van."}
                    },
                    {
                        "question": {"en": "Do you really match other tyre prices?"},
                        "answer": {"en": "Yes. Find the same tyre — same brand, size and manufacturing year — cheaper anywhere in the UAE and send us a screenshot on WhatsApp. We’ll match it or beat it. Compare fitted prices, because many quotes look cheaper until fitting and balancing get added at the counter."}
                    },
                    {
                        "question": {"en": "How do I find my tyre size?"},
                        "answer": {"en": "It’s moulded into the sidewall and looks like <strong>235/55 R19 105W</strong>. 235 is the width in mm, 55 is the sidewall height as a percentage of that width, R19 is the wheel diameter in inches, and 105W is the load index and speed rating. Send a photo on WhatsApp, or just your car’s make, model and year."}
                    },
                    {
                        "question": {"en": "Are your tyres new and date-fresh?"},
                        "answer": {"en": "Yes. Every tyre is brand new from authorised UAE channels with a recent DOT date code that we show you before fitting. The last four digits are the week and year — 1226 means week 12 of 2026. This matters more here than in cooler countries, because heat degrades rubber long before tread wears out."}
                    },
                    {
                        "question": {"en": "Can I get tyres delivered and fitted the same day?"},
                        "answer": {"en": "Usually yes. Most popular UAE sizes are in stock, so message before 12 PM and we can normally fit the same day across Dubai and Abu Dhabi. Rarer sizes may need 24–48 hours — we’ll tell you honestly which yours is when we quote."}
                    },
                    {
                        "question": {"en": "Do you deliver to Abu Dhabi as well as Dubai?"},
                        "answer": {"en": "Yes. We deliver free to partner centres across both emirates, and our mobile vans cover most of Abu Dhabi including Al Reem Island, Khalifa City, Yas Island, Mohammed Bin Zayed City and Musaffah, alongside full Dubai coverage. Send a location pin and we’ll confirm immediately."}
                    },
                    {
                        "question": {"en": "Can you fit tyres at my home or office?"},
                        "answer": {"en": "Yes, for a call-out fee confirmed before we dispatch. Our vans fit tyres in villa driveways, apartment car parks, office bays and mall parking across Dubai and Abu Dhabi. We need a safe, level spot with room to work beside the car. Tell us if your building has height limits or access approval."}
                    },
                    {
                        "question": {"en": "How long does tyre fitting take?"},
                        "answer": {"en": "A set of four takes about 30–40 minutes at your location once the technician arrives, including balancing and a final torque check. At a partner centre, allow around 45–60 minutes including waiting. A single tyre is usually around 15 minutes."}
                    },
                    {
                        "question": {"en": "Which tyre brand is best for UAE heat?"},
                        "answer": {"en": "There’s no single answer. Premium makers like Michelin, Bridgestone, Continental and Pirelli hold up best on sustained high-temperature tarmac and long highway runs. For city driving, mid-range brands like Hankook, Yokohama and Falken give most of the performance for less. Tell us how you drive and we’ll advise honestly."}
                    },
                    {
                        "question": {"en": "Do you sell tyres for SUVs and 4x4s?"},
                        "answer": {"en": "Yes, and SUV and 4x4 sizes are the biggest part of what we sell. We stock the common Land Cruiser, Patrol, Prado, Pajero, Explorer and Tahoe fitments in highway, all-terrain and mud-terrain patterns. Tell us whether you stay on tarmac or actually drive in sand."}
                    },
                    {
                        "question": {"en": "Do you have EV and run-flat tyres?"},
                        "answer": {"en": "Yes to both. EVs are heavier and need a higher load rating plus low rolling resistance to protect range, so we match to the OE specification rather than just the size — Tesla Model 3 and Model Y sizes are stocked. Run-flats need the right equipment; our vans carry it."}
                    },
                    {
                        "question": {"en": "What happens to my old tyres?"},
                        "answer": {"en": "We take them away and dispose of them through licensed recycling channels at no extra charge. It’s included in every fitted price, whether at a centre or at your location."}
                    },
                    {
                        "question": {"en": "Can you supply tyres to a company fleet?"},
                        "answer": {"en": "Yes. We offer fleet pricing, consolidated monthly invoicing and scheduled on-site visits so your vehicles never leave the yard. Cars, pickups and light commercials across Dubai and Abu Dhabi. Message us on WhatsApp and ask for the fleet desk."}
                    },
                    {
                        "question": {"en": "How do I pay for my tyres?"},
                        "answer": {"en": "Cash, card or bank transfer on completion. There’s no online checkout and no deposit — you confirm the price on WhatsApp, we do the job, you pay when it’s finished."}
                    }
                ]
            }, ensure_ascii=False),
            12,
            1
        ),
        (
            "home",
            "cta",
            json.dumps({"en": "Ready for a fresh set of tyres?", "ar": "هل أنت مستعد لتبديل إطاراتك بأحدث الموديلات؟"}, ensure_ascii=False),
            None,
            json.dumps({"en": "Send your tyre size on WhatsApp for a price in minutes — or call and we’ll sort it out on the phone.", "ar": "أرسل مقاس إطاراتك عبر واتساب للحصول على أفضل سعر في دقائق — أو اتصل بنا وسنرتب كل شيء عبر الهاتف."}, ensure_ascii=False),
            None,
            "right",
            json.dumps({"en": "WhatsApp us", "ar": "راسلنا على واتساب"}, ensure_ascii=False),
            "https://wa.me/971505069575?text=Hi%20Online%20Tyres%20Shop%2C%20I%27d%20like%20a%20tyre%20quote.",
            json.dumps({
                "call_button_text": {"en": "Call +971 50 506 9575", "ar": "اتصل بنا: 9575 506 50 971+"},
                "call_button_url": "tel:+971505069575",
                "footer_note": {
                    "en": "Open daily — call or message any time and we’ll come back to you fast.",
                    "ar": "مفتوح يومياً — اتصل أو راسلنا في أي وقت وسنرد عليك بسرعة فائقة."
                }
            }, ensure_ascii=False),
            13,
            1
        )
    ]

    sql = """
        INSERT INTO page_sections (
            page_slug, section_type, section_title, section_subtitle,
            content, image, image_position, button_text, button_url,
            section_data, sort_order, is_active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    for sec in home_sections:
        cursor.execute(sql, sec)


def main():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(CREATE_ADMIN_USERS_TBL)
            cursor.execute(CREATE_PASSWORD_RESET_TOKENS_TBL)
            cursor.execute(CREATE_USER_TBL)
            cursor.execute(CREATE_FILE_TBL)
            cursor.execute(CREATE_LOG_TBL)
            cursor.execute(CREATE_PAGES_TBL)
            cursor.execute(CREATE_PAGE_SECTIONS_TBL)
            cursor.execute(CREATE_BLOGS_TBL)
            cursor.execute(CREATE_STORELOCATOR_TBL)
            add_missing_columns(cursor)
            cleanup_deprecated_tables(cursor)
            add_missing_indexes(cursor)
            update_legacy_stopped_logs(cursor)
            seed_default_about_us_sections(cursor)
            seed_default_home_sections(cursor)
        conn.commit()
        print("Schema verified: admin_users, password_reset_tokens, fileTbl, logTbl, pages, page_sections, blogs are ready.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
