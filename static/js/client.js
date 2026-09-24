(function(){
  var WA = "971505069575";
  var yrEl = document.getElementById('yr');
  if(yrEl) yrEl.textContent = new Date().getFullYear();

  var form = document.getElementById('quoteForm');
  if(form){
    form.addEventListener('submit', function(e){
      e.preventDefault();
      var sizeEl = document.getElementById('tyreSize');
      var size = sizeEl ? sizeEl.value.trim() : '';
      if(!size){ if(sizeEl){ sizeEl.focus(); sizeEl.style.borderColor = '#C0392B'; } return; }

      var makeEl = document.getElementById('carMake');
      var make = makeEl ? makeEl.value.trim() : '';
      var emirateEl = document.getElementById('emirate');
      var emirate = emirateEl ? emirateEl.value : '';
      var fittingEl = document.getElementById('fitting');
      var fitting = fittingEl ? fittingEl.value : '';

      var lines = ["Hi Online Tyre Shop, I'd like a tyre quote.", "Tyre size: " + size];
      if(make) lines.push("Car: " + make);
      if(emirate) lines.push("Emirate: " + emirate);
      if(fitting) lines.push("Fitting: " + fitting);

      // Save enquiry record in existing hdweb_enquiry table
      try {
        fetch('/api/v1/enquiry', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify({
            tyre_size: size,
            vehicle: make,
            city: emirate,
            spec: fitting,
            enquiry_for: 'Tyre Quote (WhatsApp Home Banner)',
            form_type: 'home_banner_whatsapp',
            message: lines.join("\n")
          })
        }).catch(function(err){
          console.warn('Enquiry store error:', err);
        });
      } catch (err) {
        console.warn(err);
      }

      // Open WhatsApp with pre-filled message
      window.open("https://wa.me/" + WA + "?text=" + encodeURIComponent(lines.join("\n")), "_blank", "noopener");
    });

    var sizeInput = document.getElementById('tyreSize');
    if(sizeInput){
      sizeInput.addEventListener('input', function(){ this.style.borderColor = ''; });
    }
  }

  /* ---------- Ownership notice modal ---------- */
  window.openNotice = function(e) {
    if (e && e.preventDefault) e.preventDefault();
    var body = document.body;
    if (window.Alpine && body._x_dataStack && body._x_dataStack.length) {
      body._x_dataStack[0].noticeModalOpen = true;
    }
    var m = document.getElementById('noticeModal');
    if (m) {
      m.style.setProperty('display', 'flex', 'important');
      m.classList.add('open');
      m.removeAttribute('x-cloak');
    }
    document.documentElement.classList.add('modal-open');
    document.body.classList.add('modal-open');
    var sheetBody = m ? m.querySelector('.sheet-body') : null;
    if (sheetBody) sheetBody.scrollTop = 0;
    var closeBtn = document.getElementById('noticeClose');
    if (closeBtn && window.innerWidth > 820) closeBtn.focus();
  };

  window.closeNotice = function(e) {
    if (e && e.preventDefault) e.preventDefault();
    var body = document.body;
    if (window.Alpine && body._x_dataStack && body._x_dataStack.length) {
      body._x_dataStack[0].noticeModalOpen = false;
    }
    var m = document.getElementById('noticeModal');
    if (m) {
      m.style.setProperty('display', 'none', 'important');
      m.classList.remove('open');
    }
    document.documentElement.classList.remove('modal-open');
    document.body.classList.remove('modal-open');
  };

  // Bind click handlers globally (catches dynamically rendered or static triggers)
  document.addEventListener('click', function(e) {
    var trigger = e.target && e.target.closest && e.target.closest('a[href="#notice"], [data-notice]');
    if (trigger) {
      e.preventDefault();
      window.openNotice(e);
      return;
    }
    var closeBtn = e.target && e.target.closest && e.target.closest('#noticeClose, #noticeClose2, [data-notice-close]');
    if (closeBtn) {
      e.preventDefault();
      window.closeNotice(e);
      return;
    }
    var modal = document.getElementById('noticeModal');
    if (modal && (e.target === modal || (e.target && e.target.classList && e.target.classList.contains('notice-modal-dialog')))) {
      window.closeNotice(e);
    }
  }, true); // Use capture phase so stopPropagation inside dialog won't block it!

  window.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      var modal = document.getElementById('noticeModal');
      if (modal && (modal.style.display === 'flex' || modal.classList.contains('open') || (window.Alpine && document.body._x_dataStack && document.body._x_dataStack[0] && document.body._x_dataStack[0].noticeModalOpen))) {
        closeNotice();
      }
    }
  });

  if (window.location.hash === '#notice') {
    setTimeout(openNotice, 150);
  }

  /* ---------- Mobile Navigation Drawer ---------- */
  function initMobileNav() {
    var menuBtn = document.getElementById('mobileMenuBtn');
    var drawer = document.getElementById('mobileNavDrawer');
    var backdrop = document.getElementById('mobileNavBackdrop');
    var closeBtn = document.getElementById('mobileNavClose');

    function openMobileNav() {
      var d = document.getElementById('mobileNavDrawer');
      var b = document.getElementById('mobileNavBackdrop');
      var m = document.getElementById('mobileMenuBtn');
      if (d) d.classList.add('open');
      if (b) b.classList.add('open');
      if (m) m.setAttribute('aria-expanded', 'true');
      document.body.style.overflow = 'hidden';
    }

    function closeMobileNav() {
      var d = document.getElementById('mobileNavDrawer');
      var b = document.getElementById('mobileNavBackdrop');
      var m = document.getElementById('mobileMenuBtn');
      if (d) d.classList.remove('open');
      if (b) b.classList.remove('open');
      if (m) m.setAttribute('aria-expanded', 'false');
      document.body.style.overflow = '';
    }

    if (menuBtn) menuBtn.addEventListener('click', openMobileNav);
    if (closeBtn) closeBtn.addEventListener('click', closeMobileNav);
    if (backdrop) backdrop.addEventListener('click', closeMobileNav);

    if (drawer) {
      var links = drawer.querySelectorAll('a');
      for (var i = 0; i < links.length; i++) {
        links[i].addEventListener('click', function() {
          closeMobileNav();
        });
      }
    }

    window.addEventListener('keydown', function(e) {
      var d = document.getElementById('mobileNavDrawer');
      if (e.key === 'Escape' && d && d.classList.contains('open')) {
        closeMobileNav();
      }
    });
  }

  /* ---------- Global .btn-wa & WhatsApp Click Capture ---------- */
  document.addEventListener('click', function(e) {
    var target = e.target && e.target.closest ? e.target.closest('.btn-wa, .float-wa, a[href*="wa.me"], button[data-wa]') : null;
    if (!target) return;

    // If it's the submit button inside quoteForm, let the form submit event handle it with full input values
    if (target.closest && target.closest('#quoteForm') && (target.type === 'submit' || target.tagName === 'BUTTON')) {
      return;
    }

    var href = target.getAttribute('href') || '';
    var ctaText = (target.textContent || '').trim();
    var pageUrl = window.location.pathname || '/';

    var messageText = 'Direct WhatsApp CTA Click';
    if (href && href.indexOf('text=') !== -1) {
      try {
        var match = href.match(/text=([^&]+)/);
        if (match && match[1]) {
          messageText = decodeURIComponent(match[1]);
        }
      } catch (err) {}
    } else if (ctaText) {
      messageText = 'Clicked: ' + ctaText;
    }

    var formType = 'whatsapp_button_click';
    if (target.classList && target.classList.contains('float-wa')) {
      formType = 'floating_whatsapp_widget';
    } else if (target.closest && target.closest('.nav-cta')) {
      formType = 'header_nav_whatsapp';
    } else if (target.closest && (target.closest('.mobile-sticky-cta') || target.closest('.mobile-nav-cta'))) {
      formType = 'mobile_whatsapp_bar';
    }

    // Extract structured tyre size, vehicle, and brand from element or ancestors
    var tyreSize = target.getAttribute('data-tyre-size') || (target.closest && target.closest('[data-tyre-size]') ? target.closest('[data-tyre-size]').getAttribute('data-tyre-size') : '') || '';
    var vehicle = target.getAttribute('data-vehicle') || (target.closest && target.closest('[data-vehicle]') ? target.closest('[data-vehicle]').getAttribute('data-vehicle') : '') || '';
    var brand = target.getAttribute('data-brand') || (target.closest && target.closest('[data-brand]') ? target.closest('[data-brand]').getAttribute('data-brand') : '') || '';
    var customFormType = target.getAttribute('data-form-type') || (target.closest && target.closest('[data-form-type]') ? target.closest('[data-form-type]').getAttribute('data-form-type') : '') || '';
    var customEnquiryFor = target.getAttribute('data-enquiry-for') || (target.closest && target.closest('[data-enquiry-for]') ? target.closest('[data-enquiry-for]').getAttribute('data-enquiry-for') : '') || '';

    // Intelligent regex parsing fallback from messageText
    if (!tyreSize && messageText) {
      var sm = messageText.match(/\b([1-3]\d{2}\s*\/\s*\d{2}\s*(?:R|ZR|r|zr)?\s*\d{2})\b/);
      if (sm && sm[1]) tyreSize = sm[1].trim();
    }
    if (!vehicle && messageText) {
      var vm = messageText.match(/(?:tyre\s+options\s+for|options\s+for|vehicle:?)\s*([^.\n]+)/i);
      if (vm && vm[1]) vehicle = vm[1].trim();
    }
    if (!brand && messageText) {
      var bm = messageText.match(/(?:tyres\s+from|brand:?)\s*([^.\n]+)/i);
      if (bm && bm[1]) brand = bm[1].trim();
    }

    if (customFormType) {
      formType = customFormType;
    } else if (tyreSize) {
      formType = 'shop_by_size';
    } else if (vehicle) {
      formType = 'shop_by_vehicle';
    } else if (brand) {
      formType = 'shop_by_brand';
    }

    var enquiryFor = customEnquiryFor || (
      tyreSize ? ('Tyre Size Lead (' + tyreSize + ')') :
      vehicle ? ('Vehicle Tyre Lead (' + vehicle + ')') :
      brand ? ('Brand Tyre Lead (' + brand + ')') :
      ('WhatsApp Lead (' + (ctaText || 'CTA Button') + ')')
    );

    var cityAttr = target.getAttribute('data-city') || (target.closest && target.closest('[data-city]') ? target.closest('[data-city]').getAttribute('data-city') : '') || '';
    var locationAttr = target.getAttribute('data-location') || (target.closest && target.closest('[data-location]') ? target.closest('[data-location]').getAttribute('data-location') : '') || '';
    var resolvedCity = 'UAE';
    if (locationAttr && cityAttr) {
      resolvedCity = locationAttr + ', ' + cityAttr;
    } else if (locationAttr || cityAttr) {
      resolvedCity = locationAttr || cityAttr;
    }

    try {
      fetch('/api/v1/enquiry', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          enquiry_for: enquiryFor,
          form_type: formType,
          message: messageText + '\nSource Page: ' + pageUrl,
          tyre_size: tyreSize || '',
          vehicle: vehicle || '',
          spec: brand || '',
          city: resolvedCity
        })
      }).catch(function(err) {
        console.warn('Enquiry tracking error:', err);
      });
    } catch (err) {
      console.warn(err);
    }
  });

  /* ---------- Dynamic Nav Active State (Mobile Drawer) & ScrollSpy ---------- */
  function initNavActiveState() {
    var mobileLinks = document.querySelectorAll('.mobile-nav-links a');
    var allLinks = document.querySelectorAll('.nav-links a, .mobile-nav-links a');
    if (!allLinks.length) return;

    // Ensure desktop links never retain an active class
    var desktopLinks = document.querySelectorAll('.nav-links a');
    desktopLinks.forEach(function(l) { l.classList.remove('active'); });

    function setActive(targetKey) {
      if (!targetKey) return;
      mobileLinks.forEach(function(link) {
        var key = link.getAttribute('data-nav-target') || '';
        if (!key) {
          var href = link.getAttribute('href') || '';
          key = href.indexOf('#') !== -1 ? ('#' + href.split('#')[1]) : href;
        }
        if (key === targetKey) {
          link.classList.add('active');
        } else {
          link.classList.remove('active');
        }
      });
    }

    // 1. Click Listener
    allLinks.forEach(function(link) {
      link.addEventListener('click', function(e) {
        var key = link.getAttribute('data-nav-target') || '';
        if (!key) {
          var href = link.getAttribute('href') || '';
          key = href.indexOf('#') !== -1 ? ('#' + href.split('#')[1]) : href;
        }
        setActive(key);

        // If clicking hash link on current home page, handle smooth scroll
        if (key && key.startsWith('#')) {
          var targetEl = document.getElementById(key.substring(1));
          if (targetEl) {
            var path = window.location.pathname;
            var isHome = path === '/' || path === '/home';
            if (isHome) {
              e.preventDefault();
              history.pushState(null, null, key);
              targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
          }
        }
      });
    });

    // 2. Hash Change & Initial Check
    function checkHashOrTop() {
      if (window.location.hash) {
        setActive(window.location.hash);
      } else {
        var path = window.location.pathname;
        var isHome = path === '/' || path === '/home';
        if (isHome && window.scrollY < 200) {
          setActive('/');
        }
      }
    }

    window.addEventListener('hashchange', checkHashOrTop);
    checkHashOrTop();

    // 3. ScrollSpy on Home Page
    var sectionKeys = ['#faq', '#brands', '#how', '#services', '#prices', '#why'];
    var sectionMap = [];
    sectionKeys.forEach(function(k) {
      var el = document.getElementById(k.substring(1));
      if (el) sectionMap.push({ key: k, el: el });
    });

    if (sectionMap.length > 0) {
      var ticking = false;
      window.addEventListener('scroll', function() {
        if (!ticking) {
          window.requestAnimationFrame(function() {
            var scrollY = window.scrollY;
            if (scrollY < 200) {
              setActive('/');
            } else {
              var probe = scrollY + 180;
              for (var i = 0; i < sectionMap.length; i++) {
                if (probe >= sectionMap[i].el.offsetTop) {
                  setActive(sectionMap[i].key);
                  break;
                }
              }
            }
            ticking = false;
          });
          ticking = true;
        }
      }, { passive: true });
    }
  }

  /* ---------- HTML Escape & Localization Utilities ---------- */
  function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function getLocalizedText(val, locale) {
    if (!val) return '';
    if (typeof val === 'string') {
      var trimmed = val.trim();
      if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
        try {
          var parsed = JSON.parse(trimmed);
          return parsed[locale] || parsed.en || parsed.ar || Object.values(parsed)[0] || '';
        } catch (e) {}
      }
      return val;
    }
    if (typeof val === 'object') {
      return val[locale] || val.en || val.ar || Object.values(val)[0] || '';
    }
    return String(val);
  }

  /* ---------- Dynamic FAQ Section Renderer (via JS) ---------- */
  function renderFaqSections() {
    var locale = document.documentElement.getAttribute('lang') || 'en';

    // Home Page / Section FAQ (Rendered dynamically via JS)
    var homeFaqContainer = document.getElementById('home-faq-container');
    var homeFaqScript = document.getElementById('home-faq-json');

    if (homeFaqContainer && homeFaqScript) {
      try {
        var secData = JSON.parse(homeFaqScript.textContent || '{}');
        var title = getLocalizedText(secData.section_title, locale);
        var subtitle = getLocalizedText(secData.section_subtitle, locale);
        var rawFaqs = (secData.section_data && secData.section_data.faqs) ? secData.section_data.faqs : [];
        if (!Array.isArray(rawFaqs)) rawFaqs = [];

        // Keep only usable entries, then deal them alternately into two
        // independent columns so an open answer only grows its own column.
        var faqs = rawFaqs.filter(function(f) {
          return f && getLocalizedText(f.question, locale).trim();
        });

        var columnsHtml = ['', ''];
        faqs.forEach(function(f, idx) {
          var q = getLocalizedText(f.question, locale);
          var a = getLocalizedText(f.answer, locale);

          var isFirst = (idx === 0);
          var answerContent = a.trim().startsWith('<p') ? a : ('<p>' + a + '</p>');

          columnsHtml[idx % 2] += `
            <div class="faq-item ${isFirst ? 'active' : ''}" data-faq-item style="order:${idx}">
              <button type="button" class="faq-summary" aria-expanded="${isFirst ? 'true' : 'false'}">
                <span class="faq-question-text">${escapeHtml(q)}</span>
                <span class="faq-chevron-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </span>
              </button>
              <div class="faq-answer">
                <div class="faq-answer-inner">
                  <div class="body">${answerContent}</div>
                </div>
              </div>
            </div>
          `;
        });

        var itemsHtml = columnsHtml.map(function(col) {
          return `<div class="faq-col">${col}</div>`;
        }).join('');

        var headerHtml = '';
        if (subtitle || title) {
          headerHtml = `
            <div class="center">
              ${subtitle ? `<span class="eyebrow">${escapeHtml(subtitle)}</span>` : ''}
              ${title ? `<h2>${escapeHtml(title)}</h2>` : ''}
            </div>
          `;
        }

        homeFaqContainer.innerHTML = `
          ${headerHtml}
          <div style="margin-top:36px" class="faq-list">
            ${itemsHtml}
          </div>
        `;
      } catch (err) {
        console.error('Failed to render FAQ section via JS:', err);
      }
    }
  }

  /* ---------- Smooth Exclusive FAQ Accordion Engine ---------- */
  function initFaqAccordion() {
    // 1. Button-based FAQ items (Smooth CSS Grid Accordion)
    var faqButtons = document.querySelectorAll('.faq-item .faq-summary, .faq-item .faq-trigger, .faq-item .tv-faq-trigger, .faq-item button.faq-question-btn, .faq-item button[aria-expanded], [data-faq-item] button');
    faqButtons.forEach(function(btn) {
      if (btn._faqBound || btn.dataset.bound === 'true') return;
      btn._faqBound = true;
      btn.dataset.bound = 'true';

      btn.addEventListener('click', function(e) {
        e.preventDefault();
        var item = btn.closest('.faq-item, .tv-faq-item, [data-faq-item]');
        if (!item) return;
        var isAlreadyActive = item.classList.contains('active');

        // Smoothly close all other items in this list container
        var container = item.closest('.faq-list, .faq, .dynamic-faq-block, .tv-faq-container, [id^="faq"]') || item.parentElement;
        if (container) {
          var allItems = container.querySelectorAll('.faq-item, .tv-faq-item, [data-faq-item]');
          allItems.forEach(function(otherItem) {
            if (otherItem !== item && otherItem.classList.contains('active')) {
              otherItem.classList.remove('active');
              var otherBtn = otherItem.querySelector('.faq-summary, .faq-trigger, .tv-faq-trigger, button[aria-expanded]');
              if (otherBtn) otherBtn.setAttribute('aria-expanded', 'false');
              var otherIcon = otherItem.querySelector('.faq-icon');
              if (otherIcon) otherIcon.innerHTML = '+';
              var otherAnswer = otherItem.querySelector('.faq-answer');
              if (otherAnswer && otherAnswer.style.maxHeight) otherAnswer.style.maxHeight = '0px';
            }
          });
        }

        // Toggle clicked item
        if (isAlreadyActive) {
          item.classList.remove('active');
          btn.setAttribute('aria-expanded', 'false');
          var icon = item.querySelector('.faq-icon');
          if (icon) icon.innerHTML = '+';
          var answer = item.querySelector('.faq-answer');
          if (answer && answer.style.maxHeight) answer.style.maxHeight = '0px';
        } else {
          item.classList.add('active');
          btn.setAttribute('aria-expanded', 'true');
          var icon = item.querySelector('.faq-icon');
          if (icon) icon.innerHTML = '&minus;';
          var answer = item.querySelector('.faq-answer');
          if (answer && answer.style.maxHeight) {
            var inner = answer.querySelector('.faq-answer-inner');
            answer.style.maxHeight = ((inner ? inner.scrollHeight : 200) + 40) + 'px';
          }
        }
      });
    });

    // 2. Native <details> fallback support
    var allDetails = document.querySelectorAll('.faq details, .faq-list details, details.faq-item');
    allDetails.forEach(function(detail) {
      if (detail._faqBound || detail.dataset.bound === 'true') return;
      detail._faqBound = true;
      detail.dataset.bound = 'true';

      detail.addEventListener('toggle', function() {
        if (this.open) {
          detail.classList.add('active');
          var container = detail.closest('.faq-list, .faq') || detail.parentElement;
          if (container) {
            container.querySelectorAll('details').forEach(function(other) {
              if (other !== detail && other.open) {
                other.open = false;
                other.removeAttribute('open');
                other.classList.remove('active');
              }
            });
          }
        } else {
          detail.classList.remove('active');
        }
      });
    });
  }

  function initAll() {
    initMobileNav();
    initNavActiveState();
    renderFaqSections();
    initFaqAccordion();
    sliderInit();
  }

  // Exposed so content injected after DOMContentLoaded (e.g. dynamic
  // page/section HTML fetched and inserted by client-page-sections.js) can
  // re-scan for FAQ accordions without needing a second copy of this logic.
  window.initFaqAccordion = initFaqAccordion;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();


sliderInit = function() {

    const slides = document.querySelector(".slides");
    const slideItems = document.querySelectorAll(".slide");
    const dots = document.querySelectorAll(".dot");

    // Slider does not exist on this page
    if (!slides || slideItems.length === 0) {
        return;
    }

    let currentSlide = 0;
    const totalSlides = slideItems.length;

    function showSlide(index) {

        if (index >= totalSlides) {
            currentSlide = 0;
        } 
        else if (index < 0) {
            currentSlide = totalSlides - 1;
        } 
        else {
            currentSlide = index;
        }

        slides.style.transform =
            `translateX(-${currentSlide * 100}%)`;

        dots.forEach((dot, index) => {
            dot.classList.toggle(
                "active",
                index === currentSlide
            );
        });
    }

    window.nextSlide = function () {
        showSlide(currentSlide + 1);
    };

    window.prevSlide = function () {
        showSlide(currentSlide - 1);
    };

    window.goToSlide = function (index) {
        showSlide(index);
    };

    // Auto slide
    setInterval(function () {
        nextSlide();
    }, 3000);

};

// ==========================================================================
// TYRESVISION CMS PAGES & DYNAMIC COMPONENTS (Page.html)
// ==========================================================================
window.initTvPageComponents = function() {
    // 1. Delegate .faq-item to the primary CSS Grid FAQ accordion engine
    if (typeof window.initFaqAccordion === 'function') {
        window.initFaqAccordion();
    }

    // 1b. DataTables Responsive Expand/Collapse Accordion for Mobile Tables
    function initResponsiveDataTables() {
        var tables = document.querySelectorAll('.price-table, .tv-4x4-table, .tv-ev-table, .tv-table');
        tables.forEach(function(table) {
            // Skip if already initialized or if child rows already present
            if (table.dataset.dtrInitialized === 'true' || table.querySelector('.dtr-child-row')) {
                return;
            }

            var thead = table.querySelector('thead');
            var tbody = table.querySelector('tbody');
            if (!thead || !tbody) return;

            var headerRow = thead.querySelector('tr');
            if (!headerRow) return;

            var ths = headerRow.querySelectorAll('th');
            var colCount = ths.length;
            if (colCount < 3) return; // Only tables with collapsible intermediate columns

            table.dataset.dtrInitialized = 'true';
            table.classList.add('dtr-table');

            // Mark intermediate headers as desktop-col (hidden on mobile)
            for (var c = 1; c < colCount - 1; c++) {
                ths[c].classList.add('desktop-col');
            }

            function getDetailIcon(title) {
                var t = (title || '').toLowerCase();
                if (t.indexOf('vehicle') !== -1 || t.indexOf('car') !== -1 || t.indexOf('model') !== -1) {
                    return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.5 2.8C2.1 10.7 2 11.1 2 11.5V16c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/></svg>';
                }
                if (t.indexOf('mid') !== -1 || t.indexOf('star') !== -1) {
                    return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>';
                }
                if (t.indexOf('premium') !== -1 || t.indexOf('crown') !== -1) {
                    return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="m2 4 3 12h14l3-12-6 7-4-7-4 7-6-7zm3 16h14"/></svg>';
                }
                if (t.indexOf('value') !== -1 || t.indexOf('price') !== -1 || t.indexOf('tier') !== -1) {
                    return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>';
                }
                if (t.indexOf('size') !== -1) {
                    return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/></svg>';
                }
                if (t.indexOf('brand') !== -1 || t.indexOf('choice') !== -1) {
                    return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/></svg>';
                }
                return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polyline points="20 6 9 17 4 12"/></svg>';
            }

            var rows = Array.from(tbody.children);
            rows.forEach(function(masterRow) {
                if (masterRow.tagName !== 'TR' || masterRow.classList.contains('dtr-child-row')) return;

                var cells = masterRow.children;
                if (cells.length < colCount) return;

                masterRow.classList.add('dtr-parent-row');

                // 1. Control button in cell 0
                var firstCell = cells[0];
                var ctrlBtn = firstCell.querySelector('.dtr-control-btn');
                if (!ctrlBtn) {
                    ctrlBtn = document.createElement('button');
                    ctrlBtn.type = 'button';
                    ctrlBtn.className = 'dtr-control-btn';
                    ctrlBtn.setAttribute('aria-expanded', 'false');
                    ctrlBtn.setAttribute('aria-label', 'Toggle details');
                    ctrlBtn.innerHTML = '<span class="dtr-icon">+</span>';

                    var cellWrap = document.createElement('div');
                    cellWrap.className = 'dtr-cell-content';
                    cellWrap.appendChild(ctrlBtn);

                    while (firstCell.firstChild) {
                        cellWrap.appendChild(firstCell.firstChild);
                    }
                    firstCell.appendChild(cellWrap);
                }

                // 2. Mark intermediate cells for desktop display only
                for (var c = 1; c < colCount - 1; c++) {
                    cells[c].classList.add('desktop-col');
                }

                // 3. Create child details row
                var childRow = document.createElement('tr');
                childRow.className = 'dtr-child-row';
                childRow.style.display = 'none';

                var childTd = document.createElement('td');
                childTd.className = 'dtr-child-td';
                childTd.setAttribute('colspan', 100);

                var childDetails = document.createElement('div');
                childDetails.className = 'dtr-child-details';

                for (var c = 1; c < colCount - 1; c++) {
                    var hText = ths[c].textContent.trim();
                    var cContent = cells[c].innerHTML.trim();
                    if (!cContent) continue;

                    var detailItem = document.createElement('div');
                    detailItem.className = 'dtr-detail-item';

                    var iconHtml = getDetailIcon(hText);
                    detailItem.innerHTML =
                        '<span class="dtr-detail-title">' + iconHtml + ' ' + hText + ':</span>' +
                        '<span class="dtr-detail-value">' + cContent + '</span>';

                    childDetails.appendChild(detailItem);
                }

                childTd.appendChild(childDetails);
                childRow.appendChild(childTd);
                masterRow.insertAdjacentElement('afterend', childRow);

                // 4. Mobile Toggle Listener
                masterRow.addEventListener('click', function(e) {
                    // Ignore clicks on links or interactive buttons inside the row
                    if (e.target.closest('a') || e.target.closest('button:not(.dtr-control-btn)') || e.target.closest('input')) {
                        return;
                    }
                    if (window.innerWidth > 768) {
                        return;
                    }

                    var isExpanded = masterRow.classList.contains('dtr-expanded');

                    // Exclusive accordion: close any other expanded row in this table
                    table.querySelectorAll('.dtr-parent-row.dtr-expanded').forEach(function(otherRow) {
                        if (otherRow !== masterRow) {
                            otherRow.classList.remove('dtr-expanded');
                            var oBtn = otherRow.querySelector('.dtr-control-btn');
                            if (oBtn) {
                                oBtn.classList.remove('is-expanded');
                                oBtn.setAttribute('aria-expanded', 'false');
                                var oIcon = oBtn.querySelector('.dtr-icon');
                                if (oIcon) oIcon.textContent = '+';
                            }
                            var oChild = otherRow.nextElementSibling;
                            if (oChild && oChild.classList.contains('dtr-child-row')) {
                                oChild.classList.remove('is-open');
                                oChild.style.display = 'none';
                            }
                        }
                    });

                    if (!isExpanded) {
                        masterRow.classList.add('dtr-expanded');
                        ctrlBtn.classList.add('is-expanded');
                        ctrlBtn.setAttribute('aria-expanded', 'true');
                        var iconSpan = ctrlBtn.querySelector('.dtr-icon');
                        if (iconSpan) iconSpan.textContent = '−';
                        childRow.classList.add('is-open');
                        childRow.style.display = 'table-row';
                    } else {
                        masterRow.classList.remove('dtr-expanded');
                        ctrlBtn.classList.remove('is-expanded');
                        ctrlBtn.setAttribute('aria-expanded', 'false');
                        var iconSpan = ctrlBtn.querySelector('.dtr-icon');
                        if (iconSpan) iconSpan.textContent = '+';
                        childRow.classList.remove('is-open');
                        childRow.style.display = 'none';
                    }
                });
            });
        });
    }

    initResponsiveDataTables();

    // 2. Standalone handler for legacy .tv-faq-item ONLY (never binds to .faq-item)
    var tvFaqItems = document.querySelectorAll('.tv-faq-item:not(.faq-item)');
    tvFaqItems.forEach(function(item) {
        var summaryBtn = item.querySelector('.tv-faq-trigger');
        if (!summaryBtn) return;
        if (summaryBtn._tvFaqBound || summaryBtn.dataset.bound === 'true') return;
        summaryBtn._tvFaqBound = true;
        summaryBtn.dataset.bound = 'true';

        summaryBtn.addEventListener('click', function(e) {
            e.preventDefault();
            var isOpen = item.classList.contains('active');
            var container = item.closest('.tv-faq-container') || item.parentElement;

            // Exclusive accordion behavior within the container
            if (container) {
                container.querySelectorAll('.tv-faq-item:not(.faq-item)').forEach(function(sib) {
                    if (sib !== item) {
                        sib.classList.remove('active');
                        var sibBtn = sib.querySelector('.tv-faq-trigger');
                        if (sibBtn) sibBtn.setAttribute('aria-expanded', 'false');
                        var sibPanel = sib.querySelector('.tv-faq-panel');
                        if (sibPanel) sibPanel.style.maxHeight = '0px';
                    }
                });
            }

            if (!isOpen) {
                item.classList.add('active');
                summaryBtn.setAttribute('aria-expanded', 'true');
                var panel = item.querySelector('.tv-faq-panel');
                if (panel) panel.style.maxHeight = (panel.scrollHeight + 30) + 'px';
            } else {
                item.classList.remove('active');
                summaryBtn.setAttribute('aria-expanded', 'false');
                var panel = item.querySelector('.tv-faq-panel');
                if (panel) panel.style.maxHeight = '0px';
            }
        });
    });

    // 2. CMS Hero Quote Form Handler
    var quoteForms = document.querySelectorAll('form#quoteForm');
    quoteForms.forEach(function(qForm) {
        if (qForm.dataset.bound === 'true') return;
        qForm.dataset.bound = 'true';

        qForm.addEventListener('submit', function(e) {
            e.preventDefault();
            var sizeInput = qForm.querySelector('input[name="tyreSize"]');
            var size = sizeInput ? sizeInput.value.trim() : '';
            if (!size) {
                if (sizeInput) {
                    sizeInput.focus();
                    sizeInput.style.borderColor = '#ef4444';
                }
                return;
            }

            var makeInput = qForm.querySelector('input[name="carMake"]');
            var make = makeInput ? makeInput.value.trim() : '';
            var emirateSelect = qForm.querySelector('select[name="emirate"]');
            var emirate = emirateSelect ? emirateSelect.value : '';

            var pageTitle = document.title ? document.title.split('|')[0].trim() : 'TyresVision UAE';
            var msgLines = [
                "Hi TyresVision, I would like a tyre quote.",
                "Tyre size: " + size
            ];
            if (make) msgLines.push("Car: " + make);
            if (emirate) msgLines.push("Emirate: " + emirate);
            msgLines.push("Source: " + pageTitle);

            // Record enquiry in database asynchronously
            try {
                fetch('/api/v1/enquiry', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                    body: JSON.stringify({
                        tyre_size: size,
                        vehicle: make,
                        city: emirate,
                        enquiry_for: 'CMS Page Quote (' + pageTitle + ')',
                        form_type: 'cms_page_hero_quote',
                        message: msgLines.join("\n")
                    })
                }).catch(function() {});
            } catch (err) {}

            var waUrl = "https://wa.me/971505069575?text=" + encodeURIComponent(msgLines.join("\n"));
            window.open(waUrl, "_blank", "noopener");
        });
    });

    // 3. Open WhatsApp and external action links safely
    var extLinks = document.querySelectorAll('.tv-table-quote-btn, .tv-card-link, .tv-table-link, .chip-interactive, .get-quote-link');
    extLinks.forEach(function(link) {
        if (link.getAttribute('href') && (link.getAttribute('href').startsWith('http') || link.getAttribute('href').startsWith('https://wa.me'))) {
            link.setAttribute('target', '_blank');
            link.setAttribute('rel', 'noopener');
        }
    });

    // 4. Lift effect on Terrain Cards
    var terrainCards = document.querySelectorAll('.tv-terrain-card');
    terrainCards.forEach(function(card) {
        card.addEventListener('mouseenter', function() {
            card.style.transform = 'translateY(-6px)';
        });
        card.addEventListener('mouseleave', function() {
            card.style.transform = '';
        });
    });

    // 5. GSAP Motion & ScrollTrigger Animations
    if (typeof gsap !== 'undefined') {
        if (typeof ScrollTrigger !== 'undefined') {
            gsap.registerPlugin(ScrollTrigger);

            if (document.querySelector('.tv-terrain-grid')) {
                gsap.from('.tv-terrain-card', {
                    scrollTrigger: {
                        trigger: '.tv-terrain-grid',
                        start: 'top 95%',
                        once: true
                    },
                    y: 24,
                    duration: 0.6,
                    stagger: 0.1,
                    ease: 'power2.out',
                    clearProps: 'opacity,transform'
                });
            }

            if (document.querySelector('.tv-4x4-knowledge-grid')) {
                gsap.from('.tv-4x4-knowledge-img-wrap', {
                    scrollTrigger: {
                        trigger: '.tv-4x4-knowledge-grid',
                        start: 'top 90%',
                        once: true
                    },
                    y: 20,
                    duration: 0.7,
                    ease: 'power2.out',
                    clearProps: 'opacity,transform'
                });
                gsap.from('.tv-4x4-knowledge-card', {
                    scrollTrigger: {
                        trigger: '.tv-4x4-knowledge-grid',
                        start: 'top 90%',
                        once: true
                    },
                    y: 20,
                    duration: 0.6,
                    stagger: 0.1,
                    ease: 'power2.out',
                    clearProps: 'opacity,transform'
                });
            }
        }
    }
};

// Auto-run on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', window.initTvPageComponents);
} else {
    window.initTvPageComponents();
}

/* =============================================================================
   PRODUCT LISTING CATALOG CLIENT INTERACTIVITY
   Live filter, size search, price slider, sort, add to cart & dynamic pagination
   ============================================================================= */

window.PER_PAGE = 16;
window.currentPage = 1;
window.totalPages = 1;
window.totalCount = 0;
window.isFetching = false;

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function renderSkeletons(count) {
  const container = document.getElementById('products-grid-container');
  if (!container) return;
  const num = count || window.PER_PAGE || 16;
  
  let html = '';
  for (let i = 0; i < num; i++) {
    html += `
      <div class="tv-product-card tv-card-skeleton" aria-hidden="true">
        <!-- Top Bar Placeholder: Logo Left, Badge Right -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div class="tv-skeleton-box" style="width: 75px; height: 24px; border-radius: 6px;"></div>
          <div class="tv-skeleton-box" style="width: 80px; height: 22px; border-radius: 20px;"></div>
        </div>

        <!-- Tyre Image Placeholder (Centered, no background) -->
        <div class="tv-skeleton-box tv-skeleton-img" style="height: 180px; margin-bottom: 14px; border-radius: 12px;"></div>

        <!-- Product Title Placeholder -->
        <div class="tv-skeleton-box" style="width: 85%; height: 20px; border-radius: 6px; margin-bottom: 8px;"></div>

        <!-- Size Spec Placeholder -->
        <div class="tv-skeleton-box" style="width: 55%; height: 16px; border-radius: 4px; margin-bottom: 10px;"></div>

        <!-- Meta Pills Row Placeholder (Year, Origin, Runflat, Premium) -->
        <div style="display: flex; gap: 8px; margin-bottom: 16px;">
          <div class="tv-skeleton-box" style="width: 44px; height: 14px; border-radius: 4px;"></div>
          <div class="tv-skeleton-box" style="width: 44px; height: 14px; border-radius: 4px;"></div>
          <div class="tv-skeleton-box" style="width: 50px; height: 14px; border-radius: 4px;"></div>
          <div class="tv-skeleton-box" style="width: 55px; height: 14px; border-radius: 4px;"></div>
        </div>

        <!-- Price & Action Section -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: auto; padding-top: 10px;">
          <div>
            <div class="tv-skeleton-box" style="width: 90px; height: 24px; border-radius: 6px; margin-bottom: 4px;"></div>
            <div class="tv-skeleton-box" style="width: 105px; height: 12px; border-radius: 4px;"></div>
          </div>
          <div class="tv-skeleton-box" style="width: 110px; height: 38px; border-radius: 10px;"></div>
        </div>

        <!-- Bottom Info Strip Placeholder: In Stock | Fitted -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 14px; padding-top: 12px; border-top: 1px solid #F1F5F9;">
          <div class="tv-skeleton-box" style="width: 70px; height: 14px; border-radius: 4px;"></div>
          <div class="tv-skeleton-box" style="width: 95px; height: 14px; border-radius: 4px;"></div>
        </div>
      </div>
    `;
  }
  container.innerHTML = html;
}

function calculateSetPrice(unitPrice, qty, offerText = '') {
  let p = 0;
  if (typeof unitPrice === 'number') {
    p = unitPrice;
  } else if (unitPrice) {
    p = parseFloat(String(unitPrice).replace(/[^0-9.]/g, '')) || 0;
  }
  const q = parseInt(qty, 10) || 1;
  const offer = String(offerText || '').toUpperCase();
  let paidQty = q;

  if (offer.includes('BUY 3 GET 1')) {
    // Buy 3 Get 1 Free: for set of 3 or set of 4, customer pays for 3.
    // Handles up to 8 product qty (and beyond):
    // q=1->1, q=2->2, q=3->3, q=4->3, q=5->4, q=6->5, q=7->6, q=8->6
    const fullSets = Math.floor(q / 4);
    const remainder = q % 4;
    paidQty = (fullSets * 3) + (remainder >= 3 ? 3 : remainder);
  } else if (offer.includes('BUY 2 GET 2')) {
    // Buy 2 Get 2 Free: customer pays for 2 in every 4 tyres
    // q=1->1, q=2->2, q=3->2, q=4->2, q=5->3, q=6->4, q=7->4, q=8->4
    const fullSets = Math.floor(q / 4);
    const remainder = q % 4;
    paidQty = (fullSets * 2) + Math.min(remainder, 2);
  } else {
    // Without offer / Standard: customer pays for all tyres (1 to 8)
    // q=1->1, q=2->2, q=3->3, q=4->4, q=5->5, q=6->6, q=7->7, q=8->8
    paidQty = q;
  }

  return (paidQty * p).toFixed(2);
}

function createProductCardHTML(p) {
  const hasOffer = Boolean(p.offer_banner && String(p.offer_banner).trim());
  let offerBannerHTML = '';
  if (hasOffer) {
    const isArrival = String(p.offer_banner).toUpperCase().includes('ARRIVAL');
    const bannerClass = isArrival ? 'tv-banner-green' : 'tv-banner-blue';
    offerBannerHTML = `
      <div class="tv-card-top-banner ${bannerClass}">
        <span class="tv-offer-title">${escapeHtml(p.offer_banner)}</span>
      </div>`;
  }

  const warrantyText = escapeHtml(p.warranty || '1 Year Warranty');
  const brandName = escapeHtml(p.brand_name || '');

  // 2. Remove brand name in product name as requested
  let rawPattern = (p.pattern_name || p.display_name || 'Tyre').trim();
  if (brandName && rawPattern.toLowerCase().startsWith(brandName.toLowerCase())) {
    rawPattern = rawPattern.slice(brandName.length).trim();
  }
  rawPattern = rawPattern.replace(/^[\s\-_:]+/, '').trim();
  if (!rawPattern) rawPattern = (p.pattern_name || p.display_name || 'Tyre');
  const patternTitle = escapeHtml(rawPattern);

  const sizeSpec = escapeHtml(p.full_size_spec || p.tire_size_label || 'Standard Fit');
  const yearVal = escapeHtml(p.year || '2025');
  const originVal = escapeHtml(p.country_of_origin || 'USA');
  const runflatVal = escapeHtml(p.runflat_text || (p.is_runflat ? 'Runflat' : 'Standard'));
  const categoryVal = escapeHtml(p.tyres_category || 'Premium');

  const priceVal = typeof p.price === 'number' ? p.price : parseFloat(p.price || 0);
  const displayPrice = (priceVal % 1 === 0) ? priceVal.toFixed(0) : priceVal.toFixed(2);
  const setOf4Val = p.set_of_4_price ? (typeof p.set_of_4_price === 'number' ? p.set_of_4_price : parseFloat(p.set_of_4_price || (priceVal * 4))) : (priceVal * 4);
  const setOf4Formatted = (setOf4Val % 1 === 0) ? Math.round(setOf4Val).toLocaleString() : setOf4Val.toFixed(2);

  const rawBrandSlug = (p.brand_slug || p.brand_name || '').toLowerCase().trim().replace(/\s+/g, '-');
  const brandSlug = escapeHtml(rawBrandSlug);
  const brandLogo = p.brand_logo ? `<img src="${p.brand_logo}" alt="${brandName}" class="tv-card-brand-img" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='inline-block';"><span class="tv-card-brand-fallback" style="display:none;">${brandName}</span>` : `<span class="tv-card-brand-fallback">${brandName}</span>`;

  const imgPath = p.image_path || '/static/assets/images/no-image-available.svg';
  const cleanTitle = escapeHtml(patternTitle).replace(/'/g, "\\'");
  const fullTitle = escapeHtml(p.full_title || (brandName + ' ' + sizeSpec + ' ' + patternTitle + ' ' + yearVal));
  const widthVal = escapeHtml(p.width || '155 mm');
  const profileVal = escapeHtml(p.profile || 'None');
  const rimVal = escapeHtml(p.rim_size || 'R16');
  const loadSpeedVal = escapeHtml(p.load_speed || '86Q');
  const skuVal = escapeHtml(p.sku || ('TCKL-' + (p.id || '12726')));

  const slugVal = escapeHtml(p.slug || '');

  const badgeHTML = hasOffer
    ? `<span class="tv-card-badge tv-badge-offer">${escapeHtml(p.offer_banner)}</span>`
    : `<span class="tv-card-badge tv-badge-toprated">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="#F59E0B" stroke="#F59E0B" stroke-width="1">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
        </svg>
        <span>Top Rated</span>
      </span>`;

  return `
    <div class="tv-product-card ${hasOffer ? 'has-offer' : ''}"
         data-slug="${slugVal}"
         onclick="handleProductCardClick(event, '${slugVal}')"
         data-brand="${escapeHtml(p.brand_slug || '')}"
         data-brand-name="${brandName}"
         data-brand-logo="${escapeHtml(p.brand_logo || '')}"
         data-pattern="${patternTitle}"
         data-full-title="${fullTitle}"
         data-size="${escapeHtml(p.tire_size_label || '')}"
         data-full-spec="${sizeSpec}"
         data-width="${widthVal}"
         data-profile="${profileVal}"
         data-rim="${rimVal}"
         data-load-speed="${loadSpeedVal}"
         data-year="${yearVal}"
         data-country="${originVal}"
         data-runflat="${runflatVal}"
         data-category="${categoryVal}"
         data-warranty="${warrantyText}"
         data-sku="${skuVal}"
         data-image="${imgPath}"
         data-vehicle="${escapeHtml(p.vehicle_type || 'car')}"
         data-type="${escapeHtml(p.season || 'summer')}"
         data-price="${priceVal}"
         data-price-set2="${calculateSetPrice(priceVal, 2, p.offer_banner || '')}"
         data-price-set4="${setOf4Formatted}"
         data-offer="${escapeHtml(p.offer_banner || '')}">

      <!-- 1. Top Header Bar: Brand Logo (Left) & Top Rated / Offer Badge (Right) -->
      <div class="tv-card-header-bar">
        <a href="/tyres/brand/${encodeURIComponent(rawBrandSlug)}" class="tv-card-brand-wrap" title="View all ${brandName} tyres" onclick="event.stopPropagation();">
          ${brandLogo}
        </a>
        <div class="tv-card-badge-wrap">
          ${badgeHTML}
        </div>
      </div>

      <!-- 2. Centered Tyre Image (No background color) -->
      <div class="tv-card-img-area">
        <button class="tv-btn-quickview" onclick="event.stopPropagation(); openQuickView(this);" title="Quick view" type="button" aria-label="Quick view">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M1 12C1 12 5 4 12 4C19 4 23 12 23 12C23 12 19 20 12 20C5 20 1 12 1 12Z"></path>
            <circle cx="12" cy="12" r="3"></circle>
          </svg>
        </button>

        <a href="/${slugVal}" class="tv-card-img-link" aria-label="${patternTitle}">
          <div class="tv-card-tyre-box tv-img-loading">
            <img src="${imgPath}" 
                 alt="${patternTitle}" 
                 class="tv-product-img" 
                 loading="lazy" 
                 onload="this.parentElement.classList.remove('tv-img-loading')"
                 onerror="this.src='/static/assets/images/no-image-available.svg'; this.parentElement.classList.remove('tv-img-loading'); this.onerror=null;">
          </div>
        </a>
      </div>

      <!-- 3. Product Info Block -->
      <div class="tv-card-info-block">
        <!-- Product Pattern Name (Brand name removed) -->
        <a href="/${slugVal}" class="tv-card-pattern-link" title="${patternTitle}">
          <h3 class="tv-card-pattern">
            ${patternTitle}
          </h3>
        </a>

        <!-- 3. Product Size --> 2025 -->
        <div class="tv-card-size-row">
          <span class="tv-card-spec-text">${sizeSpec}</span>
          <span class="tv-card-year-meta" title="Manufacturing Year">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="16" y1="2" x2="16" y2="6"></line>
              <line x1="8" y1="2" x2="8" y2="6"></line>
              <line x1="3" y1="10" x2="21" y2="10"></line>
            </svg>
            <span>${yearVal}</span>
          </span>
        </div>

        <!-- 4. USA __ Runflat __ premium -->
        <div class="tv-card-meta-row">
          <span class="tv-meta-item tv-meta-country" title="Origin">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="2" y1="12" x2="22" y2="12"></line>
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
            </svg>
            <span>${originVal}</span>
          </span>

          <span class="tv-meta-item tv-meta-runflat" title="Technology">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="9"></circle>
              <circle cx="12" cy="12" r="4"></circle>
              <path d="M12 3v5"></path><path d="M12 16v5"></path><path d="M3 12h5"></path><path d="M16 12h5"></path>
            </svg>
            <span>${runflatVal}</span>
          </span>

          <span class="tv-meta-item tv-meta-premium" title="Category">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
            <span>${categoryVal}</span>
          </span>
        </div>
      </div>

      <!-- 4. Price & Add to Cart Line -->
      <div class="tv-card-price-action-row">
        <div class="tv-card-pricing-left">
          <div class="tv-card-main-price-line">
            <span class="tv-card-currency">AED</span>
            <strong class="tv-card-price-num">${displayPrice}</strong>
            <span class="tv-card-per-tyre">/tyre</span>
          </div>
          <div class="tv-card-set4-line">
            Set of 4 &bull; AED ${setOf4Formatted}
          </div>
        </div>

        <button type="button" class="tv-btn-card-add" onclick="event.stopPropagation(); addToCartWithCard(this, '${cleanTitle}', ${priceVal});" aria-label="Add to cart">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="9" cy="21" r="1"></circle>
            <circle cx="20" cy="21" r="1"></circle>
            <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
          </svg>
          <span>Add to Cart</span>
        </button>
      </div>

      <!-- 5. Bottom Info Strip: In Stock | Fitted Included -->
      <div class="tv-card-bottom-info">
        <div class="tv-stock-status">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#16A34A" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="8 12 11 15 16 9"></polyline>
          </svg>
          <span>In Stock</span>
        </div>

        <span class="tv-bottom-sep">|</span>

        <div class="tv-fitted-status">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#E02424" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path>
            <line x1="7" y1="7" x2="7.01" y2="7"></line>
          </svg>
          <span>Fitted Included</span>
          <span class="tv-fitted-info-btn" onclick="event.stopPropagation(); openFittedPriceModal(event);" role="button" tabindex="0" title="View fitted details">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="16" x2="12" y2="12"></line>
              <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
          </span>
        </div>
      </div>

    </div>
  `;
}

function addToCartWithCard(btn, title, basePrice) {
  const card = btn.closest('.tv-product-card');
  const select = card ? card.querySelector('.tv-qty-select') : null;
  const qty = select ? parseInt(select.value, 10) || 1 : 4;
  let p = basePrice;
  if (p === undefined || p === null || isNaN(p)) {
    const rawPrice = card ? (card.getAttribute('data-price') || card.querySelector('.tv-card-price-num')?.textContent || '0') : '0';
    p = parseFloat(String(rawPrice).replace(/[^0-9.]/g, '')) || 0;
  } else {
    p = parseFloat(String(p).replace(/[^0-9.]/g, '')) || 0;
  }
  const offer = card ? (card.getAttribute('data-offer') || card.querySelector('.tv-badge-offer')?.textContent?.trim() || '') : '';
  const total = calculateSetPrice(p, qty, offer);
  
  const originalHTML = btn.innerHTML;
  btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Added</span>';
  btn.style.background = '#16a34a';
  
  showToast(`Added ${qty}x ${title} to fitting cart!`);
  
  setTimeout(() => {
    btn.innerHTML = originalHTML;
    btn.style.background = '';
}

function handleProductCardClick(e, slug) {
  if (!slug) return;
  if (e.target.closest('button, select, input, a, .tv-btn-quickview, .tv-btn-card-add, .tv-card-price-note, .tv-spec-info-btn, .tv-fitted-info-btn')) {
    return;
  }
  window.location.href = '/' + encodeURIComponent(slug).replace(/%2F/g, '/');
}

let currentQuickViewProduct = null;
let currentQuickViewQty = 4;
let currentQuickViewAngle = 0;

function openQuickView(btn) {
  const card = btn.closest('.tv-product-card');
  if (!card) return;

  const modal = document.getElementById('tv-quickview-modal');
  if (!modal) return;

  const ds = card.dataset;
  const brandName = ds.brandName || card.querySelector('.tv-card-brand-fallback')?.textContent?.trim() || '';
  const brandLogo = ds.brandLogo || card.querySelector('.tv-card-brand-img')?.getAttribute('src') || '';
  const pattern = ds.pattern || card.querySelector('.tv-card-pattern-title')?.textContent?.trim() || '';
  const fullTitle = ds.fullTitle || (brandName + ' ' + (ds.fullSpec || '') + ' ' + pattern + ' ' + (ds.year || '2025')).trim();
  const width = ds.width || '155 mm';
  const profile = ds.profile || 'None';
  const rim = ds.rim || 'R16';
  const loadSpeed = ds.loadSpeed || '86Q';
  const year = ds.year || '2025';
  const country = ds.country || 'China';
  const warranty = ds.warranty || '1 Year Warranty';
  const sku = ds.sku || 'TCKL-12726';
  const size = ds.fullSpec || ds.size || `${width} ${rim} ${loadSpeed}`;
  const image = ds.image || card.querySelector('.tv-product-img')?.getAttribute('src') || '/static/assets/images/no-image-available.svg';
  const price = parseFloat(ds.price || 0);
  const vehicle = (ds.vehicle || 'car').toLowerCase();
  const vehicleLabel = vehicle === 'suv' ? 'SUV / 4x4' : (vehicle === 'van' ? 'Light Truck / Van' : 'Passenger Car');
  const season = (ds.type || 'all season').toLowerCase().includes('summer') ? 'Summer Tyre' : 'All Season';
  const offer = ds.offer || card.querySelector('.tv-card-top-banner')?.textContent?.trim() || '';

  currentQuickViewProduct = {
    brandName, brandLogo, pattern, fullTitle, width, profile, rim, loadSpeed, year, country, warranty, sku, size, image, price, vehicle, vehicleLabel, season, offer
  };
  currentQuickViewQty = 4;
  currentQuickViewAngle = 0;

  // 1. Showcase Image
  const imgEl = document.getElementById('tv-qv-img');
  if (imgEl) {
    imgEl.src = image;
    imgEl.alt = fullTitle;
    imgEl.style.transform = 'rotate(0deg)';
  }

  // 2. Main Brand Logo
  const brandImg = document.getElementById('tv-qv-brand-logo');
  const brandFallback = document.getElementById('tv-qv-brand-fallback');
  if (brandImg) {
    if (brandLogo && !brandLogo.includes('no-image') && !brandLogo.includes('undefined')) {
      brandImg.src = brandLogo;
      brandImg.alt = brandName;
      brandImg.style.display = 'inline-block';
      if (brandFallback) brandFallback.style.display = 'none';
    } else {
      brandImg.style.display = 'none';
      if (brandFallback) {
        brandFallback.textContent = brandName;
        brandFallback.style.display = 'inline-block';
      }
    }
  }

  // 3. Title & Subtitle
  const titleEl = document.getElementById('tv-qv-title');
  if (titleEl) titleEl.textContent = fullTitle;

  const subTitleEl = document.getElementById('tv-qv-subtitle');
  if (subTitleEl) subTitleEl.textContent = `Reliable performance for your daily drive. Built for durability and safety.`;

  // 4. Specifications
  const specMap = {
    'tv-qv-spec-width': width,
    'tv-qv-spec-profile': profile,
    'tv-qv-spec-rim': rim,
    'tv-qv-spec-loadspeed': loadSpeed,
    'tv-qv-spec-brand': brandName,
    'tv-qv-spec-pattern': pattern,
    'tv-qv-spec-size': size,
    'tv-qv-spec-year': year,
    'tv-qv-spec-country': country,
    'tv-qv-spec-warranty': warranty,
    'tv-qv-spec-sku': sku
  };
  Object.keys(specMap).forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = specMap[id];
  });

  // 5. Sub-features under tyre card
  const subWarranty = document.getElementById('tv-qv-subfeat-warranty');
  if (subWarranty) subWarranty.textContent = warranty;

  const subSeason = document.getElementById('tv-qv-subfeat-season');
  if (subSeason) subSeason.textContent = season;

  const subVeh = document.getElementById('tv-qv-subfeat-vehicle');
  if (subVeh) subVeh.textContent = vehicleLabel;

  const subOrigin = document.getElementById('tv-qv-subfeat-origin');
  if (subOrigin) subOrigin.textContent = `Made in ${country}`;

  // 6. Reset Stepper & Recalculate Prices
  const qtyInput = document.getElementById('tv-qv-qty-input');
  if (qtyInput) qtyInput.value = '4';
  updateQuickViewPrices();

  // 7. Contact Us Button
  const contactBtn = document.getElementById('tv-qv-contact-btn');
  if (contactBtn) {
    const msg = encodeURIComponent(`Hi, I am interested in ${fullTitle} (${sku}) priced at AED ${price.toFixed(2)}.`);
    contactBtn.href = `/contact-us?subject=Inquiry+${encodeURIComponent(sku)}&message=${msg}`;
  }

  // 8. Description Tab
  const descEl = document.getElementById('tv-qv-desc-text');
  if (descEl) {
    descEl.textContent = `${fullTitle} is engineered for reliable performance, durability and road safety. Ideal for ${vehicleLabel.toLowerCase()} and daily UAE driving conditions, it provides responsive handling, enhanced fuel efficiency and a quiet ride.`;
  }

  // Reset tab to Description
  const descTabBtn = document.querySelector('.tv-qv-tab');
  if (descTabBtn) switchQuickViewTab('desc', descTabBtn);

  // Reset Wishlist active status
  const wishBtn = document.getElementById('tv-qv-wishlist-btn');
  if (wishBtn) {
    const isWishlisted = card.querySelector('.tv-card-wishlist-btn')?.classList.contains('active');
    if (isWishlisted) wishBtn.classList.add('active');
    else wishBtn.classList.remove('active');
  }

  modal.classList.add('open');
  document.body.classList.add('tv-modal-active');
}

function updateQuickViewPrices() {
  if (!currentQuickViewProduct) return;
  const p = currentQuickViewProduct.price;
  const q = currentQuickViewQty;
  const offer = currentQuickViewProduct.offer;

  const total = calculateSetPrice(p, q, offer);
  const set2Total = calculateSetPrice(p, 2, offer);
  const set4Total = calculateSetPrice(p, 4, offer);

  const priceEl = document.getElementById('tv-qv-price');
  if (priceEl) priceEl.textContent = p.toFixed(2);

  const totalEl = document.getElementById('tv-qv-total-price');
  if (totalEl) totalEl.innerHTML = `<span class="currency-dirham tv-curr-glyph-sub">&#xe900;</span> ${total}`;

  const qtyLabelEl = document.getElementById('tv-qv-selected-qty-label');
  if (qtyLabelEl) qtyLabelEl.textContent = q;

  const set2El = document.getElementById('tv-qv-set2');
  if (set2El) set2El.innerHTML = `<span class="currency-dirham tv-curr-glyph-sub">&#xe900;</span> ${set2Total}`;

  const set4El = document.getElementById('tv-qv-set4');
  if (set4El) set4El.innerHTML = `<span class="currency-dirham tv-curr-glyph-sub">&#xe900;</span> ${set4Total}`;
}

function stepQuickViewQty(delta) {
  let newQty = currentQuickViewQty + delta;
  if (newQty < 1) newQty = 1;
  if (newQty > 8) newQty = 8;
  currentQuickViewQty = newQty;
  const input = document.getElementById('tv-qv-qty-input');
  if (input) input.value = newQty;
  updateQuickViewPrices();
}

function addQuickViewToCart(btn) {
  if (!currentQuickViewProduct) return;
  const { fullTitle, price, offer } = currentQuickViewProduct;
  const total = calculateSetPrice(price, currentQuickViewQty, offer);

  const origHTML = btn.innerHTML;
  btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg> Added';
  btn.style.background = '#008738';

  showToast(`Added ${currentQuickViewQty}x ${fullTitle} to cart!`);

  setTimeout(() => {
    btn.innerHTML = origHTML;
    btn.style.background = '';
  }, 2000);
}

function toggleQuickViewWishlist(btn) {
  btn.classList.toggle('active');
  const isSaved = btn.classList.contains('active');
  showToast(isSaved ? 'Added to your wishlist!' : 'Removed from wishlist');
}

function shareQuickViewProduct() {
  if (!currentQuickViewProduct) return;
  const title = currentQuickViewProduct.fullTitle;
  const url = window.location.href;
  if (navigator.share) {
    navigator.share({ title, text: `Check out ${title} on TyreVision UAE:`, url }).catch(() => {});
  } else {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(() => {
        showToast('Product link copied to clipboard!');
      }).catch(() => {
        showToast('Sharing link copied!');
      });
    } else {
      showToast('Link: ' + url);
    }
  }
}

function switchQuickViewTab(tabKey, btn) {
  document.querySelectorAll('.tv-qv-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');

  const tabs = ['desc', 'specs', 'reviews'];
  tabs.forEach(t => {
    const el = document.getElementById(`tv-qv-tab-${t}`);
    if (el) el.style.display = t === tabKey ? 'block' : 'none';
  });
}

function rotateQuickViewImage(dir) {
  currentQuickViewAngle += dir * 25;
  const imgEl = document.getElementById('tv-qv-img');
  if (imgEl) {
    imgEl.style.transition = 'transform 0.35s cubic-bezier(0.16, 1, 0.3, 1)';
    imgEl.style.transform = `rotate(${currentQuickViewAngle}deg) scale(1.05)`;
    setTimeout(() => {
      if (imgEl) imgEl.style.transform = `rotate(${currentQuickViewAngle}deg) scale(1)`;
    }, 350);
  }
}

function closeQuickView() {
  const modal = document.getElementById('tv-quickview-modal');
  if (modal) modal.classList.remove('open');
  const fittedModal = document.getElementById('tv-fitted-price-modal');
  if (!fittedModal || !fittedModal.classList.contains('open')) {
    document.body.classList.remove('tv-modal-active');
  }
}

function handleQuickViewBackdrop(e) {
  if (e.target.id === 'tv-quickview-modal' || e.target.classList.contains('tv-qv-modal-overlay')) {
    closeQuickView();
  }
}

function renderPaginationControls(totalP, curP) {
  const controls = document.getElementById('pagination-controls');
  if (!controls) return;

  if (totalP <= 1) {
    controls.style.display = 'none';
    return;
  }
  controls.style.display = 'flex';

  let html = '';
  // Prev button
  const prevDisabled = curP <= 1 ? 'disabled' : '';
  html += `<button type="button" class="tv-page-btn" ${prevDisabled} onclick="goToPage(${curP - 1})" aria-label="Previous page">&lsaquo;</button>`;

  // Smart page numbers
  const pagesToShow = [];
  if (totalP <= 7) {
    for (let i = 1; i <= totalP; i++) pagesToShow.push(i);
  } else {
    pagesToShow.push(1);
    if (curP > 3) pagesToShow.push('...');
    const start = Math.max(2, curP - 1);
    const end = Math.min(totalP - 1, curP + 1);
    for (let i = start; i <= end; i++) {
      if (!pagesToShow.includes(i)) pagesToShow.push(i);
    }
    if (curP < totalP - 2) pagesToShow.push('...');
    if (!pagesToShow.includes(totalP)) pagesToShow.push(totalP);
  }

  pagesToShow.forEach(p => {
    if (p === '...') {
      html += `<span class="tv-page-ellipsis">&hellip;</span>`;
    } else {
      const activeCls = p === curP ? ' active' : '';
      html += `<button type="button" class="tv-page-btn${activeCls}" onclick="goToPage(${p})">${p}</button>`;
    }
  });

  // Next button
  const nextDisabled = curP >= totalP ? 'disabled' : '';
  html += `<button type="button" class="tv-page-btn" ${nextDisabled} onclick="goToPage(${curP + 1})" aria-label="Next page">&rsaquo;</button>`;

  controls.innerHTML = html;
}

function buildFilterPath(page = 1) {
  const selectedBrands = Array.from(document.querySelectorAll('input[name="brand"]:checked')).map(cb => cb.value.trim());
  const selectedPatterns = Array.from(document.querySelectorAll('input[name="pattern"]:checked')).map(cb => cb.value.trim());
  const selectedOems = Array.from(document.querySelectorAll('input[name="oem"]:checked')).map(cb => cb.value.trim());
  const selectedWarranties = Array.from(document.querySelectorAll('input[name="warranty"]:checked')).map(cb => cb.value.trim());
  const selectedYears = Array.from(document.querySelectorAll('input[name="year"]:checked')).map(cb => cb.value.trim());
  const selectedOrigins = Array.from(document.querySelectorAll('input[name="origin"]:checked')).map(cb => cb.value.trim());
  const selectedSizes = Array.from(document.querySelectorAll('input[name="size"]:checked')).map(cb => cb.value.trim());
  const selectedVehicles = Array.from(document.querySelectorAll('input[name="vehicle_type"]:checked')).map(cb => cb.value.trim());
  const selectedTypes = Array.from(document.querySelectorAll('input[name="tire_type"]:checked')).map(cb => cb.value.trim());
  const selectedPromotions = Array.from(document.querySelectorAll('input[name="promotion"]:checked')).map(cb => cb.value.trim());
  const minPriceSlider = document.getElementById('min-price-slider');
  const minPrice = minPriceSlider ? minPriceSlider.value : '';
  const maxPriceSlider = document.getElementById('max-price-slider');
  const maxPrice = maxPriceSlider ? maxPriceSlider.value : '';
  const sortSelect = document.getElementById('sort-select');
  const sortVal = sortSelect ? sortSelect.value : 'popular';

  let currentPath = window.location.pathname;
  let basePath = '/tyres';
  const pathParts = currentPath.split('/').filter(Boolean);
  if (pathParts.length > 0 && ['ar', 'en', 'de', 'fr', 'es', 'ru', 'zh'].includes(pathParts[0].toLowerCase())) {
    basePath = '/' + pathParts[0].toLowerCase() + '/tyres';
  } else {
    basePath = '/tyres';
  }

  const segments = [];

  // 1. Page segment: page-{page}-{per_page} (e.g. page-2-16)
  if (page > 1) {
    segments.push(`page-${page}-${window.PER_PAGE || 16}`);
  }

  // 2. Brand segment: brand-pirelli
  if (selectedBrands.length > 0) {
    segments.push('brand-' + selectedBrands.map(b => encodeURIComponent(b.toLowerCase().replace(/[\s_]+/g, '-'))).join(','));
  }

  // 3. Pattern segment: pattern-energy-xm2-plus
  if (selectedPatterns.length > 0) {
    segments.push('pattern-' + selectedPatterns.map(p => encodeURIComponent(p.toLowerCase().replace(/[\s_]+/g, '-'))).join(','));
  }

  // 4. OEM Tyres segment: oem-mercedes-benz
  if (selectedOems.length > 0) {
    segments.push('oem-' + selectedOems.map(o => encodeURIComponent(o.toLowerCase().replace(/[\s_]+/g, '-'))).join(','));
  }

  // 5. Warranty segment: warranty-1-year-warranty
  if (selectedWarranties.length > 0) {
    segments.push('warranty-' + selectedWarranties.map(w => encodeURIComponent(w.toLowerCase().replace(/[\s_]+/g, '-'))).join(','));
  }

  // 6. Year segment: year-2026
  if (selectedYears.length > 0) {
    segments.push('year-' + selectedYears.map(y => encodeURIComponent(y.toLowerCase())).join(','));
  }

  // 7. Origin segment: origin-china
  if (selectedOrigins.length > 0) {
    segments.push('origin-' + selectedOrigins.map(org => encodeURIComponent(org.toLowerCase().replace(/[\s_]+/g, '-'))).join(','));
  }

  // 8. Size segment: size-225-40-r18
  if (selectedSizes.length > 0) {
    const sizeSlugs = selectedSizes.map(s => encodeURIComponent(s.toLowerCase().replace(/[\/\s_]+/g, '-')));
    segments.push('size-' + sizeSlugs.join(','));
  }

  // 9. Vehicle segment: vehicle-car
  if (selectedVehicles.length > 0) {
    segments.push('vehicle-' + selectedVehicles.map(v => encodeURIComponent(v.toLowerCase().replace(/[\s_]+/g, '-'))).join(','));
  }

  // 10. Tyre Type segment: type-summer
  if (selectedTypes.length > 0) {
    segments.push('type-' + selectedTypes.map(t => encodeURIComponent(t.toLowerCase().replace(/[\s_]+/g, '-'))).join(','));
  }

  // 11. Promotion segment: promotion-buy-3-get-1-free
  if (selectedPromotions.length > 0) {
    segments.push('promotion-' + selectedPromotions.map(pr => encodeURIComponent(pr.toLowerCase().replace(/[\s_]+/g, '-'))).join(','));
  }

  // 12. Price range segment: price-418-5668
  const sliderMin = parseFloat(minPriceSlider?.min || 0);
  const sliderMax = parseFloat(maxPriceSlider?.max || 2000);
  const curMin = minPrice !== '' ? parseFloat(minPrice) : sliderMin;
  const curMax = maxPrice !== '' ? parseFloat(maxPrice) : sliderMax;
  if (curMin > sliderMin || curMax < sliderMax) {
    segments.push(`price-${Math.round(curMin)}-${Math.round(curMax)}`);
  }

  // 13. Sort segment (Default: price-asc)
  if (sortVal && sortVal !== 'price-asc') {
    segments.push('sort-' + encodeURIComponent(sortVal.toLowerCase()));
  }

  return segments.length > 0 ? `${basePath}/${segments.join('/')}` : basePath;
}

async function fetchProducts(page = 1, scrollUp = true) {
  // Abort any prior in-flight request so user can quickly toggle filters without getting blocked
  if (window._currentAbortController) {
    try {
      window._currentAbortController.abort();
    } catch (e) {}
  }
  window._currentAbortController = new AbortController();
  const signal = window._currentAbortController.signal;

  window.isFetching = true;

  const perPage = window.PER_PAGE || 16;

  // 1. Immediately display shimmer skeletons
  renderSkeletons(perPage);

  // 2. Gather filter parameters
  const selectedBrands = Array.from(document.querySelectorAll('input[name="brand"]:checked')).map(cb => cb.value.trim());
  const selectedPatterns = Array.from(document.querySelectorAll('input[name="pattern"]:checked')).map(cb => cb.value.trim());
  const selectedOems = Array.from(document.querySelectorAll('input[name="oem"]:checked')).map(cb => cb.value.trim());
  const selectedWarranties = Array.from(document.querySelectorAll('input[name="warranty"]:checked')).map(cb => cb.value.trim());
  const selectedYears = Array.from(document.querySelectorAll('input[name="year"]:checked')).map(cb => cb.value.trim());
  const selectedOrigins = Array.from(document.querySelectorAll('input[name="origin"]:checked')).map(cb => cb.value.trim());
  const selectedSizes = Array.from(document.querySelectorAll('input[name="size"]:checked')).map(cb => cb.value.trim());
  const selectedVehicles = Array.from(document.querySelectorAll('input[name="vehicle_type"]:checked')).map(cb => cb.value.trim());
  const selectedTypes = Array.from(document.querySelectorAll('input[name="tire_type"]:checked')).map(cb => cb.value.trim());
  const selectedPromotions = Array.from(document.querySelectorAll('input[name="promotion"]:checked')).map(cb => cb.value.trim());
  const minPriceSlider = document.getElementById('min-price-slider');
  const minPrice = minPriceSlider ? minPriceSlider.value : '';
  const maxPriceSlider = document.getElementById('max-price-slider');
  const maxPrice = maxPriceSlider ? maxPriceSlider.value : '';
  const sortSelect = document.getElementById('sort-select');
  const sortVal = sortSelect ? sortSelect.value : 'price-asc';

  const params = new URLSearchParams();
  params.set('page', page);
  params.set('per_page', perPage);
  params.set('sort', sortVal || 'price-asc');

  selectedBrands.forEach(b => params.append('brand', b));
  selectedPatterns.forEach(p => params.append('pattern', p));
  selectedOems.forEach(o => params.append('oem', o));
  selectedWarranties.forEach(w => params.append('warranty', w));
  selectedYears.forEach(y => params.append('year', y));
  selectedOrigins.forEach(org => params.append('origin', org));
  selectedSizes.forEach(s => params.append('size', s));
  selectedVehicles.forEach(v => params.append('vehicle', v));
  selectedTypes.forEach(t => params.append('type', t));
  selectedPromotions.forEach(pr => params.append('promotion', pr));
  if (minPrice && parseFloat(minPrice) > parseFloat(minPriceSlider?.min || 0)) {
    params.set('min_price', minPrice);
  }
  if (maxPrice && parseFloat(maxPrice) < parseFloat(maxPriceSlider?.max || 2000)) {
    params.set('max_price', maxPrice);
  }

  // Keep browser URL clean; preserve or set /tyres/brand/<brand_slug> when 1 brand is selected
  let basePrefix = '/tyres';
  const pathParts = window.location.pathname.split('/').filter(Boolean);
  if (pathParts.length > 0 && ['ar', 'en', 'de', 'fr', 'es', 'ru', 'zh'].includes(pathParts[0].toLowerCase())) {
    basePrefix = '/' + pathParts[0].toLowerCase() + '/tyres';
  } else if (window.location.pathname.startsWith('/car-tyres')) {
    basePrefix = '/car-tyres';
  } else if (window.location.pathname.startsWith('/products')) {
    basePrefix = '/products';
  }

  let cleanBasePath = basePrefix + '/';
  if (selectedBrands.length === 1) {
    cleanBasePath = basePrefix + '/brand/' + encodeURIComponent(selectedBrands[0].toLowerCase());
  }

  if (window.location.pathname !== cleanBasePath || window.location.search) {
    window.history.replaceState({ page: page, base: cleanBasePath }, '', cleanBasePath);
  }

  try {
    const res = await fetch(`/api/products?${params.toString()}`, {
      headers: { 'Accept': 'application/json' },
      signal: signal
    });
    if (!res.ok) throw new Error('Network error loading products');
    const data = await res.json();

    window.currentPage = data.page || 1;
    window.totalPages = data.total_pages || 1;
    window.totalCount = data.total || 0;

    const container = document.getElementById('products-grid-container');
    if (!container) return;

    if (!data.products || data.products.length === 0) {
      container.innerHTML = `
        <div class="tv-empty-catalog" style="grid-column: 1 / -1; text-align: center; padding: 60px 20px; background: #fff; border-radius: 16px; border: 1px dashed #CBD5E1;">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="1.5" style="margin: 0 auto 16px; display: block;"><circle cx="12" cy="12" r="10"/><path d="M16 16s-1.5-2-4-2-4 2-4 2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>
          <h3 style="font-size: 1.25rem; font-weight: 700; color: #0F172A; margin-bottom: 8px;">No Tyres Found Matching Your Criteria</h3>
          <p style="color: #64748B; font-size: 0.95rem; max-width: 420px; margin: 0 auto 16px;">Try adjusting or clearing your sidebar filters to see more tyre options.</p>
          <button type="button" class="tv-btn-clear-filters" onclick="clearAllFilters()" style="display: inline-block; width: auto; padding: 8px 20px;">Clear All Filters</button>
        </div>
      `;
    } else {
      let cardsHtml = '';
      data.products.forEach(p => {
        cardsHtml += createProductCardHTML(p);
      });
      container.innerHTML = cardsHtml;
    }

    // Update pagination info text
    const infoEl = document.getElementById('pagination-info');
    if (infoEl) {
      if (window.totalCount === 0) {
        infoEl.textContent = 'Showing 0 tyres';
      } else {
        const startIdx = (window.currentPage - 1) * perPage + 1;
        const endIdx = Math.min((window.currentPage - 1) * perPage + data.products.length, window.totalCount);
        infoEl.innerHTML = `Showing ${startIdx}&ndash;${endIdx} of ${window.totalCount.toLocaleString()} tyres`;
      }
    }

    // Update catalog count heading, hero titles, breadcrumb & document meta
    const heading = document.getElementById('catalog-count-heading');
    const heroTitle = document.getElementById('tv-hero-title');
    const heroSub = document.getElementById('tv-hero-sub');
    const breadcrumbCurrent = document.getElementById('tv-breadcrumb-current');
    const metaDesc = document.querySelector('meta[name="description"]');

    if (selectedBrands.length === 1) {
      const brandInput = document.querySelector(`input[name="brand"][value="${selectedBrands[0]}"]`);
      const brandLabel = brandInput ? (brandInput.closest('.tv-filter-item')?.querySelector('.tv-filter-item-left span:last-child')?.textContent?.trim() || selectedBrands[0]) : selectedBrands[0];
      const brandName = brandLabel.charAt(0).toUpperCase() + brandLabel.slice(1);

      document.title = `Buy ${brandName} tyres online. Fitted locally in Dubai & Abu Dhabi. | tyresvision`;
      if (metaDesc) {
        metaDesc.setAttribute('content', `Looking for ${brandName} tyres in Dubai and Abu Dhabi? Shop online from a wide selection of tyre sizes with fast delivery throughout the UAE.`);
      }
      if (breadcrumbCurrent) {
        breadcrumbCurrent.textContent = brandName;
      }
      if (heroTitle) {
        heroTitle.textContent = `Buy ${brandName} Tyres Online UAE`;
      }
      if (heroSub) {
        heroSub.textContent = `Looking for ${brandName} tyres in Dubai and Abu Dhabi? Shop online from a wide selection of tyre sizes with fast delivery throughout the UAE.`;
      }
      if (heading) {
        heading.textContent = `${window.totalCount.toLocaleString()} ${brandName} Tyres`;
      }
    } else {
      document.title = 'Car Tyres Dubai & Abu Dhabi | Buy Premium Tyres Online | TyresVision';
      if (metaDesc) {
        metaDesc.setAttribute('content', 'Shop premium car tyres online in UAE. Leading brands including Michelin, Bridgestone, Continental, Pirelli & Goodyear with free doorstep mobile fitting.');
      }
      if (breadcrumbCurrent) {
        breadcrumbCurrent.textContent = 'Car Tyres';
      }
      if (heroTitle) {
        heroTitle.textContent = 'Car Tyres';
      }
      if (heroSub) {
        heroSub.textContent = 'Choose from a wide range of premium tyres for a safer and smoother journey.';
      }
      if (heading) {
        heading.textContent = `${window.totalCount.toLocaleString()} Car Tyres`;
      }
    }

    // Update pagination controls
    renderPaginationControls(window.totalPages, window.currentPage);
    updateActiveFilterBadges();

    // Update dynamic sidebar facet counts
    if (data.facets) {
      updateSidebarFacetCounts(data.facets);
    }

    const applyCountEl = document.getElementById('tv-apply-count');
    if (applyCountEl) {
      applyCountEl.textContent = `(${window.totalCount.toLocaleString()})`;
    }

    // Smooth scroll to top of catalog
    if (scrollUp) {
      const mainCol = document.querySelector('.tv-catalog-main');
      if (mainCol) {
        mainCol.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }

  } catch (err) {
    if (err.name === 'AbortError' || signal.aborted) {
      // Intentionally aborted in favor of a newer user filter selection
      return;
    }
    console.error('Error fetching products:', err);
    showToast('Failed to load products. Please try again.');
  } finally {
    if (!signal.aborted) {
      window.isFetching = false;
    }
  }
}

function updateSidebarFacetCounts(facets) {
  if (!facets) return;

  function updateGroupItems(inputName, facetMap, isCaseInsensitive, keyTransform) {
    if (!facetMap) return;
    const inputs = document.querySelectorAll(`input[name="${inputName}"]`);
    let groupVisibleCount = 0;
    inputs.forEach(cb => {
      let val = cb.value.trim();
      if (keyTransform) val = keyTransform(val);
      if (isCaseInsensitive) val = val.toLowerCase();

      let count = facetMap[val];
      if (count === undefined) {
        const matchKey = Object.keys(facetMap).find(k => k.toLowerCase() === val.toLowerCase());
        if (matchKey !== undefined) count = facetMap[matchKey];
      }
      if (count === undefined) count = 0;

      const item = cb.closest('.tv-filter-item');
      if (item) {
        const countSpan = item.querySelector('.tv-filter-count');
        if (countSpan) {
          countSpan.textContent = count.toLocaleString();
        }
        if (count === 0 && !cb.checked) {
          item.classList.add('tv-filter-empty');
          item.style.display = 'none';
        } else {
          item.classList.remove('tv-filter-empty');
          item.style.display = '';
          groupVisibleCount++;
        }
      }
    });

    if (inputs.length > 0) {
      const groupEl = inputs[0].closest('.tv-filter-group');
      if (groupEl) {
        if (groupVisibleCount === 0) {
          groupEl.classList.add('tv-group-empty');
        } else {
          groupEl.classList.remove('tv-group-empty');
        }
      }
    }
  }

  // 1. Warranty
  updateGroupItems('warranty', facets.warranties, false);

  // 2. Year
  updateGroupItems('year', facets.years, false);

  // 3. Brand
  updateGroupItems('brand', facets.brands, true);

  // 4. Pattern
  updateGroupItems('pattern', facets.patterns, false);

  // 5. OEM Tyres
  updateGroupItems('oem', facets.oems, false);

  // 6. Origin
  updateGroupItems('origin', facets.origins, true);

  // 7. Promotion
  updateGroupItems('promotion', facets.promotions, true, val => val.replace(/-/g, '_'));
}

function refreshFilterVisibility() {
  document.querySelectorAll('.tv-filter-group').forEach(group => {
    let groupVisibleCount = 0;
    const items = group.querySelectorAll('.tv-filter-item');
    items.forEach(item => {
      const cb = item.querySelector('input[type="checkbox"]');
      const countSpan = item.querySelector('.tv-filter-count');
      let count = 0;
      if (countSpan) {
        count = parseInt(countSpan.textContent.replace(/,/g, '').trim(), 10) || 0;
      }
      if (count === 0 && (!cb || !cb.checked)) {
        item.classList.add('tv-filter-empty');
        item.style.display = 'none';
      } else {
        item.classList.remove('tv-filter-empty');
        item.style.display = '';
        groupVisibleCount++;
      }
    });

    if (items.length > 0) {
      if (groupVisibleCount === 0) {
        group.classList.add('tv-group-empty');
      } else {
        group.classList.remove('tv-group-empty');
      }
    }
  });
}

window.updateSidebarFacetCounts = updateSidebarFacetCounts;
window.refreshFilterVisibility = refreshFilterVisibility;

function goToPage(page) {
  if (page < 1 || page > window.totalPages) return;
  fetchProducts(page, true);
}

function filterProducts() {
  updateActiveFilterBadges();
  fetchProducts(1, true);
}

function sortProducts(sortBy) {
  if (window.syncCustomSortUI && sortBy) {
    window.syncCustomSortUI(sortBy);
  }
  fetchProducts(1, true);
}

function initCustomSortDropdown() {
  const customSort = document.getElementById('tv-custom-sort');
  const trigger = document.getElementById('tv-sort-trigger');
  const menu = document.getElementById('tv-sort-menu');
  const nativeSelect = document.getElementById('sort-select');
  const triggerText = document.getElementById('tv-sort-trigger-text');
  if (!customSort || !trigger || !menu) return;

  const sortLabels = {
    'price-asc': 'Price: Low to High',
    'price-desc': 'Price: High to Low'
  };

  function openDropdown() {
    customSort.classList.add('is-open');
    trigger.setAttribute('aria-expanded', 'true');
  }

  function closeDropdown() {
    customSort.classList.remove('is-open');
    trigger.setAttribute('aria-expanded', 'false');
  }

  trigger.onclick = function(e) {
    e.stopPropagation();
    if (customSort.classList.contains('is-open')) {
      closeDropdown();
    } else {
      openDropdown();
    }
  };

  menu.querySelectorAll('.tv-sort-item').forEach(item => {
    item.onclick = function(e) {
      e.stopPropagation();
      const val = item.getAttribute('data-value');
      selectSortOption(val);
      closeDropdown();
      sortProducts(val);
    };

    item.onkeydown = function(e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const val = item.getAttribute('data-value');
        selectSortOption(val);
        closeDropdown();
        sortProducts(val);
      }
    };
  });

  function selectSortOption(val) {
    if (!val) return;
    if (nativeSelect) {
      nativeSelect.value = val;
    }
    if (triggerText && sortLabels[val]) {
      triggerText.textContent = sortLabels[val];
    }
    menu.querySelectorAll('.tv-sort-item').forEach(el => {
      if (el.getAttribute('data-value') === val) {
        el.classList.add('is-active');
      } else {
        el.classList.remove('is-active');
      }
    });
  }

  window.syncCustomSortUI = selectSortOption;

  // Initialize selected state from native select value
  if (nativeSelect && nativeSelect.value) {
    selectSortOption(nativeSelect.value);
  }

  // Close when clicking outside
  document.addEventListener('click', (e) => {
    if (!customSort.contains(e.target)) {
      closeDropdown();
    }
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && customSort.classList.contains('is-open')) {
      closeDropdown();
      trigger.focus();
    }
  });
}

function updateSliderTrack() {
  const minSlider = document.getElementById('min-price-slider');
  const maxSlider = document.getElementById('max-price-slider');
  const range = document.getElementById('tv-slider-range');
  if (!minSlider || !maxSlider || !range) return;

  const min = parseFloat(minSlider.min) || 0;
  const max = parseFloat(minSlider.max) || 2000;
  const minVal = parseFloat(minSlider.value) || min;
  const maxVal = parseFloat(maxSlider.value) || max;

  const span = (max - min) || 1;
  const leftPercent = Math.max(0, Math.min(100, ((minVal - min) / span) * 100));
  const rightPercent = Math.max(0, Math.min(100, 100 - (((maxVal - min) / span) * 100)));

  range.style.left = leftPercent + '%';
  range.style.right = rightPercent + '%';
}

function updatePriceDisplay(minVal, maxVal) {
  const minLabel = document.getElementById('min-price-display');
  const maxLabel = document.getElementById('price-slider-val');
  if (minLabel) minLabel.innerHTML = '<span class="currency-dirham tv-curr-glyph-sub">&#xe900;</span> ' + Math.round(minVal).toLocaleString();
  if (maxLabel) maxLabel.innerHTML = '<span class="currency-dirham tv-curr-glyph-sub">&#xe900;</span> ' + Math.round(maxVal).toLocaleString();
}

function onPriceSliderInput(type) {
  const minSlider = document.getElementById('min-price-slider');
  const maxSlider = document.getElementById('max-price-slider');
  if (!minSlider || !maxSlider) return;

  let minVal = parseFloat(minSlider.value);
  let maxVal = parseFloat(maxSlider.value);

  // Keep min from surpassing max
  if (type === 'min') {
    if (minVal > maxVal) {
      minSlider.value = maxVal;
      minVal = maxVal;
    }
    minSlider.style.zIndex = '5';
    maxSlider.style.zIndex = '4';
  } else {
    if (maxVal < minVal) {
      maxSlider.value = minVal;
      maxVal = minVal;
    }
    maxSlider.style.zIndex = '5';
    minSlider.style.zIndex = '4';
  }

  updateSliderTrack();
  updatePriceDisplay(minVal, maxVal);
  updateActiveFilterBadges();

  clearTimeout(window._priceFilterTimer);
  window._priceFilterTimer = setTimeout(() => {
    filterProducts();
  }, 250);
}

function updatePriceFilter(val) {
  const maxSlider = document.getElementById('max-price-slider');
  if (maxSlider) {
    maxSlider.value = val;
    onPriceSliderInput('max');
  }
}

function clearAllFilters() {
  document.querySelectorAll('.tv-filter-sidebar input[type="checkbox"]').forEach(cb => {
    cb.checked = false;
  });
  const hiddenSizeBox = document.getElementById('hidden-size-filters');
  if (hiddenSizeBox) {
    hiddenSizeBox.querySelectorAll('input[type="checkbox"]').forEach(cb => {
      cb.checked = false;
    });
  }
  document.querySelectorAll('.tv-search-filter-box, .tv-search-size-box').forEach(sb => {
    sb.value = '';
  });
  document.querySelectorAll('.tv-filter-list .tv-filter-item').forEach(it => {
    it.style.display = '';
    it.classList.remove('tv-filter-empty');
  });
  document.querySelectorAll('.tv-filter-group').forEach(grp => {
    grp.classList.remove('tv-group-empty');
  });
  const minSlider = document.getElementById('min-price-slider');
  if (minSlider) {
    minSlider.value = minSlider.min;
    const minLabel = document.getElementById('min-price-display');
    if (minLabel) minLabel.innerHTML = '<span class="currency-dirham tv-curr-glyph-sub">&#xe900;</span> ' + parseInt(minSlider.min).toLocaleString();
  }
  const maxSlider = document.getElementById('max-price-slider');
  if (maxSlider) {
    maxSlider.value = maxSlider.max;
    const maxLabel = document.getElementById('price-slider-val');
    if (maxLabel) maxLabel.innerHTML = '<span class="currency-dirham tv-curr-glyph-sub">&#xe900;</span> ' + parseInt(maxSlider.max).toLocaleString();
  }
  updateSliderTrack();
  const sortSelect = document.getElementById('sort-select');
  if (sortSelect) {
    sortSelect.value = 'price-asc';
  }
  if (window.syncCustomSortUI) {
    window.syncCustomSortUI('price-asc');
  }
  updateActiveFilterBadges();
  fetchProducts(1, true);
}

function searchFilterList(inputEl, listSelector) {
  const q = (inputEl.value || '').trim().toLowerCase();
  const container = document.querySelector(listSelector);
  if (!container) return;
  const items = container.querySelectorAll('.tv-filter-item');
  items.forEach(it => {
    const cb = it.querySelector('input[type="checkbox"]');
    const isChecked = cb ? cb.checked : false;
    if (it.classList.contains('tv-filter-empty') && !isChecked) {
      it.style.display = 'none';
      return;
    }
    const text = (it.getAttribute('data-filter-name') || it.innerText || '').toLowerCase();
    if (!q || text.includes(q)) {
      it.style.display = '';
    } else {
      it.style.display = 'none';
    }
  });
}

function searchFilterSizes(query) {
  const q = query.trim().toLowerCase();
  const items = document.querySelectorAll('#filter-size-list .tv-filter-item');
  items.forEach(it => {
    const cb = it.querySelector('input[type="checkbox"]');
    const isChecked = cb ? cb.checked : false;
    if (it.classList.contains('tv-filter-empty') && !isChecked) {
      it.style.display = 'none';
      return;
    }
    const size = (it.getAttribute('data-size') || '').toLowerCase();
    if (!q || size.includes(q)) {
      it.style.display = '';
    } else {
      it.style.display = 'none';
    }
  });
}

function toggleFilterGroup(el) {
  const group = el.closest('.tv-filter-group');
  const isCurrentlyCollapsed = el.classList.contains('collapsed') || (group && group.classList.contains('is-collapsed'));
  const willCollapse = !isCurrentlyCollapsed;

  el.classList.toggle('collapsed', willCollapse);
  if (group) {
    group.classList.toggle('is-collapsed', willCollapse);
    Array.from(group.children).forEach(child => {
      if (child !== el) {
        child.style.display = willCollapse ? 'none' : '';
      }
    });
  }
}

function toggleWishlist(btn) {
  btn.classList.toggle('active');
  const isSaved = btn.classList.contains('active');
  showToast(isSaved ? 'Added to your wishlist!' : 'Removed from wishlist');
}

function addToCart(btn, title, price) {
  const originalHTML = btn.innerHTML;
  btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg> Added';
  btn.style.background = '#10B981';

  showToast('Added ' + title + ' (AED ' + price + ') to cart!');

  setTimeout(() => {
    btn.innerHTML = originalHTML;
    btn.style.background = '';
  }, 2200);
}

function showToast(msg) {
  const toast = document.getElementById('tv-toast');
  const msgEl = document.getElementById('tv-toast-msg');
  if (!toast) return;
  if (msgEl) msgEl.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 2800);
}

window.addEventListener('popstate', function() {
  if (document.getElementById('products-grid-container')) {
    window.location.reload();
  }
});

function openMobileFilter() {
  const sidebar = document.getElementById('tv-filter-sidebar');
  const backdrop = document.getElementById('tv-filter-backdrop');
  if (sidebar) sidebar.classList.add('open');
  if (backdrop) backdrop.classList.add('active');
  document.body.classList.add('filter-open');
  updateActiveFilterBadges();
}

function closeMobileFilter() {
  const sidebar = document.getElementById('tv-filter-sidebar');
  const backdrop = document.getElementById('tv-filter-backdrop');
  if (sidebar) sidebar.classList.remove('open');
  if (backdrop) backdrop.classList.remove('active');
  document.body.classList.remove('filter-open');
}

function applyMobileFilter() {
  closeMobileFilter();
  const mainCol = document.querySelector('.tv-catalog-main');
  if (mainCol) {
    mainCol.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function updateActiveFilterBadges() {
  const selectedBrands = document.querySelectorAll('input[name="brand"]:checked').length;
  const selectedPatterns = document.querySelectorAll('input[name="pattern"]:checked').length;
  const selectedOems = document.querySelectorAll('input[name="oem"]:checked').length;
  const selectedWarranties = document.querySelectorAll('input[name="warranty"]:checked').length;
  const selectedYears = document.querySelectorAll('input[name="year"]:checked').length;
  const selectedOrigins = document.querySelectorAll('input[name="origin"]:checked').length;
  const selectedSizes = document.querySelectorAll('input[name="size"]:checked').length;
  const selectedVehicles = document.querySelectorAll('input[name="vehicle_type"]:checked').length;
  const selectedTypes = document.querySelectorAll('input[name="tire_type"]:checked').length;
  const selectedPromotions = document.querySelectorAll('input[name="promotion"]:checked').length;
  
  const minSlider = document.getElementById('min-price-slider');
  const maxSlider = document.getElementById('max-price-slider');
  const isPriceActive = (minSlider && parseFloat(minSlider.value) > parseFloat(minSlider.min || 0)) ||
                        (maxSlider && parseFloat(maxSlider.value) < parseFloat(maxSlider.max || 2000));
  const priceActive = isPriceActive ? 1 : 0;
  const totalActive = selectedBrands + selectedPatterns + selectedOems + selectedWarranties + selectedYears + selectedOrigins + selectedSizes + selectedVehicles + selectedTypes + selectedPromotions + priceActive;

  const btnBadge = document.getElementById('tv-filter-badge');
  const drawerBadge = document.getElementById('tv-drawer-badge');
  const applyCount = document.getElementById('tv-apply-count');

  [btnBadge, drawerBadge].forEach(b => {
    if (!b) return;
    if (totalActive > 0) {
      b.textContent = totalActive;
      b.style.display = 'inline-flex';
    } else {
      b.style.display = 'none';
    }
  });

  const resetBtn = document.querySelector('.tv-btn-drawer-reset');
  if (resetBtn) {
    resetBtn.style.display = totalActive > 0 ? 'inline-block' : 'none';
  }

  if (applyCount && typeof window.totalCount !== 'undefined') {
    applyCount.textContent = `(${window.totalCount.toLocaleString()})`;
  }
}

window.addEventListener('resize', function() {
  if (window.innerWidth > 1024 && document.body.classList.contains('filter-open')) {
    closeMobileFilter();
  }
});

window.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && document.body.classList.contains('filter-open')) {
    closeMobileFilter();
  }
});

function initProductCatalog(config) {
  if (config) {
    if (typeof config.currentPage !== 'undefined') window.currentPage = parseInt(config.currentPage, 10) || 1;
    if (typeof config.totalPages !== 'undefined') window.totalPages = parseInt(config.totalPages, 10) || 1;
    if (typeof config.totalCount !== 'undefined') window.totalCount = parseInt(config.totalCount, 10) || 0;
    if (typeof config.perPage !== 'undefined') window.PER_PAGE = parseInt(config.perPage, 10) || 16;
  }
  function initControls() {
    renderPaginationControls(window.totalPages, window.currentPage);
    updateActiveFilterBadges();
    updateSliderTrack();
    initCustomSortDropdown();
    refreshFilterVisibility();

    // Immediately resolve shimmer loading state for any already-cached images
    document.querySelectorAll('.tv-card-img-wrap img').forEach(img => {
      if (img.complete) {
        img.parentElement.classList.remove('tv-img-loading');
      } else {
        img.addEventListener('load', () => img.parentElement.classList.remove('tv-img-loading'), { once: true });
        img.addEventListener('error', () => {
          img.src = '/static/assets/images/no-image-available.svg';
          img.parentElement.classList.remove('tv-img-loading');
        }, { once: true });
      }
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initControls);
  } else {
    initControls();
  }
}

function openFittedPriceModal(e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  let modal = document.getElementById('tv-fitted-price-modal');
  if (!modal) {
    // Dynamic fallback injection if modal markup is not present in DOM
    const modalHTML = `
    <div id="tv-fitted-price-modal" class="tv-fitted-modal-overlay" onclick="handleFittedModalBackdrop(event)" role="dialog" aria-modal="true" aria-labelledby="tv-fitted-modal-title">
      <div class="tv-fitted-modal-container" onclick="event.stopPropagation()">
        <div class="tv-fitted-modal-card">
          <div class="tv-fitted-modal-header">
            <h2 id="tv-fitted-modal-title" class="tv-fitted-modal-title">Fully Fitted <span class="tv-text-green">Price per tyre</span></h2>
            <button type="button" class="tv-fitted-modal-close" onclick="closeFittedPriceModal()" aria-label="Close modal">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          <div class="tv-fitted-modal-body">
            <p class="tv-fitted-highlight-note">There are NO EXTRAS to pay on the day of your visit - in relation to the tyre fitting.</p>
            <h3 class="tv-fitted-included-heading">THE FOLLOWING IS INCLUDED IN THE PRICE,</h3>
            <ul class="tv-fitted-features-list">
              <li>
                <span class="tv-check-icon-wrap">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </span>
                <span>VAT</span>
              </li>
              <li>
                <span class="tv-check-icon-wrap">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </span>
                <span>Fitting (Bead lock wheel etc. excluded)</span>
              </li>
              <li>
                <span class="tv-check-icon-wrap">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </span>
                <span>Balancing</span>
              </li>
              <li>
                <span class="tv-check-icon-wrap">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </span>
                <span>New rubber valve (standard valve only)</span>
              </li>
              <li>
                <span class="tv-check-icon-wrap">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </span>
                <span>Delivery to installer</span>
              </li>
              <li>
                <span class="tv-check-icon-wrap">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </span>
                <span>Disposal of old tyres</span>
              </li>
              <li>
                <span class="tv-check-icon-wrap">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </span>
                <span>On purchase of 4 tyres, 1 FREE scheduled instance of tyre rotation every 20,000kms per year</span>
              </li>
            </ul>
            <div class="tv-fitted-modal-footer">
              <button type="button" class="tv-btn-modal-done" onclick="closeFittedPriceModal()">
                Got It
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>`;
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    modal = document.getElementById('tv-fitted-price-modal');
  }
  document.body.classList.add('tv-modal-active');
  modal.classList.add('open');
}

function closeFittedPriceModal() {
  const modal = document.getElementById('tv-fitted-price-modal');
  if (modal) {
    modal.classList.remove('open');
  }
  document.body.classList.remove('tv-modal-active');
}

function handleFittedModalBackdrop(e) {
  if (e.target && (e.target.classList.contains('tv-fitted-modal-overlay') || e.target.id === 'tv-fitted-price-modal')) {
    closeFittedPriceModal();
  }
}

// Close on Escape key
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeFittedPriceModal();
    closeQuickView();
  }
});

// Expose all functions to window for DOM event handlers
window.escapeHtml = escapeHtml;
window.capitalize = capitalize;
window.renderSkeletons = renderSkeletons;
window.createProductCardHTML = createProductCardHTML;
window.calculateSetPrice = calculateSetPrice;
window.updateCardQty = updateCardQty;
window.addToCartWithCard = addToCartWithCard;
window.handleProductCardClick = handleProductCardClick;
window.openQuickView = openQuickView;
window.closeQuickView = closeQuickView;
window.handleQuickViewBackdrop = handleQuickViewBackdrop;
window.updateQuickViewPrices = updateQuickViewPrices;
window.stepQuickViewQty = stepQuickViewQty;
window.addQuickViewToCart = addQuickViewToCart;
window.toggleQuickViewWishlist = toggleQuickViewWishlist;
window.shareQuickViewProduct = shareQuickViewProduct;
window.switchQuickViewTab = switchQuickViewTab;
window.rotateQuickViewImage = rotateQuickViewImage;
window.openFittedPriceModal = openFittedPriceModal;
window.closeFittedPriceModal = closeFittedPriceModal;
window.handleFittedModalBackdrop = handleFittedModalBackdrop;
window.renderPaginationControls = renderPaginationControls;
window.buildFilterPath = buildFilterPath;
window.fetchProducts = fetchProducts;
window.goToPage = goToPage;
window.filterProducts = filterProducts;
window.sortProducts = sortProducts;
window.clearAllFilters = clearAllFilters;
window.toggleFilterGroup = toggleFilterGroup;
window.searchFilterSizes = searchFilterSizes;
window.searchFilterList = searchFilterList;
window.updatePriceFilter = updatePriceFilter;
window.onPriceSliderInput = onPriceSliderInput;
window.updateSliderTrack = updateSliderTrack;
window.updatePriceDisplay = updatePriceDisplay;
window.toggleWishlist = toggleWishlist;
window.addToCart = addToCart;
window.showToast = showToast;
window.openMobileFilter = openMobileFilter;
window.closeMobileFilter = closeMobileFilter;
window.applyMobileFilter = applyMobileFilter;
window.updateActiveFilterBadges = updateActiveFilterBadges;
window.initProductCatalog = initProductCatalog;
window.initCustomSortDropdown = initCustomSortDropdown;
window.syncCustomSortUI = typeof syncCustomSortUI !== 'undefined' ? syncCustomSortUI : null;

// ============================================================================
// PRODUCT DETAIL PAGE (PDP) INTERACTIVITY
// ============================================================================
function updatePdpPricing(qty) {
  var unitPrice = (typeof window.pdpProductPrice === 'number' && !isNaN(window.pdpProductPrice))
    ? window.pdpProductPrice
    : 121.0;
  var offer = window.pdpProductOffer || '';

  // 1. Calculate regular and offer totals
  var regularTotal = unitPrice * qty;
  var offerTotal = (typeof calculateSetPrice === 'function')
    ? parseFloat(calculateSetPrice(unitPrice, qty, offer))
    : regularTotal;
  var savings = Math.max(0, regularTotal - offerTotal);

  // 2. Update price in dynamic "Add to Cart" button
  var btnPriceVal = document.getElementById('pdp-btn-price');
  if (btnPriceVal) {
    btnPriceVal.textContent = offerTotal.toFixed(2);
  }

  // 3. Update price in "Buy Now" button
  var buyPriceVal = document.getElementById('pdp-buy-price');
  if (buyPriceVal) {
    buyPriceVal.textContent = offerTotal.toFixed(2);
  }

  // 4. Strikethrough regular price & meta row in button if offer discount active
  var metaRow = document.getElementById('pdp-btn-meta-row');
  if (metaRow) {
    metaRow.style.display = (savings > 0.01) ? 'flex' : 'none';
  }

  var strikeEl = document.getElementById('pdp-btn-strike');
  if (strikeEl) {
    if (savings > 0.01) {
      strikeEl.innerHTML = `<span class="currency-dirham tv-curr-glyph-sub">&#xe900;</span> ${regularTotal.toFixed(2)}`;
      strikeEl.style.display = 'inline-flex';
    } else {
      strikeEl.style.display = 'none';
    }
  }

  // 5. Savings tag pill in button
  var savePill = document.getElementById('pdp-btn-save-pill');
  if (savePill) {
    if (savings > 0.01) {
      savePill.innerHTML = `SAVE <span class="currency-dirham tv-curr-glyph-sub" style="font-size:9px;">&#xe900;</span> ${savings.toFixed(2)}`;
      savePill.style.display = 'inline-flex';
    } else {
      savePill.style.display = 'none';
    }
  }

  // 6. Sync active state on Price Tier Cards (Single = 1, Set of 2 = 2, Set of 4 = 4)
  var tierCards = document.querySelectorAll('.tv-pdp-tier-card');
  tierCards.forEach(function(card) {
    var cardQty = parseInt(card.getAttribute('data-qty'), 10);
    if (cardQty === qty) {
      card.classList.add('is-active');
    } else {
      card.classList.remove('is-active');
    }
  });
}

function stepPdpQty(delta) {
  var input = document.getElementById('pdp-qty-input');
  if (!input) return;
  var currentVal = parseInt(input.value, 10) || 1;
  var newVal = Math.max(1, Math.min(20, currentVal + delta));
  input.value = newVal;
  updatePdpPricing(newVal);
}

function selectFitment(axle) {
  var frontWheel = document.getElementById('car-wheel-front');
  var rearWheel = document.getElementById('car-wheel-rear');
  var frontLabel = document.getElementById('label-fitment-front');
  var rearLabel = document.getElementById('label-fitment-rear');
  
  if (axle === 'rear') {
    if (rearWheel) {
      rearWheel.classList.add('is-selected');
      var glow = rearWheel.querySelector('.tv-wheel-glow');
      if (glow) glow.style.display = 'block';
    }
    if (frontWheel) {
      frontWheel.classList.remove('is-selected');
      var fGlow = frontWheel.querySelector('.tv-wheel-glow');
      if (fGlow) fGlow.style.display = 'none';
    }
    if (rearLabel) rearLabel.classList.add('is-active');
    if (frontLabel) frontLabel.classList.remove('is-active');
  } else {
    if (frontWheel) {
      frontWheel.classList.add('is-selected');
      var glow2 = frontWheel.querySelector('.tv-wheel-glow');
      if (glow2) glow2.style.display = 'block';
    }
    if (rearWheel) {
      rearWheel.classList.remove('is-selected');
      var rGlow = rearWheel.querySelector('.tv-wheel-glow');
      if (rGlow) rGlow.style.display = 'none';
    }
    if (frontLabel) frontLabel.classList.add('is-active');
    if (rearLabel) rearLabel.classList.remove('is-active');
  }
}

function switchPdpTab(tabId, btn) {
  var tabs = ['desc', 'specs', 'features', 'install', 'faqs'];
  tabs.forEach(function(t) {
    var el = document.getElementById('tab-' + t);
    if (el) {
      el.style.display = (t === tabId) ? 'block' : 'none';
      if (t === tabId) {
        el.classList.add('is-active');
      } else {
        el.classList.remove('is-active');
      }
    }
  });

  var navBtns = document.querySelectorAll('.tv-tab-btn');
  navBtns.forEach(function(b) {
    b.classList.remove('is-active');
    b.setAttribute('aria-selected', 'false');
  });

  if (btn) {
    btn.classList.add('is-active');
    btn.setAttribute('aria-selected', 'true');
  }
}

function addToCartPDP(productId, title, price) {
  var input = document.getElementById('pdp-qty-input');
  var qty = input ? (parseInt(input.value, 10) || 1) : 1;
  var unitPrice = (typeof window.pdpProductPrice === 'number') ? window.pdpProductPrice : price;
  var offer = window.pdpProductOffer || '';
  var total = (typeof calculateSetPrice === 'function')
    ? calculateSetPrice(unitPrice, qty, offer)
    : (unitPrice * qty).toFixed(2);
  
  var btn = document.getElementById('pdp-add-to-cart-btn');
  if (btn) {
    btn.classList.add('tv-btn-pulse');
    setTimeout(function() { btn.classList.remove('tv-btn-pulse'); }, 500);
  }

  if (typeof addToCart === 'function') {
    addToCart(productId, title, price, qty);
  } else if (typeof showToast === 'function') {
    showToast('Added ' + qty + ' \u00d7 ' + title + ' to cart!', 'success');
  }

  // Update badge
  var badge = document.getElementById('header-cart-badge');
  if (badge) {
    var curCount = parseInt(badge.textContent, 10) || 0;
    badge.textContent = curCount + qty;
  }
}

function buyNowPDP(productId, title, price) {
  addToCartPDP(productId, title, price);
  if (typeof showToast === 'function') {
    showToast('Proceeding to checkout with ' + title, 'info');
  }
}

function toggleRelHeart(btn) {
  if (!btn) return;
  btn.classList.toggle('is-loved');
  if (btn.classList.contains('is-loved')) {
    if (typeof showToast === 'function') showToast('Added to wishlist!', 'success');
  } else {
    if (typeof showToast === 'function') showToast('Removed from wishlist.', 'info');
  }
}

function addRelToCart(btn, title, price) {
  var card = btn ? btn.closest('.tv-rel-card') : null;
  var qtySelect = card ? card.querySelector('.tv-rel-qty-select') : null;
  var qty = qtySelect ? (parseInt(qtySelect.value, 10) || 1) : 1;
  
  if (typeof showToast === 'function') {
    showToast('Added ' + qty + ' \u00d7 ' + title + ' to cart!', 'success');
  }
  
  var badge = document.getElementById('header-cart-badge');
  if (badge) {
    var curCount = parseInt(badge.textContent, 10) || 0;
    badge.textContent = curCount + qty;
  }
}

function scrollRelated(direction) {
  var container = document.getElementById('related-products-carousel');
  if (!container) return;
  var scrollAmount = 300 * direction;
  container.scrollBy({ left: scrollAmount, behavior: 'smooth' });
}

function showCartModal(e) {
  if (e) e.preventDefault();
  if (typeof showToast === 'function') {
    showToast('Shopping cart: 0 items', 'info');
  }
}

// Bind PDP methods to window
window.updatePdpPricing = updatePdpPricing;
window.stepPdpQty = stepPdpQty;
window.selectFitment = selectFitment;
window.switchPdpTab = switchPdpTab;
window.addToCartPDP = addToCartPDP;
window.buyNowPDP = buyNowPDP;
window.toggleRelHeart = toggleRelHeart;
window.addRelToCart = addRelToCart;
window.scrollRelated = scrollRelated;
window.showCartModal = showCartModal;

// Initialize PDP pricing and sync tier card click listeners
document.addEventListener('DOMContentLoaded', function() {
  var tierCards = document.querySelectorAll('.tv-pdp-tier-card');
  tierCards.forEach(function(c) {
    c.addEventListener('click', function() {
      var q = parseInt(this.getAttribute('data-qty'), 10) || 1;
      var input = document.getElementById('pdp-qty-input');
      if (input) {
        input.value = q;
      }
      updatePdpPricing(q);
    });
  });

  // Initial pricing sync
  var input = document.getElementById('pdp-qty-input');
  if (input) {
    var initialQty = parseInt(input.value, 10) || 4;
    updatePdpPricing(initialQty);
  }
});

/**
 * Universal Client Dropdown Initializer
 * Transforms any select with .tv-custom-select or initializes custom dropdowns
 * matching the user reference image (bright blue border, divider, chevron, solid blue active with white checkmark)
 */
function initClientCustomDropdowns() {
  document.querySelectorAll('select.tv-custom-select').forEach(function(select) {
    if (select.parentElement.classList.contains('tv-custom-dropdown')) return;

    var wrap = document.createElement('div');
    wrap.className = 'tv-custom-dropdown';
    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select);
    select.classList.add('tv-hidden-native-select');

    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'tv-dropdown-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');

    var valSpan = document.createElement('span');
    valSpan.className = 'tv-dropdown-val';
    var selectedOpt = select.options[select.selectedIndex] || select.options[0];
    valSpan.textContent = selectedOpt ? selectedOpt.text : '';

    var divider = document.createElement('span');
    divider.className = 'tv-dropdown-divider';

    var chevronSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    chevronSvg.setAttribute('class', 'tv-dropdown-chevron');
    chevronSvg.setAttribute('width', '14');
    chevronSvg.setAttribute('height', '14');
    chevronSvg.setAttribute('viewBox', '0 0 24 24');
    chevronSvg.setAttribute('fill', 'none');
    chevronSvg.setAttribute('stroke', '#0066ff');
    chevronSvg.setAttribute('stroke-width', '2.6');
    chevronSvg.setAttribute('stroke-linecap', 'round');
    chevronSvg.setAttribute('stroke-linejoin', 'round');
    var polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    polyline.setAttribute('points', '6 9 12 15 18 9');
    chevronSvg.appendChild(polyline);

    trigger.appendChild(valSpan);
    trigger.appendChild(divider);
    trigger.appendChild(chevronSvg);
    wrap.appendChild(trigger);

    var popover = document.createElement('div');
    popover.className = 'tv-dropdown-popover';
    popover.setAttribute('role', 'listbox');

    Array.from(select.options).forEach(function(opt) {
      var optDiv = document.createElement('div');
      optDiv.className = 'tv-dropdown-opt' + (opt.selected ? ' is-selected' : '');
      optDiv.setAttribute('data-value', opt.value);
      optDiv.setAttribute('role', 'option');

      var label = document.createElement('span');
      label.className = 'tv-opt-label';
      label.textContent = opt.text;

      var checkSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      checkSvg.setAttribute('class', 'tv-opt-check');
      checkSvg.setAttribute('width', '15');
      checkSvg.setAttribute('height', '15');
      checkSvg.setAttribute('viewBox', '0 0 24 24');
      checkSvg.setAttribute('fill', 'none');
      checkSvg.setAttribute('stroke', '#ffffff');
      checkSvg.setAttribute('stroke-width', '3');
      checkSvg.setAttribute('stroke-linecap', 'round');
      checkSvg.setAttribute('stroke-linejoin', 'round');
      var checkPoly = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
      checkPoly.setAttribute('points', '20 6 9 17 4 12');
      checkSvg.appendChild(checkPoly);

      optDiv.appendChild(label);
      optDiv.appendChild(checkSvg);

      optDiv.addEventListener('click', function(e) {
        e.stopPropagation();
        select.value = opt.value;
        valSpan.textContent = opt.text;
        popover.querySelectorAll('.tv-dropdown-opt').forEach(function(o) { o.classList.remove('is-selected'); });
        optDiv.classList.add('is-selected');
        wrap.classList.remove('is-open');
        trigger.setAttribute('aria-expanded', 'false');
        select.dispatchEvent(new Event('change', { bubbles: true }));
      });

      popover.appendChild(optDiv);
    });

    wrap.appendChild(popover);

    trigger.addEventListener('click', function(e) {
      e.stopPropagation();
      var isOpen = wrap.classList.contains('is-open');
      document.querySelectorAll('.tv-custom-dropdown.is-open').forEach(function(d) {
        if (d !== wrap) d.classList.remove('is-open');
      });
      if (isOpen) {
        wrap.classList.remove('is-open');
        trigger.setAttribute('aria-expanded', 'false');
      } else {
        wrap.classList.add('is-open');
        trigger.setAttribute('aria-expanded', 'true');
      }
    });

    select.addEventListener('change', function() {
      var curVal = select.value;
      var curOpt = select.options[select.selectedIndex];
      if (curOpt) valSpan.textContent = curOpt.text;
      popover.querySelectorAll('.tv-dropdown-opt').forEach(function(o) {
        if (o.getAttribute('data-value') === curVal) {
          o.classList.add('is-selected');
        } else {
          o.classList.remove('is-selected');
        }
      });
    });
  });
}

document.addEventListener('click', function() {
  document.querySelectorAll('.tv-custom-dropdown.is-open').forEach(function(d) {
    d.classList.remove('is-open');
    var tr = d.querySelector('.tv-dropdown-trigger');
    if (tr) tr.setAttribute('aria-expanded', 'false');
  });
});

window.initClientCustomDropdowns = initClientCustomDropdowns;
document.addEventListener('DOMContentLoaded', initClientCustomDropdowns);


