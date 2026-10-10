# VisionAdmin Section Builder — Master Guide & Architectural Evolution Plan

> **Unified Master File**: `builder.md`  
> **Scope**: Complete Section Catalog, Database Schema, Field Specifications, AND the Zero-Code Composable Block Engine Plan.

---

## Complete Table of Contents

### PART I: Current Section Builder Architecture & Catalog
1. [Overview & System Architecture](#1-overview--system-architecture)
2. [Database Schema (`page_sections`)](#2-database-schema-page_sections)
3. [REST API Endpoints](#3-rest-api-endpoints)
4. [Global Section Fields (All Types)](#4-global-section-fields-all-types)
5. [Complete Catalog of All 15 Section Types & Input Fields](#5-complete-catalog-of-all-15-section-types--input-fields)
   - [5.1 Hero Banner (`hero`)](#51-hero-banner-hero)
   - [5.2 Statistics Grid (`stats`)](#52-statistics-grid-stats)
   - [5.3 Why / Features Grid (`features`)](#53-why--features-grid-features)
   - [5.4 Tyre Price Table (`price_table`)](#54-tyre-price-table-price_table)
   - [5.5 Car Care Services (`services`)](#55-car-care-services-services)
   - [5.6 How It Works 4-Step Process (`how_it_works`)](#56-how-it-works-4-step-process-how_it_works)
   - [5.7 Shop by Size, Vehicle & Brand (`shop_by`)](#57-shop-by-size-vehicle--brand-shop_by)
   - [5.8 Delivery & Fitting Coverage (`coverage`)](#58-delivery--fitting-coverage-coverage)
   - [5.9 Tyre Buying Advice (`advice`)](#59-tyre-buying-advice-advice)
   - [5.10 Brands List (`brands`)](#510-brands-list-brands)
   - [5.11 Customer Reviews (`testimonials`)](#511-customer-reviews-testimonials)
   - [5.12 FAQ Accordion (`faq`)](#512-faq-accordion-faq)
   - [5.13 Final CTA Action Box (`cta`)](#513-final-cta-action-box-cta)
   - [5.14 Content + Image 2-Column (`content_image`)](#514-content--image-2-column-content_image)
   - [5.15 Mission & Team (`mission_vision`)](#515-mission--team-mission_vision)
6. [Supported Icons Library](#6-supported-icons-library)
7. [Current Storefront Template Dispatch Architecture](#7-current-storefront-template-dispatch-architecture)
8. [Admin Operations Guide](#8-admin-operations-guide)

### PART II: The Composable Block Engine Solution & Implementation Plan
9. [Problem Analysis & The User's Real-World Case Study](#9-problem-analysis--the-users-real-world-case-study)
   - [9.1 The Core Bottlenecks](#91-the-core-bottlenecks)
   - [9.2 Concrete User Case Study: Metric inside Car Services](#92-concrete-user-case-study-metric-inside-car-services)
10. [The Architectural Solution: Composable Block Engine](#10-the-architectural-solution-composable-block-engine)
11. [The 10 Universal Atomic Building Blocks](#11-the-10-universal-atomic-building-blocks)
12. [Universal Data Structure (`section_data.blocks`)](#12-universal-data-structure-section_datablocks)
13. [Storefront Universal Block Dispatcher Architecture](#13-storefront-universal-block-dispatcher-architecture)
14. [VisionAdmin Composable Interface UI Design](#14-visionadmin-composable-interface-ui-design)
15. [Phased Step-by-Step Implementation Roadmap](#15-phased-step-by-step-implementation-roadmap)
16. [Summary of Business & Technical Benefits](#16-summary-of-business--technical-benefits)

---

## 1. Overview & System Architecture

The **Section Builder** enables administrators to compose, customize, reorder, and translate modular page sections across any page of the TyresVision website (e.g. `home`, `about-us`, `privacy-policy`, `terms-conditions`) without modifying Python or Jinja template code.

- **Admin Interface**: `/visionadmin/sections`
- **Controller & Views**:
  - Backend: `app/visionadmin/Visionadminroute.py`
  - Frontend Template: `templates/visionadmin/sections.html`
  - Client Controller JS: `static/visionadmin/sections.js`
  - Public Renderer: `templates/Client/Home.html` & `templates/Client/About.html`
- **Multilingual**: All text, headings, and descriptions provide dual **English (EN)** and **Arabic (AR)** input fields.
- **Rich Text**: Long descriptions and body content support full HTML formatting via **CKEditor**.

---

## 2. Database Schema (`page_sections`)

All sections are stored in the MySQL table `page_sections`.

| Column Name | Data Type | Nullable | Description |
|---|---|---|---|
| `id` | `INT AUTO_INCREMENT` | No | Primary Key |
| `page_slug` | `VARCHAR(100)` | No | Target page identifier (`home`, `about-us`, etc.) |
| `section_type` | `VARCHAR(50)` | No | Layout identifier (`hero`, `features`, `coverage`, etc.) |
| `section_title` | `JSON` | Yes | Title in EN & AR: `{"en": "...", "ar": "..."}` |
| `section_subtitle` | `JSON` | Yes | Eyebrow / badge in EN & AR: `{"en": "...", "ar": "..."}` |
| `meta_title` | `JSON` | Yes | Section-specific SEO title in EN & AR |
| `meta_description`| `JSON` | Yes | Section-specific SEO description snippet in EN & AR |
| `content` | `JSON` | Yes | Rich text HTML / prose description in EN & AR |
| `image` | `VARCHAR(255)` | Yes | Relative or absolute visual URL (e.g. `/static/assets/...`) |
| `image_position` | `ENUM('left','right')`| No | Image side on 2-column sections (default: `right`) |
| `button_text` | `JSON` | Yes | CTA button text in EN & AR: `{"en": "...", "ar": "..."}` |
| `button_url` | `VARCHAR(255)` | Yes | Target link URL or anchor (`https://wa.me/...`, `/#why`, etc.) |
| `section_data` | `JSON` | Yes | Type-specific structured arrays (cards, chips, FAQs, etc.) |
| `sort_order` | `INT` | No | Display sequence on the page (lowest = topmost) |
| `is_active` | `TINYINT(1)` | No | Visibility toggle: `1` = published, `0` = draft/hidden |
| `created_at` | `TIMESTAMP` | No | Record creation timestamp |
| `updated_at` | `TIMESTAMP` | Yes | Last edit timestamp |
| `deleted_at` | `TIMESTAMP` | Yes | Soft-delete timestamp (`NULL` if active) |

---

## 3. REST API Endpoints

All Section Builder operations interact with the VisionAdmin REST API:

- `GET /visionadmin/api/sections?page=<slug>`  
  Fetch all active sections for a specific page, ordered by `sort_order ASC`.
- `POST /visionadmin/api/sections`  
  Create a new page section. Returns the newly created section JSON.
- `PUT /visionadmin/api/sections/<id>`  
  Update an existing section by ID.
- `DELETE /visionadmin/api/sections/<id>`  
  Soft-delete a section (`deleted_at = NOW()`).
- `POST /visionadmin/api/sections/reorder`  
  Payload: `{"order": [{"id": 6, "sort_order": 1}, {"id": 8, "sort_order": 2}]}`.

---

## 4. Global Section Fields (All Types)

Every section edit modal includes the following standard top-level fields:

| Field Name | Input ID | UI Element | Description / Valid Values |
|---|---|---|---|
| **Target Page Slug** | `form-page-slug` | Text Input (mono) | Page identifier, e.g. `home`, `about-us`. |
| **Section Layout** | `section_type` | Radio Cards | The layout preset (1 of the 15 types below). |
| **Language Tabs** | `tab-en`, `tab-ar` | Tab Switcher | Toggles between English and Arabic input fields. |
| **Subtitle / Eyebrow** | `form-subtitle-en`, `form-subtitle-ar` | Text Input | Upper small category label (e.g. `EXPERT ADVICE`). |
| **Title / Headline** | `form-title-en`, `form-title-ar` | Text Input | Main `<h2>` or `<h1>` heading. |
| **Meta Title** | `form-meta-title-en`, `form-meta-title-ar` | Text Input | Optional SEO heading override. |
| **Meta Description** | `form-meta-desc-en`, `form-meta-desc-ar` | Text Input | Optional SEO search snippet. |
| **Section Description** | `form-content-en`, `form-content-ar` | CKEditor / Textarea | Lead paragraph or rich text HTML body. |
| **Section Image** | `form-image-url` | Text Input + File Upload | Image URL path or upload button. |
| **Image Alignment** | `image_position` | Radio (`left` / `right`) | Positions image on left or right in 2-column layouts. |
| **Button Text** | `form-btn-text-en`, `form-btn-text-ar` | Text Input | CTA label (e.g. `WhatsApp us`). |
| **Button URL** | `form-btn-url` | Text Input | Destination link (e.g. `https://wa.me/971505069575`). |
| **Sort Order** | `form-sort-order` | Number Input (1–99) | Numerical ordering on the page. |
| **Enable Section** | `form-is-active` | Checkbox Toggle | When checked, section renders on the live storefront. |

---

## 5. Complete Catalog of All 15 Section Types & Input Fields

### 5.1 Hero Banner (`hero`)
- **Emoji / Badge**: 🦸 `Hero Banner`
- **Storefront Output**: Full-width atmospheric dark gradient banner with quote card, quick-search, trust metrics, and primary WhatsApp / Call action buttons.
- **Top-Level Fields Used**:
  - `section_title`: Main hero headline (e.g. *"Buy Tyres Online in Dubai & Abu Dhabi"*).
  - `section_subtitle`: Eyebrow tag above headline.
  - `content`: Lead introductory sentence.
  - `button_text`: Primary action label (e.g. *"WhatsApp your tyre size"*).
  - `button_url`: WhatsApp deep link prefilled with quote message.
- **Repeater Schema (`section_data.badges`)**:
  ```json
  {
    "badges": [
      {
        "icon": "shield",
        "title": { "en": "100% Genuine Tyres", "ar": "إطارات أصلية 100%" }
      },
      {
        "icon": "truck",
        "title": { "en": " Fitting & Delivery", "ar": "توصيل وتركيب مجاني" }
      },
      {
        "icon": "clock",
        "title": { "en": "Same-Day Van Service", "ar": "خدمة فان في نفس اليوم" }
      }
    ]
  }
  ```

---

### 5.2 Statistics Grid (`stats`)
- **Emoji / Badge**: 📊 `Statistics Grid`
- **Storefront Output**: Compact 4-column counter strip highlighting high-credibility metrics.
- **Top-Level Fields Used**: `section_title`, `section_subtitle`.
- **Repeater Items (`section_data.metrics`)**:
  - **Metric Number**: Value string with symbols (e.g. `60+`, `10,000+`, `25+`, `30 min`).
  - **Label (English)**: Metric caption (e.g. `Tyre brands in stock`).
  - **Label (Arabic)**: Metric caption in Arabic (e.g. `علامة تجارية متوفرة`).
- **Repeater Schema**:
  ```json
  {
    "metrics": [
      { "number": "60+", "label": { "en": "Tyre brands in stock", "ar": "علامة تجارية متوفرة" } },
      { "number": "10,000+", "label": { "en": "Tyres fitted across UAE", "ar": "إطار تم تركيبه في الإمارات" } },
      { "number": "25+", "label": { "en": "Partner fitting centres", "ar": "مركز شريك معتمد" } },
      { "number": "30 min", "label": { "en": "Average mobile fitting", "ar": "متوسط وقت التركيب المتنقل" } }
    ]
  }
  ```

---

### 5.3 Why / Features Grid (`features`)
- **Emoji / Badge**: ✨ `Why / Features`
- **Storefront Output**: 3-column responsive card grid (6 value proposition cards) with green accent icons and bottom WhatsApp CTA.
- **Top-Level Fields Used**: `section_title`, `section_subtitle`, `content`, `button_text`, `button_url`.
- **Repeater Items (`section_data.cards`)**:
  - **Icon**: Dropdown (`shield`, `dollar`, `truck`, `clock`, `award`, `zap`, etc.).
  - **Title (English & Arabic)**: Card title (e.g. `Genuine tyres only`).
  - **Description (English & Arabic)**: Detailed explanation paragraph.
- **Repeater Schema**:
  ```json
  {
    "cards": [
      {
        "icon": "shield",
        "title": { "en": "Genuine tyres only", "ar": "إطارات أصلية مضمونة" },
        "description": { "en": "Every tyre is 100% authentic, sourced through authorized UAE distributors with manufacturer warranty.", "ar": "جميع الإطارات أصلية 100% ومستوردة عبر الوكلاء الرسميين مع الضمان." }
      },
      {
        "icon": "dollar",
        "title": { "en": "Best price guarantee", "ar": "ضمان أفضل سعر" },
        "description": { "en": "Show us a valid lower quote and we match or beat it on the spot.", "ar": "أظهر لنا أي عرض سعر أقل وسنطابقه أو نقدم سعراً أفضل فوراً." }
      }
    ]
  }
  ```

---

### 5.4 Tyre Price Table (`price_table`)
- **Emoji / Badge**: 💰 `Tyre Price Table`
- **Storefront Output**: Comprehensive pricing matrix by popular tyre sizes and vehicles, showing Budget, Mid-Range, and Premium price starting tiers + 4 value guarantee cards.
- **Top-Level Fields Used**: `section_title`, `section_subtitle`, `content`.
- **Repeater Items (`section_data.rows`)**:
  - **Tyre Size**: Width/Aspect/Rim (e.g. `195/65 R15`, `205/55 R16`, `265/65 R17`).
  - **Common On (EN / AR)**: Vehicle examples (e.g. `Corolla, Sunny, Civic` / `كورولا، صني، سيفيك`).
  - **Budget From**: Starting price (e.g. `AED 165`).
  - **Mid-Range From**: Starting price (e.g. `AED 240`).
  - **Premium From**: Starting price (e.g. `AED 360`).
- **Repeater Schema**:
  ```json
  {
    "rows": [
      {
        "size": "205/55 R16",
        "common_on": { "en": "Corolla, Civic, Golf", "ar": "كورولا، سيفيك، جولف" },
        "budget": "AED 180",
        "mid_range": "AED 260",
        "premium": "AED 385"
      },
      {
        "size": "265/65 R17",
        "common_on": { "en": "Prado, Pajero, Fortuner", "ar": "برادو، باجيرو، فورتشنر" },
        "budget": "AED 320",
        "mid_range": "AED 450",
        "premium": "AED 620"
      }
    ],
    "guarantees": [
      { "tag": "NO HIDDEN EXTRAS", "heading": "All-inclusive prices", "desc": "Fitting, balancing and valves included." }
    ]
  }
  ```

---

### 5.5 Car Care Services (`services`)
- **Emoji / Badge**: 🛠️ `Car Services`
- **Storefront Output**: 16-item car care service interactive chip/card grid with WhatsApp prefill links.
- **Top-Level Fields Used**: `section_title`, `section_subtitle`, `content`.
- **Repeater Items (`section_data.services`)**:
  - **Service Name (English)**: Service name (e.g. `Tyre Fitting & Replacement`).
  - **Service Name (Arabic)**: Service name in Arabic (e.g. `تركيب وتبديل الإطارات`).
- **Repeater Schema**:
  ```json
  {
    "services": [
      { "name": { "en": "Tyre Fitting & Replacement", "ar": "تركيب وتبديل الإطارات" } },
      { "name": { "en": "Wheel Balancing", "ar": "ترصيص العجلات" } },
      { "name": { "en": "Laser 3D Wheel Alignment", "ar": "ميزان ليزر ثلاثي الأبعاد" } },
      { "name": { "en": "Puncture Repair & Plug", "ar": "إصلاح البنشر والرقع" } }
    ]
  }
  ```

---

### 5.6 How It Works 4-Step Process (`how_it_works`)
- **Emoji / Badge**: 🔢 `How It Works`
- **Storefront Output**: Step-by-step ordered timeline showing customer interaction from WhatsApp inquiry to final fitting.
- **Top-Level Fields Used**: `section_title`, `section_subtitle`, `content`.
- **Repeater Items (`section_data.steps`)**:
  - **Icon**: Dropdown (`phone`, `dollar`, `truck`, `shield`, etc.).
  - **Step Title (EN / AR)**: Heading (e.g. `Step 1: Send Your Tyre Size`).
  - **Step Description (EN / AR)**: Instruction details.
- **Repeater Schema**:
  ```json
  {
    "steps": [
      {
        "step_number": 1,
        "icon": "phone",
        "title": { "en": "Send your tyre size on WhatsApp", "ar": "أرسل مقاس إطارك عبر واتساب" },
        "description": { "en": "Take a photo of your tyre sidewall or share your car's make and model. We reply in minutes with prices.", "ar": "التقط صورة لجدار الإطار أو شاركنا نوع وموديل سيارتك لنرد عليك بالأسعار فوراً." }
      },
      {
        "step_number": 2,
        "icon": "dollar",
        "title": { "en": "Pick your brand & confirm price", "ar": "اختر علامتك المفضلة وأكد السعر" },
        "description": { "en": "Choose between budget, mid-range or premium options. The price we quote is the final price.", "ar": "اختر من بين الخيارات الاقتصادية أو المتوسطة أو الفاخرة. السعر شامل كل شيء." }
      }
    ]
  }
  ```

---

### 5.7 Shop by Size, Vehicle & Brand (`shop_by`)
- **Emoji / Badge**: 🔍 `Shop by Size/Car`
- **Storefront Output**: Chip grid grouped by Popular Tyre Sizes, Popular Vehicles in UAE, and Brand Tiers. Clicking any chip pre-fills a direct WhatsApp inquiry.
- **Top-Level Fields Used**: `section_title`, `section_subtitle`, `content`.
- **Repeater Items (`section_data.groups`)**:
  - **Group Heading**: Category title (e.g. `Popular tyre sizes in the UAE`).
  - **Type Dropdown**: One of `size`, `vehicle`, or `brand`.
  - **Chips / Tags Textarea**: List of chips separated by ` · ` or commas (e.g. `195/65 R15 · 205/55 R16 · 215/55 R17`).
- **Repeater Schema**:
  ```json
  {
    "groups": [
      {
        "heading": "Popular tyre sizes in the UAE",
        "type": "size",
        "chips": ["195/65 R15", "205/55 R16", "215/55 R17", "225/45 R17", "265/65 R17", "275/40 R20"]
      },
      {
        "heading": "Tyres by vehicle",
        "type": "vehicle",
        "chips": ["Toyota Land Cruiser", "Nissan Patrol", "Toyota Prado", "Toyota Camry", "Tesla Model 3"]
      }
    ]
  }
  ```

---

### 5.8 Delivery & Fitting Coverage (`coverage`)
- **Emoji / Badge**: 📍 `Fitting Coverage`
- **Storefront Output**: 2 Service Comparison cards (*Partner Centre  Fitting* vs *Mobile Van Fitting*) and 3 geographic coverage chip groups (*Dubai*, *Abu Dhabi*, *Northern Emirates*).
- **Top-Level Fields Used**: `section_title`, `section_subtitle`, `content`.
- **Repeater Items (`section_data.areas`)**:
  - **Area Group Heading**: e.g. `Dubai coverage`, `Abu Dhabi coverage`.
  - **Emirate / Region**: e.g. `Dubai`, `Abu Dhabi`, `Northern Emirates`.
  - **Locations / Areas Textarea**: Area names separated by ` · ` or commas (e.g. `Dubai Marina · JLT · JBR · Palm Jumeirah · Downtown`).
- **Service Cards Schema (`section_data.options`)**:
  Persisted alongside areas to allow full customization of the comparison cards:
  ```json
  {
    "options": [
      {
        "tag": " Delivery & Fitting",
        "heading": " fitting at a partner centre",
        "description": "Choose any centre on our network and we deliver your tyres there  of charge. Fitting, balancing, new valves and disposal included.",
        "button_text": "Book at Partner Centre",
        "wa_msg": "Hi TyresVision, I'd like to book  tyre fitting at a partner centre."
      },
      {
        "tag": "Mobile Van Service",
        "heading": "Mobile van fitting at your location — call-out fee applies",
        "description": "Our vans fit your tyres at your villa, apartment, or office. Call-out fee confirmed before dispatch.",
        "button_text": "Book Mobile Van",
        "wa_msg": "Hi TyresVision, I'd like to book mobile van fitting at my location."
      }
    ],
    "areas": [
      {
        "heading": "Dubai coverage",
        "emirate": "Dubai",
        "chips": ["Dubai Marina", "JLT", "JBR", "Palm Jumeirah", "Downtown", "Business Bay", "Al Quoz"]
      },
      {
        "heading": "Abu Dhabi coverage",
        "emirate": "Abu Dhabi",
        "chips": ["Al Reem Island", "Khalifa City", "Yas Island", "Saadiyat Island", "Musaffah"]
      }
    ]
  }
  ```

---

### 5.9 Tyre Buying Advice (`advice`)
- **Emoji / Badge**: 💡 `Buying Advice`
- **Storefront Output**: 6-Card educational buying advice grid covering manufacturing DOT dates, load and speed ratings, premium vs. budget, summer heat compounds, replacement thresholds, and fully fitted pricing.
- **Top-Level Fields Used**: `section_title`, `section_subtitle`, `content`, `button_text`, `button_url`.
- **Repeater Items (`section_data.cards`)**:
  - **Icon**: Dropdown (`clock`, `shield`, `dollar`, `zap`, `award`, `truck`).
  - **Card Title (EN / AR)**: e.g. `Check the manufacturing date, not just the tread`.
  - **Card Description (EN / AR)**: Advice body text.
- **Repeater Schema**:
  ```json
  {
    "cards": [
      {
        "icon": "clock",
        "title": { "en": "Check the manufacturing date, not just the tread", "ar": "تحقق من تاريخ الصنع، وليس فقط عمق النقشة" },
        "description": { "en": "The last four digits of the DOT code on the sidewall are the week and year of manufacture...", "ar": "آخر أربعة أرقام من رمز DOT تشير إلى أسبوع وسنة الصنع..." }
      },
      {
        "icon": "shield",
        "title": { "en": "Match the load and speed rating to your car", "ar": "طابق مؤشر الحمولة والسرعة مع سيارتك" },
        "description": { "en": "Fitting a lower rating to save money is the most dangerous saving people make...", "ar": "اختيار تصنيف أقل لتوفير المال هو الخيار الأكثر خطورة في سوقنا..." }
      }
    ]
  }
  ```

---

### 5.10 Brands List (`brands`)
- **Emoji / Badge**: 🏷️ `Brands List`
- **Storefront Output**: Modern pill badge row of 60+ tyre brands with `+40 more` indicator.
- **Top-Level Fields Used**: `section_title`, `section_subtitle`.
- **Repeater Items (`section_data.brands`)**:
  - **Brand Name**: Single string (e.g. `Michelin`, `Bridgestone`, `Continental`, `Pirelli`, `Hankook`, `+40 more`).
- **Repeater Schema**:
  ```json
  {
    "brands": [
      "Michelin", "Bridgestone", "Goodyear", "Continental", "Pirelli", "Dunlop",
      "Hankook", "Yokohama", "Toyo", "Falken", "Nexen", "Kumho", "+40 more"
    ]
  }
  ```

---

### 5.11 Customer Reviews (`testimonials`)
- **Emoji / Badge**: ⭐ `Customer Reviews`
- **Storefront Output**: 3-column customer review cards featuring 5 gold stars, quoted feedback, verified customer avatar, and location badge (e.g. *Dubai*, *Abu Dhabi*, *Sharjah*).
- **Top-Level Fields Used**: `section_title`, `section_subtitle`.
- **Repeater Items (`section_data.reviews`)**:
  - **Author Name (EN / AR)**: e.g. `Verified customer` / `عميل موثوق`.
  - **Location (EN / AR)**: e.g. `Dubai` / `دبي`.
  - **Customer Quote (EN / AR)**: Customer testimonial.
- **Repeater Schema**:
  ```json
  {
    "reviews": [
      {
        "rating": 5,
        "author": { "en": "Verified customer", "ar": "عميل موثوق" },
        "location": { "en": "Dubai", "ar": "دبي" },
        "quote": { "en": "Sent my tyre size in the morning, had a price back in minutes and the car was done the same afternoon.", "ar": "أرسلت مقاس إطاري صباحاً، وتلقيت السعر في دقائق وتم تركيب الإطارات في نفس بعد الظهر." }
      }
    ]
  }
  ```

---

### 5.12 FAQ Accordion (`faq`)
- **Emoji / Badge**: ❓ `FAQ Accordion`
- **Storefront Output**: Collapsible `<details>` accordion list supporting rich text HTML answers and WhatsApp links.
- **Top-Level Fields Used**: `section_title`, `section_subtitle`.
- **Repeater Items (`section_data.faqs`)**:
  - **Question (English & Arabic)**: Accordion question title.
  - **Answer (English & Arabic)**: Rich text HTML answer.
- **Repeater Schema**:
  ```json
  {
    "faqs": [
      {
        "question": { "en": "How do I find my tyre size?", "ar": "كيف أجد مقاس إطاري؟" },
        "answer": { "en": "It's printed on the sidewall of your current tyre — something like <strong>235/55 R19 105W</strong>. Send a photo on WhatsApp if you're not sure.", "ar": "ستجده مطبوعاً على جدار إطارك الحالي — مثل <strong>235/55 R19 105W</strong>. يمكنك إرسال صورة عبر واتساب." }
      }
    ]
  }
  ```

---

### 5.13 Final CTA Action Box (`cta`)
- **Emoji / Badge**: 🚀 `CTA Banner`
- **Storefront Output**: High-converting full-width dark green gradient container with primary WhatsApp button, secondary phone call button, and availability note.
- **Top-Level Fields Used**:
  - `section_title`: Headline (e.g. *"Ready for a fresh set of tyres?"*).
  - `content`: Subtitle paragraph.
  - `button_text`: WhatsApp button label (e.g. *"WhatsApp us"*).
  - `button_url`: WhatsApp link.
- **Extended Fields (`section_data`)**:
  ```json
  {
    "call_button_text": { "en": "Call +971 50 506 9575", "ar": "اتصل بنا: 9575 506 50 971+" },
    "call_button_url": "tel:+971505069575",
    "footer_note": {
      "en": "Open daily — call or message any time and we’ll come back to you fast.",
      "ar": "مفتوح يومياً — اتصل أو راسلنا في أي وقت وسنرد عليك بسرعة فائقة."
    }
  }
  ```

---

### 5.14 Content + Image 2-Column (`content_image`)
- **Emoji / Badge**: 🖼️ `Content + Image`
- **Storefront Output**: 2-column split with rich narrative on one side and a rounded photography container on the other.
- **Top-Level Fields Used**:
  - `section_title`: Section heading.
  - `section_subtitle`: Small upper eyebrow tag.
  - `content`: Multi-paragraph CKEditor rich text.
  - `image`: Visual asset URL (e.g. `/static/assets/about/warehouse.webp`).
  - `image_position`: Alignment toggle (`left` or `right`).
  - `button_text`: Optional action button.
  - `button_url`: Target URL.
- **Repeater Schema (`section_data.items`)**:
  Optional key feature bullets or badges.

---

### 5.15 Mission & Team (`mission_vision`)
- **Emoji / Badge**: 🎯 `Mission / Team`
- **Storefront Output**: 2-column company mission, vision, and operational values section with image and key highlight pillars.
- **Top-Level Fields Used**: `section_title`, `section_subtitle`, `content`, `image`, `image_position`.
- **Repeater Items (`section_data.items`)**:
  List of core values/mission pillars with icons, titles, and descriptions.

---

## 6. Supported Icons Library

When editing cards, steps, or features, the following vector icon presets are selectable:

| Icon Key | Label in Admin | Description / Recommended Use |
|---|---|---|
| `shield` | Shield / Warranty | Guarantee, official warranty, genuine products |
| `dollar` | Dollar / Price | Competitive pricing, price matching, budget tiers |
| `truck` | Truck / Delivery |  delivery, mobile vans, same-day fitting |
| `clock` | Clock / 24-7 | Manufacturing DOT date code, response speed, hours |
| `award` | Award / Brands | 60+ brands, certified specialists, high ratings |
| `zap` | Zap / Fast | Quick turnaround, emergency response, fast fitting |
| `phone` | Phone / Contact | WhatsApp quotes, phone call, customer support |
| `globe` | Globe / Network | UAE-wide coverage, Dubai, Abu Dhabi, Sharjah |
| `tyre` | Tyre / Wheel | Car tyres, sizes, tread, balancing, alignment |

---

## 7. Current Storefront Template Dispatch Architecture

When the public storefront renders a page (e.g. `templates/Client/Home.html`), it iterates over the active sections from the database:

```jinja2
{% for sec in page_sections %}
  {% if sec.section_type == 'hero' %}
    <!-- 1. HERO -->
  {% elif sec.section_type == 'stats' %}
    <!-- 2. STATS -->
  {% elif sec.section_type == 'features' %}
    <!-- 3. WHY BUY FROM US -->
  {% elif sec.section_type == 'price_table' %}
    <!-- 4. PRICES MATRIX -->
  {% elif sec.section_type == 'services' %}
    <!-- 5. SERVICES GRID -->
  {% elif sec.section_type == 'how_it_works' %}
    <!-- 6. HOW IT WORKS TIMELINE -->
  {% elif sec.section_type == 'shop_by' %}
    <!-- 7. SHOP BY SIZE, VEHICLE, BRAND -->
  {% elif sec.section_type == 'coverage' %}
    <!-- 8. DELIVERY & FITTING COVERAGE -->
  {% elif sec.section_type == 'advice' %}
    <!-- 9. TYRE BUYING ADVICE (6 CARDS) -->
  {% elif sec.section_type == 'brands' %}
    <!-- 10. BRANDS LIST -->
  {% elif sec.section_type == 'testimonials' %}
    <!-- 11. REVIEWS -->
  {% elif sec.section_type == 'faq' %}
    <!-- 12. FAQ ACCORDION -->
  {% elif sec.section_type == 'cta' %}
    <!-- 13. FINAL CTA BOX -->
  {% elif sec.section_type == 'content_image' %}
    <!-- 14. 2-COLUMN CONTENT & IMAGE -->
  {% endif %}
{% endfor %}
```

---

## 8. Admin Operations Guide

### Adding a New Section
1. Navigate to `/visionadmin/sections`.
2. Select the target page from the dropdown filter (e.g. `Home (/)` or `About Us (/about)`).
3. Click the **"+ Add Section"** button at the top-right.
4. Pick a **Predefined Section Layout** card (e.g. `Buying Advice`).
5. Fill in the **Title**, **Subtitle**, and **Description** in both English and Arabic.
6. Click **"+ Add Item"** in the Repeatable Items section to populate structured cards, chips, or FAQs.
7. Set the **Sort Order** (numerical position on the page) and toggle **Enable Section**.
8. Click **"Save Section"**. The section is instantly persisted and live on the public page.

### Editing an Existing Section
1. On the Sections list, click the **"Edit"** pencil button on any section row.
2. The modal pre-populates all existing data, including all repeaters.
3. Modify fields, add or remove repeater items, and click **"Save Section"**.

### Reordering Sections
- Edit the numeric **Sort Order** in the edit modal, or drag and drop sections in the table.
- Lower numbers appear higher on the public storefront.

### Disabling / Hiding a Section
- Uncheck the **"Enable Section"** checkbox in the modal.
- The section remains in the database and admin table, but is omitted from public storefront rendering.

---

# PART II: Composable Block Engine — Solution Architecture & Implementation Plan

> **Scope**: The zero-code dynamic block stack architecture that eliminates code changes when creating or combining sections.

---

## 9. Problem Analysis & The User's Real-World Case Study

### 9.1 The Core Bottlenecks
Currently, adding or extending page sections on TyresVision requires manual code changes across 4–5 different files:
1. **Hardcoded Frontend Dispatcher**: `templates/Client/Home.html` uses rigid Jinja blocks (`{% elif sec.section_type == 'advice' %}`). If a new section type is introduced, it will not display on the storefront until a developer writes new HTML and Jinja logic.
2. **Rigid Layout Silos**: Each section type is locked into a fixed schema:
   - `features` and `advice` only allow 3-column cards (`icon`, `title`, `description`).
   - `shop_by` only allows grouped chips (`heading`, `type`, `chips`).
   - `coverage` only allows 2 fixed service cards + area chips.
   - You cannot mix and match items (e.g., adding vehicle chips inside an advice section, or adding a secondary button, or adding a comparison box) without modifying JavaScript, HTML, and Python code.
3. **Missing Fields Limitation**: If an admin needs an extra field (e.g., a secondary CTA button, a promo badge, a callout banner, or custom highlight colors), there is no way to add it in the Section Builder without altering the database handling and JS packing scripts.

### 9.2 The Goal: Zero-Code Dynamic Composable Builder
Enable any administrator to:
- Create **unlimited new sections** from the admin dashboard with **zero code changes**.
- **Mix and match any components** (e.g., Cards + Chips + Comparison Cards + FAQs + Multiple Buttons) inside any single section.
- ly add **custom attributes/fields** (secondary buttons, tags, highlight text, colors).
- Preview and publish instantly without deploying or editing code.

---

### 9.3 Concrete User Case Study: Using a "Statistic Metric" inside "Car Care Services"

**The User's Real-World Need:**
> *"For example, `Statistic Metric #1` is in the `stats` (Statistics Grid) section, but I want to use this exact metric component inside `services` (Car Care Services). That is my issue."*

#### Why the Current System Fails on This:
In the current codebase:
1. **The Admin Modal is Siloed (`static/visionadmin/sections.js:901-981`)**:
   - When `section_type == 'stats'`, the repeater *only* renders `Metric Number` and `Metric Label`.
   - When `section_type == 'services'`, the repeater *only* renders `Service Name`.
   - An admin cannot add a `Statistic Metric` into the `services` section because the code checks `if (type === 'stats')` vs `if (type === 'services')` and forbids cross-pollination.
2. **The Database Serialization is Siloed (`sections.js:1604-1623`)**:
   - `stats` only saves `section_data.metrics`.
   - `services` only saves `section_data.services`.
3. **The Frontend Template is Siloed (`templates/Client/Home.html:269-285`)**:
   - The `services` section in `Home.html` only loops through `sec.section_data.services`. It does not even look for or render metrics.

#### How the Composable Block Solution Solves It (100% Zero-Code):
Under the new **Composable Block Engine**:
1. In VisionAdmin, the admin edits or creates the **Car Care Services** section.
2. In the Section Canvas, the admin clicks **"+ Add Block"**:
   - **Block 1 (Metrics Strip)**: Admin adds Metric #1 (`16+` / `Car Care Services`), Metric #2 (`25+` / `Partner Locations`), Metric #3 (`30 min` / `Fast Service`).
   - **Block 2 (Cards / Services Grid)**: Admin adds the 16 service cards (Tyre Fitting, 3D Alignment, Balancing, etc.).
   - **Block 3 (CTA Buttons)**: Admin adds a WhatsApp button ("Inquire about car services").
3. The Admin can drag to reorder: want the metrics strip *above* the services? Or *below* the services? Just drag it!
4. The database stores:
   ```json
   {
     "blocks": [
       {
         "type": "metrics_strip",
         "items": [
           { "number": "16+", "label": { "en": "Car Care Services", "ar": "خدمة صيانة سيارات" } },
           { "number": "25+", "label": { "en": "Partner Locations", "ar": "موقع شريك" } }
         ]
       },
       {
         "type": "cards_grid",
         "columns": 4,
         "items": [
           { "title": { "en": "Tyre Fitting", "ar": "تركيب الإطارات" } },
           { "title": { "en": "3D Wheel Alignment", "ar": "ميزان ليزر 3D" } }
         ]
       }
     ]
   }
   ```
5. The frontend's universal block loop (`{% for block in sec.section_data.blocks %}`) renders the metrics band AND the services cards seamlessly inside the Car Care Services section. **Zero code touched.**

---

## 10. The Architectural Solution: Composable Block Engine

Instead of treating a Section as a **rigid, single-purpose type**, the system transitions to a **Container + Modular Block Stack** model (used by modern headless CMS engines like Strapi Dynamic Zones, Webflow, and Shopify Sections).

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PAGE SECTION CONTAINER                          │
│  • Title (EN/AR)    • Subtitle/Eyebrow (EN/AR)   • Container Width     │
│  • Background Theme • Top/Bottom Padding         • Primary / Sec CTA   │
├────────────────────────────────────────────────────────────────────────┤
│  STACK OF MODULAR BLOCKS (Admin can add, remove, and reorder any):     │
│                                                                        │
│   [ BLOCK 1: Cards Grid ] ────────── 3 cols (Icons, Titles, Descs)    │
│                                                                        │
│   [ BLOCK 2: Chips Cloud ] ───────── Vehicle / Tyre Size Chips        │
│                                                                        │
│   [ BLOCK 3: Comparison Split ] ──── Centre Fitting vs Mobile Van      │
│                                                                        │
│   [ BLOCK 4: Accordion FAQ ] ─────── Collapsible Questions & Answers  │
│                                                                        │
│   [ BLOCK 5: Action Button Row ] ─── WhatsApp + Direct Phone Call      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 11. The 10 Universal Atomic Building Blocks

By breaking all website sections into 10 reusable atomic blocks, any current or future section can be constructed without touching template code:

| Block Identifier | Block Name | Configurable Parameters | Use Cases |
|---|---|---|---|
| `cards_grid` | **Card Grid** | Columns (1, 2, 3, 4), Style (standard, bordered, glass, hover-glow), Items: `icon`, `tag`, `title`, `desc`, `link` | Why Us, Tyre Advice, Guarantee Cards, Value Props |
| `chips_cloud` | **Interactive Chips** | Layout (inline, wrap, grouped), Action (`whatsapp`, `filter`, `link`), Items: `label`, `value`, `icon` | Tyre Sizes, Vehicles, Brands, Area Coverage |
| `comparison_split` | **Service Comparison** | Cards count (2 or 3), Featured badge, Items: `badge`, `heading`, `desc`, `price_tag`, `button_text`, `button_url` | Centre vs Mobile Van, Plan Comparisons |
| `metrics_strip` | **Statistics Counter** | Columns (2, 3, 4), Items: `number`, `label`, `icon` | Stats bar, Trust counters, Milestone badges |
| `process_steps` | **Step Timeline** | Layout (horizontal, vertical), Items: `step_number`, `icon`, `title`, `desc`, `badge` | How It Works, Order Process, 4-Step Guide |
| `accordion_faq` | **Collapsible Accordion** | Open first by default (yes/no), Items: `question`, `answer` (Rich HTML) | FAQs, Technical Specs, Policies |
| `reviews_slider` | **Customer Reviews** | Layout (grid, slider), Items: `rating` (1-5), `quote`, `author`, `location`, `avatar` | Customer Testimonials, Reviews |
| `media_story` | **Media + Prose Split** | Alignment (`image_left`, `image_right`, `full_bleed`), `image_url`, `content` (Rich HTML), `bullet_points` | About Story, Warehouse Media, 2-Column Narratives |
| `pricing_matrix` | **Tabular Pricing** | Columns definitions, Rows: `size`, `vehicle`, `budget_price`, `mid_price`, `prem_price` | Tyre Size Price Matrix, Service Price Lists |
| `cta_actions` | **Action Button Group** | Alignment (center, left, right), Buttons list: `text`, `url`, `variant` (whatsapp, phone, white, dark, outline) | CTA Banners, Contact Buttons, Conversion Strips |

---

## 12. Universal Data Structure (`section_data.blocks`)

To maintain 100% backward compatibility with existing hardcoded sections while enabling unlimited dynamic sections, `section_data` supports the composable `blocks` array:

```json
{
  "theme": {
    "bg_style": "default", 
    "padding_y": "compact",
    "container_max_w": "1280px"
  },
  "blocks": [
    {
      "type": "cards_grid",
      "columns": 3,
      "items": [
        {
          "icon": "clock",
          "tag": { "en": "SAFETY", "ar": "أمان" },
          "title": { "en": "Check Manufacturing Date", "ar": "تحقق من تاريخ الصنع" },
          "description": { "en": "UAE heat ages rubber faster than tread...", "ar": "حرارة الإمارات تؤثر على المطاط..." }
        }
      ]
    },
    {
      "type": "chips_cloud",
      "group_title": { "en": "Popular Sizes", "ar": "مقاسات شائعة" },
      "action_type": "whatsapp",
      "chips": ["195/65 R15", "205/55 R16", "265/65 R17"]
    },
    {
      "type": "cta_actions",
      "buttons": [
        {
          "text": { "en": "WhatsApp Expert", "ar": "تواصل عبر واتساب" },
          "url": "https://wa.me/971505069575",
          "variant": "whatsapp"
        },
        {
          "text": { "en": "Call Support", "ar": "اتصال هاتف" },
          "url": "tel:+971505069575",
          "variant": "phone"
        }
      ]
    }
  ]
}
```

---

## 13. Storefront Universal Block Dispatcher Architecture

In `templates/Client/Home.html` (and any custom page like `About.html`), the renderer checks if the section has dynamic `blocks`. If so, it dispatches each block through a universal Jinja macro:

```jinja2
<!-- Check if section uses the Composable Block Engine -->
{% if sec.section_data and sec.section_data.blocks %}
  <section class="dynamic-section" id="section-{{ sec.id }}">
    <div class="wrap">
      <!-- Section Header -->
      {% if sec.section_title %}
        <div class="center mb-8">
          {% if sec.section_subtitle %}<span class="eyebrow">{{ sec.section_subtitle }}</span>{% endif %}
          <h2>{{ sec.section_title }}</h2>
          {% if sec.content %}<div class="lead">{{ sec.content | safe }}</div>{% endif %}
        </div>
      {% endif %}

      <!-- Dynamic Blocks Stack -->
      {% for block in sec.section_data.blocks %}
        {% include 'Client/components/blocks/' ~ block.type ~ '.html' ignore missing %}
      {% endfor %}
    </div>
  </section>

<!-- Backward Compatibility: Fallback to existing legacy hardcoded types -->
{% elif sec.section_type == 'hero' %}
  ...
{% elif sec.section_type == 'advice' %}
  ...
{% endif %}
```

### Why this solves the issue permanently:
- When an admin adds a new section in VisionAdmin and adds any combination of blocks, the template **automatically loops through the blocks and renders them**.
- **No Python code, no Jinja template edits, and no deployment are required.**

---

## 14. VisionAdmin Composable Interface UI Design

### 6.1 The Composable Block Modal
In `/visionadmin/sections`:
1. **Section General Settings** (Top):
   - Page Slug, Section Title (EN/AR), Subtitle (EN/AR), Description (CKEditor), Visibility, Sort Order.
2. **Composable Blocks Canvas** (Middle):
   - A visual stack showing the blocks currently inside the section.
   - Drag-and-drop handles to reorder blocks vertically.
   - **"+ Add Block" Dropdown Menu**:
     - 🃏 Add Cards Grid (Advice, Features, Guarantees)
     - 🏷️ Add Chips Cloud (Sizes, Vehicles, Brands, Areas)
     - ⚖️ Add Comparison Service Split (Fitting Centre vs Mobile Van)
     - 📊 Add Metric Counters (Stats, Numbers)
     - 🔢 Add Step Timeline (How It Works)
     - ❓ Add FAQ Accordion
     - ⭐ Add Reviews
     - 🖼️ Add Media / Story Split
     - 💰 Add Price Matrix
     - 🔘 Add Action Buttons Row
3. **Custom Fields & Attributes Drawer** (Bottom):
   - Allows adding optional key-value pairs (e.g. `callout_badge: "Limited Offer"`, `accent_color: "#58B31B"`, `secondary_url: "..."`) without altering database tables.

---

## 15. Phased Step-by-Step Implementation Roadmap

```
┌────────────────────────────────────────────────────────────────────────┐
│                        IMPLEMENTATION PHASES                           │
│                                                                        │
│  PHASE 1 ── Core Universal Block Macros (Frontend)                     │
│  PHASE 2 ── Composable Block Controller & UI (VisionAdmin)             │
│  PHASE 3 ── Dynamic Custom Fields & Attributes Drawer                  │
│  PHASE 4 ── Presets & Auto-Migration for Existing Sections             │
│  PHASE 5 ── Verification & Stress Testing                              │
└────────────────────────────────────────────────────────────────────────┘
```

### Phase 1: Core Universal Block Macros (Frontend)
- Create modular Jinja partials under `templates/Client/components/blocks/`:
  - `cards_grid.html`
  - `chips_cloud.html`
  - `comparison_split.html`
  - `metrics_strip.html`
  - `process_steps.html`
  - `accordion_faq.html`
  - `reviews_slider.html`
  - `media_story.html`
  - `pricing_matrix.html`
  - `cta_actions.html`
- Update `templates/Client/Home.html` and `About.html` to check for `sec.section_data.blocks` first before checking legacy types.

### Phase 2: Composable Block Controller & UI (VisionAdmin)
- In `templates/visionadmin/sections.html`:
  - Add a **"Custom Composable Layout"** option in the Predefined Section Layout selector.
  - Create the **Block Palette & Canvas**: buttons to append any atomic block to the active section.
- In `static/visionadmin/sections.js`:
  - Implement block add/remove/reorder event handlers.
  - Build universal serializing logic: collects all configured blocks into `section_data.blocks`.

### Phase 3: Dynamic Custom Fields & Attributes
- Add a key-value attribute manager inside the modal.
- Any custom attribute (e.g., `promo_pill`, `custom_badge`, `wa_custom_message`) is serialized into `section_data.custom_fields` and exposed in Jinja.

### Phase 4: Presets & Auto-Migration
- Pre-configure 1-click presets in the admin (e.g., *"Buying Advice + Vehicle Chips"*, *"Service Options + Area Coverage"*, *"Hero + Stat Strip"*).
- Admins can click any preset as a starting template, then ly modify blocks.

### Phase 5: Verification & Quality Assurance
- Test creating 3 completely new, composite sections with mixed blocks (e.g. Cards + Chips + FAQ + CTA) strictly from the browser.
- Verify instant storefront rendering in both English and Arabic.
- Ensure 100% backward compatibility for existing sections (`hero`, `features`, `coverage`, `advice`, etc.).

---

## 16. Summary of Business & Technical Benefits

1. **Zero Code Touched**: New sections with any combination of content are created directly from the browser.
2. **Infinite Flexibility**: No longer restricted to rigid "cards-only" or "chips-only" layouts — components can be stacked ly.
3. **Multilingual by Default**: Every block element inherently supports English and Arabic.
4. **Instant Turnaround**: Marketing or content updates take seconds instead of requiring developer deployments.
