/**
 * static/visionadmin/sections.js
 * VisionAdmin CMS — Dynamic Page Sections Controller (Home & Custom Pages)
 */

document.addEventListener('DOMContentLoaded', () => {
  let allSections = [];
  let currentLocaleTab = 'en';
  let deleteSectionId = null;
    let repeaterItems = [];
  let extraSectionData = {};
  let composableBlocks = [];

  const TYPE_METADATA = {
    hero: { 
      label: 'Hero Banner', 
      shortLabel: 'Hero', 
      emoji: '🦸', 
      badgeBg: 'bg-blue-50 text-blue-800 border-blue-200/80',
      tagColor: 'bg-[#2563FF]',
      desc: 'Hero Banner with Quote Card & Trust Badges' 
    },
    stats: { 
      label: 'Statistics Grid', 
      shortLabel: 'Stats', 
      emoji: '📊', 
      badgeBg: 'bg-indigo-50 text-indigo-800 border-indigo-200/80',
      tagColor: 'bg-indigo-500',
      desc: 'Atmospheric 4-Metric Stats Band' 
    },
    features: { 
      label: 'Why / Features', 
      shortLabel: 'Features', 
      emoji: '✨', 
      badgeBg: 'bg-purple-50 text-purple-800 border-purple-200/80',
      tagColor: 'bg-purple-500',
      desc: '6 Value Cards with Icons + WhatsApp/Call' 
    },
    price_table: { 
      label: 'Tyre Price Table', 
      shortLabel: 'Prices', 
      emoji: '💰', 
      badgeBg: 'bg-blue-50 text-blue-800 border-blue-200/80',
      tagColor: 'bg-[#2563FF]',
      desc: 'Vehicle & Tyre Size Price Matrix with Value Cards' 
    },
    services: { 
      label: 'Car Care Services', 
      shortLabel: 'Services', 
      emoji: '🛠️', 
      badgeBg: 'bg-teal-50 text-teal-800 border-teal-200/80',
      tagColor: 'bg-teal-500',
      desc: '16 Car Care Services Grid' 
    },
    how_it_works: { 
      label: 'How It Works', 
      shortLabel: 'Steps', 
      emoji: '🔢', 
      badgeBg: 'bg-cyan-50 text-cyan-800 border-cyan-200/80',
      tagColor: 'bg-cyan-500',
      desc: '4-Step Process Flow with WhatsApp/Call' 
    },
    shop_by: { 
      label: 'Shop by Size, Car & Brand', 
      shortLabel: 'Shop By', 
      emoji: '🔍', 
      badgeBg: 'bg-blue-50 text-blue-800 border-blue-200/80',
      tagColor: 'bg-[#2563FF]',
      desc: 'Browse Tyres by Sizes, Vehicles, and Brand Tiers' 
    },
    coverage: { 
      label: 'Delivery & Fitting Coverage', 
      shortLabel: 'Coverage', 
      emoji: '📍', 
      badgeBg: 'bg-teal-50 text-teal-800 border-teal-200/80',
      tagColor: 'bg-teal-500',
      desc: 'Partner Centres, Mobile Vans & Area Coverage Chips' 
    },
    advice: { 
      label: 'Tyre Buying Advice', 
      shortLabel: 'Advice', 
      emoji: '💡', 
      badgeBg: 'bg-indigo-50 text-indigo-800 border-indigo-200/80',
      tagColor: 'bg-indigo-500',
      desc: '6 Buying Guide & Tyre Advice Cards' 
    },
    brands: { 
      label: 'Brands List', 
      shortLabel: 'Brands', 
      emoji: '🏷️', 
      badgeBg: 'bg-amber-50 text-amber-800 border-amber-200/80',
      tagColor: 'bg-amber-500',
      desc: '60+ Brand Pills & Logos' 
    },
    testimonials: { 
      label: 'Customer Reviews', 
      shortLabel: 'Reviews', 
      emoji: '⭐', 
      badgeBg: 'bg-yellow-50 text-yellow-800 border-yellow-200/80',
      tagColor: 'bg-yellow-500',
      desc: 'Customer Star Reviews Grid' 
    },
    faq: { 
      label: 'FAQ Accordion', 
      shortLabel: 'FAQ', 
      emoji: '❓', 
      badgeBg: 'bg-sky-50 text-sky-800 border-sky-200/80',
      tagColor: 'bg-sky-500',
      desc: 'Collapsible Q&A Accordion List' 
    },
    cta: { 
      label: 'CTA Action Box', 
      shortLabel: 'CTA Box', 
      emoji: '🚀', 
      badgeBg: 'bg-rose-50 text-rose-800 border-rose-200/80',
      tagColor: 'bg-rose-500',
      desc: 'Bottom Action Card with Buttons & Footer Note' 
    },
    content_image: { 
      label: 'Content + Image', 
      shortLabel: '2-Column', 
      emoji: '🖼️', 
      badgeBg: 'bg-blue-50 text-blue-800 border-blue-200/80',
      tagColor: 'bg-blue-500',
      desc: 'Narrative Story with Media & Floating Badge' 
    },
    custom: { 
      label: 'Composable Custom Section', 
      shortLabel: 'Composable', 
      emoji: '🧩', 
      badgeBg: 'bg-violet-50 text-violet-800 border-violet-200/80',
      tagColor: 'bg-violet-500',
      desc: 'Stack any combination of Cards, Metrics, Chips, FAQs, and CTAs freely' 
    },
    mission_vision: { 
      label: 'Mission & Team', 
      shortLabel: 'Mission', 
      emoji: '🎯', 
      badgeBg: 'bg-orange-50 text-orange-800 border-orange-200/80',
      tagColor: 'bg-orange-500',
      desc: 'Specialist Team / Mission 2-Column Split' 
    }
  };

  // Target Page handling (Query param ?page=...)
  const urlParams = new URLSearchParams(window.location.search);
  let currentPageSlug = urlParams.get('page') || 'home';

  const selectTargetPage = document.getElementById('select-target-page');
  const btnTargetPageDropdown = document.getElementById('btn-target-page-dropdown');
  const targetPageDropdownMenu = document.getElementById('target-page-dropdown-menu');
  const targetPageCurrentLabel = document.getElementById('target-page-current-label');
  const targetPageChevron = document.getElementById('target-page-chevron');
  const targetPageOptionsList = document.getElementById('target-page-options-list');
  const badgePageSlug = document.getElementById('badge-page-slug');
  const pageSectionsTitle = document.getElementById('page-sections-title');
  const linkViewLivePage = document.getElementById('link-view-live-page');

  // DOM Elements
  const sectionsContainer = document.getElementById('sections-container');
  const statTotal = document.getElementById('stat-total-sections');
  const statActive = document.getElementById('stat-active-sections');
  const statInactive = document.getElementById('stat-inactive-sections');

  // Modal Elements
  const sectionModal = document.getElementById('section-modal');
  const sectionModalBox = document.getElementById('section-modal-box');
  const modalTitle = document.getElementById('modal-title');
  const sectionForm = document.getElementById('section-form');
  const btnAddSection = document.getElementById('btn-add-section');
  const btnCloseModal = document.getElementById('btn-close-modal');
  const btnCancelModal = document.getElementById('btn-cancel-modal');
  const btnSaveSection = document.getElementById('btn-save-section');

  // Preview Modal Elements
  const previewModal = document.getElementById('preview-modal');
  const previewModalBox = document.getElementById('preview-modal-box');
  const previewModalTitle = document.getElementById('preview-modal-title');
  const previewModalBadge = document.getElementById('preview-modal-badge');
  const previewIframeWrapper = document.getElementById('preview-iframe-wrapper');
  const previewIframe = document.getElementById('preview-iframe');
  const btnClosePreviewModal = document.getElementById('btn-close-preview-modal');
  const previewOpenExternal = document.getElementById('preview-open-external');
  let currentPreviewSecId = null;

  // Language Tabs
  const tabEn = document.getElementById('tab-en');
  const tabAr = document.getElementById('tab-ar');

  // Form Fields
  const formSectionId = document.getElementById('form-section-id');
  const formPageSlug = document.getElementById('form-page-slug');
  const formTitleEn = document.getElementById('form-title-en');
  const formTitleAr = document.getElementById('form-title-ar');
  const formSubtitleEn = document.getElementById('form-subtitle-en');
  const formSubtitleAr = document.getElementById('form-subtitle-ar');
  const formMetaTitleEn = document.getElementById('form-meta-title-en');
  const formMetaTitleAr = document.getElementById('form-meta-title-ar');
  const formMetaDescEn = document.getElementById('form-meta-desc-en');
  const formMetaDescAr = document.getElementById('form-meta-desc-ar');
  const formContentEn = document.getElementById('form-content-en');
  const formContentAr = document.getElementById('form-content-ar');
  const formImageUrl = document.getElementById('form-image-url');
  const imageFileInput = document.getElementById('image-file-input');
  const previewImageBox = document.getElementById('preview-image-box');
  const btnClearImage = document.getElementById('btn-clear-image');
  const formBtnTextEn = document.getElementById('form-btn-text-en');
  const formBtnTextAr = document.getElementById('form-btn-text-ar');
  const formBtnUrl = document.getElementById('form-btn-url');
  const formIsActive = document.getElementById('form-is-active');
  const formSortOrder = document.getElementById('form-sort-order');

  // Repeater Items List
  const repeaterList = document.getElementById('repeater-items-list');
    const btnAddRepeaterItem = document.getElementById('btn-add-repeater-item');

  // Composable Blocks DOM Elements
  const fieldComposableWrap = document.getElementById('field-composable-blocks-wrap');
  const composableContainer = document.getElementById('composable-blocks-container');
  const btnOpenBlockPalette = document.getElementById('btn-open-block-palette');
  const blockPaletteMenu = document.getElementById('block-palette-menu');
  const formThemeBg = document.getElementById('form-theme-bg');
  const formThemePad = document.getElementById('form-theme-pad');
  const formThemeClass = document.getElementById('form-theme-class');

  // Delete Modal
  const deleteModal = document.getElementById('delete-modal');
  const btnCancelDelete = document.getElementById('btn-cancel-delete');
  const btnConfirmDelete = document.getElementById('btn-confirm-delete');

  // ---------------------------------------------------------------------------
  // 1. Flask-CKEditor Helper Functions
  // ---------------------------------------------------------------------------
  function getEditorContent(name) {
    if (window.CKEDITOR && CKEDITOR.instances && CKEDITOR.instances[name]) {
      try {
        CKEDITOR.instances[name].updateElement();
        return CKEDITOR.instances[name].getData() || '';
      } catch (err) {
        console.warn(`Error getting data from CKEditor "${name}":`, err);
      }
    }
    const el = document.getElementById(name);
    return el ? el.value : '';
  }

  function setEditorContent(name, val) {
    val = val || '';
    const el = document.getElementById(name);
    if (el) el.value = val;

    if (window.CKEDITOR && CKEDITOR.instances && CKEDITOR.instances[name]) {
      try {
        const inst = CKEDITOR.instances[name];
        if (inst.status === 'ready' || inst.instanceReady) {
          inst.setData(val);
        } else {
          inst.on('instanceReady', function() {
            this.setData(val);
          });
        }
      } catch (err) {
        console.warn(`Error setting data in CKEditor "${name}":`, err);
      }
    }
  }

  // Pasted content (Word docs, web pages, etc.) arrives carrying inline
  // style="" attributes and Office markup. ACF is disabled below so admins
  // can hand-edit arbitrary markup in Source view, which means nothing else
  // filters a paste automatically — strip it here instead, so saved content
  // relies on .article-prose classes only (same convention enforced at
  // render time by app/siteapp/clientroute.py's _strip_inline_styles).
  function cleanPastedHtml(html) {
    if (!html) return html;
    const wrapper = document.createElement('div');
    wrapper.innerHTML = html;

    Array.from(wrapper.getElementsByTagName('font')).forEach((el) => {
      el.replaceWith(...el.childNodes);
    });
    Array.from(wrapper.getElementsByTagName('o:p')).forEach((el) => {
      el.replaceWith(...el.childNodes);
    });

    Array.from(wrapper.querySelectorAll('*')).forEach((el) => {
      el.removeAttribute('style');
      el.removeAttribute('lang');
      if (/^Mso/i.test(el.className || '')) el.removeAttribute('class');
      Array.from(el.attributes).forEach((attr) => {
        if (/^(xmlns|o:|v:|w:)/i.test(attr.name)) el.removeAttribute(attr.name);
      });
    });

    Array.from(wrapper.querySelectorAll('span,font')).forEach((el) => {
      if (!el.attributes.length) el.replaceWith(...el.childNodes);
    });

    return wrapper.innerHTML;
  }

  // Hook change events and disable ACF to preserve all HTML/CSS formatting
  if (window.CKEDITOR) {
    CKEDITOR.config.allowedContent = true;
    CKEDITOR.config.extraAllowedContent = '*(*);*{*};*[*];*<*>';
    CKEDITOR.config.autoParagraph = false;
    CKEDITOR.config.fillEmptyBlocks = false;
    CKEDITOR.config.basicEntities = false;
    CKEDITOR.config.entities = false;

    CKEDITOR.on('instanceReady', function(evt) {
      try {
        if (evt.editor && evt.editor.filter) {
          evt.editor.filter.disabled = true;
        }
      } catch (err) {}
      evt.editor.on('paste', function(evtPaste) {
        if (evtPaste.data && typeof evtPaste.data.dataValue === 'string') {
          evtPaste.data.dataValue = cleanPastedHtml(evtPaste.data.dataValue);
        }
      });
      evt.editor.on('change', function() {
        this.updateElement();
      });
      evt.editor.on('mode', function() {
        if (this.mode === 'source') {
          const editable = this.editable();
          editable.attachListener(editable, 'input', () => {
            this.updateElement();
          });
        }
      });
    });
  }

  function showToast(msg, type = 'success') {
    const toast = document.getElementById('va-toast');
    if (!toast) return;
    toast.className = `fixed bottom-5 right-5 z-50 transform transition-all duration-300 px-4 py-3 rounded-2xl shadow-xl border text-sm font-semibold flex items-center gap-3 ${
      type === 'success'
        ? 'bg-slate-900 text-emerald-400 border-slate-800'
        : 'bg-rose-900 text-rose-200 border-rose-800'
    }`;
    toast.innerHTML = `<svg class="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg><span>${msg}</span>`;
    toast.classList.remove('translate-y-20', 'opacity-0', 'pointer-events-none');
    setTimeout(() => {
      toast.classList.add('translate-y-20', 'opacity-0', 'pointer-events-none');
    }, 3500);
  }

  function updateTargetPageUI(slug, title) {
    currentPageSlug = slug || 'home';
    if (badgePageSlug) badgePageSlug.textContent = currentPageSlug.toUpperCase();
    if (formPageSlug) formPageSlug.value = currentPageSlug;

    if (targetPageCurrentLabel) {
      if (title) {
        targetPageCurrentLabel.textContent = `${title} (${currentPageSlug})`;
      } else {
        const prettySlug = currentPageSlug === 'home' ? 'Home Page' : currentPageSlug.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        targetPageCurrentLabel.textContent = `${prettySlug} (${currentPageSlug})`;
      }
    }

    if (pageSectionsTitle) {
      pageSectionsTitle.textContent = currentPageSlug === 'home' ? 'Home Page Sections' : 'Page Sections';
    }
    if (linkViewLivePage) {
      linkViewLivePage.href = currentPageSlug === 'home' ? '/' : (currentPageSlug === 'about-us' ? '/about-us' : `/${currentPageSlug}`);
    }
  }

  function selectPage(slug, title) {
    if (targetPageDropdownMenu) targetPageDropdownMenu.classList.add('hidden');
    if (targetPageChevron) {
      targetPageChevron.classList.remove('rotate-180');
      targetPageChevron.classList.remove('text-[#1D4ED8]');
    }
    if (btnTargetPageDropdown) btnTargetPageDropdown.setAttribute('aria-expanded', 'false');

    updateTargetPageUI(slug, title);
    if (selectTargetPage) selectTargetPage.value = slug;

    const newUrl = window.location.pathname + '?page=' + encodeURIComponent(currentPageSlug);
    window.history.pushState({ page: currentPageSlug }, '', newUrl);

      // Attach Quick-Add Block Palette Buttons listener
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-palette-add');
    if (btn) {
      e.preventDefault();
      e.stopPropagation();
      const bType = btn.dataset.blockType;
      if (bType) {
        addComposableBlock(bType);
      }
    }
  });

  loadAvailablePages();
    fetchSections();
  }

  async function loadAvailablePages() {
    try {
      const resp = await fetch('/visionadmin/api/pages?status=all');
      if (resp.status === 401 || resp.status === 403) {
        window.location.href = `/visionadmin/login?next=${encodeURIComponent(window.location.pathname)}`;
        return;
      }
      const data = await resp.json();
      const pages = data.pages || [];

      const pageList = [
        { slug: 'home', title: 'Home Page' },
        { slug: 'about-us', title: 'About Us' }
      ];

      pages.forEach(p => {
        const titleEn = typeof p.title === 'object' ? (p.title.en || p.title.ar) : p.title;
        if (!pageList.some(x => x.slug === p.slug)) {
          pageList.push({ slug: p.slug, title: titleEn || p.slug });
        }
      });

      if (!pageList.some(x => x.slug === currentPageSlug)) {
        pageList.push({ slug: currentPageSlug, title: currentPageSlug });
      }

      const activePage = pageList.find(p => p.slug === currentPageSlug) || { slug: currentPageSlug, title: currentPageSlug };
      updateTargetPageUI(activePage.slug, activePage.title);

      if (targetPageOptionsList) {
        targetPageOptionsList.innerHTML = pageList.map(p => {
          const isSelected = p.slug === currentPageSlug;
          return `
            <button 
              type="button" 
              class="w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-bold transition-all text-left cursor-pointer ${
                isSelected 
                  ? 'bg-[#EFF6FF] text-[#0E1108] font-extrabold' 
                  : 'text-slate-700 hover:bg-slate-50 hover:text-[#0E1108]'
              }"
              data-slug="${p.slug}"
              data-title="${p.title}"
            >
              <div class="flex items-center gap-2 min-w-0">
                <span class="w-1.5 h-1.5 rounded-full ${isSelected ? 'bg-[#2563FF]' : 'bg-slate-300'} shrink-0"></span>
                <span class="truncate">${p.title} <span class="text-[11px] text-slate-400 font-semibold">(${p.slug})</span></span>
              </div>
              ${isSelected ? '<svg class="w-4 h-4 text-[#1D4ED8] shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>' : ''}
            </button>
          `;
        }).join('');

        targetPageOptionsList.querySelectorAll('button[data-slug]').forEach(btn => {
          btn.addEventListener('click', () => {
            const slug = btn.getAttribute('data-slug');
            const title = btn.getAttribute('data-title');
            selectPage(slug, title);
          });
        });
      }

      if (selectTargetPage) {
        selectTargetPage.innerHTML = pageList.map(p => `
          <option value="${p.slug}" ${p.slug === currentPageSlug ? 'selected' : ''}>
            ${p.title} (${p.slug})
          </option>
        `).join('');
      }
    } catch (e) {
      console.warn('Could not load pages list:', e);
    }
  }

  if (btnTargetPageDropdown && targetPageDropdownMenu) {
    btnTargetPageDropdown.addEventListener('click', (e) => {
      e.stopPropagation();
      const isHidden = targetPageDropdownMenu.classList.toggle('hidden');
      btnTargetPageDropdown.setAttribute('aria-expanded', !isHidden);
      if (targetPageChevron) {
        targetPageChevron.classList.toggle('rotate-180', !isHidden);
        targetPageChevron.classList.toggle('text-[#1D4ED8]', !isHidden);
      }
    });

    document.addEventListener('click', (e) => {
      if (!targetPageDropdownMenu.contains(e.target) && !btnTargetPageDropdown.contains(e.target)) {
        targetPageDropdownMenu.classList.add('hidden');
        btnTargetPageDropdown.setAttribute('aria-expanded', 'false');
        if (targetPageChevron) {
          targetPageChevron.classList.remove('rotate-180', 'text-[#1D4ED8]');
        }
      }
    });
  }

  async function fetchSections() {
    try {
      updateTargetPageUI(currentPageSlug);
      const resp = await fetch(`/visionadmin/api/sections?page=${encodeURIComponent(currentPageSlug)}`);
      if (resp.status === 401 || resp.status === 403) {
        window.location.href = `/visionadmin/login?next=${encodeURIComponent(window.location.pathname)}`;
        return;
      }
      const data = await resp.json();
      allSections = data.sections || [];
      renderSectionsList();
      updateStats();
    } catch (err) {
      console.error(err);
      sectionsContainer.innerHTML = '<div class="p-8 text-center text-rose-500 bg-white rounded-3xl border border-rose-100 font-bold">Failed to load sections. Please refresh the page.</div>';
    }
  }

  function updateStats() {
    statTotal.textContent = allSections.length;
    statActive.textContent = allSections.filter(s => s.is_active).length;
    statInactive.textContent = allSections.filter(s => !s.is_active).length;
  }

  function renderSectionsList() {
    if (allSections.length === 0) {
      const pageName = currentPageSlug === 'home' ? 'Home Page' : currentPageSlug.split(/[-_]/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
      sectionsContainer.innerHTML = `
        <div class="p-12 text-center text-slate-400 bg-white rounded-3xl border border-slate-200/80 shadow-2xs">
          <div class="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3 text-xl">📄</div>
          <p class="text-sm font-black text-slate-800">No Sections Configured for "${pageName}"</p>
          <p class="text-xs text-slate-400 mt-1">Click "+ Add Section" or choose a predefined layout above to start building this page.</p>
        </div>
      `;
      return;
    }

    sectionsContainer.innerHTML = allSections.map((sec, idx) => {
      const meta = TYPE_METADATA[sec.section_type] || { 
        label: sec.section_type, 
        shortLabel: 'Section', 
        emoji: '📄', 
        badgeBg: 'bg-slate-100 text-slate-800 border-slate-200', 
        tagColor: 'bg-slate-500', 
        desc: '' 
      };

      let titleEn = '';
      let titleAr = '';
      if (typeof sec.section_title === 'object' && sec.section_title !== null) {
        titleEn = sec.section_title.en || sec.section_title.ar || '';
        titleAr = sec.section_title.ar || '';
      } else if (typeof sec.section_title === 'string') {
        if (sec.section_title.trim().startsWith('{')) {
          try {
            const parsed = JSON.parse(sec.section_title);
            titleEn = parsed.en || parsed.ar || sec.section_title;
            titleAr = parsed.ar || '';
          } catch (e) {
            titleEn = sec.section_title;
          }
        } else {
          titleEn = sec.section_title;
        }
      }

      let subtitleEn = '';
      if (typeof sec.section_subtitle === 'object' && sec.section_subtitle !== null) {
        subtitleEn = sec.section_subtitle.en || sec.section_subtitle.ar || '';
      } else if (typeof sec.section_subtitle === 'string') {
        if (sec.section_subtitle.trim().startsWith('{')) {
          try {
            const parsed = JSON.parse(sec.section_subtitle);
            subtitleEn = parsed.en || parsed.ar || sec.section_subtitle;
          } catch (e) {
            subtitleEn = sec.section_subtitle;
          }
        } else {
          subtitleEn = sec.section_subtitle;
        }
      }

      let contentEn = '';
      if (typeof sec.content === 'object' && sec.content !== null) {
        contentEn = sec.content.en || sec.content.ar || '';
      } else if (typeof sec.content === 'string') {
        if (sec.content.trim().startsWith('{')) {
          try {
            const parsed = JSON.parse(sec.content);
            contentEn = parsed.en || parsed.ar || sec.content;
          } catch (e) {
            contentEn = sec.content;
          }
        } else {
          contentEn = sec.content;
        }
      }

      const seqNum = String(idx + 1).padStart(2, '0');
      const isFirst = idx === 0;
      const isLast = idx === allSections.length - 1;

      // Extract repeater count and render miniature structured preview chips
      let itemsCount = 0;
      let renderedItemsChips = '';

      if (sec.section_data) {
        let chipList = [];
        if (Array.isArray(sec.section_data.metrics) && sec.section_data.metrics.length > 0) {
          itemsCount = sec.section_data.metrics.length;
          chipList = sec.section_data.metrics.map(m => {
            const raw = m?.label || m?.heading || '';
            const heading = typeof raw === 'object' ? (raw.en || raw.ar || '') : String(raw || '');
            return `<span class="px-2 py-0.5 rounded-md bg-slate-100/90 text-slate-700 text-[10px] font-bold border border-slate-200/80"><span class="font-black text-slate-900">${m.number || ''}</span> ${heading}</span>`;
          });
        } else if (Array.isArray(sec.section_data.cards) && sec.section_data.cards.length > 0) {
          itemsCount = sec.section_data.cards.length;
          chipList = sec.section_data.cards.map(c => {
            const raw = c?.title || c?.heading || c?.name || '';
            const title = typeof raw === 'object' ? (raw.en || raw.ar || '') : String(raw || '');
            return `<span class="px-2 py-0.5 rounded-md bg-slate-100/90 text-slate-700 text-[10px] font-semibold border border-slate-200/80 truncate max-w-[160px]">${title}</span>`;
          });
        } else if (Array.isArray(sec.section_data.services) && sec.section_data.services.length > 0) {
          itemsCount = sec.section_data.services.length;
          chipList = sec.section_data.services.map(s => {
            const raw = s?.name || s?.title || s?.text || s || '';
            const name = typeof raw === 'object' ? (raw.en || raw.ar || '') : String(raw || '');
            return `<span class="px-2 py-0.5 rounded-md bg-teal-50 text-teal-800 text-[10px] font-semibold border border-teal-200/80 truncate max-w-[160px]">${name}</span>`;
          });
        } else if (Array.isArray(sec.section_data.steps) && sec.section_data.steps.length > 0) {
          itemsCount = sec.section_data.steps.length;
          chipList = sec.section_data.steps.map(st => {
            const raw = st?.title || st?.heading || st?.name || '';
            const title = typeof raw === 'object' ? (raw.en || raw.ar || '') : String(raw || '');
            return `<span class="px-2 py-0.5 rounded-md bg-cyan-50 text-cyan-800 text-[10px] font-semibold border border-cyan-200/80 truncate max-w-[160px]">Step ${st.step_number || ''}: ${title}</span>`;
          });
        } else if (Array.isArray(sec.section_data.brands) && sec.section_data.brands.length > 0) {
          itemsCount = sec.section_data.brands.length;
          chipList = sec.section_data.brands.map(b => {
            const raw = typeof b === 'object' ? (b.name || b.title || '') : (b || '');
            return `<span class="px-2 py-0.5 rounded-md bg-amber-50 text-amber-800 text-[10px] font-semibold border border-amber-200/80">${raw}</span>`;
          });
        } else if (Array.isArray(sec.section_data.reviews) && sec.section_data.reviews.length > 0) {
          itemsCount = sec.section_data.reviews.length;
          chipList = sec.section_data.reviews.map(r => {
            const raw = r?.author || r?.name || 'Review';
            const auth = typeof raw === 'object' ? (raw.en || raw.ar || '') : String(raw || '');
            return `<span class="px-2 py-0.5 rounded-md bg-yellow-50 text-yellow-800 text-[10px] font-semibold border border-yellow-200/80">★ 5 - ${auth}</span>`;
          });
        } else if (Array.isArray(sec.section_data.faqs) && sec.section_data.faqs.length > 0) {
          itemsCount = sec.section_data.faqs.length;
          chipList = sec.section_data.faqs.map(f => {
            const raw = f?.question || f?.title || '';
            const q = typeof raw === 'object' ? (raw.en || raw.ar || '') : String(raw || '');
            return `<span class="px-2 py-0.5 rounded-md bg-sky-50 text-sky-800 text-[10px] font-semibold border border-sky-200/80 truncate max-w-[180px]">? ${q}</span>`;
          });
        } else if (Array.isArray(sec.section_data.badges) && sec.section_data.badges.length > 0) {
          itemsCount = sec.section_data.badges.length;
          chipList = sec.section_data.badges.map(b => {
            const raw = b?.title || b?.text || b?.name || b?.label || b || '';
            const txt = typeof raw === 'object' ? (raw.en || raw.ar || Object.values(raw)[0] || '') : String(raw || '');
            return `<span class="px-2 py-0.5 rounded-md bg-blue-50 text-blue-800 text-[10px] font-semibold border border-blue-200/80">✓ ${txt}</span>`;
          });
        } else if (Array.isArray(sec.section_data.features) && sec.section_data.features.length > 0) {
          itemsCount = sec.section_data.features.length;
          chipList = sec.section_data.features.map(f => {
            const raw = f?.title || f?.name || f?.text || f || '';
            const txt = typeof raw === 'object' ? (raw.en || raw.ar || Object.values(raw)[0] || '') : String(raw || '');
            return `<span class="px-2 py-0.5 rounded-md bg-blue-50 text-blue-800 text-[10px] font-semibold border border-blue-200/80">✓ ${txt}</span>`;
          });
        } else if (Array.isArray(sec.section_data.rows) && sec.section_data.rows.length > 0) {
          itemsCount = sec.section_data.rows.length;
          chipList = sec.section_data.rows.map(r => {
            return `<span class="px-2 py-0.5 rounded-md bg-blue-50 text-blue-800 text-[10px] font-bold border border-blue-200/80 font-mono">🛞 ${r.size || ''}</span>`;
          });
        } else if (Array.isArray(sec.section_data.groups) && sec.section_data.groups.length > 0) {
          itemsCount = sec.section_data.groups.length;
          chipList = sec.section_data.groups.map(g => {
            const count = Array.isArray(g.chips) ? g.chips.length : 0;
            return `<span class="px-2 py-0.5 rounded-md bg-blue-50 text-blue-800 text-[10px] font-bold border border-blue-200/80">📂 ${g.heading || 'Group'} (${count})</span>`;
          });
        } else if (sec.section_type === 'coverage' && Array.isArray(sec.section_data.areas) && sec.section_data.areas.length > 0) {
          itemsCount = sec.section_data.areas.length;
          chipList = sec.section_data.areas.map(a => {
            const count = Array.isArray(a.chips) ? a.chips.length : 0;
            return `<span class="px-2 py-0.5 rounded-md bg-teal-50 text-teal-800 text-[10px] font-bold border border-teal-200/80">📍 ${a.heading || a.emirate || 'Area'} (${count})</span>`;
          });
        }

        if (chipList.length > 0) {
          renderedItemsChips = chipList.slice(0, 4).join(' ') + (chipList.length > 4 ? `<span class="text-[10px] text-slate-400 font-bold px-1">+${chipList.length - 4} more</span>` : '');
        }
      }

      return `
        <div class="section-row bg-white rounded-3xl border border-slate-200/80 hover:border-slate-300 shadow-xs hover:shadow-md transition-all duration-200 overflow-hidden group" data-id="${sec.id}" data-type="${sec.section_type}">
          <div class="p-5 sm:p-6 flex flex-col md:flex-row md:items-center gap-5 justify-between">
            
            <!-- Left Side: Order Handle, Icon & Details -->
            <div class="flex items-start gap-4 min-w-0 flex-1">
              
              <!-- Reorder Buttons -->
              <div class="flex flex-col items-center justify-center gap-1 shrink-0 pt-0.5">
                <button type="button" class="btn-move-up w-6 h-6 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 flex items-center justify-center transition disabled:opacity-30 disabled:pointer-events-none cursor-pointer" data-id="${sec.id}" ${isFirst ? 'disabled' : ''} title="Move Up">
                  <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="18 15 12 9 6 15"/></svg>
                </button>
                <span class="text-[11px] font-black text-slate-400 select-none">${seqNum}</span>
                <button type="button" class="btn-move-down w-6 h-6 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 flex items-center justify-center transition disabled:opacity-30 disabled:pointer-events-none cursor-pointer" data-id="${sec.id}" ${isLast ? 'disabled' : ''} title="Move Down">
                  <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
                </button>
              </div>

              <!-- Layout Icon Badge -->
              <div class="w-12 h-12 rounded-2xl ${meta.badgeBg} border flex items-center justify-center text-xl shrink-0 shadow-2xs">
                ${meta.emoji}
              </div>

              <!-- Title, Subtitle & Meta -->
              <div class="min-w-0 flex-1 space-y-1.5">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold tracking-wider uppercase ${meta.badgeBg} border">
                    ${meta.label}
                  </span>
                  ${subtitleEn ? `<span class="text-xs font-bold text-[#00A650] tracking-wide uppercase">· ${subtitleEn}</span>` : ''}
                  ${!sec.is_active ? '<span class="px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 text-[10px] font-bold">Inactive / Hidden</span>' : ''}
                </div>

                <h3 class="text-base font-black text-[#0E1108] truncate tracking-tight">
                  ${titleEn || '<span class="text-slate-400 italic">Untitled Section</span>'}
                </h3>

                ${titleAr ? `<p class="text-xs font-bold text-slate-500 truncate" dir="rtl">${titleAr}</p>` : ''}

                ${contentEn ? `<p class="text-xs text-slate-500 line-clamp-1">${contentEn.replace(/<[^>]*>/g, '')}</p>` : ''}

                ${renderedItemsChips ? `<div class="flex flex-wrap items-center gap-1.5 pt-1">${renderedItemsChips}</div>` : ''}
              </div>

            </div>

            <!-- Right Side Actions -->
            <div class="flex items-center gap-2.5 shrink-0 self-end md:self-center pt-2 md:pt-0 border-t md:border-t-0 border-slate-100 w-full md:w-auto justify-end">
              
              <!-- Toggle Active Switch -->
              <span class="inline-flex items-center gap-2 mr-2">
                <button type="button" class="btn-toggle-active relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-hidden ${sec.is_active ? 'bg-[#00A650]' : 'bg-slate-200'}" data-id="${sec.id}" role="switch" aria-checked="${sec.is_active}">
                  <span class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${sec.is_active ? 'translate-x-5' : 'translate-x-0'}"></span>
                </button>
              </span>

              <!-- Edit Button -->
              <button type="button" class="btn-edit-section inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#00A650] hover:bg-[#008f45] text-white text-xs font-bold shadow-xs hover:shadow transition active:scale-95 cursor-pointer" data-id="${sec.id}">
                <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                <span>Edit</span>
              </button>

              <!-- Live Preview Button -->
              <button type="button" class="btn-preview-section inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-blue-500 hover:border-blue-600 text-blue-600 hover:bg-blue-50 text-xs font-bold shadow-2xs transition active:scale-95 cursor-pointer" data-id="${sec.id}" title="Live Preview this section">
                <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                <span>Live Preview</span>
              </button>

              <!-- Delete Button -->
              <button type="button" class="btn-delete-section w-8 h-8 rounded-xl border border-rose-200 hover:border-rose-300 text-rose-500 hover:bg-rose-50 flex items-center justify-center transition cursor-pointer" data-id="${sec.id}" title="Delete Section">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>

          </div>
        </div>
      `;
    }).join('');

    attachRowEvents();
  }

  function attachRowEvents() {
    document.querySelectorAll('.btn-edit-section').forEach(b => {
      b.addEventListener('click', () => openEditModal(parseInt(b.dataset.id)));
    });

    document.querySelectorAll('.btn-preview-section').forEach(b => {
      b.addEventListener('click', () => openPreviewModal(parseInt(b.dataset.id)));
    });

    document.querySelectorAll('.btn-toggle-active').forEach(b => {
      b.addEventListener('click', () => toggleActive(parseInt(b.dataset.id)));
    });

    document.querySelectorAll('.btn-delete-section').forEach(b => {
      b.addEventListener('click', () => openDeleteModal(parseInt(b.dataset.id)));
    });

    document.querySelectorAll('.btn-move-up').forEach(b => {
      b.addEventListener('click', () => moveSection(parseInt(b.dataset.id), -1));
    });

    document.querySelectorAll('.btn-move-down').forEach(b => {
      b.addEventListener('click', () => moveSection(parseInt(b.dataset.id), 1));
    });
  }

  async function moveSection(secId, direction) {
    const idx = allSections.findIndex(s => s.id === secId);
    if (idx < 0) return;
    const targetIdx = idx + direction;
    if (targetIdx < 0 || targetIdx >= allSections.length) return;

    const temp = allSections[idx];
    allSections[idx] = allSections[targetIdx];
    allSections[targetIdx] = temp;

    renderSectionsList();

    const orderedIds = allSections.map(s => s.id);
    try {
      const resp = await fetch('/visionadmin/api/sections/reorder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ordered_ids: orderedIds })
      });
      const res = await resp.json();
      if (res.success) {
        showToast('Section order updated.');
      } else {
        showToast(res.error || 'Failed to reorder', 'error');
        fetchSections();
      }
    } catch (e) {
      showToast('Error saving section order', 'error');
      fetchSections();
    }
  }

  async function toggleActive(secId) {
    try {
      const resp = await fetch(`/visionadmin/api/sections/${secId}/toggle`, { method: 'POST' });
      const data = await resp.json();
      if (data.success) {
        showToast(data.message || 'Status updated');
        fetchSections();
      } else {
        showToast(data.error || 'Failed to toggle status', 'error');
      }
    } catch (e) {
      showToast('Network error', 'error');
    }
  }

  function openDeleteModal(secId) {
    deleteSectionId = secId;
    deleteModal.classList.remove('hidden');
    setTimeout(() => {
      deleteModal.classList.remove('opacity-0');
      deleteModal.firstElementChild.classList.remove('scale-95');
    }, 10);
  }

  function closeDeleteModal() {
    deleteModal.classList.add('opacity-0');
    deleteModal.firstElementChild.classList.add('scale-95');
    setTimeout(() => {
      deleteModal.classList.add('hidden');
      deleteSectionId = null;
    }, 200);
  }

  btnCancelDelete.addEventListener('click', closeDeleteModal);

  btnConfirmDelete.addEventListener('click', async () => {
    if (!deleteSectionId) return;
    try {
      const resp = await fetch(`/visionadmin/api/sections/${deleteSectionId}`, { method: 'DELETE' });
      const data = await resp.json();
      if (data.success) {
        showToast('Section deleted successfully.');
        closeDeleteModal();
        fetchSections();
      } else {
        showToast(data.error || 'Failed to delete', 'error');
      }
    } catch (e) {
      showToast('Network error', 'error');
    }
  });

  // =========================================================================
  // LIVE SECTION PREVIEW MODAL LOGIC
  // =========================================================================
  function openPreviewModal(secId) {
    const sec = allSections.find(s => s.id === secId);
    if (!sec) return;

    currentPreviewSecId = secId;
    currentPreviewLocale = 'en';

    const meta = TYPE_METADATA[sec.section_type] || { label: sec.section_type };
    const titleEn = typeof sec.section_title === 'object' ? (sec.section_title?.en || '') : (sec.section_title || '');
    const displayTitle = titleEn ? `Live Preview - ${titleEn}` : `Live Preview - ${meta.label}`;

    if (previewModalTitle) previewModalTitle.textContent = displayTitle;
    if (previewModalBadge) previewModalBadge.textContent = sec.page_slug || currentPageSlug;

    // Reset viewport size to 100%
    updatePreviewViewport('100%');

    // Update iframe and external link
    const previewUrl = `/visionadmin/sections/${secId}/preview`;
    if (previewIframe) previewIframe.src = previewUrl;
    if (previewOpenExternal) previewOpenExternal.href = previewUrl;

    // Open modal
    if (previewModal) {
      previewModal.classList.remove('hidden');
      setTimeout(() => {
        previewModal.classList.remove('opacity-0');
        if (previewModalBox) previewModalBox.classList.remove('scale-95');
      }, 10);
    }
  }

  function closePreviewModal() {
    if (!previewModal) return;
    previewModal.classList.add('opacity-0');
    if (previewModalBox) previewModalBox.classList.add('scale-95');
    setTimeout(() => {
      previewModal.classList.add('hidden');
      if (previewIframe) previewIframe.src = 'about:blank';
      currentPreviewSecId = null;
    }, 200);
  }

  function updatePreviewViewport(width) {
    if (previewIframeWrapper) {
      previewIframeWrapper.style.maxWidth = width;
    }
    document.querySelectorAll('.btn-viewport-size').forEach(btn => {
      if (btn.dataset.width === width) {
        btn.className = 'btn-viewport-size px-2.5 py-1 rounded-lg text-xs font-bold transition cursor-pointer bg-slate-100 text-slate-900';
      } else {
        btn.className = 'btn-viewport-size px-2.5 py-1 rounded-lg text-xs font-bold text-slate-500 hover:text-slate-900 transition cursor-pointer';
      }
    });
  }

  if (btnClosePreviewModal) {
    btnClosePreviewModal.addEventListener('click', closePreviewModal);
  }

  if (previewModal) {
    previewModal.addEventListener('click', (e) => {
      if (e.target === previewModal) closePreviewModal();
    });
  }

  document.querySelectorAll('.btn-viewport-size').forEach(btn => {
    btn.addEventListener('click', () => updatePreviewViewport(btn.dataset.width));
  });

  // Global Escape Key Listener for Modals
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (previewModal && !previewModal.classList.contains('hidden')) {
        closePreviewModal();
      } else if (deleteModal && !deleteModal.classList.contains('hidden')) {
        closeDeleteModal();
      } else if (sectionModal && !sectionModal.classList.contains('hidden')) {
        closeModal();
      }
    }
  });

  function getSelectedType() {
    const checked = document.querySelector('input[name="section_type"]:checked');
    return checked ? checked.value : 'hero';
  }

  function setSelectedType(type) {
    const radio = document.querySelector(`input[name="section_type"][value="${type}"]`);
    if (radio) {
      radio.checked = true;
      document.querySelectorAll('.type-card').forEach(c => {
        c.className = 'type-card flex items-center gap-2.5 p-3 rounded-2xl border-2 border-[#E8EDE4] bg-white hover:bg-[#F8FAF7] cursor-pointer transition';
      });
      const card = radio.closest('.type-card');
      if (card) {
        card.className = 'type-card flex items-center gap-2.5 p-3 rounded-2xl border-2 border-[#2563FF] bg-[#EFF6FF]/50 cursor-pointer transition';
      }
      applyTypeFormRules(type);
    }
  }

    document.querySelectorAll('.type-card').forEach(card => {
    card.addEventListener('click', () => {
      const radio = card.querySelector('input[name="section_type"]');
      if (radio) {
        setSelectedType(radio.value);
      }
    });
  });

  document.querySelectorAll('input[name="section_type"]').forEach(r => {
    r.addEventListener('change', () => {
      setSelectedType(r.value);
    });
  });

  
  // ---------------------------------------------------------------------------
  // COMPOSABLE BLOCK ENGINE METHODS
  // ---------------------------------------------------------------------------
  function addComposableBlock(bType) {
    let newBlock = { type: bType };
    if (bType === 'metrics_strip') {
      newBlock.heading = 'Key Statistics';
      newBlock.items = [
        { number: '16+', label: { en: 'Car Care Services', ar: 'خدمة صيانة سيارات' } },
        { number: '25+', label: { en: 'Partner Centres', ar: 'مركز شريك معتمد' } },
        { number: '30 min', label: { en: 'Average Mobile Van Fit', ar: 'متوسط وقت التركيب' } }
      ];
    } else if (bType === 'cards_grid') {
      newBlock.heading = 'Service Highlights';
      newBlock.columns = 3;
      newBlock.items = [
        { icon: 'shield', tag: 'GUARANTEED', title: { en: 'Certified Fitting', ar: 'تركيب معتمد' }, description: { en: 'Installed by verified technicians across the UAE.', ar: 'تركيب بواسطة فنيين معتمدين في كافة أنحاء الإمارات.' } },
        { icon: 'dollar', tag: 'BEST PRICE', title: { en: 'Transparent Pricing', ar: 'أسعار واضحة' }, description: { en: 'No hidden callout or fitting fees.', ar: 'بدون أي رسوم خفية إضافية.' } },
        { icon: 'truck', tag: 'CONVENIENT', title: { en: 'Mobile Van Service', ar: 'خدمة الفان المتنقل' }, description: { en: 'We come to your villa or apartment parking.', ar: 'نصل إلى باب منزلك أو مقر عملك.' } }
      ];
    } else if (bType === 'chips_cloud') {
      newBlock.heading = 'Popular Sizes & Vehicles';
      newBlock.chips = ['195/65 R15', '205/55 R16', '215/55 R17', '225/45 R17', 'Nissan Patrol', 'Toyota Land Cruiser'];
    } else if (bType === 'comparison_split') {
      newBlock.heading = 'Choose Your Fitting Option';
      newBlock.options = [
        { tag: 'FREE FITTING', heading: 'Partner Centre Fitting', description: 'Mounting, balancing and new valves included free at 25+ centres.', button_text: 'Book Centre', wa_msg: 'Hi TyresVision, I would like to book free fitting at a partner centre.' },
        { tag: 'MOBILE VAN', heading: 'Mobile Van at Your Doorstep', description: 'Fully equipped tyre van visits your location across UAE.', button_text: 'Book Mobile Van', wa_msg: 'Hi TyresVision, I would like to book mobile van fitting at my location.' }
      ];
    } else if (bType === 'process_steps') {
      newBlock.heading = 'How It Works';
      newBlock.items = [
        { step_number: 1, title: { en: 'Share Tyre Size', ar: 'أرسل مقاس الإطار' }, description: { en: 'WhatsApp us your car model or tyre size.', ar: 'راسلنا على واتساب بمقاس إطاراتك.' } },
        { step_number: 2, title: { en: 'Confirm Best Quote', ar: 'أكد أفضل سعر' }, description: { en: 'Transparent quote with zero surprises.', ar: 'عرض سعر واضح بدون أي رسوم خفية.' } },
        { step_number: 3, title: { en: 'Fitted at Your Convenience', ar: 'التركيب أينما كنت' }, description: { en: 'At a verified centre or via our mobile van.', ar: 'في المركز أو بواسطة الفان المتنقل.' } }
      ];
    } else if (bType === 'accordion_faq') {
      newBlock.heading = 'Frequently Asked Questions';
      newBlock.items = [
        { question: { en: 'How soon can my tyres be fitted?', ar: 'ما هي سرعة تركيب الإطارات؟' }, answer: { en: 'Same-day mobile van dispatch and partner centre fitting are available across Dubai, Abu Dhabi and Sharjah.', ar: 'التركيب في نفس اليوم متوفر في المراكز المعتمدة وعبر الفان المتنقل في كافة أنحاء الإمارات.' } }
      ];
    } else if (bType === 'reviews_slider') {
      newBlock.heading = 'Customer Feedback';
      newBlock.items = [
        { rating: 5, author: 'Sultan Al-Marzouqi', location: 'Dubai Marina', quote: 'Excellent service! The mobile van arrived on time and fitted four tyres right in my villa parking.' }
      ];
    } else if (bType === 'media_story') {
      newBlock.title = 'Precision Tyre Installation & Alignment';
      newBlock.subtitle = 'EXPERT WORKMANSHIP';
      newBlock.content = '<p>Every tyre purchased includes complimentary precision digital wheel balancing and brand new safety valve stems.</p>';
      newBlock.image = '';
      newBlock.image_position = 'right';
      newBlock.button_text = 'Chat on WhatsApp';
      newBlock.button_url = 'https://wa.me/971505069575';
    } else if (bType === 'pricing_matrix') {
      newBlock.heading = 'Tyre Starting Prices';
      newBlock.items = [
        { size: '205/55 R16', common_on: 'Corolla, Civic, Elantra', budget: 'AED 180', mid_range: 'AED 265', premium: 'AED 390' },
        { size: '265/65 R17', common_on: 'Prado, Pajero, Fortuner', budget: 'AED 310', mid_range: 'AED 430', premium: 'AED 620' }
      ];
    } else if (bType === 'cta_actions') {
      newBlock.buttons = [
        { text: 'WhatsApp for Quote', url: 'https://wa.me/971505069575', variant: 'whatsapp' },
        { text: 'Call Tyre Expert', url: 'tel:+971505069575', variant: 'phone' }
      ];
      newBlock.note = 'Instant response within minutes • Open 7 days a week';
    }

    composableBlocks.push(newBlock);
    renderComposableBlocks();
    showToast(`Added ${bType.replace('_', ' ').toUpperCase()} block!`);
  }

  function renderComposableBlocks() {
    const cContainer = document.getElementById('composable-blocks-container');
    if (!cContainer) return;

    if (!composableBlocks || composableBlocks.length === 0) {
      cContainer.innerHTML = '<div class="p-4 text-center text-slate-400 bg-white rounded-xl border-2 border-dashed border-[#DCE4D6] text-xs font-semibold">No composable blocks added yet. Click any button in the palette above to add cards, metrics, chips, or FAQ.</div>';
      return;
    }

    const BLOCK_META = {
      metrics_strip: { label: 'Statistic Metrics Strip', icon: '📊', color: 'text-indigo-600' },
      cards_grid: { label: 'Cards Grid', icon: '🃏', color: 'text-[#2563FF]' },
      chips_cloud: { label: 'Interactive Chips / Sizes', icon: '🏷️', color: 'text-amber-600' },
      comparison_split: { label: 'Comparison Split Cards', icon: '⚖️', color: 'text-blue-600' },
      process_steps: { label: 'Step Timeline Flow', icon: '🔢', color: 'text-purple-600' },
      accordion_faq: { label: 'Accordion FAQ List', icon: '❓', color: 'text-rose-600' },
      reviews_slider: { label: 'Customer Reviews Grid', icon: '⭐', color: 'text-amber-500' },
      media_story: { label: 'Media & Narrative Story', icon: '🖼️', color: 'text-cyan-600' },
      pricing_matrix: { label: 'Tyre Pricing Matrix Table', icon: '💰', color: 'text-blue-700' },
      cta_actions: { label: 'Action Buttons Group', icon: '🔘', color: 'text-slate-800' }
    };

    cContainer.innerHTML = composableBlocks.map((block, bIdx) => {
      const meta = BLOCK_META[block.type] || { label: block.type, icon: '🧱', color: 'text-slate-700' };
      let innerHtml = '';

      if (block.type === 'metrics_strip') {
        const mList = block.items || [];
        innerHtml = `
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <label class="text-[10px] font-black uppercase tracking-wider text-slate-600">Metric Counters (${mList.length})</label>
              <button type="button" class="btn-add-comp-subitem text-[11px] font-bold text-[#2563FF] hover:underline cursor-pointer" data-bidx="${bIdx}" data-subtype="metric">+ Add Metric</button>
            </div>
            <div class="space-y-2">
              ${mList.map((m, mIdx) => `
                <div class="flex items-center gap-2 p-2 bg-[#F8FAF7] rounded-xl border border-[#E8EDE4]">
                  <input type="text" placeholder="Number (e.g. 16+)" class="comp-input w-24 px-2.5 py-1.5 rounded-lg border border-[#E8EDE4] text-xs font-black bg-white" data-bidx="${bIdx}" data-subidx="${mIdx}" data-prop="number" value="${m.number || ''}" />
                  <input type="text" placeholder="Label EN (e.g. Services)" class="comp-input flex-1 px-2.5 py-1.5 rounded-lg border border-[#E8EDE4] text-xs font-bold bg-white" data-bidx="${bIdx}" data-subidx="${mIdx}" data-prop="label_en" value="${typeof m.label === 'object' ? (m.label.en || '') : (m.label || '')}" />
                  <input type="text" dir="rtl" placeholder="Label AR (عربي)" class="comp-input flex-1 px-2.5 py-1.5 rounded-lg border border-[#E8EDE4] text-xs font-bold bg-white text-right" data-bidx="${bIdx}" data-subidx="${mIdx}" data-prop="label_ar" value="${typeof m.label === 'object' ? (m.label.ar || '') : ''}" />
                  <button type="button" class="btn-del-comp-subitem text-rose-500 hover:text-rose-700 text-xs px-2 cursor-pointer" data-bidx="${bIdx}" data-subidx="${mIdx}">✕</button>
                </div>
              `).join('')}
            </div>
          </div>
        `;
      } else if (block.type === 'cards_grid') {
        const cList = block.items || [];
        innerHtml = `
          <div class="space-y-2">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <div>
                <label class="block text-[10px] font-black uppercase text-slate-600 mb-1">Block Title</label>
                <input type="text" class="comp-block-heading w-full px-3 py-1.5 rounded-lg border border-[#E8EDE4] text-xs font-bold bg-white" data-bidx="${bIdx}" value="${block.heading || ''}" placeholder="e.g. Why Choose TyresVision" />
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase text-slate-600 mb-1">Columns</label>
                <select class="comp-block-cols w-full px-3 py-1.5 rounded-lg border border-[#E8EDE4] text-xs font-bold bg-white" data-bidx="${bIdx}">
                  <option value="2" ${block.columns === 2 ? 'selected' : ''}>2 Columns</option>
                  <option value="3" ${block.columns === 3 || !block.columns ? 'selected' : ''}>3 Columns (Standard)</option>
                  <option value="4" ${block.columns === 4 ? 'selected' : ''}>4 Columns</option>
                </select>
              </div>
            </div>
            <div class="flex items-center justify-between pt-1">
              <label class="text-[10px] font-black uppercase text-slate-600">Cards (${cList.length})</label>
              <button type="button" class="btn-add-comp-subitem text-[11px] font-bold text-[#2563FF] hover:underline cursor-pointer" data-bidx="${bIdx}" data-subtype="card">+ Add Card</button>
            </div>
            <div class="space-y-2">
              ${cList.map((c, cIdx) => `
                <div class="p-2.5 bg-[#F8FAF7] rounded-xl border border-[#E8EDE4] space-y-2">
                  <div class="flex items-center justify-between">
                    <span class="text-[10px] font-bold text-slate-700">Card #${cIdx + 1}</span>
                    <button type="button" class="btn-del-comp-subitem text-rose-500 hover:text-rose-700 text-xs cursor-pointer" data-bidx="${bIdx}" data-subidx="${cIdx}">Remove</button>
                  </div>
                  <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <input type="text" placeholder="Icon (shield, dollar, truck, clock, zap, award, tyre)" class="comp-card-icon px-2.5 py-1.5 rounded-lg border border-[#E8EDE4] text-xs bg-white" data-bidx="${bIdx}" data-subidx="${cIdx}" value="${c.icon || 'shield'}" />
                    <input type="text" placeholder="Title EN" class="comp-card-title-en px-2.5 py-1.5 rounded-lg border border-[#E8EDE4] text-xs font-bold bg-white" data-bidx="${bIdx}" data-subidx="${cIdx}" value="${typeof c.title === 'object' ? (c.title.en || '') : (c.title || '')}" />
                    <input type="text" dir="rtl" placeholder="Title AR" class="comp-card-title-ar px-2.5 py-1.5 rounded-lg border border-[#E8EDE4] text-xs font-bold bg-white text-right" data-bidx="${bIdx}" data-subidx="${cIdx}" value="${typeof c.title === 'object' ? (c.title.ar || '') : ''}" />
                  </div>
                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <input type="text" placeholder="Description EN" class="comp-card-desc-en px-2.5 py-1.5 rounded-lg border border-[#E8EDE4] text-xs bg-white" data-bidx="${bIdx}" data-subidx="${cIdx}" value="${typeof c.description === 'object' ? (c.description.en || '') : (c.description || '')}" />
                    <input type="text" dir="rtl" placeholder="Description AR" class="comp-card-desc-ar px-2.5 py-1.5 rounded-lg border border-[#E8EDE4] text-xs bg-white text-right" data-bidx="${bIdx}" data-subidx="${cIdx}" value="${typeof c.description === 'object' ? (c.description.ar || '') : ''}" />
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        `;
      } else if (block.type === 'chips_cloud') {
        const chipsStr = Array.isArray(block.chips) ? block.chips.join(' · ') : (block.chips || '');
        innerHtml = `
          <div class="space-y-2">
            <div>
              <label class="block text-[10px] font-black uppercase text-slate-600 mb-1">Group Heading</label>
              <input type="text" class="comp-block-heading w-full px-3 py-1.5 rounded-lg border border-[#E8EDE4] text-xs font-bold bg-white" data-bidx="${bIdx}" value="${block.heading || ''}" placeholder="e.g. Popular tyre sizes in the UAE" />
            </div>
            <div>
              <label class="block text-[10px] font-black uppercase text-slate-600 mb-1">Chips (separated by ' · ' or commas)</label>
              <textarea rows="2" class="comp-block-chips w-full px-3 py-1.5 rounded-lg border border-[#E8EDE4] text-xs bg-white font-medium" data-bidx="${bIdx}">${chipsStr}</textarea>
            </div>
          </div>
        `;
      } else if (block.type === 'cta_actions') {
        const bButtons = block.buttons || [];
        innerHtml = `
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <label class="text-[10px] font-black uppercase text-slate-600">Action Buttons</label>
              <button type="button" class="btn-add-comp-subitem text-[11px] font-bold text-[#2563FF] hover:underline cursor-pointer" data-bidx="${bIdx}" data-subtype="button">+ Add Button</button>
            </div>
            <div class="space-y-2">
              ${bButtons.map((b, btnIdx) => `
                <div class="flex items-center gap-2 p-2 bg-[#F8FAF7] rounded-xl border border-[#E8EDE4]">
                  <input type="text" placeholder="Button Text" class="comp-btn-text flex-1 px-2.5 py-1.5 rounded-lg border border-[#E8EDE4] text-xs font-bold bg-white" data-bidx="${bIdx}" data-subidx="${btnIdx}" value="${typeof b.text === 'object' ? (b.text.en || '') : (b.text || '')}" />
                  <input type="text" placeholder="URL / Link" class="comp-btn-url flex-1 px-2.5 py-1.5 rounded-lg border border-[#E8EDE4] text-xs bg-white" data-bidx="${bIdx}" data-subidx="${btnIdx}" value="${b.url || ''}" />
                  <select class="comp-btn-variant w-28 px-2 py-1.5 rounded-lg border border-[#E8EDE4] text-xs bg-white font-bold" data-bidx="${bIdx}" data-subidx="${btnIdx}">
                    <option value="whatsapp" ${b.variant === 'whatsapp' ? 'selected' : ''}>WhatsApp</option>
                    <option value="phone" ${b.variant === 'phone' ? 'selected' : ''}>Phone Call</option>
                    <option value="primary" ${b.variant === 'primary' ? 'selected' : ''}>Dark Button</option>
                  </select>
                  <button type="button" class="btn-del-comp-subitem text-rose-500 hover:text-rose-700 text-xs px-1 cursor-pointer" data-bidx="${bIdx}" data-subidx="${btnIdx}">✕</button>
                </div>
              `).join('')}
            </div>
            <div>
              <label class="block text-[10px] font-black uppercase text-slate-600 mb-1">Footer Note (Optional)</label>
              <input type="text" class="comp-block-note w-full px-3 py-1.5 rounded-lg border border-[#E8EDE4] text-xs bg-white" data-bidx="${bIdx}" value="${block.note || ''}" placeholder="e.g. Open 7 days across Dubai & Abu Dhabi" />
            </div>
          </div>
        `;
      } else {
        innerHtml = `
          <div>
            <label class="block text-[10px] font-black uppercase text-slate-600 mb-1">Block Heading / Title</label>
            <input type="text" class="comp-block-heading w-full px-3 py-1.5 rounded-lg border border-[#E8EDE4] text-xs font-bold bg-white" data-bidx="${bIdx}" value="${block.heading || block.title || ''}" placeholder="Enter heading..." />
          </div>
        `;
      }

      return `
        <div class="p-3.5 bg-white rounded-2xl border-2 border-[#DCE4D6] shadow-sm space-y-3" data-block-index="${bIdx}">
          <div class="flex items-center justify-between pb-2 border-b border-[#E8EDE4]">
            <span class="text-xs font-black text-[#0E1108] flex items-center gap-2">
              <span class="text-base">${meta.icon}</span>
              <span>Block #${bIdx + 1}: ${meta.label}</span>
            </span>
            <div class="flex items-center gap-1.5">
              <button type="button" class="btn-move-block-up p-1 px-2 rounded-lg text-slate-500 hover:text-[#0E1108] hover:bg-slate-100 text-xs font-black transition cursor-pointer" data-bidx="${bIdx}" title="Move Up" ${bIdx === 0 ? 'disabled style="opacity:0.3;cursor:not-allowed"' : ''}>▲</button>
              <button type="button" class="btn-move-block-down p-1 px-2 rounded-lg text-slate-500 hover:text-[#0E1108] hover:bg-slate-100 text-xs font-black transition cursor-pointer" data-bidx="${bIdx}" title="Move Down" ${bIdx === composableBlocks.length - 1 ? 'disabled style="opacity:0.3;cursor:not-allowed"' : ''}>▼</button>
              <button type="button" class="btn-remove-composable-block ml-2 px-2.5 py-1 rounded-lg text-rose-600 hover:bg-rose-50 text-xs font-black transition cursor-pointer" data-bidx="${bIdx}">Remove</button>
            </div>
          </div>
          ${innerHtml}
        </div>
      `;
    }).join('');

    attachComposableListeners();
  }

  function attachComposableListeners() {
    const cContainer = document.getElementById('composable-blocks-container');
    if (!cContainer) return;

    cContainer.querySelectorAll('.btn-remove-composable-block').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.bidx);
        collectComposableBlocks();
        composableBlocks.splice(idx, 1);
        renderComposableBlocks();
      });
    });

    cContainer.querySelectorAll('.btn-move-block-up').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.bidx);
        if (idx > 0) {
          collectComposableBlocks();
          const temp = composableBlocks[idx];
          composableBlocks[idx] = composableBlocks[idx - 1];
          composableBlocks[idx - 1] = temp;
          renderComposableBlocks();
        }
      });
    });

    cContainer.querySelectorAll('.btn-move-block-down').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.bidx);
        if (idx < composableBlocks.length - 1) {
          collectComposableBlocks();
          const temp = composableBlocks[idx];
          composableBlocks[idx] = composableBlocks[idx + 1];
          composableBlocks[idx + 1] = temp;
          renderComposableBlocks();
        }
      });
    });

    cContainer.querySelectorAll('.btn-add-comp-subitem').forEach(btn => {
      btn.addEventListener('click', () => {
        const bIdx = parseInt(btn.dataset.bidx);
        const subType = btn.dataset.subtype;
        collectComposableBlocks();
        if (!composableBlocks[bIdx].items) composableBlocks[bIdx].items = [];

        if (subType === 'metric') {
          composableBlocks[bIdx].items.push({ number: '10+', label: { en: 'New Metric', ar: 'إحصائية جديدة' } });
        } else if (subType === 'card') {
          composableBlocks[bIdx].items.push({ icon: 'shield', tag: 'FEATURE', title: { en: 'New Feature', ar: 'ميزة جديدة' }, description: { en: 'Description text...', ar: 'وصف...' } });
        } else if (subType === 'button') {
          if (!composableBlocks[bIdx].buttons) composableBlocks[bIdx].buttons = [];
          composableBlocks[bIdx].buttons.push({ text: 'New Button', url: 'https://wa.me/971505069575', variant: 'whatsapp' });
        }
        renderComposableBlocks();
      });
    });

    cContainer.querySelectorAll('.btn-del-comp-subitem').forEach(btn => {
      btn.addEventListener('click', () => {
        const bIdx = parseInt(btn.dataset.bidx);
        const subIdx = parseInt(btn.dataset.subidx);
        collectComposableBlocks();
        if (composableBlocks[bIdx].items) {
          composableBlocks[bIdx].items.splice(subIdx, 1);
        } else if (composableBlocks[bIdx].buttons) {
          composableBlocks[bIdx].buttons.splice(subIdx, 1);
        }
        renderComposableBlocks();
      });
    });
  }

  function collectComposableBlocks() {
    const cContainer = document.getElementById('composable-blocks-container');
    if (!cContainer) return composableBlocks;
    const blockEls = cContainer.querySelectorAll('[data-block-index]');
    blockEls.forEach((el, bIdx) => {
      if (!composableBlocks[bIdx]) return;
      const b = composableBlocks[bIdx];

      const hEl = el.querySelector('.comp-block-heading');
      if (hEl) b.heading = hEl.value.trim();

      const colsEl = el.querySelector('.comp-block-cols');
      if (colsEl) b.columns = parseInt(colsEl.value) || 3;

      const chipsEl = el.querySelector('.comp-block-chips');
      if (chipsEl) {
        b.chips = chipsEl.value.split(/[·,\n]/).map(c => c.trim()).filter(Boolean);
      }

      const noteEl = el.querySelector('.comp-block-note');
      if (noteEl) b.note = noteEl.value.trim();

      if (b.type === 'metrics_strip' && b.items) {
        b.items.forEach((m, mIdx) => {
          const numEl = el.querySelector(`.comp-input[data-subidx="${mIdx}"][data-prop="number"]`);
          const lEnEl = el.querySelector(`.comp-input[data-subidx="${mIdx}"][data-prop="label_en"]`);
          const lArEl = el.querySelector(`.comp-input[data-subidx="${mIdx}"][data-prop="label_ar"]`);
          if (numEl) m.number = numEl.value.trim();
          if (lEnEl || lArEl) {
            m.label = {
              en: lEnEl ? lEnEl.value.trim() : '',
              ar: lArEl ? lArEl.value.trim() : ''
            };
          }
        });
      }

      if (b.type === 'cards_grid' && b.items) {
        b.items.forEach((c, cIdx) => {
          const icEl = el.querySelector(`.comp-card-icon[data-subidx="${cIdx}"]`);
          const tEnEl = el.querySelector(`.comp-card-title-en[data-subidx="${cIdx}"]`);
          const tArEl = el.querySelector(`.comp-card-title-ar[data-subidx="${cIdx}"]`);
          const dEnEl = el.querySelector(`.comp-card-desc-en[data-subidx="${cIdx}"]`);
          const dArEl = el.querySelector(`.comp-card-desc-ar[data-subidx="${cIdx}"]`);
          if (icEl) c.icon = icEl.value.trim() || 'shield';
          c.title = { en: tEnEl ? tEnEl.value.trim() : '', ar: tArEl ? tArEl.value.trim() : '' };
          c.description = { en: dEnEl ? dEnEl.value.trim() : '', ar: dArEl ? dArEl.value.trim() : '' };
        });
      }

      if (b.type === 'cta_actions' && b.buttons) {
        b.buttons.forEach((btnObj, btnIdx) => {
          const tEl = el.querySelector(`.comp-btn-text[data-subidx="${btnIdx}"]`);
          const uEl = el.querySelector(`.comp-btn-url[data-subidx="${btnIdx}"]`);
          const vEl = el.querySelector(`.comp-btn-variant[data-subidx="${btnIdx}"]`);
          if (tEl) btnObj.text = tEl.value.trim();
          if (uEl) btnObj.url = uEl.value.trim();
          if (vEl) btnObj.variant = vEl.value;
        });
      }
    });

    return composableBlocks;
  }

    function applyTypeFormRules(type) {
    const imageWrap = document.getElementById('field-image-wrap');
    const imagePosWrap = document.getElementById('field-image-pos-wrap');
    const btnWrap = document.getElementById('field-button-wrap');
    const structWrap = document.getElementById('field-structured-data-wrap');
    const structTitle = document.getElementById('structured-data-title');
    const fieldComposableWrap = document.getElementById('field-composable-blocks-wrap');

    if (type === 'custom') {
      if (structWrap) structWrap.classList.add('hidden');
      if (fieldComposableWrap) fieldComposableWrap.classList.remove('hidden');
      if (imageWrap) imageWrap.classList.remove('hidden');
      if (imagePosWrap) imagePosWrap.classList.remove('hidden');
      if (btnWrap) btnWrap.classList.remove('hidden');
      renderComposableBlocks();
      return;
    }

    if (fieldComposableWrap) fieldComposableWrap.classList.add('hidden');
    if (imageWrap) imageWrap.classList.remove('hidden');
    if (imagePosWrap) imagePosWrap.classList.remove('hidden');
    if (btnWrap) btnWrap.classList.remove('hidden');
    if (structWrap) structWrap.classList.remove('hidden');

    if (type === 'hero') {
      structTitle.textContent = 'Hero Badges & Trust Highlights';
      imageWrap.classList.add('hidden');
      imagePosWrap.classList.add('hidden');
    } else if (type === 'stats') {
      structTitle.textContent = 'Statistics Metric Counters (4 Numbers)';
      imageWrap.classList.add('hidden');
      btnWrap.classList.add('hidden');
    } else if (type === 'features') {
      structTitle.textContent = 'Why / Value Cards (6 Cards)';
      imageWrap.classList.add('hidden');
      btnWrap.classList.add('hidden');
    } else if (type === 'price_table') {
      structTitle.textContent = 'Tyre Sizes & Starting Prices Matrix';
      imageWrap.classList.add('hidden');
      imagePosWrap.classList.add('hidden');
    } else if (type === 'services') {
      structTitle.textContent = 'Car Care Services List';
      imageWrap.classList.add('hidden');
      btnWrap.classList.add('hidden');
    } else if (type === 'how_it_works') {
      structTitle.textContent = 'How It Works Steps (4 Steps)';
      imageWrap.classList.add('hidden');
      btnWrap.classList.add('hidden');
    } else if (type === 'shop_by') {
      structTitle.textContent = 'Shop By Groups (Sizes, Vehicles, Brand Tiers)';
      imageWrap.classList.add('hidden');
      imagePosWrap.classList.add('hidden');
      btnWrap.classList.add('hidden');
    } else if (type === 'coverage') {
      structTitle.textContent = 'Delivery & Fitting Coverage Areas';
      imageWrap.classList.add('hidden');
      imagePosWrap.classList.add('hidden');
      btnWrap.classList.add('hidden');
    } else if (type === 'advice') {
      structTitle.textContent = 'Advice Guide Cards (6 Cards)';
      imageWrap.classList.add('hidden');
      imagePosWrap.classList.add('hidden');
      btnWrap.classList.add('hidden');
    } else if (type === 'brands') {
      structTitle.textContent = 'Brand Names List';
      imageWrap.classList.add('hidden');
      btnWrap.classList.add('hidden');
    } else if (type === 'testimonials') {
      structTitle.textContent = 'Customer Star Reviews';
      imageWrap.classList.add('hidden');
      btnWrap.classList.add('hidden');
    } else if (type === 'faq') {
      structTitle.textContent = 'FAQ Accordion Questions & Answers';
      imageWrap.classList.add('hidden');
      btnWrap.classList.add('hidden');
    } else if (type === 'cta') {
      structTitle.textContent = 'Extra CTA Info & Note';
      imageWrap.classList.add('hidden');
      imagePosWrap.classList.add('hidden');
    } else if (type === 'content_image') {
      structTitle.textContent = 'Additional Highlights';
      imagePosWrap.classList.remove('hidden');
    } else if (type === 'mission_vision') {
      structTitle.textContent = 'Extra Highlights (Optional)';
      imagePosWrap.classList.remove('hidden');
    }

    renderRepeaterItems();
  }

  function renderRepeaterItems() {
    const type = getSelectedType();
    if (repeaterItems.length === 0) {
      repeaterList.innerHTML = '<div class="p-4 text-center text-slate-400 bg-white rounded-xl border border-dashed border-[#E8EDE4] text-xs">No structured items added yet. Click "+ Add Item" above.</div>';
      return;
    }

    const ICON_CHOICES = [
      { val: 'shield', label: 'Shield / Warranty' },
      { val: 'dollar', label: 'Dollar / Price' },
      { val: 'truck', label: 'Truck / Delivery' },
      { val: 'clock', label: 'Clock / 24-7' },
      { val: 'award', label: 'Award / Brands' },
      { val: 'zap', label: 'Zap / Fast' },
      { val: 'phone', label: 'Phone / Contact' },
      { val: 'globe', label: 'Globe / Network' },
      { val: 'tyre', label: 'Tyre / Wheel' }
    ];

    repeaterList.innerHTML = repeaterItems.map((item, i) => {
      const currentIcon = String(item.icon || '').toLowerCase();
      let matchedIcon = 'shield';
      if (currentIcon.includes('dollar') || currentIcon.includes('price')) matchedIcon = 'dollar';
      else if (currentIcon.includes('truck') || currentIcon.includes('deliver') || currentIcon.includes('van')) matchedIcon = 'truck';
      else if (currentIcon.includes('clock') || currentIcon.includes('time')) matchedIcon = 'clock';
      else if (currentIcon.includes('award') || currentIcon.includes('brand')) matchedIcon = 'award';
      else if (currentIcon.includes('zap') || currentIcon.includes('fast')) matchedIcon = 'zap';
      else if (currentIcon.includes('phone') || currentIcon.includes('call')) matchedIcon = 'phone';
      else if (currentIcon.includes('globe') || currentIcon.includes('network') || currentIcon.includes('uae')) matchedIcon = 'globe';
      else if (currentIcon.includes('tyre') || currentIcon.includes('wheel')) matchedIcon = 'tyre';
      else if (currentIcon.includes('shield') || currentIcon.includes('warrant')) matchedIcon = 'shield';

      if (type === 'stats') {
        return `
          <div class="p-4 bg-white rounded-2xl border border-[#E8EDE4] shadow-2xs space-y-3">
            <div class="flex items-center justify-between pb-2 border-b border-[#E8EDE4]">
              <span class="text-[11px] font-black uppercase tracking-wider text-[#0E1108] flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-[#2563FF]"></span>
                <span>Statistic Metric #${i + 1}</span>
              </span>
              <button type="button" class="btn-remove-repeater text-rose-600 hover:text-rose-800 text-xs font-bold transition cursor-pointer" data-index="${i}">Remove</button>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Metric Number *</label>
                <input type="text" placeholder="e.g. 60+ or 7,000+" class="rep-num w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white focus:ring-2 focus:ring-[#2563FF]/15 outline-none" value="${item.number || ''}" />
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Label (English) *</label>
                <input type="text" placeholder="e.g. Tyre brands" class="rep-head-en w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white focus:ring-2 focus:ring-[#2563FF]/15 outline-none" value="${typeof item.label === 'object' ? (item.label.en || '') : (item.heading?.en || item.label || item.heading || '')}" />
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Label (Arabic) *</label>
                <input type="text" dir="rtl" placeholder="مثال: علامة تجارية" class="rep-head-ar w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold text-right bg-[#F8FAF7] focus:bg-white focus:ring-2 focus:ring-[#2563FF]/15 outline-none" value="${typeof item.label === 'object' ? (item.label.ar || '') : (item.heading?.ar || '')}" />
              </div>
            </div>
          </div>
        `;
      } else if (type === 'price_table') {
        const commonEn = typeof item.common_on === 'object' ? (item.common_on?.en || '') : (item.common_on || '');
        const commonAr = typeof item.common_on === 'object' ? (item.common_on?.ar || '') : '';
        return `
          <div class="p-4 bg-white rounded-2xl border border-[#E8EDE4] shadow-2xs space-y-3">
            <div class="flex items-center justify-between pb-2 border-b border-[#E8EDE4]">
              <span class="text-[11px] font-black uppercase tracking-wider text-[#0E1108] flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-[#2563FF]"></span>
                <span>Tyre Size Row #${i + 1}</span>
              </span>
              <button type="button" class="btn-remove-repeater text-rose-600 hover:text-rose-800 text-xs font-bold transition cursor-pointer" data-index="${i}">Remove</button>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Tyre Size (e.g. 195/65 R15) *</label>
                <input type="text" placeholder="e.g. 195/65 R15" class="rep-size font-mono w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none" value="${item.size || ''}" />
              </div>
              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Common On (EN)</label>
                  <input type="text" placeholder="Corolla, Sunny..." class="rep-common-en w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs bg-[#F8FAF7] focus:bg-white outline-none" value="${commonEn}" />
                </div>
                <div>
                  <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Common On (AR)</label>
                  <input type="text" dir="rtl" placeholder="كورولا، صني..." class="rep-common-ar w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs text-right bg-[#F8FAF7] focus:bg-white outline-none" value="${commonAr}" />
                </div>
              </div>
            </div>
            <div class="grid grid-cols-3 gap-3">
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Budget From</label>
                <input type="text" placeholder="AED —" class="rep-budget w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none" value="${item.budget || 'AED —'}" />
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Mid-Range From</label>
                <input type="text" placeholder="AED —" class="rep-mid w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none" value="${item.mid_range || 'AED —'}" />
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Premium From</label>
                <input type="text" placeholder="AED —" class="rep-prem w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none" value="${item.premium || 'AED —'}" />
              </div>
            </div>
          </div>
        `;
      } else if (type === 'services') {
        return `
          <div class="p-3 bg-white rounded-2xl border border-[#E8EDE4] shadow-2xs flex items-center gap-3">
            <span class="w-2 h-2 rounded-full bg-[#2563FF] shrink-0"></span>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 flex-1">
              <input type="text" placeholder="Service Name (English)" class="rep-svc-en px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.name === 'object' ? (item.name.en || '') : (item.name || item || '')}" />
              <input type="text" dir="rtl" placeholder="اسم الخدمة (عربي)" class="rep-svc-ar px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold text-right bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.name === 'object' ? (item.name.ar || '') : ''}" />
            </div>
            <button type="button" class="btn-remove-repeater text-rose-600 hover:text-rose-800 text-xs font-bold transition cursor-pointer" data-index="${i}">✕</button>
          </div>
        `;
      } else if (type === 'shop_by') {
        const chipsVal = Array.isArray(item.chips) ? item.chips.join(' · ') : (item.chips || '');
        return `
          <div class="p-4 bg-white rounded-2xl border border-[#E8EDE4] shadow-2xs space-y-3">
            <div class="flex items-center justify-between pb-2 border-b border-[#E8EDE4]">
              <span class="text-[11px] font-black uppercase tracking-wider text-[#0E1108] flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-[#2563FF]"></span>
                <span>Group #${i + 1}: ${item.heading || 'New Group'}</span>
              </span>
              <button type="button" class="btn-remove-repeater text-rose-600 hover:text-rose-800 text-xs font-bold transition cursor-pointer" data-index="${i}">Remove</button>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div class="sm:col-span-2">
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Group Heading</label>
                <input type="text" placeholder="e.g. Popular tyre sizes in the UAE" class="rep-shopby-heading w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none" value="${item.heading || ''}" />
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Type</label>
                <select class="rep-shopby-type w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none">
                  <option value="size" ${item.type === 'size' ? 'selected' : ''}>Tyre Size</option>
                  <option value="vehicle" ${item.type === 'vehicle' ? 'selected' : ''}>Vehicle</option>
                  <option value="brand" ${item.type === 'brand' ? 'selected' : ''}>Brand</option>
                </select>
              </div>
            </div>
            <div>
              <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Chips (separated by " · " or commas)</label>
              <textarea rows="2" placeholder="e.g. 195/65 R15 · 205/55 R16 · 215/55 R17" class="rep-shopby-chips w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-medium bg-[#F8FAF7] focus:bg-white outline-none">${chipsVal}</textarea>
            </div>
          </div>
        `;
      } else if (type === 'coverage') {
        const chipsVal = Array.isArray(item.chips) ? item.chips.join(' · ') : (item.chips || '');
        return `
          <div class="p-4 bg-white rounded-2xl border border-[#E8EDE4] shadow-2xs space-y-3">
            <div class="flex items-center justify-between pb-2 border-b border-[#E8EDE4]">
              <span class="text-[11px] font-black uppercase tracking-wider text-[#0E1108] flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-[#2563FF]"></span>
                <span>Area Group #${i + 1}: ${item.heading || 'New Area'}</span>
              </span>
              <button type="button" class="btn-remove-repeater text-rose-600 hover:text-rose-800 text-xs font-bold transition cursor-pointer" data-index="${i}">Remove</button>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Area Group Heading</label>
                <input type="text" placeholder="e.g. Dubai coverage" class="rep-cov-heading w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none" value="${item.heading || ''}" />
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Emirate / Region</label>
                <input type="text" placeholder="e.g. Dubai" class="rep-cov-emirate w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none" value="${item.emirate || ''}" />
              </div>
            </div>
            <div>
              <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Locations / Areas (separated by " · " or commas)</label>
              <textarea rows="3" placeholder="e.g. Dubai Marina · JLT · JBR · Palm Jumeirah" class="rep-cov-chips w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-medium bg-[#F8FAF7] focus:bg-white outline-none">${chipsVal}</textarea>
            </div>
          </div>
        `;
      } else if (type === 'brands') {
        return `
          <div class="p-3 bg-white rounded-2xl border border-[#E8EDE4] shadow-2xs flex items-center gap-3">
            <span class="text-xs font-black text-slate-400">#${i + 1}</span>
            <input type="text" placeholder="Brand Name (e.g. Michelin)" class="rep-brand-name flex-1 px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item === 'string' ? item : (item.name || '')}" />
            <button type="button" class="btn-remove-repeater text-rose-600 hover:text-rose-800 text-xs font-bold transition cursor-pointer" data-index="${i}">✕</button>
          </div>
        `;
      } else if (type === 'faq') {
        return `
          <div class="p-4 bg-white rounded-2xl border border-[#E8EDE4] shadow-2xs space-y-3">
            <div class="flex items-center justify-between pb-2 border-b border-[#E8EDE4]">
              <span class="text-[11px] font-black uppercase tracking-wider text-[#0E1108] flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-[#2563FF]"></span>
                <span>FAQ Question #${i + 1}</span>
              </span>
              <button type="button" class="btn-remove-repeater text-rose-600 hover:text-rose-800 text-xs font-bold transition cursor-pointer" data-index="${i}">Remove</button>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Question (English) *</label>
                <input type="text" placeholder="e.g. How do I find my tyre size?" class="rep-q-en w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.question === 'object' ? (item.question.en || '') : (item.question || '')}" />
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Question (Arabic) *</label>
                <input type="text" dir="rtl" placeholder="مثال: كيف أجد مقاس إطاري؟" class="rep-q-ar w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold text-right bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.question === 'object' ? (item.question.ar || '') : ''}" />
              </div>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Answer (English) *</label>
                <textarea rows="2" placeholder="Answer content..." class="rep-a-en w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs bg-[#F8FAF7] focus:bg-white outline-none">${typeof item.answer === 'object' ? (item.answer.en || '') : (item.answer || '')}</textarea>
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Answer (Arabic) *</label>
                <textarea rows="2" dir="rtl" placeholder="نص الإجابة..." class="rep-a-ar w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs text-right bg-[#F8FAF7] focus:bg-white outline-none">${typeof item.answer === 'object' ? (item.answer.ar || '') : ''}</textarea>
              </div>
            </div>
          </div>
        `;
      } else if (type === 'testimonials') {
        return `
          <div class="p-4 bg-white rounded-2xl border border-[#E8EDE4] shadow-2xs space-y-3">
            <div class="flex items-center justify-between pb-2 border-b border-[#E8EDE4]">
              <span class="text-[11px] font-black uppercase tracking-wider text-[#0E1108] flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-[#2563FF]"></span>
                <span>Customer Review #${i + 1}</span>
              </span>
              <button type="button" class="btn-remove-repeater text-rose-600 hover:text-rose-800 text-xs font-bold transition cursor-pointer" data-index="${i}">Remove</button>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Author Name (English)</label>
                <input type="text" placeholder="Verified customer" class="rep-rev-auth-en w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.author === 'object' ? (item.author.en || '') : (item.author || '')}" />
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Author Name (Arabic)</label>
                <input type="text" dir="rtl" placeholder="عميل موثوق" class="rep-rev-auth-ar w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold text-right bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.author === 'object' ? (item.author.ar || '') : ''}" />
              </div>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Customer Quote (English) *</label>
                <textarea rows="2" placeholder="Quote text..." class="rep-rev-quote-en w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs bg-[#F8FAF7] focus:bg-white outline-none">${typeof item.quote === 'object' ? (item.quote.en || '') : (item.quote || '')}</textarea>
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Customer Quote (Arabic) *</label>
                <textarea rows="2" dir="rtl" placeholder="نص التقييم..." class="rep-rev-quote-ar w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs text-right bg-[#F8FAF7] focus:bg-white outline-none">${typeof item.quote === 'object' ? (item.quote.ar || '') : ''}</textarea>
              </div>
            </div>
          </div>
        `;
      } else if (type === 'how_it_works') {
        return `
          <div class="p-4 bg-white rounded-2xl border border-[#E8EDE4] shadow-2xs space-y-3">
            <div class="flex items-center justify-between pb-2 border-b border-[#E8EDE4]">
              <span class="text-[11px] font-black uppercase tracking-wider text-[#0E1108] flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-[#2563FF]"></span>
                <span>Step #${i + 1}</span>
              </span>
              <button type="button" class="btn-remove-repeater text-rose-600 hover:text-rose-800 text-xs font-bold transition cursor-pointer" data-index="${i}">Remove</button>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Icon</label>
                <select class="rep-icon w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none">
                  ${ICON_CHOICES.map(opt => `<option value="${opt.val}" ${matchedIcon === opt.val ? 'selected' : ''}>${opt.label}</option>`).join('')}
                </select>
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Step Title (English) *</label>
                <input type="text" placeholder="Send your size" class="rep-title-en w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.title === 'object' ? (item.title.en || '') : (item.title || '')}" />
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Step Title (Arabic) *</label>
                <input type="text" dir="rtl" placeholder="أرسل مقاس إطارك" class="rep-title-ar w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold text-right bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.title === 'object' ? (item.title.ar || '') : ''}" />
              </div>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Step Description (English)</label>
                <input type="text" placeholder="WhatsApp us..." class="rep-desc-en w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.description === 'object' ? (item.description.en || '') : (item.description || item.desc || '')}" />
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Step Description (Arabic)</label>
                <input type="text" dir="rtl" placeholder="راسلنا على واتساب..." class="rep-desc-ar w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs text-right bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.description === 'object' ? (item.description.ar || '') : ''}" />
              </div>
            </div>
          </div>
        `;
      } else {
        // Default Cards (Why / Features / Hero Badges)
        return `
          <div class="p-4 bg-white rounded-2xl border border-[#E8EDE4] shadow-2xs space-y-3">
            <div class="flex items-center justify-between pb-2 border-b border-[#E8EDE4]">
              <span class="text-[11px] font-black uppercase tracking-wider text-[#0E1108] flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-[#2563FF]"></span>
                <span>Item / Card #${i + 1}</span>
              </span>
              <button type="button" class="btn-remove-repeater text-rose-600 hover:text-rose-800 text-xs font-bold transition cursor-pointer" data-index="${i}">Remove</button>
            </div>
            
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Icon</label>
                <select class="rep-icon w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none">
                  ${ICON_CHOICES.map(opt => `<option value="${opt.val}" ${matchedIcon === opt.val ? 'selected' : ''}>${opt.label}</option>`).join('')}
                </select>
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Title / Text (English) *</label>
                <input type="text" placeholder="e.g. Genuine tyres only" class="rep-title-en w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.title === 'object' ? (item.title?.en || '') : (typeof item.title === 'string' ? item.title : (typeof item.text === 'object' ? (item.text?.en || '') : (item.text || item.name || '')))}" />
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Title / Text (Arabic) *</label>
                <input type="text" dir="rtl" placeholder="مثال: إطارات أصلية 100%" class="rep-title-ar w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs font-bold text-right bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.title === 'object' ? (item.title?.ar || '') : (typeof item.text === 'object' ? (item.text?.ar || '') : '')}" />
              </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Description (English)</label>
                <input type="text" placeholder="Details..." class="rep-desc-en w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.description === 'object' ? (item.description?.en || '') : (typeof item.description === 'string' ? item.description : (typeof item.desc === 'object' ? (item.desc?.en || '') : (item.desc || '')))}" />
              </div>
              <div>
                <label class="block text-[10px] font-black uppercase tracking-wider text-slate-600 mb-1">Description (Arabic)</label>
                <input type="text" dir="rtl" placeholder="التفاصيل..." class="rep-desc-ar w-full px-3 py-2 rounded-xl border border-[#E8EDE4] text-xs text-right bg-[#F8FAF7] focus:bg-white outline-none" value="${typeof item.description === 'object' ? (item.description?.ar || '') : (typeof item.desc === 'object' ? (item.desc?.ar || '') : '')}" />
              </div>
            </div>
          </div>
        `;
      }
    }).join('');

    document.querySelectorAll('.btn-remove-repeater').forEach(b => {
      b.addEventListener('click', () => {
        const idx = parseInt(b.dataset.index);
        repeaterItems.splice(idx, 1);
        renderRepeaterItems();
      });
    });
  }

  btnAddRepeaterItem.addEventListener('click', () => {
    const type = getSelectedType();
    if (type === 'stats') {
      repeaterItems.push({ number: '10+', label: { en: 'New Metric', ar: 'إحصائية جديدة' }, icon: 'award' });
    } else if (type === 'services') {
      repeaterItems.push({ name: { en: 'New Service', ar: 'خدمة جديدة' } });
    } else if (type === 'brands') {
      repeaterItems.push({ name: 'Brand Name' });
    } else if (type === 'faq') {
      repeaterItems.push({ question: { en: 'Question?', ar: 'سؤال؟' }, answer: { en: 'Answer text', ar: 'نص الإجابة' } });
    } else if (type === 'testimonials') {
      repeaterItems.push({ rating: 5, author: { en: 'Verified customer', ar: 'عميل موثوق' }, quote: { en: 'Great service!', ar: 'خدمة ممتازة!' } });
    } else if (type === 'how_it_works') {
      repeaterItems.push({ step_number: repeaterItems.length + 1, icon: 'phone', title: { en: 'Step Title', ar: 'عنوان الخطوة' }, description: { en: 'Description', ar: 'الوصف' } });
    } else if (type === 'price_table') {
      repeaterItems.push({ size: '205/55 R16', common_on: { en: 'Civic, Jetta, Cerato', ar: 'سيفيك، جيتا، سيراتو' }, budget: 'AED —', mid_range: 'AED —', premium: 'AED —' });
    } else if (type === 'shop_by') {
      repeaterItems.push({ heading: 'New Group', type: 'size', chips: [] });
    } else if (type === 'coverage') {
      repeaterItems.push({ heading: 'New Area Coverage', emirate: 'Dubai', chips: [] });
    } else {
      repeaterItems.push({ icon: 'shield', title: { en: 'Card Title', ar: 'عنوان البطاقة' }, description: { en: 'Description', ar: 'الوصف' } });
    }
    renderRepeaterItems();
  });

  function collectRepeaterItems() {
    const type = getSelectedType();
    const items = [];
    const rows = repeaterList.querySelectorAll('.p-3, .p-4');

    rows.forEach(row => {
      if (type === 'stats') {
        const num = row.querySelector('.rep-num')?.value.trim() || '';
        const icon = row.querySelector('.rep-icon')?.value.trim() || 'award';
        const headEn = row.querySelector('.rep-head-en')?.value.trim() || '';
        const headAr = row.querySelector('.rep-head-ar')?.value.trim() || '';
        if (num || headEn) {
          items.push({
            number: num,
            icon: icon,
            label: { en: headEn, ar: headAr || headEn }
          });
        }
      } else if (type === 'services') {
        const nameEn = row.querySelector('.rep-svc-en')?.value.trim() || '';
        const nameAr = row.querySelector('.rep-svc-ar')?.value.trim() || '';
        if (nameEn || nameAr) {
          items.push({ name: { en: nameEn, ar: nameAr || nameEn } });
        }
      } else if (type === 'brands') {
        const bName = row.querySelector('.rep-brand-name')?.value.trim() || '';
        if (bName) items.push(bName);
      } else if (type === 'faq') {
        const qEn = row.querySelector('.rep-q-en')?.value.trim() || '';
        const qAr = row.querySelector('.rep-q-ar')?.value.trim() || '';
        const aEn = row.querySelector('.rep-a-en')?.value.trim() || '';
        const aAr = row.querySelector('.rep-a-ar')?.value.trim() || '';
        if (qEn || qAr) {
          items.push({
            question: { en: qEn, ar: qAr || qEn },
            answer: { en: aEn, ar: aAr || aEn }
          });
        }
      } else if (type === 'testimonials') {
        const authEn = row.querySelector('.rep-rev-auth-en')?.value.trim() || '';
        const authAr = row.querySelector('.rep-rev-auth-ar')?.value.trim() || '';
        const qEn = row.querySelector('.rep-rev-quote-en')?.value.trim() || '';
        const qAr = row.querySelector('.rep-rev-quote-ar')?.value.trim() || '';
        if (qEn || authEn) {
          items.push({
            rating: 5,
            author: { en: authEn || 'Verified customer', ar: authAr || 'عميل موثوق' },
            quote: { en: qEn, ar: qAr || qEn }
          });
        }
      } else if (type === 'how_it_works') {
        const icon = row.querySelector('.rep-icon')?.value.trim() || 'phone';
        const titleEn = row.querySelector('.rep-title-en')?.value.trim() || '';
        const titleAr = row.querySelector('.rep-title-ar')?.value.trim() || '';
        const descEn = row.querySelector('.rep-desc-en')?.value.trim() || '';
        const descAr = row.querySelector('.rep-desc-ar')?.value.trim() || '';
        if (titleEn || titleAr) {
          items.push({
            step_number: items.length + 1,
            icon: icon,
            title: { en: titleEn, ar: titleAr || titleEn },
            description: { en: descEn, ar: descAr || descEn }
          });
        }
      } else if (type === 'price_table') {
        const size = row.querySelector('.rep-size')?.value.trim() || '';
        const cEn = row.querySelector('.rep-common-en')?.value.trim() || '';
        const cAr = row.querySelector('.rep-common-ar')?.value.trim() || cEn;
        const budget = row.querySelector('.rep-budget')?.value.trim() || 'AED —';
        const mid = row.querySelector('.rep-mid')?.value.trim() || 'AED —';
        const prem = row.querySelector('.rep-prem')?.value.trim() || 'AED —';
        if (size) {
          items.push({
            size: size,
            common_on: { en: cEn, ar: cAr },
            budget: budget,
            mid_range: mid,
            premium: prem
          });
        }
      } else if (type === 'shop_by') {
        const heading = row.querySelector('.rep-shopby-heading')?.value.trim() || '';
        const groupType = row.querySelector('.rep-shopby-type')?.value || 'size';
        const rawChips = row.querySelector('.rep-shopby-chips')?.value || '';
        const chips = rawChips.split(/[·,\n]/)
          .map(s => s.trim())
          .filter(s => s.length > 0);
        if (heading || chips.length > 0) {
          items.push({
            heading: heading,
            type: groupType,
            chips: chips
          });
        }
      } else if (type === 'coverage') {
        const heading = row.querySelector('.rep-cov-heading')?.value.trim() || '';
        const emirate = row.querySelector('.rep-cov-emirate')?.value.trim() || '';
        const rawChips = row.querySelector('.rep-cov-chips')?.value || '';
        const chips = rawChips.split(/[·,\n]/)
          .map(s => s.trim())
          .filter(s => s.length > 0);
        if (heading || chips.length > 0) {
          items.push({
            heading: heading,
            emirate: emirate || heading,
            chips: chips
          });
        }
      } else {
        const icon = row.querySelector('.rep-icon')?.value.trim() || 'shield';
        const titleEn = row.querySelector('.rep-title-en')?.value.trim() || '';
        const titleAr = row.querySelector('.rep-title-ar')?.value.trim() || '';
        const descEn = row.querySelector('.rep-desc-en')?.value.trim() || '';
        const descAr = row.querySelector('.rep-desc-ar')?.value.trim() || '';
        if (titleEn || titleAr) {
          items.push({
            icon: icon,
            title: { en: titleEn, ar: titleAr || titleEn },
            description: { en: descEn, ar: descAr || descEn }
          });
        }
      }
    });
    return items;
  }

  function setLocaleTab(locale) {
    currentLocaleTab = 'en';
    const titleEnWrap = document.getElementById('wrap-title-en');
    if (titleEnWrap) titleEnWrap.classList.remove('hidden');
    const subEnWrap = document.getElementById('wrap-subtitle-en');
    if (subEnWrap) subEnWrap.classList.remove('hidden');
    const contentEnWrap = document.getElementById('wrap-content-en');
    if (contentEnWrap) contentEnWrap.classList.remove('hidden');
    const btnTextEnWrap = document.getElementById('wrap-btn-text-en');
    if (btnTextEnWrap) btnTextEnWrap.classList.remove('hidden');
  }

  if (tabEn) tabEn.addEventListener('click', () => setLocaleTab('en'));

  imageFileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      showToast('Uploading image…');
      const resp = await fetch('/visionadmin/api/upload-banner', {
        method: 'POST',
        body: formData
      });
      const data = await resp.json();
      if (data.url) {
        formImageUrl.value = data.url;
        updateImagePreview(data.url);
        showToast('Image uploaded successfully.');
      } else {
        showToast(data.error || 'Upload failed', 'error');
      }
    } catch (err) {
      showToast('Network error during upload', 'error');
    }
  });

  formImageUrl.addEventListener('input', () => {
    updateImagePreview(formImageUrl.value.trim());
  });

  btnClearImage.addEventListener('click', () => {
    formImageUrl.value = '';
    updateImagePreview('');
  });

  function updateImagePreview(url) {
    if (url) {
      previewImageBox.innerHTML = `<img src="${url}" alt="Preview" class="w-full h-full object-cover rounded-xl" />`;
    } else {
      previewImageBox.innerHTML = '<span class="text-[10px] text-slate-400 text-center font-bold">No Image</span>';
    }
  }

  btnAddSection.addEventListener('click', () => {
    formSectionId.value = '';
    modalTitle.textContent = 'Add Section';
    sectionForm.reset();
    if (formPageSlug) formPageSlug.value = currentPageSlug;
    setSelectedType('features');
    setLocaleTab('en');
    setEditorContent('form-content-en', '');
    setEditorContent('form-content-ar', '');
    if (formMetaTitleEn) formMetaTitleEn.value = '';
    if (formMetaTitleAr) formMetaTitleAr.value = '';
    if (formMetaDescEn) formMetaDescEn.value = '';
    if (formMetaDescAr) formMetaDescAr.value = '';
    updateImagePreview('');
    repeaterItems = [];
    extraSectionData = {};
    composableBlocks = [];
    renderComposableBlocks();
    formSortOrder.value = allSections.length + 1;
    formIsActive.checked = true;
    renderRepeaterItems();
    openModal();
  });

  function openEditModal(secId) {
    const sec = allSections.find(s => s.id === secId);
    if (!sec) return;

    formSectionId.value = sec.id;
    modalTitle.textContent = `Edit ${TYPE_METADATA[sec.section_type]?.label || 'Section'}`;
    if (formPageSlug) formPageSlug.value = sec.page_slug || currentPageSlug;

    formTitleEn.value = typeof sec.section_title === 'object' ? (sec.section_title.en || '') : (sec.section_title || '');
    if (formTitleAr) formTitleAr.value = '';

    formSubtitleEn.value = typeof sec.section_subtitle === 'object' ? (sec.section_subtitle.en || '') : (sec.section_subtitle || '');
    if (formSubtitleAr) formSubtitleAr.value = '';

    if (formMetaTitleEn) formMetaTitleEn.value = typeof sec.meta_title === 'object' ? (sec.meta_title?.en || '') : (sec.meta_title || '');
    if (formMetaTitleAr) formMetaTitleAr.value = '';

    if (formMetaDescEn) formMetaDescEn.value = typeof sec.meta_description === 'object' ? (sec.meta_description?.en || '') : (sec.meta_description || '');
    if (formMetaDescAr) formMetaDescAr.value = '';

    const rawContentEn = typeof sec.content === 'object' ? (sec.content.en || '') : (sec.content || '');
    setEditorContent('form-content-en', rawContentEn);
    if (document.getElementById('form-content-ar')) setEditorContent('form-content-ar', '');

    formImageUrl.value = sec.image || '';
    updateImagePreview(sec.image || '');

    const imgPosRadio = document.querySelector(`input[name="image_position"][value="${sec.image_position || 'right'}"]`);
    if (imgPosRadio) imgPosRadio.checked = true;

    formBtnTextEn.value = typeof sec.button_text === 'object' ? (sec.button_text.en || '') : (sec.button_text || '');
    if (formBtnTextAr) formBtnTextAr.value = '';
    formBtnUrl.value = sec.button_url || '';

    formSortOrder.value = sec.sort_order || 1;
    formIsActive.checked = Boolean(sec.is_active);

    const sData = sec.section_data || {};
    // Unpack composable blocks & theme
    if (sData.blocks && Array.isArray(sData.blocks)) {
      composableBlocks = JSON.parse(JSON.stringify(sData.blocks));
    } else if (sData.extra_blocks && Array.isArray(sData.extra_blocks)) {
      composableBlocks = JSON.parse(JSON.stringify(sData.extra_blocks));
    } else {
      composableBlocks = [];
    }
    renderComposableBlocks();

    if (formThemeBg) formThemeBg.value = sData.theme?.bg_style || 'default';
    if (formThemePad) formThemePad.value = sData.theme?.padding_y || 'standard';
    if (formThemeClass) formThemeClass.value = sData.theme?.custom_class || '';
    extraSectionData = JSON.parse(JSON.stringify(sData));

    if (sData.metrics && Array.isArray(sData.metrics)) {
      repeaterItems = JSON.parse(JSON.stringify(sData.metrics));
    } else if (sData.cards && Array.isArray(sData.cards)) {
      repeaterItems = JSON.parse(JSON.stringify(sData.cards));
    } else if (sData.services && Array.isArray(sData.services)) {
      repeaterItems = JSON.parse(JSON.stringify(sData.services));
    } else if (sData.steps && Array.isArray(sData.steps)) {
      repeaterItems = JSON.parse(JSON.stringify(sData.steps));
    } else if (sData.brands && Array.isArray(sData.brands)) {
      repeaterItems = JSON.parse(JSON.stringify(sData.brands));
    } else if (sData.reviews && Array.isArray(sData.reviews)) {
      repeaterItems = JSON.parse(JSON.stringify(sData.reviews));
    } else if (sData.faqs && Array.isArray(sData.faqs)) {
      repeaterItems = JSON.parse(JSON.stringify(sData.faqs));
    } else if (sData.badges && Array.isArray(sData.badges)) {
      repeaterItems = JSON.parse(JSON.stringify(sData.badges));
    } else if (sData.rows && Array.isArray(sData.rows)) {
      repeaterItems = JSON.parse(JSON.stringify(sData.rows));
    } else if (sData.features && Array.isArray(sData.features)) {
      repeaterItems = JSON.parse(JSON.stringify(sData.features));
    } else if (sData.groups && Array.isArray(sData.groups)) {
      repeaterItems = JSON.parse(JSON.stringify(sData.groups));
    } else if (sData.areas && Array.isArray(sData.areas)) {
      repeaterItems = JSON.parse(JSON.stringify(sData.areas));
    } else {
      repeaterItems = [];
    }

    setSelectedType(sec.section_type);
    setLocaleTab('en');
    openModal();
  }

  function openModal() {
    sectionModal.classList.remove('hidden');
    setTimeout(() => {
      sectionModal.classList.remove('opacity-0');
      sectionModalBox.classList.remove('scale-95');
    }, 50);
  }

  function closeModal() {
    sectionModal.classList.add('opacity-0');
    sectionModalBox.classList.add('scale-95');
    setTimeout(() => {
      sectionModal.classList.add('hidden');
    }, 200);
  }

  btnCloseModal.addEventListener('click', closeModal);
  btnCancelModal.addEventListener('click', closeModal);

  btnSaveSection.addEventListener('click', async () => {
    const secId = formSectionId.value;
    const isEdit = Boolean(secId);
    const sectionType = getSelectedType();

    if (window.CKEDITOR && CKEDITOR.instances) {
      for (const instName in CKEDITOR.instances) {
        try {
          CKEDITOR.instances[instName].updateElement();
        } catch (e) {}
      }
    }

    const titleEn = formTitleEn.value.trim();
    const titleAr = titleEn;
    if (!titleEn) {
      showToast('Section title is required.', 'error');
      setLocaleTab('en');
      formTitleEn.focus();
      return;
    }

    const subtitleEn = formSubtitleEn.value.trim();
    const subtitleAr = subtitleEn;

    const metaTitleEn = formMetaTitleEn ? formMetaTitleEn.value.trim() : '';
    const metaTitleAr = metaTitleEn;

    const metaDescEn = formMetaDescEn ? formMetaDescEn.value.trim() : '';
    const metaDescAr = metaDescEn;

    const contentEn = getEditorContent('form-content-en').trim();
    const contentAr = contentEn;

    const btnTextEn = formBtnTextEn.value.trim();
    const btnTextAr = btnTextEn;
    const btnUrl = formBtnUrl.value.trim();

    const imgPos = document.querySelector('input[name="image_position"]:checked')?.value || 'right';

    const repData = collectRepeaterItems();
    const sectionData = Object.assign({}, extraSectionData);
    // Save theme
    sectionData.theme = {
      bg_style: formThemeBg?.value || 'default',
      padding_y: formThemePad?.value || 'standard',
      custom_class: formThemeClass?.value?.trim() || ''
    };

    // Save composable blocks
    const collectedBlocks = collectComposableBlocks();
    if (collectedBlocks && collectedBlocks.length > 0) {
      sectionData.blocks = collectedBlocks;
      sectionData.extra_blocks = collectedBlocks;
    } else {
      delete sectionData.blocks;
      delete sectionData.extra_blocks;
    }

    if (sectionType === 'stats') {
      sectionData.metrics = repData;
    } else if (sectionType === 'features') {
      sectionData.cards = repData;
    } else if (sectionType === 'services') {
      sectionData.services = repData;
    } else if (sectionType === 'how_it_works') {
      sectionData.steps = repData;
    } else if (sectionType === 'brands') {
      sectionData.brands = repData;
    } else if (sectionType === 'testimonials') {
      sectionData.reviews = repData;
    } else if (sectionType === 'faq') {
      sectionData.faqs = repData;
    } else if (sectionType === 'price_table') {
      sectionData.rows = repData;
    } else if (sectionType === 'shop_by') {
      sectionData.groups = repData;
    } else if (sectionType === 'coverage') {
      sectionData.areas = repData;
      if (!sectionData.options && extraSectionData && extraSectionData.options) {
        sectionData.options = extraSectionData.options;
      }
      if (!sectionData.options) {
        sectionData.options = [
          {
            tag: "FREE Delivery & Fitting",
            heading: "Free fitting at a partner centre",
            description: "Choose any centre on our network and we deliver your tyres there free of charge. Fitting, balancing, new valves and disposal of your old tyres are all included at no extra cost — the price we quote on WhatsApp is the price you pay.",
            button_text: "Book at Partner Centre",
            wa_msg: "Hi TyresVision, I'd like to book free tyre fitting at a partner centre."
          },
          {
            tag: "Mobile Van Service",
            heading: "Mobile van fitting at your location — call-out fee applies",
            description: "Our fully equipped vans fit your tyres at your villa, apartment car park, office bay or roadside. The van service carries a call-out fee on top of the tyre price, which we always confirm before dispatch so there are no surprises. Mounting, balancing, valves and old-tyre disposal are included in the job.",
            button_text: "Book Mobile Van",
            wa_msg: "Hi TyresVision, I'd like to book mobile van fitting at my location."
          }
        ];
      }
    } else if (sectionType === 'advice') {
      sectionData.cards = repData;
    } else if (sectionType === 'hero') {
      if (repData.length > 0) sectionData.badges = repData;
    } else {
      if (repData.length > 0) sectionData.items = repData;
    }

    const targetSlug = formPageSlug?.value?.trim() || currentPageSlug || 'home';

    const payload = {
      page_slug: targetSlug,
      section_type: sectionType,
      section_title: { en: titleEn, ar: titleAr },
      section_subtitle: { en: subtitleEn, ar: subtitleAr },
      meta_title: { en: metaTitleEn, ar: metaTitleAr },
      meta_description: { en: metaDescEn, ar: metaDescAr },
      content: { en: contentEn, ar: contentAr },
      image: formImageUrl.value.trim() || null,
      image_position: imgPos,
      button_text: { en: btnTextEn, ar: btnTextAr },
      button_url: btnUrl || null,
      section_data: sectionData,
      sort_order: parseInt(formSortOrder.value) || 1,
      is_active: formIsActive.checked
    };

    btnSaveSection.disabled = true;
    btnSaveSection.innerHTML = '<div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div><span>Saving…</span>';

    try {
      const url = isEdit ? `/visionadmin/api/sections/${secId}` : '/visionadmin/api/sections';
      const method = isEdit ? 'PUT' : 'POST';

      const resp = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();

      if (data.success) {
        showToast(isEdit ? 'Section updated successfully.' : 'Section created successfully.');
        closeModal();
        fetchSections();
      } else {
        showToast(data.error || 'Failed to save section', 'error');
      }
    } catch (e) {
      showToast('Network error while saving', 'error');
    } finally {
      btnSaveSection.disabled = false;
      btnSaveSection.innerHTML = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg><span>Save Section</span>';
    }
  });

    // Attach Quick-Add Block Palette Buttons listener
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-palette-add');
    if (btn) {
      e.preventDefault();
      e.stopPropagation();
      const bType = btn.dataset.blockType;
      if (bType) {
        addComposableBlock(bType);
      }
    }
  });

  loadAvailablePages();
  fetchSections();
});
