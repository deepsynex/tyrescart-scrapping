// pages.js - VisionAdmin Pages & Policies CRUD Controller with Flask-CKEditor
document.addEventListener('DOMContentLoaded', () => {
  let pagesData = [];
  let currentFilter = 'all';
  let currentSearch = '';
  let activeLocaleTab = 'en';

  const tableBody = document.getElementById('pages-table-body');
  const searchInput = document.getElementById('pages-search-input');
  const modal = document.getElementById('page-modal');
  const modalTitle = document.getElementById('modal-title');
  const pageForm = document.getElementById('page-form');
  const editIdInput = document.getElementById('edit-page-id');
  const saveBtn = document.getElementById('btn-save-page');
  const saveBtnText = document.getElementById('save-btn-text');

  const bannerFileInput = document.getElementById('banner_file_input');
  const bannerImageInput = document.getElementById('banner_image');
  const bannerPreviewImg = document.getElementById('banner-preview-img');
  const bannerPlaceholderIcon = document.getElementById('banner-placeholder-icon');
  const bannerRemoveBtn = document.getElementById('btn-remove-banner');
  const bannerStatusText = document.getElementById('banner-file-status');

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

  // Hook change events to automatically sync to textarea
  if (window.CKEDITOR) {
    CKEDITOR.on('instanceReady', function(evt) {
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

  // ---------------------------------------------------------------------------
  // 2. Banner Image File Upload Handler
  // ---------------------------------------------------------------------------
  function setBannerPreview(url) {
    const bannerBox = document.getElementById('banner-preview-box');
    const previewImg = document.getElementById('banner-preview-img');
    if (url) {
      if (bannerImageInput) bannerImageInput.value = url;
      if (previewImg) previewImg.src = url;
      if (bannerBox) bannerBox.classList.remove('hidden');
      if (bannerStatusText) bannerStatusText.textContent = url.split('/').pop();
    } else {
      if (bannerImageInput) bannerImageInput.value = '';
      if (previewImg) previewImg.src = '';
      if (bannerBox) bannerBox.classList.add('hidden');
      if (bannerFileInput) bannerFileInput.value = '';
      if (bannerStatusText) bannerStatusText.textContent = 'PNG, JPG, WEBP, SVG or AVIF up to 10MB.';
    }
  }

  bannerFileInput?.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (bannerStatusText) bannerStatusText.textContent = `Uploading "${file.name}"…`;
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/visionadmin/api/upload-banner', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.error || 'Failed to upload banner');

      setBannerPreview(data.url);
      window.vaShowToast('Banner image uploaded successfully!');
    } catch (err) {
      alert(`Upload error: ${err.message}`);
      setBannerPreview('');
    }
  });

  bannerImageInput?.addEventListener('input', () => {
    const val = bannerImageInput.value.trim();
    if (val) {
      const previewImg = document.getElementById('banner-preview-img');
      const bannerBox = document.getElementById('banner-preview-box');
      if (previewImg) previewImg.src = val;
      if (bannerBox) bannerBox.classList.remove('hidden');
    } else {
      const bannerBox = document.getElementById('banner-preview-box');
      if (bannerBox) bannerBox.classList.add('hidden');
    }
  });

  bannerRemoveBtn?.addEventListener('click', () => setBannerPreview(''));

  // ---------------------------------------------------------------------------
  // 3. Fetch & Render Pages Table
  // ---------------------------------------------------------------------------
  async function loadPages() {
    try {
      const isTrash = currentFilter === 'trash';
      const url = `/visionadmin/api/pages?status=${currentFilter}&trash=${isTrash ? '1' : '0'}&q=${encodeURIComponent(currentSearch)}`;
      const res = await fetch(url);
      if (res.status === 401 || res.status === 403) {
        window.location.href = `/visionadmin/login?next=${encodeURIComponent(window.location.pathname)}`;
        return;
      }
      const data = await res.json();

      if (!res.ok) throw new Error(data.error || 'Failed to load pages');

      pagesData = data.pages || [];
      updateMetrics(data.metrics || {});
      renderTable(pagesData);
    } catch (err) {
      tableBody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-rose-500 font-bold">Error loading pages: ${err.message}</td></tr>`;
    }
  }

  function updateMetrics(metrics) {
    document.getElementById('stat-total').textContent = metrics.total || 0;
    document.getElementById('stat-active').textContent = metrics.active || 0;
    document.getElementById('stat-inactive').textContent = metrics.inactive || 0;
    document.getElementById('stat-trash').textContent = metrics.trash || 0;
  }

  function renderTable(pages) {
    if (!pages.length) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="5" class="py-14 text-center text-slate-400">
            <svg class="w-10 h-10 mx-auto text-slate-300 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <p class="font-bold text-sm text-[#0E1108]">No static pages found</p>
            <p class="text-xs text-slate-400 mt-0.5">${currentFilter === 'trash' ? 'Trash is empty.' : 'Click "+ Create New Page" to add one.'}</p>
          </td>
        </tr>
      `;
      return;
    }

    tableBody.innerHTML = pages.map(p => {
      let enTitle = 'Untitled';
      if (typeof p.title === 'object' && p.title !== null) {
        enTitle = p.title.en || p.title.ar || 'Untitled';
      } else if (typeof p.title === 'string') {
        if (p.title.trim().startsWith('{')) {
          try {
            const parsed = JSON.parse(p.title);
            enTitle = parsed.en || parsed.ar || p.title;
          } catch (e) {
            enTitle = p.title;
          }
        } else {
          enTitle = p.title;
        }
      }

      const statusBadge = p.is_active 
        ? `<span class="px-3 py-1 rounded-full text-xs font-bold bg-[#EFF6FF] text-[#1D4ED8] border border-[#BFDBFE] inline-flex items-center gap-1.5">
             <span class="w-1.5 h-1.5 rounded-full bg-[#2563FF]"></span>
             <span>Active (Live)</span>
           </span>`
        : `<span class="px-3 py-1 rounded-full text-xs font-bold bg-[#FEF3C7] text-[#D97706] border border-[#FDE68A] inline-flex items-center gap-1.5">
             <span class="w-1.5 h-1.5 rounded-full bg-[#D97706]"></span>
             <span>Inactive</span>
           </span>`;

      const isTrash = currentFilter === 'trash';
      const rawDate = p.updated_at || p.created_at || '';
      let displayDate = '—';
      let displayTime = '';
      if (rawDate) {
        const d = new Date(rawDate);
        if (!isNaN(d.getTime())) {
          displayDate = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
          displayTime = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        } else {
          displayDate = rawDate.split('T')[0];
        }
      }

      return `
        <tr class="hover:bg-[#F8FAF7]/80 transition">
          <!-- 1. Page Title & Route -->
          <td class="py-4 px-4 sm:px-6">
            <div class="space-y-1">
              <div class="flex items-center gap-2">
                <span class="font-black text-sm text-[#0E1108]">${escapeHtml(enTitle)}</span>
              </div>
              <div class="flex items-center gap-2 text-xs">
                <a href="/${p.slug}" target="_blank" class="text-[#2563FF] font-semibold hover:underline inline-flex items-center gap-1">
                  <span>/${p.slug}</span>
                  <svg class="w-3 h-3 text-[#2563FF]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                </a>
              </div>
            </div>
          </td>

          <!-- 2. Banner Asset -->
          <td class="py-4 px-4">
            ${p.banner_image ? `
              <div class="flex items-center gap-2.5">
                <img src="${escapeHtml(p.banner_image)}" alt="Banner" class="w-10 h-7 object-cover rounded-lg border border-[#E8EDE4] shadow-2xs shrink-0" />
                <a href="${escapeHtml(p.banner_image)}" target="_blank" class="px-3 py-1 rounded-xl bg-white hover:bg-slate-50 border border-[#E8EDE4] text-xs font-bold text-slate-700 hover:text-[#1D4ED8] hover:border-[#2563FF] shadow-2xs transition">View</a>
              </div>
            ` : '<span class="text-xs text-slate-400 font-medium">None</span>'}
          </td>

          <!-- 3. Live Status -->
          <td class="py-4 px-4">
            ${statusBadge}
          </td>

          <!-- 4. Last Updated -->
          <td class="py-4 px-4 text-xs">
            <p class="font-bold text-[#0E1108]">${displayDate}</p>
            ${displayTime ? `<p class="text-[11px] text-slate-400 font-medium">${displayTime}</p>` : ''}
          </td>

          <!-- 5. Quick Actions (Matching Image) -->
          <td class="py-4 px-4 sm:px-6 text-right whitespace-nowrap">
            <div class="inline-flex items-center gap-2">
              ${!isTrash ? `
                <a href="/visionadmin/sections?page=${encodeURIComponent(p.slug)}" class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-[#DBEAFE] bg-white hover:bg-[#EFF6FF] text-[#1D4ED8] text-xs font-bold shadow-2xs transition">
                  <svg class="w-3.5 h-3.5 text-[#2563FF]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                  <span>Sections</span>
                </a>
                <button type="button" onclick="window.editPage(${p.id})" class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-white hover:bg-slate-50 border border-[#E8EDE4] text-slate-700 text-xs font-bold shadow-2xs transition cursor-pointer">
                  <svg class="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                  <span>Edit</span>
                </button>
                <button type="button" onclick="window.deletePage(${p.id}, '${escapeHtml(enTitle)}', false)" class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-white hover:bg-[#FFF1F2] border border-[#FECDD3] text-[#E11D48] text-xs font-bold shadow-2xs transition cursor-pointer">
                  <svg class="w-3.5 h-3.5 text-[#E11D48]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                  <span>Trash</span>
                </button>
                <button type="button" class="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition" title="More options">
                  <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>
                </button>
              ` : `
                <button type="button" onclick="window.restorePage(${p.id})" class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[#EFF6FF] hover:bg-[#DBEAFE] border border-[#BFDBFE] text-[#1D4ED8] text-xs font-bold transition cursor-pointer">
                  <svg class="w-3.5 h-3.5 text-[#2563FF]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
                  <span>Restore</span>
                </button>
                <button type="button" onclick="window.deletePage(${p.id}, '${escapeHtml(enTitle)}', true)" class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 text-white text-xs font-extrabold shadow-sm hover:shadow-md transition cursor-pointer">
                  <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                  <span>Delete Permanently</span>
                </button>
              `}
            </div>
          </td>
        </tr>
      `;
    }).join('');

    if (window.jQuery && $.fn.DataTable) {
      if ($.fn.DataTable.isDataTable('#pages-table')) {
        $('#pages-table').DataTable().destroy();
      }
      $('#pages-table').DataTable({
        responsive: true,
        pageLength: 10,
        lengthMenu: [10, 25, 50, 100],
        pagingType: 'full_numbers',
        autoWidth: false,
        columnDefs: [
          { orderable: false, targets: [1, 4] }
        ],
        order: [[3, 'desc']],
        language: {
          search: '',
          searchPlaceholder: 'Search pages...',
          lengthMenu: 'Show _MENU_ per page',
          info: 'Showing _START_ to _END_ of _TOTAL_ pages',
          infoEmpty: 'No pages to show',
          infoFiltered: '(filtered from _MAX_ total)',
          paginate: { first: 'First', last: 'Last', next: 'Next', previous: 'Previous' }
        }
      });
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }

  // ---------------------------------------------------------------------------
  // 4. Filter Tabs & Search Handler
  // ---------------------------------------------------------------------------
  document.querySelectorAll('.tab-filter').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-filter').forEach(b => {
        b.className = 'tab-filter px-4 py-2 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition cursor-pointer';
      });
      btn.className = 'tab-filter px-4 py-2 rounded-xl bg-[#EFF6FF] text-[#1D4ED8] font-bold transition cursor-pointer';
      currentFilter = btn.dataset.status;
      loadPages();
    });
  });

  let searchTimeout = null;
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        currentSearch = e.target.value.trim();
        loadPages();
      }, 250);
    });
  }

  // ---------------------------------------------------------------------------
  // 5. Multi-Locale Tab Switcher
  // ---------------------------------------------------------------------------
  document.querySelectorAll('.locale-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const loc = tab.dataset.locale;
      activeLocaleTab = loc;
      document.querySelectorAll('.locale-tab').forEach(t => {
        t.className = 'locale-tab px-3.5 py-1.5 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition';
      });
      tab.className = 'locale-tab px-3.5 py-1.5 rounded-xl text-xs font-bold bg-slate-900 text-white shadow-xs transition';

      if (loc === 'en') {
        document.getElementById('locale-block-en').classList.remove('hidden');
        document.getElementById('locale-block-ar').classList.add('hidden');
      } else {
        document.getElementById('locale-block-en').classList.add('hidden');
        document.getElementById('locale-block-ar').classList.remove('hidden');
      }

      // Refresh/resize CKEditor on tab switch
      setTimeout(() => {
        if (window.CKEDITOR && CKEDITOR.instances) {
          if (loc === 'ar' && CKEDITOR.instances.content_ar) {
            CKEDITOR.instances.content_ar.resize();
          } else if (loc === 'en' && CKEDITOR.instances.content_en) {
            CKEDITOR.instances.content_en.resize();
          }
        }
      }, 50);
    });
  });

  // ---------------------------------------------------------------------------
  // 6. Modal Open / Close & Auto Slugify
  // ---------------------------------------------------------------------------
  function setVal(id, v) {
    const el = document.getElementById(id);
    if (el) el.value = v !== undefined && v !== null ? v : '';
  }
  function getVal(id) {
    const el = document.getElementById(id);
    return el ? el.value.trim() : '';
  }

  function openModal(isEdit = false, page = null) {
    if (pageForm) pageForm.reset();
    if (editIdInput) editIdInput.value = isEdit && page ? page.id : '';
    if (modalTitle) modalTitle.textContent = isEdit ? 'Edit Static Page' : 'Create New Static Page';
    if (saveBtnText) saveBtnText.textContent = isEdit ? 'Save Changes' : 'Create Page';

    const currLang = (window.VISION_STORE && window.VISION_STORE.language_code) || 'en';

    if (isEdit && page) {
      const pageTitle = (typeof page.title === 'object' ? (page.title?.[currLang] || page.display_title || page.title?.en) : page.title) || '';
      setVal('title_en', pageTitle);
      setVal('slug', page.slug || '');
      if (document.getElementById('is_active')) {
        document.getElementById('is_active').checked = Boolean(page.is_active);
      }
      const seoTitle = (typeof page.seo_title === 'object' ? (page.seo_title?.[currLang] || page.seo_title?.en) : page.seo_title) || '';
      const metaDesc = (typeof page.meta_description === 'object' ? (page.meta_description?.[currLang] || page.meta_description?.en) : page.meta_description) || '';
      setVal('seo_title_en', seoTitle);
      setVal('meta_description_en', metaDesc);

      setBannerPreview(page.banner_image || '');

      const contentEnVal = (typeof page.content === 'object' ? (page.content?.[currLang] || page.display_content || page.content?.en) : page.content) || '';
      setEditorContent('content_en', contentEnVal);

    } else {
      if (document.getElementById('is_active')) {
        document.getElementById('is_active').checked = true;
      }
      setBannerPreview('');

      setEditorContent('content_en', '');
      setEditorContent('content_ar', '');
    }

    if (modal) modal.classList.remove('hidden');

    // Resize active editor after modal animation
    setTimeout(() => {
      if (window.CKEDITOR && CKEDITOR.instances) {
        if (CKEDITOR.instances.content_en) CKEDITOR.instances.content_en.resize();
        if (CKEDITOR.instances.content_ar) CKEDITOR.instances.content_ar.resize();
      }
    }, 100);
  }

  function closeModal() {
    if (modal) modal.classList.add('hidden');
  }

  document.getElementById('btn-create-page')?.addEventListener('click', () => openModal(false));
  document.getElementById('btn-close-modal')?.addEventListener('click', closeModal);
  document.getElementById('btn-cancel-modal')?.addEventListener('click', closeModal);
  document.getElementById('modal-backdrop')?.addEventListener('click', closeModal);

  // Auto slug generator on English title change
  const titleEnInput = document.getElementById('title_en');
  const slugInput = document.getElementById('slug');
  titleEnInput?.addEventListener('input', () => {
    if (!editIdInput?.value && slugInput) {
      const slugified = titleEnInput.value.toLowerCase()
        .replace(/[^\w\s-]/g, '')
        .replace(/[\s_-]+/g, '-')
        .replace(/^-+|-+$/g, '');
      slugInput.value = slugified;
    }
  });

  // ---------------------------------------------------------------------------
  // 7. Submit Form (Create / Update)
  // ---------------------------------------------------------------------------
  saveBtn?.addEventListener('click', async () => {
    const editId = editIdInput?.value || '';
    const title_en = getVal('title_en');
    const slug = getVal('slug');

    if (!title_en) {
      alert('Please provide a page title.');
      document.getElementById('title_en')?.focus();
      return;
    }

    // Force update from all CKEditor instances
    if (window.CKEDITOR && CKEDITOR.instances) {
      for (const instName in CKEDITOR.instances) {
        try {
          CKEDITOR.instances[instName].updateElement();
        } catch (e) {}
      }
    }

    const content_en = getEditorContent('content_en');
    const seo_title = getVal('seo_title_en');
    const meta_desc = getVal('meta_description_en');
    const currLang = (window.VISION_STORE && window.VISION_STORE.language_code) || 'en';

    const payload = {
      title: { [currLang]: title_en },
      content: { [currLang]: content_en },
      slug: slug,
      banner_image: bannerImageInput ? bannerImageInput.value.trim() || null : null,
      is_active: document.getElementById('is_active') ? document.getElementById('is_active').checked : true,
      seo_title: { [currLang]: seo_title },
      meta_description: { [currLang]: meta_desc }
    };

    if (saveBtn) saveBtn.disabled = true;
    if (saveBtnText) saveBtnText.textContent = 'Saving…';

    try {
      const url = editId ? `/visionadmin/api/pages/${editId}` : '/visionadmin/api/pages';
      const method = editId ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method: method,
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to save page');

      window.vaShowToast(data.message || 'Page saved successfully!');
      closeModal();
      loadPages();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      if (saveBtn) saveBtn.disabled = false;
      if (saveBtnText) saveBtnText.textContent = editId ? 'Save Changes' : 'Create Page';
    }
  });

  // ---------------------------------------------------------------------------
  // 8. Global Action Helpers
  // ---------------------------------------------------------------------------
  window.editPage = async function(id) {
    try {
      const res = await fetch(`/visionadmin/api/pages/${id}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to fetch page data');
      openModal(true, data.page);
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  window.deletePage = async function(id, title, isHard = false) {
    const executeDelete = async () => {
      try {
        const url = isHard ? `/visionadmin/api/pages/${id}?hard=1` : `/visionadmin/api/pages/${id}`;
        const res = await fetch(url, {
          method: 'DELETE'
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to delete page');

        window.vaShowToast(data.message || (isHard ? 'Page deleted permanently.' : 'Page moved to Trash.'));
        loadPages();
      } catch (err) {
        window.vaShowToast(`Error: ${err.message}`, 'error');
      }
    };

    if (isHard) {
      // Trigger Glassmorphism Hard Delete Modal
      window.vaConfirmHardDelete({
        title: 'Delete Page Permanently',
        message: `Are you sure you want to permanently purge page "${title}"? All translations, metadata, and database records will be erased forever.`,
        itemName: title || `Page #${id}`,
        confirmText: 'Purge Page',
        onConfirm: executeDelete
      });
    } else {
      if (!confirm(`Are you sure you want to move page "${title}" to Trash?`)) return;
      executeDelete();
    }
  };

  window.restorePage = async function(id) {
    try {
      const res = await fetch(`/visionadmin/api/pages/${id}/restore`, {
        method: 'POST'
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to restore page');

      window.vaShowToast('Page restored successfully.');
      loadPages();
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  // Initial Load
  loadPages();
});
