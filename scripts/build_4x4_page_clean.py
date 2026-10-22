"""
scripts/update_pages_from_build_plan.py
Synchronizes all 13 CMS pages in the MySQL `pages` table with the exact
specifications, headings, content briefs, vehicle tables, local angles, FAQs,
and internal links defined in 'TyresVision-13-Page-Build-Plan 1.docx'.

Preserves the modern brand-blue UI styling, interactive working accordions,
quote forms, and responsive tables.
"""

import os
import sys
import json
import urllib.parse

# Path configuration
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app'))

from db import get_connection

DEFAULT_HERO_BG = "/static/uploads/pages/banner_1788954653_64dd43ed.png"


def build_hero_section(title, eyebrow, lead, wa_text, wa_msg, breadcrumb_label="Page"):
    wa_encoded = urllib.parse.quote(wa_msg)
    return f"""
<!-- 1. HERO SECTION -->
<section class="tv-page-hero">
  <div class="wrap hero-grid">
    <div class="tv-hero-left">
      <nav class="about-breadcrumb" aria-label="Breadcrumb" style="margin-bottom: 20px; display: flex; align-items: center; flex-wrap: wrap; gap: 6px;">
        <a href="/">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>
          <span>Home</span>
        </a>
        <span class="sep" aria-hidden="true">/</span>
        <span class="current">{breadcrumb_label}</span>
        <span class="breadcrumb-eyebrow" style="color:#38bdf8; font-weight:700; font-size:0.84rem; letter-spacing:0.06em; margin-left:4px;">&mdash; {eyebrow}</span>
      </nav>
      <h1>{title}</h1>
      <p class="lead">{lead}</p>
      <div class="cta-row">
        <a class="btn btn-wa" href="https://wa.me/971505069575?text={wa_encoded}" target="_blank" rel="noopener">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.46 1.32 4.96L2 22l5.25-1.38a9.9 9.9 0 004.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91C21.96 6.45 17.5 2 12.04 2zm5.8 14.06c-.24.68-1.42 1.31-1.96 1.36-.54.05-1.04.24-3.52-.73-2.99-1.18-4.86-4.29-5.01-4.49-.15-.2-1.2-1.6-1.2-3.05 0-1.45.76-2.16 1.03-2.46.27-.29.59-.37.78-.37s.39 0 .56.01c.18.01.42-.07.66.5.24.59.83 2.03.9 2.18.07.15.12.32.02.51-.1.2-.15.32-.29.5s-.3.4-.43.53c-.15.15-.3.31-.13.6.17.29.76 1.25 1.62 2.02 1.11.99 2.05 1.3 2.34 1.45.29.15.46.12.63-.07.17-.2.73-.85.92-1.14.2-.29.39-.24.66-.15.27.1 1.71.81 2 .96.29.15.49.22.56.34.07.13.07.75-.17 1.43z"/></svg>
          <span>{wa_text}</span>
        </a>
        <a class="btn btn-ghost-light" href="tel:+971505069575">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6.62 10.79a15.05 15.05 0 006.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1C10.4 21 3 13.6 3 4.5 3 3.95 3.45 3.5 4 3.5h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"/></svg>
          <span>+971 50 506 9575</span>
        </a>
      </div>
      <div class="hero-badges">
        <span class="pill"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg> 100% Genuine Tyres</span>
        <span class="pill"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg> Free Fitting &amp; Balancing</span>
        <span class="pill"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg> Doorstep Mobile Van</span>
        <span class="pill"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg> Official GCC Spec</span>
      </div>
    </div>
    <div class="quote-card tv-hero-quote-box">
      <div class="tv-quote-head">
        <span class="badge" style="background:rgba(37,99,255,0.18); color:#38bdf8; font-weight:800; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.06em; padding:4px 10px; border-radius:100px; display:inline-block; margin-bottom:8px;">Fast UAE Dispatch</span>
        <h3 style="margin:0; font-size:1.35rem; color:#fff;">Get Tyre Pricing in Minutes</h3>
        <p class="sub" style="margin-top:6px; color:rgba(255,255,255,0.7); font-size:0.9rem;">Send your size on WhatsApp for verified price options across 60+ brands.</p>
      </div>
      <form id="quoteForm" novalidate style="margin-top:16px;">
        <div class="field">
          <label for="tyreSize">Tyre size (e.g. 235/55 R19)</label>
          <input id="tyreSize" name="tyreSize" type="text" placeholder="235/55 R19" autocomplete="off" required>
        </div>
        <div class="field-row">
          <div class="field">
            <label for="carMake">Vehicle details</label>
            <input id="carMake" name="carMake" type="text" placeholder="e.g. Nissan Patrol / Model Y" autocomplete="off">
          </div>
          <div class="field">
            <label for="emirate">Emirate</label>
            <select id="emirate" name="emirate">
              <option>Dubai</option><option>Abu Dhabi</option><option>Sharjah</option>
              <option>Ajman</option><option>Ras Al Khaimah</option><option>Fujairah</option><option>Umm Al Quwain</option>
            </select>
          </div>
        </div>
        <button type="submit" class="btn btn-wa w-full" style="margin-top:10px; width:100%; justify-content:center;">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.46 1.32 4.96L2 22l5.25-1.38a9.9 9.9 0 004.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91C21.96 6.45 17.5 2 12.04 2zm5.8 14.06c-.24.68-1.42 1.31-1.96 1.36-.54.05-1.04.24-3.52-.73-2.99-1.18-4.86-4.29-5.01-4.49-.15-.2-1.2-1.6-1.2-3.05 0-1.45.76-2.16 1.03-2.46.27-.29.59-.37.78-.37s.39 0 .56.01c.18.01.42-.07.66.5.24.59.83 2.03.9 2.18.07.15.12.32.02.51-.1.2-.15.32-.29.5s-.3.4-.43.53c-.15.15-.3.31-.13.6.17.29.76 1.25 1.62 2.02 1.11.99 2.05 1.3 2.34 1.45.29.15.46.12.63-.07.17-.2.73-.85.92-1.14.2-.29.39-.24.66-.15.27.1 1.71.81 2 .96.29.15.49.22.56.34.07.13.07.75-.17 1.43z"/></svg>
          <span>Instant WhatsApp Quote</span>
        </button>
      </form>
    </div>
  </div>
</section>
"""


def build_faq_section(title, faqs):
    items_html = ""
    for idx, f in enumerate(faqs):
        is_active = " active" if idx == 0 else ""
        expanded = "true" if idx == 0 else "false"
        items_html += f"""
      <div class="faq-item{is_active}" data-faq-item>
        <button type="button" class="faq-summary" aria-expanded="{expanded}">
          <span class="faq-question-text">{f['q']}</span>
          <span class="faq-chevron-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </span>
        </button>
        <div class="faq-answer">
          <div class="faq-answer-inner">
            <div class="body"><p>{f['a']}</p></div>
          </div>
        </div>
      </div>
"""
    return f"""
<!-- FAQ SECTION -->
<section class="faq tv-section-block" style="background:#F8FAFC;">
  <div class="wrap" style="max-width:860px">
    <div class="center tv-section-head">
      <span class="eyebrow">&bull; FREQUENTLY ASKED QUESTIONS &bull;</span>
      <h2>{title}</h2>
      <p class="lead">Answers to key questions from drivers across the Emirates.</p>
    </div>
    <div class="faq-list" style="margin-top:36px;">
{items_html}
    </div>
  </div>
</section>
"""


def build_bottom_cta(heading, lead, wa_msg, wa_btn_text="WhatsApp Our Specialists"):
    wa_encoded = urllib.parse.quote(wa_msg)
    return f"""
<!-- BOTTOM CTA SECTION -->
<section class="tv-4x4-bottom-cta">
  <div class="wrap">
    <div class="tv-4x4-bottom-grid">
      <div>
        <h2 style="font-size:clamp(1.9rem, 3.4vw, 2.6rem); font-weight:800; color:#ffffff; margin:0 0 14px 0; letter-spacing:-0.02em;">{heading}</h2>
        <p style="font-size:1.05rem; line-height:1.7; color:rgba(255,255,255,0.92); margin:0 0 28px 0; max-width:620px;">{lead}</p>
        <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
          <a class="tv-btn-wa-green" href="https://wa.me/971505069575?text={wa_encoded}" target="_blank" rel="noopener">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.46 1.32 4.96L2 22l5.25-1.38a9.9 9.9 0 004.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91C21.96 6.45 17.5 2 12.04 2zm5.8 14.06c-.24.68-1.42 1.31-1.96 1.36-.54.05-1.04.24-3.52-.73-2.99-1.18-4.86-4.29-5.01-4.49-.15-.2-1.2-1.6-1.2-3.05 0-1.45.76-2.16 1.03-2.46.27-.29.59-.37.78-.37s.39 0 .56.01c.18.01.42-.07.66.5.24.59.83 2.03.9 2.18.07.15.12.32.02.51-.1.2-.15.32-.29.5s-.3.4-.43.53c-.15.15-.3.31-.13.6.17.29.76 1.25 1.62 2.02 1.11.99 2.05 1.3 2.34 1.45.29.15.46.12.63-.07.17-.2.73-.85.92-1.14.2-.29.39-.24.66-.15.27.1 1.71.81 2 .96.29.15.49.22.56.34.07.13.07.75-.17 1.43z"/></svg>
            <span>{wa_btn_text}</span>
          </a>
          <a class="tv-btn-white-pill" href="tel:+971505069575">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6.62 10.79a15.05 15.05 0 006.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1C10.4 21 3 13.6 3 4.5 3 3.95 3.45 3.5 4 3.5h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"/></svg>
            <span>Call +971 50 506 9575</span>
          </a>
        </div>
      </div>
      <div class="tv-4x4-bottom-badges-list">
        <div class="tv-4x4-bottom-badge-item">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
          <span>Free fitting across Dubai, Abu Dhabi &amp; Sharjah</span>
        </div>
        <div class="tv-4x4-bottom-badge-item">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
          <span>Expert advice on tyre sizes &amp; brands</span>
        </div>
        <div class="tv-4x4-bottom-badge-item">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>
          <span>Mobile van fitting at your location</span>
        </div>
        <div class="tv-4x4-bottom-badge-item">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
          <span>Trusted by 7,000+ UAE drivers</span>
        </div>
      </div>
    </div>
  </div>
</section>
"""


# ==============================================================================
# PAGE 3: Off-Road & 4x4 Tyres (/off-road-4x4-tyres)
# Exact match to TyresVision-13-Page-Build-Plan 1.docx
# ==============================================================================
def build_page_off_road_4x4():
    return """
<!-- 1. HERO SECTION -->
<section class="tv-4x4-hero">
  <div class="wrap">
    <div class="tv-4x4-hero-content" style="max-width: 760px;">
      <nav class="about-breadcrumb" aria-label="Breadcrumb" style="margin-bottom: 20px;">
        <a href="/">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>
          <span>Home</span>
        </a>
        <span class="sep" aria-hidden="true">/</span>
        <span class="current">Off-Road &amp; 4x4 Tyres</span>
      </nav>
      <h1 class="tv-4x4-hero-h1">Off-Road and 4x4 Tyres in the UAE</h1>
      <p class="tv-4x4-hero-lead" style="margin-bottom: 28px;">Off-road, all-terrain and highway 4x4 tyres for Patrol, Land Cruiser and Prado. Honest advice on desert versus tarmac, fitted free across the UAE.</p>
      
      <div class="tv-4x4-trust-strip">
        <div class="tv-4x4-trust-item">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
          <span>Free Fitting at Partner Centres</span>
        </div>
        <div class="tv-4x4-trust-item">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          <span>GCC-Spec Tyres</span>
        </div>
        <div class="tv-4x4-trust-item">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>
          <span>Mobile Van Service</span>
        </div>
        <div class="tv-4x4-trust-item">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
          <span>Trusted by 7,000+ Drivers</span>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- 2. TERRAIN COMPARISON SECTION -->
<!-- H2 1: Highway, all-terrain or mud-terrain — which do you actually need? -->
<section class="tv-section-block" style="background:#ffffff;">
  <div class="wrap">
    <div class="center tv-section-head">
      <span class="eyebrow">&bull; HONEST TYRE ADVICE &bull;</span>
      <h2 class="center tv-section-title">Highway, all-terrain or mud-terrain &mdash; which do you actually need?</h2>
      <p class="center tv-section-subtitle" style="max-width:840px; margin:0 auto 36px auto; font-size:1.06rem; line-height:1.75; color:#475569;">Most UAE SUV owners never leave tarmac but get sold all-terrain tyres they don&rsquo;t need. A/T tyres are noisier, wear faster in heat and cost fuel. If your off-road is the gravel outside a farm gate, buy highway tyres.</p>
    </div>

    <div class="tv-terrain-grid">
      <!-- Card 1: All-Terrain -->
      <div class="tv-terrain-card">
        <div class="tv-terrain-card-top">
          <div class="tv-terrain-card-img-col">
            <img class="tv-terrain-tyre-img" src="/static/assets/images/4x4/all_terrain_tyre.webp" alt="All-Terrain 4x4 Tyre" loading="lazy">
          </div>
          <div class="tv-terrain-card-info-col">
            <h3>All-Terrain (A/T)</h3>
            <div class="tv-terrain-pattern-icon" aria-hidden="true">
              <svg width="24" height="22" viewBox="0 0 24 24" fill="none" stroke="#2563FF" stroke-width="2.2" stroke-linecap="round"><line x1="6" y1="21" x2="8" y2="3"></line><line x1="12" y1="21" x2="12" y2="3" stroke-dasharray="3 3"></line><line x1="18" y1="21" x2="16" y2="3"></line></svg>
            </div>
            <p style="font-size:0.86rem; color:#475569; margin:0 0 10px 0; font-weight:600;"><strong>Best for:</strong> 60% tarmac, 40% desert dunes, wadis, camping.</p>
            <ul class="tv-terrain-checklist">
              <li>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                <span>Interlocking tread blocks &amp; sidewall armor</span>
              </li>
              <li>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                <span>Excellent sand flotation when deflated</span>
              </li>
              <li>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                <span>Moderate road hum on highway</span>
              </li>
              <li>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                <span>Leading picks: KO2/KO3, Geolandar, Scorpion</span>
              </li>
            </ul>
          </div>
        </div>
        <div class="tv-terrain-pill-btn">Balanced for city + desert driving</div>
      </div>

      <!-- Card 2: Mud-Terrain -->
      <div class="tv-terrain-card">
        <div class="tv-terrain-card-top">
          <div class="tv-terrain-card-img-col">
            <img class="tv-terrain-tyre-img" src="/static/assets/images/4x4/mud_terrain_tyre.png" alt="Mud-Terrain 4x4 Tyre" loading="lazy">
          </div>
          <div class="tv-terrain-card-info-col">
            <h3>Mud-Terrain (M/T)</h3>
            <div class="tv-terrain-pattern-icon" aria-hidden="true">
              <svg width="26" height="22" viewBox="0 0 24 24" fill="none" stroke="#2563FF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 20l7-12 4 7 3-4 4 9H3z"/></svg>
            </div>
            <p style="font-size:0.86rem; color:#475569; margin:0 0 10px 0; font-weight:600;"><strong>Best for:</strong> Dedicated off-road rigs, rocky trails, heavy mud.</p>
            <ul class="tv-terrain-checklist">
              <li>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                <span>Massive tread lugs &amp; sidewall bite</span>
              </li>
              <li>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                <span>Maximum puncture resistance on sharp rock</span>
              </li>
              <li>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                <span>Noticeably louder on pavement &amp; highways</span>
              </li>
              <li>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                <span>Longer braking distances in wet conditions</span>
              </li>
            </ul>
          </div>
        </div>
        <div class="tv-terrain-pill-btn">Built for dedicated extreme off-road</div>
      </div>

      <!-- Card 3: Highway-Terrain -->
      <div class="tv-terrain-card">
        <div class="tv-terrain-card-top">
          <div class="tv-terrain-card-img-col">
            <img class="tv-terrain-tyre-img" src="/static/assets/images/4x4/highway_terrain_tyre.png" alt="Highway-Terrain 4x4 Tyre" loading="lazy">
          </div>
          <div class="tv-terrain-card-info-col">
            <h3>Highway-Terrain (H/T)</h3>
            <div class="tv-terrain-pattern-icon" aria-hidden="true">
              <svg width="24" height="22" viewBox="0 0 24 24" fill="none" stroke="#2563FF" stroke-width="2.2" stroke-linecap="round"><line x1="6" y1="21" x2="8" y2="3"></line><line x1="12" y1="21" x2="12" y2="3" stroke-dasharray="3 3"></line><line x1="18" y1="21" x2="16" y2="3"></line></svg>
            </div>
            <p style="font-size:0.86rem; color:#475569; margin:0 0 10px 0; font-weight:600;"><strong>Best for:</strong> 90%+ tarmac commuting, family road trips, school runs.</p>
            <ul class="tv-terrain-checklist">
              <li>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                <span>Quietest cabin &amp; luxury comfort</span>
              </li>
              <li>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                <span>Shortest braking distance on dry/wet tarmac</span>
              </li>
              <li>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                <span>Superior heat dissipation at 140 km/h in summer</span>
              </li>
              <li>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                <span>Lowest rolling resistance &amp; maximum fuel economy</span>
              </li>
            </ul>
          </div>
        </div>
        <div class="tv-terrain-pill-btn">Ideal for daily city &amp; highway driving</div>
      </div>
    </div>
  </div>
</section>

<!-- 3. TYRES BY 4X4 MODEL SECTION -->
<!-- H2 2: Tyres by 4x4 model -->
<section class="price-section tv-section-block" style="background:#F8FAFC;">
  <div class="wrap">
    <div class="center tv-section-head">
      <span class="eyebrow">&bull; POPULAR 4X4 &amp; SUV VEHICLES &bull;</span>
      <h2>Tyres by 4x4 model</h2>
      <p class="lead">Factory dimensions and recommended fitment for the most popular 4x4s and SUVs driven across the UAE.</p>
    </div>

    <!-- Guarantees 4 Cards Strip -->
    <div class="price-guarantees-grid" style="margin-top:24px; margin-bottom:28px;">
      <div class="price-guarantee-card">
        <div class="pg-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg></div>
        <div class="pg-text"><div class="pg-title">Fresh Production Dates</div><div class="pg-sub">Guaranteed latest stock</div></div>
      </div>
      <div class="price-guarantee-card">
        <div class="pg-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg></div>
        <div class="pg-text"><div class="pg-title">Free 3D Balancing &amp; Fitting</div><div class="pg-sub">At partner centres across UAE</div></div>
      </div>
      <div class="price-guarantee-card">
        <div class="pg-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M4 18l5-9 4 7 3-4 4 6H4z"/></svg></div>
        <div class="pg-text"><div class="pg-title">Desert Deflation Capable</div><div class="pg-sub">Tested for sand dunes</div></div>
      </div>
      <div class="price-guarantee-card">
        <div class="pg-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg></div>
        <div class="pg-text"><div class="pg-title">Doorstep Mobile Fitting</div><div class="pg-sub">At your home or office</div></div>
      </div>
    </div>

    <!-- Table with the 10 exact models from build plan -->
    <div class="price-table-card">
      <div class="price-table-scroll">
        <table class="price-table tv-4x4-table" aria-label="Tyres by 4x4 Model">
          <thead>
            <tr>
              <th scope="col">Vehicle</th>
              <th scope="col">Common Size</th>
              <th scope="col">Usually Best</th>
              <th scope="col" style="text-align:right;">Action</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style="font-weight:700; color:#0F172A;">Toyota Land Cruiser</td>
              <td style="color:#475569;">285/60 R18, 275/60 R20</td>
              <td style="color:#2563FF; font-weight:600;">Highway, A/T if you drive in sand</td>
              <td style="text-align:right;"><a class="get-quote-link" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20need%20a%20tyre%20quote%20for%20Toyota%20Land%20Cruiser." target="_blank" rel="noopener"><span>Get Quote</span> &rarr;</a></td>
            </tr>
            <tr>
              <td style="font-weight:700; color:#0F172A;">Nissan Patrol</td>
              <td style="color:#475569;">285/50 R20, 275/60 R20</td>
              <td style="color:#2563FF; font-weight:600;">Highway, A/T if you drive in sand</td>
              <td style="text-align:right;"><a class="get-quote-link" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20need%20a%20tyre%20quote%20for%20Nissan%20Patrol." target="_blank" rel="noopener"><span>Get Quote</span> &rarr;</a></td>
            </tr>
            <tr>
              <td style="font-weight:700; color:#0F172A;">Toyota Prado</td>
              <td style="color:#475569;">265/65 R17, 265/60 R18</td>
              <td style="color:#2563FF; font-weight:600;">Highway or A/T</td>
              <td style="text-align:right;"><a class="get-quote-link" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20need%20a%20tyre%20quote%20for%20Toyota%20Prado." target="_blank" rel="noopener"><span>Get Quote</span> &rarr;</a></td>
            </tr>
            <tr>
              <td style="font-weight:700; color:#0F172A;">Mitsubishi Pajero</td>
              <td style="color:#475569;">265/60 R18</td>
              <td style="color:#2563FF; font-weight:600;">Highway</td>
              <td style="text-align:right;"><a class="get-quote-link" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20need%20a%20tyre%20quote%20for%20Mitsubishi%20Pajero." target="_blank" rel="noopener"><span>Get Quote</span> &rarr;</a></td>
            </tr>
            <tr>
              <td style="font-weight:700; color:#0F172A;">Toyota Fortuner</td>
              <td style="color:#475569;">265/65 R17</td>
              <td style="color:#2563FF; font-weight:600;">Highway or A/T</td>
              <td style="text-align:right;"><a class="get-quote-link" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20need%20a%20tyre%20quote%20for%20Toyota%20Fortuner." target="_blank" rel="noopener"><span>Get Quote</span> &rarr;</a></td>
            </tr>
            <tr>
              <td style="font-weight:700; color:#0F172A;">Toyota Hilux</td>
              <td style="color:#475569;">265/65 R17, 265/60 R18</td>
              <td style="color:#2563FF; font-weight:600;">A/T</td>
              <td style="text-align:right;"><a class="get-quote-link" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20need%20a%20tyre%20quote%20for%20Toyota%20Hilux." target="_blank" rel="noopener"><span>Get Quote</span> &rarr;</a></td>
            </tr>
            <tr>
              <td style="font-weight:700; color:#0F172A;">Ford Explorer</td>
              <td style="color:#475569;">255/50 R20, 235/55 R19</td>
              <td style="color:#2563FF; font-weight:600;">Highway</td>
              <td style="text-align:right;"><a class="get-quote-link" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20need%20a%20tyre%20quote%20for%20Ford%20Explorer." target="_blank" rel="noopener"><span>Get Quote</span> &rarr;</a></td>
            </tr>
            <tr>
              <td style="font-weight:700; color:#0F172A;">Chevrolet Tahoe</td>
              <td style="color:#475569;">275/60 R20</td>
              <td style="color:#2563FF; font-weight:600;">Highway</td>
              <td style="text-align:right;"><a class="get-quote-link" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20need%20a%20tyre%20quote%20for%20Chevrolet%20Tahoe." target="_blank" rel="noopener"><span>Get Quote</span> &rarr;</a></td>
            </tr>
            <tr>
              <td style="font-weight:700; color:#0F172A;">Jeep Wrangler</td>
              <td style="color:#475569;">255/75 R17, 285/70 R17</td>
              <td style="color:#2563FF; font-weight:600;">A/T or M/T</td>
              <td style="text-align:right;"><a class="get-quote-link" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20need%20a%20tyre%20quote%20for%20Jeep%20Wrangler." target="_blank" rel="noopener"><span>Get Quote</span> &rarr;</a></td>
            </tr>
            <tr>
              <td style="font-weight:700; color:#0F172A;">Mercedes G-Class</td>
              <td style="color:#475569;">275/50 R20</td>
              <td style="color:#2563FF; font-weight:600;">Highway or A/T</td>
              <td style="text-align:right;"><a class="get-quote-link" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20need%20a%20tyre%20quote%20for%20Mercedes%20G-Class." target="_blank" rel="noopener"><span>Get Quote</span> &rarr;</a></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</section>

<!-- 4. LOAD RATING ON HEAVY SUVS -->
<!-- H2 3: Load rating on heavy SUVs -->
<section class="tv-section-block" style="background:#ffffff;">
  <div class="wrap">
    <div class="center tv-section-head">
      <span class="eyebrow">&bull; CRUCIAL SAFETY STANDARD &bull;</span>
      <h2>Load rating on heavy SUVs</h2>
      <p class="lead">Why tyre load capacity is non-negotiable for large vehicles in extreme summer heat.</p>
    </div>

    <div class="tv-4x4-load-block">
      <div class="tv-4x4-load-grid">
        <div>
          <span class="tv-4x4-load-badge-pill">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            Critical UAE Summer Safety Rule
          </span>
          <h3 style="font-size:1.45rem; font-weight:800; color:#0F172A; margin:0 0 12px 0;">Never compromise on load index</h3>
          <p style="font-size:1.02rem; line-height:1.7; color:#334155; margin:0 0 16px 0;">The 116 or 121 after the size is the load index. Fitting a lower rating to save a few hundred dirhams on a loaded Patrol in July is the most dangerous saving in this market. We won’t sell one.</p>
          <p style="font-size:1.02rem; line-height:1.7; color:#334155; margin:0;">Heavy 4x4s like the Nissan Patrol and Toyota Land Cruiser weigh approximately 2.8 tonnes unloaded. Fully loaded with passengers, luggage, and desert recovery gear, gross vehicle weight easily surpasses 3.3 tonnes. At sustained 140 km/h highway speeds in 50&deg;C summer temperatures, an under-rated passenger tyre flexes excessively, building fatal heat that leads to catastrophic sidewall blowout.</p>
        </div>
        <div class="tv-4x4-load-card">
          <div style="display:flex; align-items:center; gap:10px;">
            <div style="width:36px; height:36px; border-radius:8px; background:#EFF6FF; color:#2563FF; display:flex; align-items:center; justify-content:center; font-weight:800;">116</div>
            <div>
              <div style="font-weight:800; color:#0F172A; font-size:0.95rem;">1,250 kg Max Load per Tyre</div>
              <div style="font-size:0.8rem; color:#64748B;">Standard requirement for LC200 &amp; Prado</div>
            </div>
          </div>
          <div style="border-top:1px solid #E2E8F0; padding-top:10px; display:flex; align-items:center; gap:10px;">
            <div style="width:36px; height:36px; border-radius:8px; background:#EFF6FF; color:#2563FF; display:flex; align-items:center; justify-content:center; font-weight:800;">121</div>
            <div>
              <div style="font-weight:800; color:#0F172A; font-size:0.95rem;">1,450 kg Heavy Duty Load</div>
              <div style="font-size:0.8rem; color:#64748B;">Recommended for Patrol Y62 with full gear</div>
            </div>
          </div>
          <div style="margin-top:8px;">
            <a class="tv-btn-wa-green" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20please%20verify%20the%20load%20index%20for%20my%204x4." target="_blank" rel="noopener" style="width:100%; justify-content:center; padding:10px 14px; font-size:clamp(0.82rem, 2.5vw, 0.9rem); white-space:normal; text-align:center; line-height:1.35;">
              <span>Check My 4x4 Load Rating on WhatsApp</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- 5. TYRES FOR DESERT DRIVING -->
<!-- H2 4: Tyres for desert driving -->
<section class="tv-section-block" style="background:#F8FAFC;">
  <div class="wrap">
    <div class="tv-4x4-knowledge-grid">
      <div class="tv-4x4-knowledge-img-wrap">
        <img src="/static/assets/images/4x4/desert_tyre_vehicle.png" alt="Desert Ready Always - 4x4 Tyre on UAE Sand Dunes" loading="lazy">
      </div>
      <div class="tv-4x4-knowledge-content">
        <span class="eyebrow" style="color:#2563FF; font-weight:800; font-size:0.82rem; letter-spacing:0.1em; text-transform:uppercase;">&bull; DESERT EXPEDITIONS &bull;</span>
        <h2 style="font-size:clamp(1.85rem, 3.2vw, 2.4rem); font-weight:800; color:#0F172A; margin:8px 0 12px 0;">Tyres for desert driving</h2>
        <p style="font-size:1.02rem; line-height:1.65; color:#475569; margin:0 0 24px 0;">Sidewall strength, deflating to 15&ndash;18 psi for sand, and re-inflating before rejoining the highway &mdash; driving on tarmac at sand pressure is how sidewalls fail.</p>

        <div class="tv-4x4-knowledge-cards">
          <!-- Card 1 -->
          <div class="tv-4x4-knowledge-card">
            <div class="tv-4x4-k-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            </div>
            <h4>Deflate to 15&ndash;18 PSI for Sand</h4>
            <p>Dropping tyre pressure expands the contact patch by over 30%, allowing your 4x4 to "float" across soft sand dunes without sinking.</p>
          </div>

          <!-- Card 2 -->
          <div class="tv-4x4-knowledge-card">
            <div class="tv-4x4-k-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            </div>
            <h4>Sidewall Strength &amp; Flexibility</h4>
            <p>Look for flexible 2-ply or 3-ply polyester sidewalls that bag out evenly without popping off the rim in sharp dune bowls.</p>
          </div>

          <!-- Card 3 -->
          <div class="tv-4x4-knowledge-card">
            <div class="tv-4x4-k-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/></svg>
            </div>
            <h4>Re-inflate Before Highway Tarmac</h4>
            <p>Driving on deflated tyres at 120 km/h on paved tarmac overheats rubber instantly, leading to irreversible sidewall failure. Always re-inflate to 32&ndash;35 PSI.</p>
          </div>

          <!-- Card 4 -->
          <div class="tv-4x4-knowledge-card">
            <div class="tv-4x4-k-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/><line x1="4.93" y1="4.93" x2="9.17" y2="9.17"/><line x1="14.83" y1="14.83" x2="19.07" y2="19.07"/></svg>
            </div>
            <h4>Wheel Rim Sizing for Sand</h4>
            <p>Avoid 21&quot; or 22&quot; low-profile rims for desert driving; 17&quot; or 18&quot; rims provide substantial sidewall cushion and protection.</p>
          </div>
        </div>

        <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap; margin-top:24px;">
          <a class="tv-btn-wa-green" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20have%20a%20question%20about%20desert%204x4%20tyres." target="_blank" rel="noopener">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="currentColor"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.46 1.32 4.96L2 22l5.25-1.38a9.9 9.9 0 004.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91C21.96 6.45 17.5 2 12.04 2zm5.8 14.06c-.24.68-1.42 1.31-1.96 1.36-.54.05-1.04.24-3.52-.73-2.99-1.18-4.86-4.29-5.01-4.49-.15-.2-1.2-1.6-1.2-3.05 0-1.45.76-2.16 1.03-2.46.27-.29.59-.37.78-.37s.39 0 .56.01c.18.01.42-.07.66.5.24.59.83 2.03.9 2.18.07.15.12.32.02.51-.1.2-.15.32-.29.5s-.3.4-.43.53c-.15.15-.3.31-.13.6.17.29.76 1.25 1.62 2.02 1.11.99 2.05 1.3 2.34 1.45.29.15.46.12.63-.07.17-.2.73-.85.92-1.14.2-.29.39-.24.66-.15.27.1 1.71.81 2 .96.29.15.49.22.56.34.07.13.07.75-.17 1.43z"/></svg>
            <span>Ask Our Off-Road Team on WhatsApp</span>
          </a>
          <a class="tv-btn-white-pill" href="tel:+971505069575">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6.62 10.79a15.05 15.05 0 006.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1C10.4 21 3 13.6 3 4.5 3 3.95 3.45 3.5 4 3.5h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"/></svg>
            <span>+971 50 506 9575</span>
          </a>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- 6. 4X4 TYRE PRICES & INTERNAL LINKS -->
<!-- H2 5: 4x4 tyre prices -->
<section class="tv-section-block" style="background:#ffffff;">
  <div class="wrap">
    <div class="center tv-section-head">
      <span class="eyebrow">&bull; TRANSPARENT PRICING &bull;</span>
      <h2>4x4 tyre prices</h2>
      <p class="lead">Clear upfront pricing tiers with free workshop balancing or doorstep mobile fitting.</p>
    </div>

    <div class="tv-4x4-prices-strip">
      <div class="tv-4x4-price-card">
        <div>
          <span style="font-size:0.75rem; font-weight:800; color:#0284c7; text-transform:uppercase; letter-spacing:0.08em;">Value Tier</span>
          <h3 style="font-size:1.25rem; font-weight:800; color:#0F172A; margin:6px 0 10px 0;">Budget Highway Tyres</h3>
          <p style="font-size:0.88rem; color:#475569; line-height:1.55; margin:0 0 14px 0;">Dependable ESMA-certified highway tyres for urban driving and daily family school runs.</p>
        </div>
        <div>
          <div style="font-size:1.5rem; font-weight:800; color:#0F172A; margin-bottom:10px;">AED 280 &ndash; 450 <span style="font-size:0.85rem; font-weight:500; color:#64748B;">/ tyre</span></div>
          <a class="tv-btn-wa-green" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20need%20budget%204x4%20tyre%20options." target="_blank" rel="noopener" style="width:100%; justify-content:center; padding:10px 14px; font-size:0.88rem;">
            <span>WhatsApp for Value Options</span>
          </a>
        </div>
      </div>

      <div class="tv-4x4-price-card" style="border-color:#2563FF; box-shadow:0 8px 24px -4px rgba(37,99,255,0.12);">
        <div>
          <span style="font-size:0.75rem; font-weight:800; color:#2563FF; text-transform:uppercase; letter-spacing:0.08em;">Most Popular</span>
          <h3 style="font-size:1.25rem; font-weight:800; color:#0F172A; margin:6px 0 10px 0;">Mid-Range All-Terrain</h3>
          <p style="font-size:0.88rem; color:#475569; line-height:1.55; margin:0 0 14px 0;">The sweet spot for 80% of UAE drivers: Yokohama, Hankook, Toyo, Dunlop. High durability in summer heat.</p>
        </div>
        <div>
          <div style="font-size:1.5rem; font-weight:800; color:#0F172A; margin-bottom:10px;">AED 460 &ndash; 720 <span style="font-size:0.85rem; font-weight:500; color:#64748B;">/ tyre</span></div>
          <a class="tv-btn-wa-green" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20need%20mid-range%20All-Terrain%20tyre%20options." target="_blank" rel="noopener" style="width:100%; justify-content:center; padding:10px 14px; font-size:0.88rem;">
            <span>WhatsApp for Mid-Range</span>
          </a>
        </div>
      </div>

      <div class="tv-4x4-price-card">
        <div>
          <span style="font-size:0.75rem; font-weight:800; color:#0284c7; text-transform:uppercase; letter-spacing:0.08em;">Top Tier</span>
          <h3 style="font-size:1.25rem; font-weight:800; color:#0F172A; margin:6px 0 10px 0;">Premium Off-Road &amp; A/T</h3>
          <p style="font-size:0.88rem; color:#475569; line-height:1.55; margin:0 0 14px 0;">BFGoodrich KO2/KO3, Michelin LTX Trail, Pirelli Scorpion, Bridgestone Dueler. Ultimate durability.</p>
        </div>
        <div>
          <div style="font-size:1.5rem; font-weight:800; color:#0F172A; margin-bottom:10px;">AED 750 &ndash; 1,250+ <span style="font-size:0.85rem; font-weight:500; color:#64748B;">/ tyre</span></div>
          <a class="tv-btn-wa-green" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20need%20premium%204x4%20tyre%20options." target="_blank" rel="noopener" style="width:100%; justify-content:center; padding:10px 14px; font-size:0.88rem;">
            <span>WhatsApp for Premium</span>
          </a>
        </div>
      </div>
    </div>

    <!-- Exact internal links out mandated by build plan -->
    <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:14px; padding:20px 24px; text-align:center; margin-top:20px;">
      <p style="margin:0; font-size:1rem; line-height:1.7; color:#334155;">
        Explore our full catalogue of <a href="/tyre-brands" style="color:#2563FF; font-weight:700; text-decoration:underline;">tyre brands</a>, check our guide to <a href="/tyres-by-car" style="color:#2563FF; font-weight:700; text-decoration:underline;">tyres for your car model</a>, or compare common <a href="/tyre-sizes" style="color:#2563FF; font-weight:700; text-decoration:underline;">tyre sizes</a>. Need professional fitting in Dubai? Book our <a href="/tyre-shop-dubai" style="color:#2563FF; font-weight:700; text-decoration:underline;">tyre fitting in Dubai</a> service with free mobile van delivery across the UAE.
      </p>
    </div>
  </div>
</section>

<!-- 7. OFF-ROAD TYRE FAQS -->
<!-- H2 6: Off-road tyre FAQs -->
<section class="faq tv-section-block" style="background:#F8FAFC;">
  <div class="wrap" style="max-width:860px">
    <div class="center tv-section-head">
      <span class="eyebrow">&mdash; OFF-ROAD FAQ &mdash;</span>
      <h2>Off-road tyre FAQs</h2>
      <p class="lead">Essential questions answered on sand deflation, tyre sizes, and balancing.</p>
    </div>
    <div class="faq-list" style="margin-top:36px;">
      <!-- Item 1 -->
      <div class="faq-item active" data-faq-item>
        <button type="button" class="faq-summary" aria-expanded="true">
          <span class="faq-question-text">What is the best tyre pressure for dune bashing in Dubai?</span>
          <span class="faq-chevron-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </span>
        </button>
        <div class="faq-answer">
          <div class="faq-answer-inner">
            <div class="body"><p>Between 14 and 18 PSI is ideal for general sand driving. For standard 4x4 tyres on soft dunes, 12 to 15 PSI is ideal. For heavier SUVs like a Nissan Patrol Y62, aim for 14&ndash;15 PSI. Always re-inflate to manufacturer highway pressure (32&ndash;35 PSI) before returning to paved tarmac.</p></div>
          </div>
        </div>
      </div>

      <!-- Item 2 -->
      <div class="faq-item" data-faq-item>
        <button type="button" class="faq-summary" aria-expanded="false">
          <span class="faq-question-text">How long do All-Terrain tyres last in the UAE?</span>
          <span class="faq-chevron-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </span>
        </button>
        <div class="faq-answer">
          <div class="faq-answer-inner">
            <div class="body"><p>With regular rotation every 8,000 to 10,000 km and correct highway inflation pressures, quality All-Terrain tyres (like BFGoodrich KO2 or Yokohama Geolandar) typically last between 50,000 to 70,000 km in UAE conditions. UAE ESMA regulations mandate replacing tyres after 5 years from production date regardless of remaining tread.</p></div>
          </div>
        </div>
      </div>

      <!-- Item 3 -->
      <div class="faq-item" data-faq-item>
        <button type="button" class="faq-summary" aria-expanded="false">
          <span class="faq-question-text">Can I use Mud-Terrain (M/T) tyres for daily highway driving?</span>
          <span class="faq-chevron-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </span>
        </button>
        <div class="faq-answer">
          <div class="faq-answer-inner">
            <div class="body"><p>You can, but they are significantly louder, generate vibration at highway speeds above 100 km/h, wear faster in summer heat, and yield longer braking distances on wet city roads. Unless you tackle rocky wadis weekly, All-Terrain or Highway tyres are much better suited for daily UAE driving.</p></div>
          </div>
        </div>
      </div>

      <!-- Item 4 -->
      <div class="faq-item" data-faq-item>
        <button type="button" class="faq-summary" aria-expanded="false">
          <span class="faq-question-text">Do bigger tyres affect my speedometer?</span>
          <span class="faq-chevron-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </span>
        </button>
        <div class="faq-answer">
          <div class="faq-answer-inner">
            <div class="body"><p>Yes. Installing taller tyres increases overall rolling circumference, causing your speedometer to read slightly slower than your actual road speed (e.g. reading 115 km/h when actually travelling at 120 km/h). It also slightly increases fuel consumption due to altered final drive gearing.</p></div>
          </div>
        </div>
      </div>

      <!-- Item 5 -->
      <div class="faq-item" data-faq-item>
        <button type="button" class="faq-summary" aria-expanded="false">
          <span class="faq-question-text">Why is load rating crucial on heavy 4x4s in UAE summer heat?</span>
          <span class="faq-chevron-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </span>
        </button>
        <div class="faq-answer">
          <div class="faq-answer-inner">
            <div class="body"><p>Heavy SUVs like the Nissan Patrol and Land Cruiser weigh over 2.8 tonnes. Fitting a passenger tyre with a lower load index (such as 108 instead of 116 or 121) causes the sidewall to flex excessively, accumulating dangerous internal heat that causes tyre blowouts at 140 km/h on hot summer tarmac.</p></div>
          </div>
        </div>
      </div>

      <!-- Item 6 -->
      <div class="faq-item" data-faq-item>
        <button type="button" class="faq-summary" aria-expanded="false">
          <span class="faq-question-text">Can I fit a larger tyre size on my 4x4 without a lift kit?</span>
          <span class="faq-chevron-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </span>
        </button>
        <div class="faq-answer">
          <div class="faq-answer-inner">
            <div class="body"><p>On most popular UAE 4x4s (such as Land Cruiser LC200/LC300 and Patrol Y62), you can safely move up one profile size (e.g. from 265/65 R18 to 275/65 R18) without rubbing. For oversized 33" or 35" fitments on Jeep Wranglers or Ford Raptors, lift clearances or offset adjustments may be required.</p></div>
          </div>
        </div>
      </div>

      <!-- Item 7 -->
      <div class="faq-item" data-faq-item>
        <button type="button" class="faq-summary" aria-expanded="false">
          <span class="faq-question-text">Why do 4x4 tyres need special dynamic balancing?</span>
          <span class="faq-chevron-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </span>
        </button>
        <div class="faq-answer">
          <div class="faq-answer-inner">
            <div class="body"><p>Heavier all-terrain and mud-terrain tyres require precision 3D dynamic balancing to prevent steering vibrations at highway speeds. At our partner centres, computerized laser balancers ensure smooth ride comfort even with large, aggressive tread patterns.</p></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- 8. BOTTOM CTA SECTION -->
<section class="tv-4x4-bottom-cta">
  <div class="wrap">
    <div class="tv-4x4-bottom-grid">
      <div>
        <h2 style="font-size:clamp(1.9rem, 3.4vw, 2.6rem); font-weight:800; color:#ffffff; margin:0 0 14px 0; letter-spacing:-0.02em;">Ready to Equip Your 4x4 for the Desert?</h2>
        <p style="font-size:1.05rem; line-height:1.7; color:rgba(255,255,255,0.92); margin:0 0 28px 0; max-width:620px;">WhatsApp our off-road specialists. We recommend the optimal All-Terrain or Mud-Terrain fitment and schedule free workshop or mobile fitting.</p>
        <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
          <a class="tv-btn-wa-green" href="https://wa.me/971505069575?text=Hi%20TyresVision%2C%20I%20am%20ready%20to%20equip%20my%204x4%20for%20the%20desert." target="_blank" rel="noopener">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.46 1.32 4.96L2 22l5.25-1.38a9.9 9.9 0 004.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91C21.96 6.45 17.5 2 12.04 2zm5.8 14.06c-.24.68-1.42 1.31-1.96 1.36-.54.05-1.04.24-3.52-.73-2.99-1.18-4.86-4.29-5.01-4.49-.15-.2-1.2-1.6-1.2-3.05 0-1.45.76-2.16 1.03-2.46.27-.29.59-.37.78-.37s.39 0 .56.01c.18.01.42-.07.66.5.24.59.83 2.03.9 2.18.07.15.12.32.02.51-.1.2-.15.32-.29.5s-.3.4-.43.53c-.15.15-.3.31-.13.6.17.29.76 1.25 1.62 2.02 1.11.99 2.05 1.3 2.34 1.45.29.15.46.12.63-.07.17-.2.73-.85.92-1.14.2-.29.39-.24.66-.15.27.1 1.71.81 2 .96.29.15.49.22.56.34.07.13.07.75-.17 1.43z"/></svg>
            <span>WhatsApp for 4x4 Quote</span>
          </a>
          <a class="tv-btn-white-pill" href="tel:+971505069575">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6.62 10.79a15.05 15.05 0 006.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1C10.4 21 3 13.6 3 4.5 3 3.95 3.45 3.5 4 3.5h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"/></svg>
            <span>Call +971 50 506 9575</span>
          </a>
        </div>
      </div>

      <div class="tv-4x4-bottom-badges-list">
        <div class="tv-4x4-bottom-badge-item">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
          <span>Free fitting across Dubai, Abu Dhabi &amp; Sharjah</span>
        </div>
        <div class="tv-4x4-bottom-badge-item">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
          <span>Expert advice on tyre sizes &amp; brands</span>
        </div>
        <div class="tv-4x4-bottom-badge-item">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>
          <span>Mobile van fitting at your location</span>
        </div>
        <div class="tv-4x4-bottom-badge-item">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
          <span>Trusted by 7,000+ UAE drivers</span>
        </div>
      </div>
    </div>
  </div>
</section>
"""
