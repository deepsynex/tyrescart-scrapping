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
        <!-- 1. Top Header Bar: Brand Logo Left & Top Rated Badge Right -->
        <div class="tv-card-header-bar">
          <div class="tv-skeleton-box" style="width: 82px; height: 26px; border-radius: 6px;"></div>
        </div>

        <!-- 2. Centered Tyre Image Area -->
        <div class="tv-card-img-area">
          <div class="tv-btn-quickview" style="pointer-events: none; border-color: transparent; background: transparent;">
            <div class="tv-skeleton-box" style="width: 100%; height: 100%; border-radius: 50%;"></div>
          </div>

          <div class="tv-card-img-link" style="display: flex; align-items: center; justify-content: center;">
            <div class="tv-skeleton-box tv-skeleton-tyre"></div>
          </div>

          <div class="car-brand-logos" style="opacity: 0.35;">
            <div class="tv-skeleton-box" style="width: 18px; height: 18px; border-radius: 50%; margin-bottom: 4px;"></div>
            <div class="tv-skeleton-box" style="width: 18px; height: 18px; border-radius: 50%;"></div>
          </div>

          <div class="tyre-type-icons" style="opacity: 0.35;">
            <div class="tv-skeleton-box" style="width: 32px; height: 12px; border-radius: 3px;"></div>
          </div>

          <span class="tv-card-warranty-badge" style="background: transparent !important; box-shadow: none !important; padding: 0 !important; border: none !important;">
            <div class="tv-skeleton-box" style="width: 104px; height: 22px; border-radius: 20px 0 0 20px;"></div>
          </span>
        </div>

        <!-- 3. Bottom Detail Wrapper -->
        <div class="product-bottom-detail">
          <div class="tv-card-info-block">
            <!-- Pattern Title -->
            <div class="tv-skeleton-box" style="width: 68%; height: 20px; border-radius: 6px; margin-bottom: 8px;"></div>

            <!-- Size Row: Size (Left) & Year (Right) -->
            <div class="tv-card-size-row" style="margin-bottom: 6px;">
              <div class="tv-skeleton-box" style="width: 110px; height: 16px; border-radius: 4px;"></div>
              <div class="tv-skeleton-box" style="width: 48px; height: 16px; border-radius: 4px;"></div>
            </div>

            <!-- Meta Row: 3 columns (Country, Runflat, Premium) -->
            <div class="tv-card-meta-row">
              <span class="tv-meta-item tv-meta-country">
                <div class="tv-skeleton-box" style="width: 44px; height: 14px; border-radius: 4px;"></div>
              </span>
              <span class="tv-meta-item tv-meta-runflat">
                <div class="tv-skeleton-box" style="width: 58px; height: 14px; border-radius: 4px; margin: auto;"></div>
              </span>
              <span class="tv-meta-item tv-meta-premium">
                <div class="tv-skeleton-box" style="width: 48px; height: 14px; border-radius: 4px; margin-left: auto;"></div>
              </span>
            </div>
          </div>

          <!-- Bottom Info Strip: In Stock | Fitted Included -->
          <div class="tv-card-bottom-info">
            <div class="tv-stock-status">
              <div class="tv-skeleton-box" style="width: 65px; height: 16px; border-radius: 4px;"></div>
            </div>
            <div class="tv-fitted-status">
              <div class="tv-skeleton-box" style="width: 105px; height: 16px; border-radius: 4px;"></div>
            </div>
          </div>

          <!-- Price & Add to Cart Row -->
          <div class="tv-card-price-action-row">
            <div class="tv-card-pricing-left">
              <div class="tv-card-main-price-line">
                <div class="tv-skeleton-box" style="width: 88px; height: 24px; border-radius: 6px; margin-bottom: 4px;"></div>
              </div>
              <div class="tv-card-set4-line">
                <div class="tv-skeleton-box" style="width: 115px; height: 13px; border-radius: 4px;"></div>
              </div>
            </div>

            <div class="tv-skeleton-box" style="width: 115px; height: 38px; border-radius: 8px;"></div>
          </div>
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
    const ribbonClass = isArrival ? 'tv-ribbon-green' : '';
    offerBannerHTML = `
          <!-- 0. Top Offer Ribbon (Only when offer exists) -->
          <div class="tv-card-offer-ribbon ${ribbonClass}">
            <span class="tv-offer-ribbon-text">${escapeHtml(p.offer_banner)}</span>
          </div>`;
  }

  const brandName = escapeHtml(p.brand_name || '');
  const rawBrandSlug = (p.brand_slug || p.brand_name || '').toLowerCase().trim().replace(/[\s_]+/g, '-');
  const cardBrandSlug = escapeHtml(rawBrandSlug);

  // Brand Logo (Left) & Fallback
  let brandLogoHTML = '';
  if (p.brand_logo) {
    brandLogoHTML = `
              <img src="${escapeHtml(p.brand_logo)}" alt="${brandName}" class="tv-card-brand-img" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='inline-block';">
              <span class="tv-card-brand-fallback" style="display:none;">${brandName}</span>`;
  } else {
    brandLogoHTML = `<span class="tv-card-brand-fallback">${brandName}</span>`;
  }

  // const badgeHTML = `
  //             <span class="tv-card-badge tv-badge-toprated">
  //               <svg width="12" height="12" viewBox="0 0 24 24" fill="#F59E0B" stroke="#F59E0B" stroke-width="1">
  //                 <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
  //               </svg>
  //               <span>Top Rated</span>
  //             </span>`;

  // Pattern / Model Name (Brand name removed)
  let rawPattern = (p.pattern_name || p.display_name || '').trim();
  if (brandName && rawPattern.toLowerCase().startsWith(brandName.toLowerCase())) {
    rawPattern = rawPattern.slice(brandName.length).trim();
  }
  rawPattern = rawPattern.replace(/^[\s\-_:]+/, '').trim();
  if (!rawPattern) rawPattern = (p.pattern_name || p.display_name || 'Tyre');
  const patternTitle = escapeHtml(rawPattern);

  const sizeSpec = escapeHtml(p.full_size_spec || p.tire_size_label || '');
  const yearVal = escapeHtml(p.year || '2025');
  const originVal = escapeHtml(p.country_of_origin || 'USA');
  const categoryVal = escapeHtml(p.tyres_category || 'Premium');
  const warrantyText = escapeHtml(p.warranty || '1 Year Warranty');

  const isRunflat = Boolean(
    p.is_runflat === true ||
    p.is_runflat === 1 ||
    p.is_runflat === '1' ||
    p.run_flat === 1 ||
    p.run_flat === '1' ||
    (p.runflat_text && p.runflat_text.toLowerCase() === 'runflat')
  );
  const runflatDataVal = isRunflat ? 'Runflat' : '';
  const runflatContent = isRunflat ? `<span><img src="/static/assets/images/run-flat.svg" alt="Runflat"></span>` : '';

  const priceVal = typeof p.price === 'number' ? p.price : parseFloat(p.price || 0);
  const displayPrice = (priceVal % 1 === 0) ? priceVal.toFixed(0) : priceVal.toFixed(2);
  const setOf4Val = p.set_of_4_price ? (typeof p.set_of_4_price === 'number' ? p.set_of_4_price : parseFloat(p.set_of_4_price || (priceVal * 4))) : (priceVal * 4);
  const setOf4Formatted = (setOf4Val % 1 === 0) ? (setOf4Val).toFixed(0) : setOf4Val.toFixed(2);

  const priceSet2 = (priceVal * 2).toFixed(2);
  const priceSet4 = (setOf4Val).toFixed(2);
  const priceSet8 = (p.set_of_8_price ? parseFloat(p.set_of_8_price) : (priceVal * 8)).toFixed(2);

  const imgPath = escapeHtml(p.image_path || '/static/assets/images/no-image-available.svg');
  const slugVal = escapeHtml(p.slug || '');
  const cleanTitle = escapeHtml(patternTitle).replace(/'/g, "\\'");
  const fullTitle = escapeHtml(p.full_title || (brandName + ' ' + sizeSpec + ' ' + patternTitle + ' ' + yearVal));
  const widthVal = escapeHtml(p.width || '155 mm');
  const profileVal = escapeHtml(p.profile || 'None');
  const rimVal = escapeHtml(p.rim_size || 'R16');
  const loadSpeedVal = escapeHtml(p.load_speed || '86Q');
  const skuVal = escapeHtml(p.sku || ('TCKL-' + (p.id || '12726')));
  const ratingVal = p.rating ? parseFloat(p.rating) : 4.5;
  const orderVal = p.sort_order || 1;

  return `
        <div class="tv-product-card ${hasOffer ? 'has-offer' : ''}"
             data-slug="${slugVal}"
             onclick="handleProductCardClick(event, '${slugVal}')"
             data-brand="${cardBrandSlug}"
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
             data-warranty="${warrantyText}"
             data-sku="${skuVal}"
             data-image="${imgPath}"
             data-vehicle="${escapeHtml(p.vehicle_type || 'car')}"
             data-type="${escapeHtml(p.tire_type || p.season || 'summer')}"
             data-price="${priceVal}"
             data-price-set2="${priceSet2}"
             data-price-set4="${priceSet4}"
             data-price-set8="${priceSet8}"
             data-rating="${ratingVal}"
             data-order="${orderVal}"
             data-runflat="${runflatDataVal}"
             data-category="${categoryVal}"
             data-offer="${escapeHtml(p.offer_banner || '')}">
          
          ${offerBannerHTML}

          <!-- 1. Top Header Bar: Brand Logo (Left) & Top Rated Badge (Right) -->
          <div class="tv-card-header-bar">
            <a href="/tyres/brand/${cardBrandSlug}" class="tv-card-brand-wrap" title="View all ${brandName} tyres" onclick="event.stopPropagation();">
              ${brandLogoHTML}
            </a>

            
          </div>

          <!-- 2. Centered Tyre Image (Transparent / Clean - No background color) -->
          <div class="tv-card-img-area">
            <button class="tv-btn-quickview" onclick="event.stopPropagation(); openQuickView(this);" title="Quick view" type="button" aria-label="Quick view">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12C1 12 5 4 12 4C19 4 23 12 23 12C23 12 19 20 12 20C5 20 1 12 1 12Z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
            </button>

            <div class="tv-card-img-link">
              <div class="tv-card-tyre-box tv-img-loading">
                <img src="${imgPath}" 
                     alt="${patternTitle}" 
                     class="tv-product-img" 
                     loading="lazy" 
                     onload="this.parentElement.classList.remove('tv-img-loading')"
                     onerror="this.src='/static/assets/images/no-image-available.svg'; this.parentElement.classList.remove('tv-img-loading'); this.onerror=null;">
              </div>
            </div>

            ${(p.oem_logos && p.oem_logos.length > 0) ? `
            <div class="car-brand-logos">
              ${p.oem_logos.map(l => `<img src="${l.image_url}" alt="${l.name || 'Brand Image'}" title="${l.name || 'Brand Image'} Approved OEM Tyre">`).join('')}
            </div>` : ''}

            <div class="tyre-type-icons" onclick="event.stopPropagation(); openTyreVehicleModal(this);" style="cursor: pointer;" title="View Compatible Vehicles">
              <span>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 47.747 16.977" class="w-[1.75rem] sm:w-[2.25rem] h-[0.625rem] sm:h-[1rem]">
                     <g id="Group_243" data-name="Group 243" transform="translate(0)">
                        <path id="Path_411" data-name="Path 411" d="M-122.615,146.25a14.294,14.294,0,0,0,.9,1.807,1.609,1.609,0,0,0,.935.518c1.073.245,2.161.424,3.313.642a4.4,4.4,0,0,1,2.574-3.96,4.107,4.107,0,0,1,2.686-.294,4.432,4.432,0,0,1,3.413,4.935l21.435.432a4.315,4.315,0,0,1,1.162-4.224,4.061,4.061,0,0,1,3.118-1.236,4.36,4.36,0,0,1,4.163,5.139c.687-.113,1.356-.194,2.011-.338,1.472-.323,1.693-.616,1.987-2.158a5.746,5.746,0,0,0-.342-2.547,2.327,2.327,0,0,0-1.6-1.7,39.349,39.349,0,0,0-7.593-2.017,16.658,16.658,0,0,1-3.88-1.389c-1.793-.78-3.566-1.607-5.351-2.407a21.266,21.266,0,0,0-9.744-1.617,33.618,33.618,0,0,0-11.928,2.885,20.127,20.127,0,0,1-5.156,1.381c-1.089.153-1.255.357-1.256,1.444,0,.358-.012.716,0,1.073a2.047,2.047,0,0,1-.454,1.677,2.842,2.842,0,0,0-.391.931Zm30.034-4.853a.274.274,0,0,1-.12.014c-2.485-.069-4.97-.144-7.455-.2-.27-.007-.33-.139-.381-.359-.23-.982-.476-1.96-.714-2.939-.071-.291-.135-.584-.222-.962,3.475.284,6.78.76,9.465,2.868Zm-9.58-.407a.745.745,0,0,1-.153.049c-2.3-.068-4.594-.135-6.89-.218a.451.451,0,0,1-.317-.243,1.572,1.572,0,0,1,.174-1.881,8.174,8.174,0,0,0,.455-.7.938.938,0,0,1,.418-.325,17.885,17.885,0,0,1,5.381-.687.411.411,0,0,1,.315.232C-102.558,138.468-102.363,139.723-102.161,140.989Zm-11.361-.195a1.036,1.036,0,0,1,.612-1.247c.563-.291,1.137-.561,1.714-.823.506-.23,1.022-.436,1.534-.653-.557.9-1.154,1.725-1.762,2.543a.451.451,0,0,1-.3.172C-112.325,140.8-112.928,140.794-113.522,140.794Z" transform="translate(122.615 -135.806)" />
                        <path id="Path_412" data-name="Path 412" d="M512.565,314.14a3.6,3.6,0,1,0,3.6,3.624A3.629,3.629,0,0,0,512.565,314.14Zm.312,1.314,1.1.473c-.269.253-.451.444-.653.61-.235.192-.407.1-.443-.176A8.107,8.107,0,0,1,512.877,315.454Zm0,4.553c0-.385-.021-.647.006-.906s.2-.346.412-.185.426.372.718.632Zm-2.582-2.585.5-1.186c.23.3.4.5.543.717.06.089.121.236.086.313a.392.392,0,0,1-.29.149C510.886,317.437,510.64,317.422,510.295,317.422Zm.463,1.772-.445-1.135c.352,0,.615-.021.874.005.3.03.368.2.177.436C511.2,318.705,511.02,318.9,510.757,319.194Zm4.1-1.678-1.151-.247c.2-.267.4-.534.6-.8.012-.015.057,0,.144-.009Zm-.416,1.52-.189.072c-.151-.194-.314-.38-.449-.584a.47.47,0,0,1-.082-.321c.014-.063.158-.13.248-.137.259-.018.52-.006.861-.006Zm-2.194-3.58a7.38,7.38,0,0,1-.008.906c-.039.276-.2.369-.445.165-.2-.165-.407-.324-.714-.568Zm-1.139,4.083c.3-.255.48-.424.679-.567a.428.428,0,0,1,.309-.082c.067.017.138.154.145.242.019.255.007.513.007.871Z" transform="translate(-503.07 -304.356)" />
                        <path id="Path_413" data-name="Path 413" d="M-32.965,314.14a3.616,3.616,0,0,0-3.619,3.614,3.631,3.631,0,0,0,3.609,3.579,3.607,3.607,0,0,0,3.585-3.545A3.6,3.6,0,0,0-32.965,314.14Zm.3,1.326,1.144.474c-.3.256-.5.447-.72.612s-.389.1-.418-.169S-32.665,315.835-32.665,315.466Zm1.5.812.453,1.144c-.355,0-.617.017-.876,0-.306-.025-.363-.2-.185-.434C-31.619,316.775-31.436,316.585-31.17,316.278Zm.472,1.782-.484,1.09c-.26-.282-.452-.465-.612-.673s-.1-.386.177-.413S-31.093,318.06-30.7,318.06Zm-2.6-2.6c0,.355.012.614-.007.871-.006.088-.074.225-.14.244a.419.419,0,0,1-.314-.071c-.208-.15-.4-.328-.682-.57Zm-1.483.8c.25.3.428.492.58.7a.415.415,0,0,1,.067.313c-.019.066-.156.131-.244.138-.258.018-.518.007-.863.007Zm.011,2.963-.474-1.164c.356,0,.619-.018.878,0,.287.025.382.18.194.428C-34.341,318.712-34.523,318.919-34.774,319.224Zm2.107.794c0-.357-.014-.6.007-.846a.379.379,0,0,1,.15-.279.394.394,0,0,1,.308.076c.213.145.409.314.708.55Zm-1.762-.474c.29-.253.468-.426.666-.572a.429.429,0,0,1,.312-.081c.065.016.136.154.142.242.019.258.007.519.007.871Z" transform="translate(72.415 -304.356)" />
                     </g>
                  </svg>
              </span>
            </div>

            <span class="tv-card-warranty-badge">
              <span>${warrantyText}</span>
            </span>
          </div>

          <div class="product-bottom-detail">
            <!-- 3. Product Info Block -->
            <div class="tv-card-info-block">
              <!-- Product Pattern / Model Name (Brand name removed) -->
              <a href="/${slugVal}" class="tv-card-pattern-link" title="${patternTitle}">
                <h3 class="tv-card-pattern">
                  ${patternTitle}
                </h3>
              </a>

              <!-- 3. Product Size -->
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
                <span class="tv-meta-item tv-meta-country" title="Origin: ${originVal}">
                  <span>${originVal}</span>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="tv-meta-icon" style="color: #64748b; margin-left: 2px;">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="2" y1="12" x2="22" y2="12"></line>
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                  </svg>
                </span>

                <span class="tv-meta-item tv-meta-runflat" title="Technology">
                  ${runflatContent}
                </span>

                <span class="tv-meta-item tv-meta-premium" title="Category: ${categoryVal}">
                  <span>${categoryVal}</span>
                  ${categoryVal ? `
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="tv-meta-icon" style="color: #64748b; margin-left: 2px;">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                  </svg>` : ''}
                </span>
              </div>
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

              <div class="tv-fitted-status">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#E02424" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path>
                  <line x1="7" y1="7" x2="7.01" y2="7"></line>
                </svg>
                <span>Fitted Included</span>
                <span class="tv-fitted-info-btn" onclick="event.stopPropagation(); openFittedPriceModal(event);" role="button" tabindex="0" title="View fitted details">
                  <svg class="w-[0.713rem] md:w-[0.813rem] h-auto" width="13" height="13" fill="currentColor" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M256 32a224 224 0 1 1 0 448 224 224 0 1 1 0-448zm0 480A256 256 0 1 0 256 0a256 256 0 1 0 0 512zM208 352c-8.8 0-16 7.2-16 16s7.2 16 16 16h96c8.8 0 16-7.2 16-16s-7.2-16-16-16H272V240c0-8.8-7.2-16-16-16H216c-8.8 0-16 7.2-16 16s7.2 16 16 16h24v96H208zm48-168a24 24 0 1 0 0-48 24 24 0 1 0 0 48z"></path></svg>
                </span>
              </div>
            </div>

            <!-- 4. Price & Add to Cart Line -->
            <div class="tv-card-price-action-row">
              <div class="tv-card-pricing-left">
                <div class="tv-card-main-price-line">
                  <span class="currency-dirham tv-ref-curr">&#xe900;</span>
                  <strong class="tv-card-price-num">${displayPrice}</strong>
                  <span class="tv-card-per-tyre">/tyre</span>
                </div>
                <div class="tv-card-set4-line">
                  Set of 4 &bull; <span class="currency-dirham">&#xe900;</span> ${setOf4Formatted}
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
          </div>
          <!-- /product-bottom-detail -->

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
  const imgEl = card ? card.querySelector('.tv-product-img') : null;
  const imgSrc = imgEl ? (imgEl.src || imgEl.getAttribute('data-src') || '') : '';
  const specEl = card ? card.querySelector('.tv-card-spec-text') : null;
  const sizeSpec = specEl ? specEl.textContent.trim() : '';
  
  const originalHTML = btn.innerHTML;
  btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Added</span>';
  btn.style.background = '#16a34a';

  if (typeof window.addTyreToCart === 'function') {
    window.addTyreToCart({
      title: title,
      price: p,
      qty: qty,
      image: imgSrc,
      size: sizeSpec,
      sku: 'SKU-' + (title || '').replace(/[^a-zA-Z0-9]/g, '-').toLowerCase()
    });
  } else if (typeof showToast === 'function') {
    showToast(`Added ${qty}x ${title} to fitting cart!`);
  }
  
  setTimeout(() => {
    btn.innerHTML = originalHTML;
    btn.style.background = '';
  }, 2000);
}

function handleProductCardClick(e, slug) {
  if (!slug) return;
  if (e.target.closest('button, select, input, a, .tv-btn-quickview, .tv-btn-card-add, .tv-card-price-note, .tv-spec-info-btn, .tv-fitted-info-btn, .tyre-type-icons')) {
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

  // 12. Run Flat segment: runflat
  const selectedRunflat = document.querySelector('input[name="runflat"]:checked');
  if (selectedRunflat) {
    segments.push('runflat');
  }

  // 13. Price range segment: price-418-5668
  const sliderMin = parseFloat(minPriceSlider?.min || 0);
  const sliderMax = parseFloat(maxPriceSlider?.max || 2000);
  const curMin = minPrice !== '' ? parseFloat(minPrice) : sliderMin;
  const curMax = maxPrice !== '' ? parseFloat(maxPrice) : sliderMax;
  if (curMin > sliderMin || curMax < sliderMax) {
    segments.push(`price-${Math.round(curMin)}-${Math.round(curMax)}`);
  }

  // 14. Sort segment (Default: price-asc)
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
  const activeRunflatCb = document.querySelector('input[name="runflat"]:checked');
  if (activeRunflatCb) {
    params.set('runflat', 'runflat');
  }
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

  // 8. Run Flat
  if (facets.runflat !== undefined) {
    const rfCount = facets.runflat;
    const rfEl = document.getElementById('tv-filter-count-runflat');
    if (rfEl) rfEl.textContent = Number(rfCount).toLocaleString();
    const rfCb = document.querySelector('input[name="runflat"]');
    const rfItem = rfCb ? rfCb.closest('.tv-filter-item') : null;
    if (rfItem) {
      if (rfCount === 0 && (!rfCb || !rfCb.checked)) {
        rfItem.classList.add('tv-filter-empty');
        rfItem.style.display = 'none';
      } else {
        rfItem.classList.remove('tv-filter-empty');
        rfItem.style.display = '';
      }
    }
    const rfGroup = rfCb ? rfCb.closest('.tv-filter-group') : null;
    if (rfGroup) {
      if (rfCount === 0 && (!rfCb || !rfCb.checked)) {
        rfGroup.classList.add('tv-group-empty');
      } else {
        rfGroup.classList.remove('tv-group-empty');
      }
    }
  }
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
  const selectedRunflat = document.querySelectorAll('input[name="runflat"]:checked').length;
  
  const minSlider = document.getElementById('min-price-slider');
  const maxSlider = document.getElementById('max-price-slider');
  const isPriceActive = (minSlider && parseFloat(minSlider.value) > parseFloat(minSlider.min || 0)) ||
                        (maxSlider && parseFloat(maxSlider.value) < parseFloat(maxSlider.max || 2000));
  const priceActive = isPriceActive ? 1 : 0;
  const totalActive = selectedBrands + selectedPatterns + selectedOems + selectedWarranties + selectedYears + selectedOrigins + selectedSizes + selectedVehicles + selectedTypes + selectedPromotions + selectedRunflat + priceActive;

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
function updateCardQty(select) {
  if (!select) return;
  const card = select.closest('.tv-product-card');
  if (!card) return;
  const priceEl = card.querySelector('.tv-card-price-num');
  const basePrice = parseFloat(card.getAttribute('data-price') || (priceEl ? priceEl.textContent : 0)) || 0;
  const qty = parseInt(select.value, 10) || 1;
  const total = basePrice * qty;
  const totalEl = card.querySelector('.tv-card-total-price');
  if (totalEl) totalEl.textContent = total.toFixed(2);
}
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

/* ==========================================================================
   TYRESVISION CART OVERVIEW DRAWER & CHECKOUT MODULE (Next.js Port)
   ========================================================================== */

(function() {
  'use strict';

  // ── Global Cart & Drawer State ──
  var currentDrawerSection = 'cart'; // 'cart' | 'fitting' | 'contact'
  var drawerOpen = false;
  var appliedCoupon = null;
  var couponDiscount = 0.0;
  var orderNotes = '';

  // Step 3: Store Locator State
  var storeData = {
    cities: ["All", "Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah"],
    branches: [],
    mobileVans: [],
    timeSlots: [
      "09:00 AM - 11:00 AM",
      "11:00 AM - 01:00 PM",
      "02:00 PM - 04:00 PM",
      "04:00 PM - 06:00 PM",
      "06:00 PM - 08:00 PM"
    ]
  };
  var deliveryMode = 'install_outlet'; // 'install_outlet' | 'mobile_van' | 'free_shipping'
  var selectedCity = 'All';
  var searchQuery = '';
  var expandedStoreId = null;
  var selectedStore = null;
  var selectedVan = null;
  var selectedDate = '';
  var selectedTimeSlot = '';
  var mobileAddress = '';
  var isLocating = false;

  // Step 4: Vehicle & Payment State
  var makesList = [];
  var selectedMake = '';
  var selectedModel = '';
  var selectedYear = '';
  var paymentMethod = 'payment_link'; // 'payment_link' | 'cashondelivery'
  var isPlacingOrder = false;

  // ── Utility: Generate upcoming 14 dates ──
  function getUpcomingDates() {
    var dates = [];
    var now = new Date();
    var days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    for (var i = 1; i <= 14; i++) {
      var d = new Date(now);
      d.setDate(now.getDate() + i);
      var dayName = days[d.getDay()];
      var monthName = months[d.getMonth()];
      var dateNum = d.getDate();
      var iso = d.toISOString().split('T')[0];
      var prefix = i === 1 ? 'Tomorrow - ' : '';
      dates.push({
        value: iso,
        label: prefix + dayName + ', ' + dateNum + ' ' + monthName
      });
    }
    return dates;
  }

  // ── Cart Storage Helpers ──
  function getCartItems() {
    try {
      var raw = localStorage.getItem('tv_cart_items');
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function saveCartItems(items) {
    try {
      localStorage.setItem('tv_cart_items', JSON.stringify(items));
    } catch (e) {}
    updateCartBadges();
  }

  function getCartTotalTyres(items) {
    if (!items) items = getCartItems();
    return items.reduce(function(sum, it) {
      return sum + (parseInt(it.qty, 10) || 1);
    }, 0);
  }

  function getCartSubtotal(items) {
    if (!items) items = getCartItems();
    return items.reduce(function(sum, it) {
      var price = parseFloat(it.price) || 0;
      var qty = parseInt(it.qty, 10) || 1;
      return sum + (price * qty);
    }, 0);
  }

  function updateCartBadges() {
    var items = getCartItems();
    var totalTyres = getCartTotalTyres(items);

    // Floating side tab badge
    var sideBadge = document.getElementById('tv-overview-badge');
    if (sideBadge) {
      if (totalTyres > 0) {
        sideBadge.textContent = totalTyres;
        sideBadge.style.display = 'flex';
      } else {
        sideBadge.style.display = 'none';
      }
    }

    // Navbar cart badge
    var navBadge = document.getElementById('header-cart-badge');
    if (navBadge) {
      if (totalTyres > 0) {
        navBadge.textContent = totalTyres;
        navBadge.style.display = 'flex';
      } else {
        navBadge.style.display = 'none';
      }
    }
  }

  // ── Public Cart Mutation API ──
  function addTyreToCart(item) {
    var items = getCartItems();
    var sku = item.sku || item.title || 'TYRE-' + Date.now();
    var existingIndex = -1;

    for (var i = 0; i < items.length; i++) {
      if (items[i].sku === sku || items[i].title === item.title) {
        existingIndex = i;
        break;
      }
    }

    var addQty = parseInt(item.qty, 10) || 1;
    if (existingIndex > -1) {
      items[existingIndex].qty = (parseInt(items[existingIndex].qty, 10) || 1) + addQty;
    } else {
      items.push({
        id: item.id || sku,
        sku: sku,
        title: item.title || 'Genuine Tyre',
        name: item.title || 'Genuine Tyre',
        price: parseFloat(item.price) || 0,
        qty: addQty,
        image: item.image || '/static/assets/images/no-image-available.svg',
        size: item.size || ''
      });
    }

    saveCartItems(items);
    renderDrawerCart();
    openOverviewDrawer('cart');
  }

  // ── Drawer Open / Close / Toggle ──
  function openOverviewDrawer(section) {
    drawerOpen = true;
    var backdrop = document.getElementById('tv-overview-backdrop');
    var panel = document.getElementById('tv-overview-panel');
    var successScreen = document.getElementById('tv-drawer-success-screen');
    var mainFlow = document.getElementById('tv-drawer-main-flow');

    if (successScreen) successScreen.style.display = 'none';
    if (mainFlow) mainFlow.style.display = 'block';

    if (backdrop) backdrop.classList.add('is-open');
    if (panel) panel.classList.add('is-open');
    document.body.style.overflow = 'hidden';

    if (section) {
      setOverviewActiveSection(section);
    } else {
      renderDrawerCart();
    }

    // Lazy load stores and vehicle makes
    loadStoreLocatorData();
    loadVehicleMakes();
  }

  function closeOverviewDrawer() {
    drawerOpen = false;
    var backdrop = document.getElementById('tv-overview-backdrop');
    var panel = document.getElementById('tv-overview-panel');
    if (backdrop) backdrop.classList.remove('is-open');
    if (panel) panel.classList.remove('is-open');
    document.body.style.overflow = '';
  }

  function toggleOverviewDrawer() {
    if (drawerOpen) {
      closeOverviewDrawer();
    } else {
      openOverviewDrawer();
    }
  }

  // ── Step Navigation & Progress Stepper ──
  function setOverviewActiveSection(section) {
    currentDrawerSection = section;

    var cartBody = document.getElementById('tv-cart-section-body');
    var fittingBody = document.getElementById('tv-fitting-section-body');
    var contactBody = document.getElementById('tv-contact-section-body');

    var cartChev = document.getElementById('tv-cart-chevron');
    var fittingChev = document.getElementById('tv-fitting-chevron');
    var contactChev = document.getElementById('tv-contact-chevron');

    var subtitle = document.getElementById('tv-progress-subtitle');
    var fillBar = document.getElementById('tv-stepper-fill-bar');

    var circle2 = document.getElementById('tv-step-circle-2');
    var lbl2 = document.getElementById('tv-step-lbl-2');
    var circle3 = document.getElementById('tv-step-circle-3');
    var lbl3 = document.getElementById('tv-step-lbl-3');
    var circle4 = document.getElementById('tv-step-circle-4');
    var lbl4 = document.getElementById('tv-step-lbl-4');

    // Hide all accordion bodies first
    if (cartBody) cartBody.style.display = 'none';
    if (fittingBody) fittingBody.style.display = 'none';
    if (contactBody) contactBody.style.display = 'none';

    if (cartChev) cartChev.classList.remove('is-open');
    if (fittingChev) fittingChev.classList.remove('is-open');
    if (contactChev) contactChev.classList.remove('is-open');

    // Reset circles
    [circle2, circle3, circle4].forEach(function(c) {
      if (c) {
        c.className = 'tv-step-circle';
      }
    });
    [lbl2, lbl3, lbl4].forEach(function(l) {
      if (l) {
        l.className = 'tv-step-lbl';
      }
    });

    if (section === 'cart') {
      if (cartBody) cartBody.style.display = 'block';
      if (cartChev) cartChev.classList.add('is-open');
      if (subtitle) subtitle.textContent = 'Step 2 of 5 • Shopping Cart';
      if (fillBar) fillBar.style.width = '25%';

      if (circle2) { circle2.classList.add('is-current'); circle2.textContent = '2'; }
      if (lbl2) lbl2.classList.add('is-current');
      if (circle3) circle3.textContent = '3';
      if (circle4) circle4.textContent = '4';

      renderDrawerCart();

    } else if (section === 'fitting') {
      if (fittingBody) fittingBody.style.display = 'block';
      if (fittingChev) fittingChev.classList.add('is-open');
      if (subtitle) subtitle.textContent = 'Step 3 of 5 • Installer Network';
      if (fillBar) fillBar.style.width = '50%';

      if (circle2) {
        circle2.classList.add('is-checked');
        circle2.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg>';
      }
      if (lbl2) lbl2.classList.add('is-checked');
      if (circle3) { circle3.classList.add('is-current'); circle3.textContent = '3'; }
      if (lbl3) lbl3.classList.add('is-current');
      if (circle4) circle4.textContent = '4';

      renderStoreLocator();

    } else if (section === 'contact') {
      if (contactBody) contactBody.style.display = 'block';
      if (contactChev) contactChev.classList.add('is-open');
      if (subtitle) subtitle.textContent = 'Step 4 of 5 • Contact & Vehicle';
      if (fillBar) fillBar.style.width = '75%';

      if (circle2) {
        circle2.classList.add('is-checked');
        circle2.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg>';
      }
      if (circle3) {
        circle3.classList.add('is-checked');
        circle3.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg>';
      }
      if (lbl2) lbl2.classList.add('is-checked');
      if (lbl3) lbl3.classList.add('is-checked');

      if (circle4) { circle4.classList.add('is-current'); circle4.textContent = '4'; }
      if (lbl4) lbl4.classList.add('is-current');

      updateCheckoutSummary();
      loadVehicleMakes();
    }
  }

  function toggleOverviewSection(section) {
    if (currentDrawerSection === section) {
      var body = document.getElementById('tv-' + section + '-section-body');
      var chev = document.getElementById('tv-' + section + '-chevron');
      if (body) {
        var isHidden = body.style.display === 'none' || (!body.style.display && window.getComputedStyle(body).display === 'none');
        body.style.display = isHidden ? 'block' : 'none';
        if (chev) {
          if (isHidden) chev.classList.add('is-open');
          else chev.classList.remove('is-open');
        }
      }
    } else {
      setOverviewActiveSection(section);
    }
  }

  // ── Render Cart Items (Step 2) ──
  function renderDrawerCart() {
    var items = getCartItems();
    var emptyView = document.getElementById('tv-cart-empty-view');
    var filledView = document.getElementById('tv-cart-filled-view');
    var itemsContainer = document.getElementById('tv-cart-items-list');

    var totalTyres = getCartTotalTyres(items);
    var subtotal = getCartSubtotal(items);
    // var vat = Math.round(Math.max(0, subtotal - couponDiscount) * 0.05 * 100) / 100;
    var grandTotal = Math.max(0, subtotal - couponDiscount); //+ vat;

    // Header summaries
    var summaryText = document.getElementById('tv-cart-summary-text');
    if (summaryText) {
      summaryText.textContent = totalTyres + ' ' + (totalTyres === 1 ? 'tyre selected' : 'tyres selected');
    }

    var totalBadge = document.getElementById('tv-cart-total-badge');
    var headerTotal = document.getElementById('tv-header-order-total');
    if (totalBadge && headerTotal) {
      if (grandTotal > 0) {
        headerTotal.textContent = 'AED ' + grandTotal.toFixed(2);
        totalBadge.style.display = 'block';
      } else {
        totalBadge.style.display = 'none';
      }
    }

    // Top Strip
    var stripTyres = document.getElementById('tv-total-strip-tyres');
    var stripAmount = document.getElementById('tv-total-strip-amount');
    if (stripTyres) stripTyres.textContent = totalTyres + ' ' + (totalTyres === 1 ? 'tyre in your cart' : 'tyres in your cart');
    if (stripAmount) stripAmount.textContent = 'AED ' + grandTotal.toFixed(2);

    // Summary calculation rows
    var subtotalEl = document.getElementById('tv-calc-subtotal');
    var discountRow = document.getElementById('tv-calc-discount-row');
    var discountEl = document.getElementById('tv-calc-discount');
    var vatEl = document.getElementById('tv-calc-vat');
    var grandTotalEl = document.getElementById('tv-calc-grand-total');
    var placeOrderBtnText = document.getElementById('tv-place-order-text');

    if (subtotalEl) subtotalEl.textContent = 'AED ' + subtotal.toFixed(2);
    if (discountRow && discountEl) {
      if (couponDiscount > 0) {
        discountEl.textContent = '-AED ' + couponDiscount.toFixed(2);
        discountRow.style.display = 'flex';
      } else {
        discountRow.style.display = 'none';
      }
    }
    // if (vatEl) vatEl.textContent = 'AED ' + vat.toFixed(2);
    if (grandTotalEl) grandTotalEl.textContent = 'AED ' + grandTotal.toFixed(2);
    if (placeOrderBtnText) placeOrderBtnText.textContent = 'PLACE ORDER • AED ' + grandTotal.toFixed(2);

    if (items.length === 0) {
      if (emptyView) emptyView.style.display = 'block';
      if (filledView) filledView.style.display = 'none';
      return;
    }

    if (emptyView) emptyView.style.display = 'none';
    if (filledView) filledView.style.display = 'block';

    if (!itemsContainer) return;
    itemsContainer.innerHTML = '';

    items.forEach(function(item) {
      var card = document.createElement('div');
      card.className = 'tv-cart-item-card';

      var qty = parseInt(item.qty, 10) || 1;
      var unitPrice = parseFloat(item.price) || 0;
      var lineTotal = (qty * unitPrice).toFixed(2);

      card.innerHTML = `
        <div class="tv-item-thumb-box">
          <img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.title)}" class="tv-item-thumb-img" onerror="this.src='/static/assets/images/no-image-available.svg'" />
        </div>
        <div class="tv-item-info">
          <h4 class="tv-item-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</h4>
          <div class="tv-item-meta">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>
            <span>TyresVision Certified Fitment</span>
          </div>
          <div class="tv-item-controls">
            <div class="tv-qty-dropdown-wrap">
              <select class="tv-qty-select" onchange="window.updateDrawerCartQty('${escapeHtml(item.sku)}', this.value)">
                ${[1, 2, 3, 4, 5, 6, 7, 8].map(function(n) {
                  return '<option value="' + n + '"' + (n === qty ? ' selected' : '') + '>' + n + '</option>';
                }).join('')}
              </select>
              <svg class="tv-qty-select-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </div>
            <span class="tv-item-price-unit">AED ${lineTotal}</span>
            <button type="button" onclick="window.removeDrawerCartItem('${escapeHtml(item.sku)}')" class="tv-btn-remove-item" title="Remove item" aria-label="Remove item">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
          </div>
        </div>
      `;
      itemsContainer.appendChild(card);
    });
  }

  function updateDrawerCartQty(sku, newQty) {
    var items = getCartItems();
    var q = parseInt(newQty, 10) || 1;
    for (var i = 0; i < items.length; i++) {
      if (items[i].sku === sku) {
        items[i].qty = q;
        break;
      }
    }
    saveCartItems(items);
    renderDrawerCart();
  }

  function removeDrawerCartItem(sku) {
    var items = getCartItems();
    items = items.filter(function(it) {
      return it.sku !== sku;
    });
    saveCartItems(items);
    renderDrawerCart();
  }

  // ── Coupon Sub-Accordion ──
  function toggleSubAccordion(sub) {
    var body = document.getElementById('tv-sub-acc-' + sub + '-body');
    var chev = document.getElementById('tv-chevron-' + sub);
    if (!body) return;
    var isHidden = body.style.display === 'none' || (!body.style.display && window.getComputedStyle(body).display === 'none');
    body.style.display = isHidden ? 'block' : 'none';
    if (chev) {
      if (isHidden) chev.classList.add('is-open');
      else chev.classList.remove('is-open');
    }
  }

  function applyDrawerCoupon() {
    var input = document.getElementById('tv-drawer-coupon-code');
    var msg = document.getElementById('tv-coupon-status-msg');
    var appliedBox = document.getElementById('tv-coupon-applied-box');
    var inputForm = document.getElementById('tv-coupon-input-form');
    var tag = document.getElementById('tv-coupon-active-tag');

    var code = input ? input.value.trim() : '';
    if (!code) return;

    var items = getCartItems();
    fetch('/api/cart', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ op: 'applyCoupon', code: code, items: items })
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.success) {
        appliedCoupon = data.coupon || code;
        couponDiscount = parseFloat(data.discount) || 0.0;
        if (msg) {
          msg.textContent = 'Coupon applied: ' + (data.label || appliedCoupon);
          msg.className = 'tv-coupon-feedback text-emerald-600 font-bold text-xs mt-1';
          msg.style.display = 'block';
        }
        if (appliedBox) appliedBox.style.display = 'flex';
        if (inputForm) inputForm.style.display = 'none';
        if (tag) tag.textContent = appliedCoupon;
        renderDrawerCart();
      } else {
        if (msg) {
          msg.textContent = data.error || 'Invalid coupon code.';
          msg.className = 'tv-coupon-feedback text-red-600 font-bold text-xs mt-1';
          msg.style.display = 'block';
        }
      }
    })
    .catch(function(err) {
      if (msg) {
        msg.textContent = 'Error applying coupon.';
        msg.className = 'tv-coupon-feedback text-red-600 font-bold text-xs mt-1';
        msg.style.display = 'block';
      }
    });
  }

  function removeDrawerCoupon() {
    appliedCoupon = null;
    couponDiscount = 0.0;
    var msg = document.getElementById('tv-coupon-status-msg');
    var appliedBox = document.getElementById('tv-coupon-applied-box');
    var inputForm = document.getElementById('tv-coupon-input-form');
    var input = document.getElementById('tv-drawer-coupon-code');

    if (appliedBox) appliedBox.style.display = 'none';
    if (inputForm) inputForm.style.display = 'flex';
    if (input) input.value = '';
    if (msg) msg.style.display = 'none';

    renderDrawerCart();
  }

  // ── Step 3: Store Locator & Fitment Network ──
  function loadStoreLocatorData(coords) {
    var url = '/api/store-locator';
    if (coords && coords.lat && coords.lng) {
      url += '?lat=' + coords.lat + '&lng=' + coords.lng;
    }
    fetch(url)
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (data && data.success) {
          storeData = data;
          if (!selectedStore && data.branches && data.branches.length > 0) {
            selectedStore = data.branches[0];
          }
          if (!selectedVan && data.mobileVans && data.mobileVans.length > 0) {
            selectedVan = data.mobileVans[0];
          }
          renderStoreLocator();
        }
      })
      .catch(function(err) {
        console.warn('Failed to fetch store locator:', err);
      });
  }

  function setDrawerDeliveryMode(mode) {
    deliveryMode = mode;

    var btnOutlet = document.getElementById('tv-mode-btn-outlet');
    var btnVan = document.getElementById('tv-mode-btn-van');
    var btnShip = document.getElementById('tv-mode-btn-shipping');

    var contentOutlet = document.getElementById('tv-mode-content-outlet');
    var contentVan = document.getElementById('tv-mode-content-van');
    var contentShip = document.getElementById('tv-mode-content-shipping');

    // Reset buttons
    [btnOutlet, btnVan, btnShip].forEach(function(b) {
      if (b) {
        b.classList.remove('is-active');
        var ic = b.querySelector('.tv-mode-icon-circle');
        if (ic) ic.classList.remove('is-active');
      }
    });

    // Reset contents
    if (contentOutlet) contentOutlet.style.display = 'none';
    if (contentVan) contentVan.style.display = 'none';
    if (contentShip) contentShip.style.display = 'none';

    if (mode === 'install_outlet') {
      if (btnOutlet) {
        btnOutlet.classList.add('is-active');
        var ic1 = btnOutlet.querySelector('.tv-mode-icon-circle');
        if (ic1) ic1.classList.add('is-active');
      }
      if (contentOutlet) contentOutlet.style.display = 'block';
    } else if (mode === 'mobile_van') {
      if (btnVan) {
        btnVan.classList.add('is-active');
        var ic2 = btnVan.querySelector('.tv-mode-icon-circle');
        if (ic2) ic2.classList.add('is-active');
      }
      if (contentVan) contentVan.style.display = 'block';
    } else if (mode === 'free_shipping') {
      if (btnShip) {
        btnShip.classList.add('is-active');
        var ic3 = btnShip.querySelector('.tv-mode-icon-circle');
        if (ic3) ic3.classList.add('is-active');
      }
      if (contentShip) contentShip.style.display = 'block';
    }
  }

  function filterDrawerCity(city, btn) {
    selectedCity = city;
    var pills = document.querySelectorAll('.tv-city-pill');
    pills.forEach(function(p) { p.classList.remove('is-active'); });
    if (btn) btn.classList.add('is-active');
    renderStoreLocator();
  }

  function handleDrawerInstallerSearch(query) {
    searchQuery = (query || '').toLowerCase().trim();
    renderStoreLocator();
  }

  function handleDrawerUseMyLocation() {
    if (isLocating) return;
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser.');
      return;
    }

    var locateBtn = document.getElementById('tv-btn-my-location');
    var locateLbl = document.getElementById('tv-locate-label');
    isLocating = true;
    if (locateLbl) locateLbl.textContent = 'Locating...';

    navigator.geolocation.getCurrentPosition(
      function(pos) {
        var lat = pos.coords.latitude;
        var lng = pos.coords.longitude;
        loadStoreLocatorData({ lat: lat, lng: lng });

        // Geocode area name
        fetch('/api/geocode?lat=' + lat + '&lng=' + lng)
          .then(function(r) { return r.json(); })
          .then(function(d) {
            var searchInput = document.getElementById('tv-installer-search');
            if (searchInput && d.address) {
              searchInput.value = d.address;
            }
          })
          .finally(function() {
            isLocating = false;
            if (locateLbl) locateLbl.textContent = 'Location set';
          });
      },
      function(err) {
        isLocating = false;
        if (locateLbl) locateLbl.textContent = 'Use my location';
        alert('Could not determine your location. Please select an outlet or city manually.');
      },
      { timeout: 8000, enableHighAccuracy: true }
    );
  }

  function renderStoreLocator() {
    renderOutletBranches();
    renderMobileVans();
  }

  function renderOutletBranches() {
    var container = document.getElementById('tv-branches-list');
    if (!container) return;
    container.innerHTML = '';

    var branches = storeData.branches || [];
    var filtered = branches.filter(function(b) {
      var matchCity = selectedCity === 'All' || (b.city && b.city.toLowerCase() === selectedCity.toLowerCase());
      var matchSearch = !searchQuery ||
        (b.name && b.name.toLowerCase().indexOf(searchQuery) > -1) ||
        (b.address && b.address.toLowerCase().indexOf(searchQuery) > -1) ||
        (b.city && b.city.toLowerCase().indexOf(searchQuery) > -1);
      return matchCity && matchSearch;
    });

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="p-6 text-center bg-white rounded-xl border border-gray-200">
          <p class="text-xs text-gray-500">No fitting partners found for this city or search.</p>
          <button type="button" onclick="window.resetStoreFilters()" class="text-xs font-bold text-[#7C3AED] mt-2 underline cursor-pointer">Reset Filters</button>
        </div>
      `;
      return;
    }

    var upcomingDates = getUpcomingDates();
    var timeSlots = storeData.timeSlots || [
      "09:00 AM - 11:00 AM", "11:00 AM - 01:00 PM", "02:00 PM - 04:00 PM", "04:00 PM - 06:00 PM"
    ];

    if (!selectedDate && upcomingDates.length > 0) {
      selectedDate = upcomingDates[0].value;
    }
    if (!selectedTimeSlot && timeSlots.length > 0) {
      selectedTimeSlot = timeSlots[0];
    }

    filtered.forEach(function(branch) {
      var isSelected = selectedStore && selectedStore.id === branch.id;
      var isExpanded = expandedStoreId === branch.id;

      var card = document.createElement('div');
      card.className = 'tv-branch-card' + (isSelected ? ' is-selected' : '');
      card.id = 'branch-card-' + branch.id;

      var whatsappNum = (branch.whatsapp || '+971505069575').replace(/[^0-9]/g, '');
      var lat = branch.lat || 25.2048;
      var lng = branch.lng || 55.2708;

      card.innerHTML = `
        <div class="tv-branch-head" onclick="window.toggleDrawerBranch('${escapeHtml(branch.id)}')">
          <div class="tv-branch-badge-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
          </div>
          <div class="flex-1 min-w-0">
            <div class="tv-branch-title-row">
              <h4 class="tv-branch-name">${escapeHtml(branch.name)}</h4>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="text-gray-400 ${isExpanded ? 'rotate-180 text-[#7C3AED]' : ''}"><polyline points="6 9 12 15 18 9"/></svg>
            </div>
            <p class="tv-branch-address">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="shrink-0 mt-0.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
              <span>${escapeHtml(branch.address)}</span>
            </p>
            <p class="tv-branch-distance">
              <span class="tv-dot-purple"></span>
              <span>${(branch.distance !== undefined ? parseFloat(branch.distance) : 4.5).toFixed(2)} km away</span>
            </p>
          </div>
        </div>

        <div class="tv-branch-actions">
          <a href="https://wa.me/${whatsappNum}" target="_blank" rel="noopener">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="#25D366"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.46 1.32 4.96L2 22l5.25-1.38a9.9 9.9 0 004.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91C21.96 6.45 17.5 2 12.04 2z"/></svg>
            <span>WhatsApp</span>
          </a>
          <a href="https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}" target="_blank" rel="noopener">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>
            <span>Directions</span>
          </a>
          <button type="button" onclick="window.toggleDrawerBranch('${escapeHtml(branch.id)}')">
            <span>Select Date &amp; Time</span>
          </button>
        </div>

        <!-- Floating Anchored Popover -->
        ${isExpanded ? `
          <div class="tv-anchored-popover">
            <div class="tv-popover-caret"></div>
            <div class="tv-popover-header">
              <span class="tv-popover-title">
                <span class="tv-dot-purple"></span>
                <span>Select Fitting Date &amp; Time</span>
              </span>
              <button type="button" onclick="window.toggleDrawerBranch('${escapeHtml(branch.id)}')" class="tv-btn-popover-close">✕</button>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3">
              <div>
                <label class="block text-[11px] font-bold text-gray-700 mb-1">Preferred Date</label>
                <select id="popover-date-${escapeHtml(branch.id)}" class="w-full h-8 px-2 text-xs border border-gray-300 rounded-lg outline-none focus:border-black bg-white">
                  ${upcomingDates.map(function(d) {
                    var isDSelected = selectedDate === d.value;
                    return '<option value="' + d.value + '"' + (isDSelected ? ' selected' : '') + '>' + d.label + '</option>';
                  }).join('')}
                </select>
              </div>

              <div>
                <label class="block text-[11px] font-bold text-gray-700 mb-1">Time Slot</label>
                <select id="popover-time-${escapeHtml(branch.id)}" class="w-full h-8 px-2 text-xs border border-gray-300 rounded-lg outline-none focus:border-black bg-white">
                  ${timeSlots.map(function(t) {
                    var isTSelected = selectedTimeSlot === t;
                    return '<option value="' + t + '"' + (isTSelected ? ' selected' : '') + '>' + t + '</option>';
                  }).join('')}
                </select>
              </div>
            </div>

            <button
              type="button"
              onclick="window.confirmBranchFitting('${escapeHtml(branch.id)}')"
              class="btn-slide-black w-full py-2.5 rounded-lg text-xs font-extrabold uppercase tracking-wider flex items-center justify-center gap-2"
            >
              <span>CONFIRM &amp; PROCEED TO CHECKOUT</span>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg>
            </button>
          </div>
        ` : ''}
      `;
      container.appendChild(card);
    });
  }

  function toggleDrawerBranch(branchId) {
    if (expandedStoreId === branchId) {
      expandedStoreId = null;
    } else {
      expandedStoreId = branchId;
      var branches = storeData.branches || [];
      for (var i = 0; i < branches.length; i++) {
        if (branches[i].id === branchId) {
          selectedStore = branches[i];
          break;
        }
      }
    }
    renderOutletBranches();
  }

  function confirmBranchFitting(branchId) {
    var dateEl = document.getElementById('popover-date-' + branchId);
    var timeEl = document.getElementById('popover-time-' + branchId);

    if (dateEl && dateEl.value) selectedDate = dateEl.value;
    if (timeEl && timeEl.value) selectedTimeSlot = timeEl.value;

    var upcomingDates = getUpcomingDates();
    var timeSlots = storeData.timeSlots || [
      "09:00 AM - 11:00 AM", "11:00 AM - 01:00 PM", "02:00 PM - 04:00 PM", "04:00 PM - 06:00 PM"
    ];
    if (!selectedDate && upcomingDates.length > 0) selectedDate = upcomingDates[0].value;
    if (!selectedTimeSlot && timeSlots.length > 0) selectedTimeSlot = timeSlots[0];

    var branches = storeData.branches || [];
    for (var i = 0; i < branches.length; i++) {
      if (branches[i].id === branchId) {
        selectedStore = branches[i];
        break;
      }
    }

    expandedStoreId = null;
    deliveryMode = 'install_outlet';

    // Update Step 3 header text
    var summaryEl = document.getElementById('tv-fitting-summary-text');
    if (summaryEl && selectedStore) {
      summaryEl.textContent = selectedStore.name + ' (' + selectedDate + ')';
    }

    setOverviewActiveSection('contact');
  }

  function renderMobileVans() {
    var container = document.getElementById('tv-mobile-vans-list');
    if (!container) return;
    container.innerHTML = '';

    var vans = storeData.mobileVans || [];
    var upcomingDates = getUpcomingDates();
    var timeSlots = storeData.timeSlots || [
      "09:00 AM - 11:00 AM", "11:00 AM - 01:00 PM", "02:00 PM - 04:00 PM", "04:00 PM - 06:00 PM"
    ];

    if (!selectedDate && upcomingDates.length > 0) {
      selectedDate = upcomingDates[0].value;
    }
    if (!selectedTimeSlot && timeSlots.length > 0) {
      selectedTimeSlot = timeSlots[0];
    }

    vans.forEach(function(van) {
      var card = document.createElement('div');
      card.className = 'tv-branch-card';
      var whatsappNum = (van.whatsapp || '+971505069575').replace(/[^0-9]/g, '');

      card.innerHTML = `
        <div class="tv-branch-head">
          <div class="tv-branch-badge-icon tv-van-badge-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>
          </div>
          <div class="flex-1 min-w-0">
            <h4 class="tv-branch-name">${escapeHtml(van.name)}</h4>
            <p class="tv-branch-address">${escapeHtml(van.address)}</p>
            <p class="tv-branch-distance">
              <span class="text-emerald-600 font-bold">Doorstep Fitting Across UAE</span>
            </p>
          </div>
        </div>

        <!-- Mobile Fitting Location Input -->
        <div class="mt-3 pt-3 border-t border-gray-100">
          <label class="block text-[11px] font-bold text-gray-700 mb-1">Fitting Address / Villa / Office Car Park <span class="text-red-500">*</span></label>
          <input
            type="text"
            id="van-addr-${escapeHtml(van.id)}"
            value="${escapeHtml(mobileAddress)}"
            placeholder="e.g. Villa 24, Springs 14, Dubai"
            class="tv-form-input mb-2.5"
          />

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3">
            <div>
              <label class="block text-[10.5px] font-bold text-gray-700 mb-1">Preferred Date</label>
              <select id="van-date-${escapeHtml(van.id)}" class="tv-form-select">
                ${upcomingDates.map(function(d) {
                  return '<option value="' + d.value + '"' + (selectedDate === d.value ? ' selected' : '') + '>' + d.label + '</option>';
                }).join('')}
              </select>
            </div>
            <div>
              <label class="block text-[10.5px] font-bold text-gray-700 mb-1">Time Slot</label>
              <select id="van-time-${escapeHtml(van.id)}" class="tv-form-select">
                ${timeSlots.map(function(t) {
                  return '<option value="' + t + '"' + (selectedTimeSlot === t ? ' selected' : '') + '>' + t + '</option>';
                }).join('')}
              </select>
            </div>
          </div>

          <button
            type="button"
            onclick="window.confirmVanFitting('${escapeHtml(van.id)}')"
            class="btn-slide-black w-full py-2.5 rounded-lg text-xs font-bold uppercase tracking-wider flex items-center justify-center gap-2"
          >
            <span>CONFIRM &amp; PROCEED TO CHECKOUT</span>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg>
          </button>
        </div>
      `;
      container.appendChild(card);
    });
  }

  function confirmVanFitting(vanId) {
    var addrEl = document.getElementById('van-addr-' + vanId);
    var dateEl = document.getElementById('van-date-' + vanId);
    var timeEl = document.getElementById('van-time-' + vanId);

    mobileAddress = addrEl ? addrEl.value.trim() : '';
    if (dateEl && dateEl.value) selectedDate = dateEl.value;
    if (timeEl && timeEl.value) selectedTimeSlot = timeEl.value;

    var upcomingDates = getUpcomingDates();
    var timeSlots = storeData.timeSlots || [
      "09:00 AM - 11:00 AM", "11:00 AM - 01:00 PM", "02:00 PM - 04:00 PM", "04:00 PM - 06:00 PM"
    ];
    if (!selectedDate && upcomingDates.length > 0) selectedDate = upcomingDates[0].value;
    if (!selectedTimeSlot && timeSlots.length > 0) selectedTimeSlot = timeSlots[0];

    if (!mobileAddress) {
      alert('Please enter your doorstep fitting address.');
      if (addrEl) addrEl.focus();
      return;
    }

    var vans = storeData.mobileVans || [];
    for (var i = 0; i < vans.length; i++) {
      if (vans[i].id === vanId) {
        selectedVan = vans[i];
        break;
      }
    }

    deliveryMode = 'mobile_van';

    var summaryEl = document.getElementById('tv-fitting-summary-text');
    if (summaryEl) {
      summaryEl.textContent = 'Mobile Doorstep Van (' + selectedDate + ')';
    }

    setOverviewActiveSection('contact');
  }

  function handleConfirmFreeShipping() {
    deliveryMode = 'free_shipping';
    var summaryEl = document.getElementById('tv-fitting-summary-text');
    if (summaryEl) {
      summaryEl.textContent = 'Free Delivery to Doorstep';
    }
    setOverviewActiveSection('contact');
  }

  function resetStoreFilters() {
    selectedCity = 'All';
    searchQuery = '';
    var searchInput = document.getElementById('tv-installer-search');
    if (searchInput) searchInput.value = '';
    var pills = document.querySelectorAll('.tv-city-pill');
    pills.forEach(function(p, idx) {
      if (idx === 0) p.classList.add('is-active');
      else p.classList.remove('is-active');
    });
    renderStoreLocator();
  }

  // ── Step 4: Contact & Vehicle Details ──
  function loadVehicleMakes() {
    if (makesList.length > 0) return;
    fetch('/api/vehicles?action=makes')
      .then(function(res) { return res.json(); })
      .then(function(data) {
        if (Array.isArray(data)) {
          makesList = data;
          var makeSelect = document.getElementById('tv-vehicle-make');
          if (makeSelect) {
            makeSelect.innerHTML = '<option value="">Select Make</option>';
            data.forEach(function(m) {
              var opt = document.createElement('option');
              opt.value = m.value;
              opt.textContent = m.label;
              makeSelect.appendChild(opt);
            });
          }
        }
      })
      .catch(function(e) { console.warn('Vehicle makes load error:', e); });
  }

  function handleDrawerMakeChange(make) {
    selectedMake = make;
    selectedModel = '';
    selectedYear = '';

    var modelSelect = document.getElementById('tv-vehicle-model');
    var yearSelect = document.getElementById('tv-vehicle-year');

    if (!make) {
      if (modelSelect) {
        modelSelect.innerHTML = '<option value="">Select Model</option>';
        modelSelect.disabled = true;
      }
      if (yearSelect) {
        yearSelect.innerHTML = '<option value="">Select Year</option>';
      }
      return;
    }

    fetch('/api/vehicles?action=models&make=' + encodeURIComponent(make))
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (modelSelect && Array.isArray(data)) {
          modelSelect.disabled = false;
          modelSelect.innerHTML = '<option value="">Select Model</option>';
          data.forEach(function(m) {
            var opt = document.createElement('option');
            opt.value = m.value;
            opt.textContent = m.label;
            modelSelect.appendChild(opt);
          });
        }
      });
  }

  function handleDrawerModelChange(model) {
    selectedModel = model;
    var yearSelect = document.getElementById('tv-vehicle-year');

    fetch('/api/vehicles?action=years&model=' + encodeURIComponent(model))
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (yearSelect && Array.isArray(data)) {
          yearSelect.innerHTML = '<option value="">Select Year</option>';
          data.forEach(function(y) {
            var opt = document.createElement('option');
            opt.value = y.value;
            opt.textContent = y.label;
            yearSelect.appendChild(opt);
          });
        }
      });
  }

  function handlePaymentMethodChange(val) {
    paymentMethod = val;
    var wrapLink = document.getElementById('tv-pm-wrap-link');
    var wrapCod = document.getElementById('tv-pm-wrap-cod');

    if (val === 'payment_link') {
      if (wrapLink) wrapLink.classList.add('is-active');
      if (wrapCod) wrapCod.classList.remove('is-active');
      if (wrapLink) {
        var c1 = wrapLink.querySelector('.tv-radio-circle');
        if (c1) c1.classList.add('is-checked');
      }
      if (wrapCod) {
        var c2 = wrapCod.querySelector('.tv-radio-circle');
        if (c2) c2.classList.remove('is-checked');
      }
    } else {
      if (wrapCod) wrapCod.classList.add('is-active');
      if (wrapLink) wrapLink.classList.remove('is-active');
      if (wrapCod) {
        var c1 = wrapCod.querySelector('.tv-radio-circle');
        if (c1) c1.classList.add('is-checked');
      }
      if (wrapLink) {
        var c2 = wrapLink.querySelector('.tv-radio-circle');
        if (c2) c2.classList.remove('is-checked');
      }
    }
  }

  function updateCheckoutSummary() {
    var summaryEl = document.getElementById('tv-shipping-summary-text');
    if (!summaryEl) return;

    if (deliveryMode === 'free_shipping') {
      summaryEl.innerHTML = '<span><strong class="text-gray-900">Mode:</strong> Free Direct Shipping (Doorstep)</span>';
    } else if (deliveryMode === 'mobile_van') {
      var vName = selectedVan ? selectedVan.name : 'Mobile Fitting Fleet';
      summaryEl.innerHTML = `
        <span><strong class="text-gray-900">Mode:</strong> Mobile Van Service</span> • 
        <span><strong class="text-gray-900">Address:</strong> ${escapeHtml(mobileAddress || 'Customer Doorstep')}</span>
        ${selectedDate ? ` • <span><strong class="text-gray-900">Date:</strong> ${selectedDate}</span>` : ''}
        ${selectedTimeSlot ? ` • <span><strong class="text-gray-900">Time:</strong> ${selectedTimeSlot}</span>` : ''}
      `;
    } else {
      var sName = selectedStore ? selectedStore.name : 'TyresVision Al Quoz Hub';
      summaryEl.innerHTML = `
        <span><strong class="text-gray-900">Mode:</strong> Install at Outlet</span> • 
        <span><strong class="text-gray-900">Installer:</strong> ${escapeHtml(sName)}</span>
        ${selectedDate ? ` • <span><strong class="text-gray-900">Date:</strong> ${selectedDate}</span>` : ''}
        ${selectedTimeSlot ? ` • <span><strong class="text-gray-900">Time:</strong> ${selectedTimeSlot}</span>` : ''}
      `;
    }

    // Auto fill street with mobileAddress if set
    var streetInput = document.getElementById('tv-input-street');
    if (streetInput && !streetInput.value && mobileAddress) {
      streetInput.value = mobileAddress;
    }
  }

  // ── Place Order API Call ──
  function handleDrawerPlaceOrder() {
    var errorBanner = document.getElementById('tv-checkout-error-banner');
    var errorMsg = document.getElementById('tv-checkout-error-msg');
    var placeBtn = document.getElementById('tv-btn-place-order');
    var spinner = document.getElementById('tv-place-order-spinner');
    var arrow = document.getElementById('tv-place-order-arrow');

    function showError(msg) {
      if (errorBanner && errorMsg) {
        errorMsg.textContent = msg;
        errorBanner.style.display = 'flex';
        errorBanner.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else {
        alert(msg);
      }
    }

    if (errorBanner) errorBanner.style.display = 'none';

    var items = getCartItems();
    if (!items || items.length === 0) {
      showError('Your cart is empty. Please add tyres first.');
      return;
    }

    var fname = (document.getElementById('tv-input-fname')?.value || '').trim();
    var lname = (document.getElementById('tv-input-lname')?.value || '').trim();
    var phone = (document.getElementById('tv-input-phone')?.value || '').trim();
    var email = (document.getElementById('tv-input-email')?.value || '').trim();
    var street = (document.getElementById('tv-input-street')?.value || '').trim();
    var city = (document.getElementById('tv-input-city')?.value || '').trim();
    var emirate = document.getElementById('tv-input-emirate')?.value || 'Dubai';

    var make = document.getElementById('tv-vehicle-make')?.value || '';
    var model = document.getElementById('tv-vehicle-model')?.value || '';
    var year = document.getElementById('tv-vehicle-year')?.value || '';
    var plate = (document.getElementById('tv-vehicle-plate')?.value || '').trim();
    var comments = (document.getElementById('tv-drawer-order-comments')?.value || '').trim();

    if (!fname || !lname) {
      showError('Please enter your First Name and Last Name.');
      return;
    }
    if (!phone) {
      showError('Please enter your UAE mobile number.');
      return;
    }
    if (!street || !city) {
      showError('Please enter your Street address and City.');
      return;
    }

    // Format phone with +971
    var cleanPhone = phone.replace(/^0+/, '');
    if (!cleanPhone.startsWith('+')) {
      cleanPhone = '+971' + cleanPhone.replace(/^971/, '');
    }

    var vehicleParts = [
      make ? 'Make: ' + make : '',
      model ? 'Model: ' + model : '',
      year ? 'Year: ' + year : '',
      plate ? 'Plate: ' + plate : ''
    ].filter(Boolean).join(', ');

    var shippingPayload = {
      firstname: fname,
      lastname: lname,
      telephone: cleanPhone,
      email: email,
      street: street + (vehicleParts ? ' (' + vehicleParts + ')' : ''),
      city: city,
      emirate: emirate,
      country_code: 'AE'
    };

    var installerPayload = {
      deliveryMode: deliveryMode,
      storeId: selectedStore ? selectedStore.id : (selectedVan ? selectedVan.id : null),
      pickupDate: selectedDate,
      pickupTime: selectedTimeSlot,
      pickupLocation: deliveryMode === 'mobile_van' ? (mobileAddress || street) : ''
    };

    isPlacingOrder = true;
    if (placeBtn) placeBtn.disabled = true;
    if (spinner) spinner.style.display = 'inline-block';
    if (arrow) arrow.style.display = 'none';

    fetch('/api/cart', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        op: 'placeOrder',
        items: items,
        shipping: shippingPayload,
        installer: installerPayload,
        paymentMethod: paymentMethod,
        discount: couponDiscount,
        orderComments: comments
      })
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data && data.success) {
        var orderNum = data.orderNumber || data.orderId || 'TV-' + Date.now().toString().slice(-6);

        // Update Success Screen details
        var successNum = document.getElementById('tv-success-ordernumber');
        var successCust = document.getElementById('tv-success-customer');
        var successPhone = document.getElementById('tv-success-phone');
        var successService = document.getElementById('tv-success-service');
        var successPayment = document.getElementById('tv-success-payment');

        if (successNum) successNum.textContent = orderNum;
        if (successCust) successCust.textContent = fname + ' ' + lname;
        if (successPhone) successPhone.textContent = cleanPhone;
        if (successService) {
          successService.textContent = deliveryMode === 'install_outlet' ?
            'Installer Workshop Fitting (' + (selectedStore ? selectedStore.name : 'Al Quoz Hub') + ')' :
            deliveryMode === 'mobile_van' ? 'Mobile Van Doorstep Fitting' : 'Direct Tyre Shipping';
        }
        if (successPayment) {
          successPayment.textContent = paymentMethod === 'payment_link' ?
            'Pay via Payment Link' : 'Cash / Card on Completion';
        }

        // Show Success Screen
        var successScreen = document.getElementById('tv-drawer-success-screen');
        var mainFlow = document.getElementById('tv-drawer-main-flow');
        if (mainFlow) mainFlow.style.display = 'none';
        if (successScreen) successScreen.style.display = 'flex';

        // Clear local cart
        saveCartItems([]);
        appliedCoupon = null;
        couponDiscount = 0.0;
        updateCartBadges();

      } else {
        showError(data.error || 'Failed to place order. Please try again.');
      }
    })
    .catch(function(err) {
      showError('Connection error while placing order. Please try again.');
    })
    .finally(function() {
      isPlacingOrder = false;
      if (placeBtn) placeBtn.disabled = false;
      if (spinner) spinner.style.display = 'none';
      if (arrow) arrow.style.display = 'inline-block';
    });
  }

  function resetDrawerAndContinue() {
    closeOverviewDrawer();
    var successScreen = document.getElementById('tv-drawer-success-screen');
    var mainFlow = document.getElementById('tv-drawer-main-flow');
    if (successScreen) successScreen.style.display = 'none';
    if (mainFlow) mainFlow.style.display = 'flex';
    setOverviewActiveSection('cart');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // ── Integrate Existing Storefront Add-To-Cart Handlers ──
  window.addToCartWithCard = function(btn, title, basePrice) {
    var card = btn ? btn.closest('.tv-product-card') : null;
    var select = card ? card.querySelector('.tv-qty-select') : null;
    var qty = select ? parseInt(select.value, 10) || 1 : 4;
    var imgEl = card ? (card.querySelector('.tv-product-img') || card.querySelector('.tv-card-main-img')) : null;
    var imgSrc = imgEl ? (imgEl.src || imgEl.getAttribute('data-src') || card.getAttribute('data-image')) : '';
    var sizeBadge = card ? (card.querySelector('.tv-card-spec-text') || card.querySelector('.tv-card-size-badge')) : null;
    var sizeText = sizeBadge ? sizeBadge.textContent.trim() : (card ? (card.getAttribute('data-full-spec') || card.getAttribute('data-size') || '') : '');
    var brand = card ? (card.getAttribute('data-brand-name') || '') : '';
    var pattern = card ? (card.getAttribute('data-pattern') || title) : title;
    var sku = card ? (card.getAttribute('data-sku') || ('SKU-' + pattern.replace(/[^a-zA-Z0-9]/g, '-').toLowerCase())) : '';

    var originalHTML = btn.innerHTML;
    btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg> Added';
    btn.style.background = '#10B981';

    addTyreToCart({
      title: pattern,
      brand: brand,
      price: basePrice,
      qty: qty,
      image: imgSrc,
      size: sizeText,
      sku: sku
    });

    if (typeof showToast === 'function') {
      showToast('Added ' + qty + 'x ' + pattern + ' to cart!', 'success');
    }

    setTimeout(function() {
      btn.innerHTML = originalHTML;
      btn.style.background = '';
    }, 1200);
  };

  window.addQuickViewToCart = function(btn) {
    if (!window.currentQuickViewProduct) return;
    var p = window.currentQuickViewProduct;
    var qty = window.currentQuickViewQty || 4;

    addTyreToCart({
      title: p.fullTitle || p.name || 'Tyre',
      price: p.price,
      qty: qty,
      image: p.image || '',
      size: p.size || '',
      sku: p.sku || 'SKU-QV'
    });

    if (typeof closeQuickView === 'function') closeQuickView();
    if (typeof showToast === 'function') {
      showToast('Added ' + qty + 'x ' + p.fullTitle + ' to cart!', 'success');
    }
  };

  window.addToCartPDP = function(productId, title, price) {
    var input = document.getElementById('pdp-qty-input');
    var qty = input ? (parseInt(input.value, 10) || 1) : 4;
    var unitPrice = (typeof window.pdpProductPrice === 'number') ? window.pdpProductPrice : price;
    var imgEl = document.querySelector('.tv-pdp-main-img img, .pdp-gallery-main img');
    var imgSrc = imgEl ? imgEl.src : '';

    addTyreToCart({
      id: productId,
      sku: 'PDP-' + productId,
      title: title,
      price: unitPrice,
      qty: qty,
      image: imgSrc
    });

    if (typeof showToast === 'function') {
      showToast('Added ' + qty + 'x ' + title + ' to cart!', 'success');
    }
  };

  window.addRelToCart = function(btn, title, price) {
    var card = btn ? btn.closest('.tv-rel-card') : null;
    var qtySelect = card ? card.querySelector('.tv-rel-qty-select') : null;
    var qty = qtySelect ? (parseInt(qtySelect.value, 10) || 1) : 4;
    var imgEl = card ? card.querySelector('img') : null;
    var imgSrc = imgEl ? imgEl.src : '';

    addTyreToCart({
      title: title,
      price: price,
      qty: qty,
      image: imgSrc,
      sku: 'REL-' + (title || '').replace(/[^a-zA-Z0-9]/g, '-').toLowerCase()
    });

    if (typeof showToast === 'function') {
      showToast('Added ' + qty + 'x ' + title + ' to cart!', 'success');
    }
  };

  window.showCartModal = function(e) {
    if (e) e.preventDefault();
    openOverviewDrawer('cart');
  };

  // Expose global drawer APIs
  window.openOverviewDrawer = openOverviewDrawer;
  window.closeOverviewDrawer = closeOverviewDrawer;
  window.toggleOverviewDrawer = toggleOverviewDrawer;
  window.setOverviewActiveSection = setOverviewActiveSection;
  window.toggleOverviewSection = toggleOverviewSection;
  window.updateDrawerCartQty = updateDrawerCartQty;
  window.removeDrawerCartItem = removeDrawerCartItem;
  window.toggleSubAccordion = toggleSubAccordion;
  window.applyDrawerCoupon = applyDrawerCoupon;
  window.removeDrawerCoupon = removeDrawerCoupon;
  window.setDrawerDeliveryMode = setDrawerDeliveryMode;
  window.filterDrawerCity = filterDrawerCity;
  window.handleDrawerInstallerSearch = handleDrawerInstallerSearch;
  window.handleDrawerUseMyLocation = handleDrawerUseMyLocation;
  window.toggleDrawerBranch = toggleDrawerBranch;
  window.confirmBranchFitting = confirmBranchFitting;
  window.confirmVanFitting = confirmVanFitting;
  window.handleConfirmFreeShipping = handleConfirmFreeShipping;
  window.resetStoreFilters = resetStoreFilters;
  window.handleDrawerMakeChange = handleDrawerMakeChange;
  window.handleDrawerModelChange = handleDrawerModelChange;
  window.handlePaymentMethodChange = handlePaymentMethodChange;
  window.handleDrawerPlaceOrder = handleDrawerPlaceOrder;
  window.resetDrawerAndContinue = resetDrawerAndContinue;
  window.addTyreToCart = addTyreToCart;

  /* ==========================================================================
     Vehicle Compatibility Overlay Modal (Matching TyresCart Design)
     ========================================================================== */
  function ItemSizeClose() {
    var modal = document.getElementById("item-size");
    var overlay = document.getElementById("item-size-overlay");
    if (modal) modal.classList.add("translate-y-full");
    if (overlay) overlay.classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
  }

  function filterTyrePopupContent(query) {
    var container = document.querySelector('#item-size .tyre-popup-content');
    if (!container) return;
    var items = container.querySelectorAll(':scope > div');
    var q = (query || '').toLowerCase().trim();
    items.forEach(function(item) {
      var text = item.textContent.toLowerCase();
      item.style.display = (!q || text.indexOf(q) !== -1) ? '' : 'none';
    });
  }

  function openTyreVehicleModal(width, height, rim, productName) {
    // If passed a DOM element, extract attributes from closest product card
    if (width && typeof width === 'object' && width.nodeType) {
      var card = width.closest('.tv-product-card') || width.closest('[data-width]') || width.closest('.tv-rel-carousel-card') || width.closest('[data-slug]');
      if (card) {
        productName = card.getAttribute('data-full-title') || card.getAttribute('data-title') || card.querySelector('.tv-card-pattern')?.textContent?.trim() || '';
        width = card.getAttribute('data-width') || '';
        height = card.getAttribute('data-profile') || card.getAttribute('data-height') || '';
        rim = card.getAttribute('data-rim') || '';

        // Robust fallback: parse from data-size, data-full-spec, or productName if any dimension missing
        if (!width || !height || !rim) {
          var sizeStr = card.getAttribute('data-size') || card.getAttribute('data-full-spec') || productName || '';
          var match = sizeStr.match(/(\d{3})(?:[\/\s-](\d{2,3}))?\s*(?:R|Z|ZR|r)?\s*(\d{2})/i);
          if (match) {
            if (!width) width = match[1];
            if (!height) height = match[2] || '';
            if (!rim) rim = match[3];
          }
        }
      }
    }

    var modal = document.getElementById("item-size");
    var overlay = document.getElementById("item-size-overlay");
    var loader = document.getElementById("item-size-loader");
    var contentEl = document.querySelector("#item-size .tyre-popup-content");
    var titleEl = document.querySelector("#item-size .product-name");
    var searchInput = document.getElementById("item-size-search");

    if (titleEl && productName) {
      titleEl.textContent = productName;
    }
    if (searchInput) searchInput.value = '';
    if (contentEl) contentEl.innerHTML = '';
    if (loader) loader.classList.remove('hidden');

    if (modal) modal.classList.remove("translate-y-full");
    if (overlay) overlay.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");

    var wClean = (String(width || '').match(/\d+/) || ['175'])[0];
    var hClean = (String(height || '').match(/\d+/) || ['65'])[0];
    var rClean = (String(rim || '').match(/\d+/) || ['14'])[0];

    var params = new URLSearchParams();
    params.append('width', wClean);
    params.append('height', hClean);
    params.append('rim', rClean);

    fetch('/tyrefinder/ajax/buytyresearch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
      body: params.toString()
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (loader) loader.classList.add('hidden');
      if (data.status === 'success' && data.html) {
        if (contentEl) {
          contentEl.innerHTML = data.html;
        }
      } else {
        if (contentEl) {
          contentEl.innerHTML = '<div class="col-span-full py-12 text-center text-gray-500 font-medium">' + (data.message || 'No vehicle fitment data found for this size.') + '</div>';
        }
      }
    })
    .catch(function(err) {
      if (loader) loader.classList.add('hidden');
      if (contentEl) {
        contentEl.innerHTML = '<div class="col-span-full py-12 text-center text-gray-500 font-medium">Unable to load compatible vehicles. Please try again.</div>';
      }
    });
  }

  // Delegated capturing click listener so clicking the car icon anywhere ALWAYS opens the modal
  document.addEventListener('click', function(e) {
    var iconBtn = e.target.closest('.tyre-type-icons');
    if (iconBtn) {
      e.preventDefault();
      e.stopPropagation();
      openTyreVehicleModal(iconBtn);
    }
  }, true);

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      var modal = document.getElementById("item-size");
      if (modal && !modal.classList.contains("translate-y-full")) {
        ItemSizeClose();
      }
    }
  });

  window.openTyreVehicleModal = openTyreVehicleModal;
  window.filterTyrePopupContent = filterTyrePopupContent;
  window.ItemSizeClose = ItemSizeClose;

  // Initialize on load
  document.addEventListener('DOMContentLoaded', function() {
    updateCartBadges();
  });

})();



