// blogs.js - VisionAdmin Blogs & Articles CRUD Controller
document.addEventListener('DOMContentLoaded', () => {
  let blogsData = [];
  let currentFilter = 'all';
  let currentSearch = '';
  let activeLocaleTab = 'en';

  const tableBody = document.getElementById('blogs-table-body');
  const searchInput = document.getElementById('blogs-search-input');
  const modal = document.getElementById('blog-modal');
  const modalTitle = document.getElementById('blog-modal-title');
  const blogForm = document.getElementById('blog-form');
  const editIdInput = document.getElementById('edit-blog-id');
  const saveBtn = document.getElementById('btn-save-blog');
  const saveBtnText = document.getElementById('save-blog-btn-text');

  const fileInput = document.getElementById('blog_file_input');
  const imageInput = document.getElementById('blog_image');
  const previewImg = document.getElementById('blog-preview-img');
  const placeholderIcon = document.getElementById('blog-placeholder-icon');
  const removeBtn = document.getElementById('btn-remove-blog-img');
  const fileStatusText = document.getElementById('blog-file-status');

  // ---------------------------------------------------------------------------
  // 1. Flask-CKEditor Helper Functions
  // ---------------------------------------------------------------------------
  function getEditorContent(name) {
    if (window.CKEDITOR && CKEDITOR.instances && CKEDITOR.instances[name]) {
      try {
        CKEDITOR.instances[name].updateElement();
        return CKEDITOR.instances[name].getData() || '';
      } catch (err) {
        console.warn(`Error reading CKEditor "${name}":`, err);
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
        console.warn(`Error setting CKEditor "${name}":`, err);
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
  // 2. Featured Image Upload Handler
  // ---------------------------------------------------------------------------
  function setImagePreview(url) {
    const previewBox = document.getElementById('blog-preview-box');
    const previewImageEl = document.getElementById('blog-preview-img');
    if (url) {
      if (imageInput) imageInput.value = url;
      if (previewImageEl) previewImageEl.src = url;
      if (previewBox) previewBox.classList.remove('hidden');
      if (fileStatusText) fileStatusText.textContent = url.split('/').pop();
    } else {
      if (imageInput) imageInput.value = '';
      if (previewImageEl) previewImageEl.src = '';
      if (previewBox) previewBox.classList.add('hidden');
      if (fileInput) fileInput.value = '';
      if (fileStatusText) fileStatusText.textContent = 'PNG, JPG, WEBP, SVG or AVIF up to 10MB.';
    }
  }

  fileInput?.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (fileStatusText) fileStatusText.textContent = `Uploading "${file.name}"…`;
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/visionadmin/api/upload-blog-image', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.error || 'Failed to upload image');

      setImagePreview(data.url);
      window.vaShowToast('Featured image uploaded successfully!');
    } catch (err) {
      alert(`Upload error: ${err.message}`);
      setImagePreview('');
    }
  });

  imageInput?.addEventListener('input', () => {
    const val = imageInput.value.trim();
    if (val) {
      const previewImageEl = document.getElementById('blog-preview-img');
      const previewBox = document.getElementById('blog-preview-box');
      if (previewImageEl) previewImageEl.src = val;
      if (previewBox) previewBox.classList.remove('hidden');
    } else {
      const previewBox = document.getElementById('blog-preview-box');
      if (previewBox) previewBox.classList.add('hidden');
    }
  });

  removeBtn?.addEventListener('click', () => setImagePreview(''));

  // ---------------------------------------------------------------------------
  // 3. Fetch & Render Blogs Table
  // ---------------------------------------------------------------------------
  async function loadBlogs() {
    try {
      const isTrash = currentFilter === 'trash';
      const statusParam = (currentFilter !== 'all' && currentFilter !== 'trash') ? currentFilter : '';
      const url = `/visionadmin/api/blogs?status=${statusParam}&trash=${isTrash ? '1' : '0'}&q=${encodeURIComponent(currentSearch)}`;
      const res = await fetch(url);
      if (res.status === 401 || res.status === 403) {
        window.location.href = `/visionadmin/login?next=${encodeURIComponent(window.location.pathname)}`;
        return;
      }
      const data = await res.json();

      if (!res.ok) throw new Error(data.error || 'Failed to load blogs');

      blogsData = data.blogs || [];
      updateMetrics(data.metrics || {});
      renderTable(blogsData);
    } catch (err) {
      tableBody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-rose-500 font-bold">Error loading articles: ${err.message}</td></tr>`;
    }
  }

  function updateMetrics(metrics) {
    document.getElementById('stat-total').textContent = metrics.total || 0;
    document.getElementById('stat-published').textContent = metrics.published || 0;
    document.getElementById('stat-draft').textContent = metrics.draft || 0;
    document.getElementById('stat-archived').textContent = metrics.archived || 0;
    document.getElementById('stat-trash').textContent = metrics.trash || 0;
  }

  function renderTable(blogs) {
    if (!blogs.length) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="5" class="py-12 text-center text-slate-400">
            <svg class="w-8 h-8 mx-auto text-slate-300 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><line x1="9" y1="6" x2="16" y2="6"/><line x1="9" y1="10" x2="16" y2="10"/></svg>
            <p class="font-bold text-sm text-slate-600">No blog articles found</p>
            <p class="text-xs text-slate-400 mt-0.5">${currentFilter === 'trash' ? 'Trash is empty.' : 'Click "+ Create New Article" to publish one.'}</p>
          </td>
        </tr>
      `;
      return;
    }

    tableBody.innerHTML = blogs.map(b => {
      let enTitle = 'Untitled Article';
      let arTitle = '';
      if (typeof b.title === 'object' && b.title !== null) {
        enTitle = b.title.en || b.title.ar || 'Untitled Article';
        arTitle = b.title.ar || '';
      } else if (typeof b.title === 'string') {
        if (b.title.trim().startsWith('{')) {
          try {
            const parsed = JSON.parse(b.title);
            enTitle = parsed.en || parsed.ar || b.title;
            arTitle = parsed.ar || '';
          } catch (e) {
            enTitle = b.title;
          }
        } else {
          enTitle = b.title;
        }
      }

      let statusBadge = '';
      if (b.status === 'published') {
        statusBadge = '<span class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">Published</span>';
      } else if (b.status === 'archived') {
        statusBadge = '<span class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">Archived</span>';
      } else {
        statusBadge = '<span class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">Draft</span>';
      }

      const isTrash = currentFilter === 'trash';
      const pubDate = b.published_at ? b.published_at.split('T')[0] : (b.created_at ? b.created_at.split('T')[0] : '—');

      return `
        <tr class="hover:bg-slate-50/70 transition">
          <td class="py-3.5 px-4 sm:px-6">
            <div class="space-y-0.5">
              <div class="flex items-center gap-2">
                <span class="font-bold text-slate-900">${escapeHtml(enTitle)}</span>
                ${arTitle ? `<span class="text-xs text-slate-400" dir="rtl">(${escapeHtml(arTitle)})</span>` : ''}
              </div>
              <div class="flex items-center gap-2 text-xs">
                <a href="/blog/${b.slug}" target="_blank" class="text-[#2563FF] font-mono hover:underline inline-flex items-center gap-1">
                  <span>/blog/${b.slug}</span>
                  <svg class="w-3 h-3 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                </a>
              </div>
            </div>
          </td>
          <td class="py-3.5 px-4">
            ${b.category_name ? `
              <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-800 border border-slate-200">
                ${escapeHtml(b.category_name)}
              </span>
            ` : '<span class="text-xs text-slate-400">—</span>'}
          </td>
          <td class="py-3.5 px-4">
            ${b.image ? `
              <div class="flex items-center gap-2">
                <img src="${escapeHtml(b.image)}" alt="Thumbnail" class="w-10 h-7 object-cover rounded-lg border border-slate-200 shadow-2xs shrink-0" />
                <a href="${escapeHtml(b.image)}" target="_blank" class="text-[11px] text-indigo-600 font-bold hover:underline truncate max-w-[100px]">View</a>
              </div>
            ` : '<span class="text-xs text-slate-400">No Image</span>'}
          </td>
          <td class="py-3.5 px-4">
            ${statusBadge}
          </td>
          <td class="py-3.5 px-4 font-mono text-xs text-slate-500">
            ${pubDate}
          </td>
          <td class="py-3.5 px-4 sm:px-6 text-right space-x-1.5 whitespace-nowrap">
            ${!isTrash ? `
              <button type="button" onclick="window.editBlog(${b.id})" class="group inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-200/90 text-slate-700 text-xs font-bold shadow-2xs hover:shadow-xs transition cursor-pointer">
                <svg class="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-700 group-hover:-rotate-12 transition-transform duration-200" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                <span>Edit</span>
              </button>
              <button type="button" onclick="window.deleteBlog(${b.id}, '${escapeHtml(enTitle)}', false)" class="group inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-50/80 hover:bg-rose-100/90 border border-rose-200/70 text-rose-700 text-xs font-bold transition cursor-pointer">
                <svg class="w-3.5 h-3.5 text-rose-500 group-hover:scale-110 group-hover:rotate-6 transition-transform duration-200" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                <span>Trash</span>
              </button>
            ` : `
              <button type="button" onclick="window.restoreBlog(${b.id})" class="group inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-50 hover:bg-blue-100 border border-blue-200/80 text-blue-700 text-xs font-bold transition cursor-pointer">
                <svg class="w-3.5 h-3.5 text-[#2563FF] group-hover:rotate-180 transition-transform duration-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
                <span>Restore</span>
              </button>
              <button type="button" onclick="window.deleteBlog(${b.id}, '${escapeHtml(enTitle)}', true)" class="group inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 text-white text-xs font-extrabold shadow-sm hover:shadow-md transition cursor-pointer">
                <svg class="w-3.5 h-3.5 group-hover:scale-110 transition-transform duration-200" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                <span>Delete Permanently</span>
              </button>
            `}
          </td>
        </tr>
      `;
    }).join('');

    if (window.jQuery && $.fn.DataTable) {
      if ($.fn.DataTable.isDataTable('#blogs-table')) {
        $('#blogs-table').DataTable().destroy();
      }
      $('#blogs-table').DataTable({
        responsive: true,
        pageLength: 10,
        lengthMenu: [10, 25, 50, 100],
        pagingType: 'full_numbers',
        autoWidth: false,
        columnDefs: [
          { orderable: false, targets: [2, 5] }
        ],
        order: [[4, 'desc']],
        language: {
          search: '',
          searchPlaceholder: 'Search articles...',
          lengthMenu: 'Show _MENU_ per page',
          info: 'Showing _START_ to _END_ of _TOTAL_ articles',
          infoEmpty: 'No articles to show',
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
      loadBlogs();
    });
  });

  let searchTimeout = null;
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        currentSearch = e.target.value.trim();
        loadBlogs();
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
          if (loc === 'ar' && CKEDITOR.instances.blog_content_ar) {
            CKEDITOR.instances.blog_content_ar.resize();
          } else if (loc === 'en' && CKEDITOR.instances.blog_content_en) {
            CKEDITOR.instances.blog_content_en.resize();
          }
        }
      }, 50);
    });
  });

  // ---------------------------------------------------------------------------
  // 5.5 Category Dropdown & Inline "+ Add Category" Handler
  // ---------------------------------------------------------------------------
  // ---------------------------------------------------------------------------
  // 5.8 Blog FAQs Repeater Management
  // ---------------------------------------------------------------------------
  let blogFaqItems = [];
  const faqListContainer = document.getElementById('blog-faq-list');
  const addFaqBtn = document.getElementById('btn-add-faq-item');

  function renderFaqItems() {
    if (!faqListContainer) return;
    if (blogFaqItems.length === 0) {
      faqListContainer.innerHTML = `
        <div class="py-6 px-4 rounded-xl border border-dashed border-slate-200 text-center bg-white/60">
          <p class="text-xs text-slate-400 font-semibold">No FAQ items added yet for this article.</p>
          <button type="button" class="mt-2 text-xs font-bold text-[#2563FF] hover:text-blue-700 underline cursor-pointer" onclick="document.getElementById('btn-add-faq-item').click()">
            + Add first FAQ question &amp; answer
          </button>
        </div>
      `;
      return;
    }

    faqListContainer.innerHTML = blogFaqItems.map((item, idx) => {
      const qEn = escapeHtml(item?.question?.en || (typeof item?.question === 'string' ? item.question : ''));
      const qAr = escapeHtml(item?.question?.ar || '');
      const aEn = escapeHtml(item?.answer?.en || (typeof item?.answer === 'string' ? item.answer : ''));
      const aAr = escapeHtml(item?.answer?.ar || '');

      return `
        <div class="p-4 rounded-2xl bg-white border border-slate-200/80 shadow-2xs space-y-3.5" data-faq-idx="${idx}">
          <div class="flex items-center justify-between pb-2 border-b border-slate-100">
            <span class="text-[11px] font-extrabold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
              <span class="w-5 h-5 rounded-full bg-blue-50 text-blue-700 flex items-center justify-center text-[10px] font-black">${idx + 1}</span>
              <span>FAQ Item #${idx + 1}</span>
            </span>
            <button type="button" class="btn-remove-faq text-[11px] font-bold text-rose-500 hover:text-rose-700 transition flex items-center gap-1 cursor-pointer" data-idx="${idx}">
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              <span>Remove</span>
            </button>
          </div>

          <!-- Question Fields -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block text-[11px] font-extrabold uppercase tracking-wider text-slate-600 mb-1">Question (English)</label>
              <input type="text" class="faq-input-q-en w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-600 shadow-inner" placeholder="e.g. How often should tyres be rotated?" value="${qEn}" />
            </div>
            <div>
              <label class="block text-[11px] font-extrabold uppercase tracking-wider text-slate-600 mb-1">Question (Arabic)</label>
              <input type="text" dir="rtl" class="faq-input-q-ar w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-600 shadow-inner" placeholder="السؤال بالعربية (مثال: كم مرة يجب تدوير الإطارات؟)..." value="${qAr}" />
            </div>
          </div>

          <!-- Answer Fields -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block text-[11px] font-extrabold uppercase tracking-wider text-slate-600 mb-1">Answer (English)</label>
              <textarea rows="2" class="faq-input-a-en w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-blue-600 shadow-inner" placeholder="Provide detailed answer in English...">${aEn}</textarea>
            </div>
            <div>
              <label class="block text-[11px] font-extrabold uppercase tracking-wider text-slate-600 mb-1">Answer (Arabic)</label>
              <textarea rows="2" dir="rtl" class="faq-input-a-ar w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-blue-600 shadow-inner" placeholder="الإجابة التفصيلية بالعربية...">${aAr}</textarea>
            </div>
          </div>
        </div>
      `;
    }).join('');

    // Attach listeners
    faqListContainer.querySelectorAll('.btn-remove-faq').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.idx, 10);
        syncFaqFromDOM();
        blogFaqItems.splice(idx, 1);
        renderFaqItems();
      });
    });
  }

  function syncFaqFromDOM() {
    if (!faqListContainer) return;
    const cards = faqListContainer.querySelectorAll('[data-faq-idx]');
    cards.forEach((card, idx) => {
      if (!blogFaqItems[idx]) blogFaqItems[idx] = { question: {}, answer: {} };
      const qEn = card.querySelector('.faq-input-q-en')?.value.trim() || '';
      const qAr = card.querySelector('.faq-input-q-ar')?.value.trim() || '';
      const aEn = card.querySelector('.faq-input-a-en')?.value.trim() || '';
      const aAr = card.querySelector('.faq-input-a-ar')?.value.trim() || '';

      blogFaqItems[idx] = {
        question: { en: qEn, ar: qAr },
        answer: { en: aEn, ar: aAr }
      };
    });
  }

  addFaqBtn?.addEventListener('click', () => {
    syncFaqFromDOM();
    blogFaqItems.push({
      question: { en: '', ar: '' },
      answer: { en: '', ar: '' }
    });
    renderFaqItems();
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

  async function loadCategories(selectedVal = null, selectedId = null) {
    const catSelect = document.getElementById('category_name');
    if (!catSelect) return;

    try {
      const res = await fetch('/visionadmin/api/blog-categories');
      const data = await res.json();
      const categories = data.categories || [];

      let html = '<option value="">Select Category...</option>';
      categories.forEach(c => {
        const isSelected = (selectedId && selectedId == c.id) ||
          (selectedVal && (selectedVal.toLowerCase() === c.name_en.toLowerCase() || selectedVal.toLowerCase() === c.slug.toLowerCase()));
        html += `<option value="${escapeHtml(c.name_en)}" data-id="${c.id}" ${isSelected ? 'selected' : ''}>${escapeHtml(c.name_en)}</option>`;
      });
      catSelect.innerHTML = html;

      if (selectedVal && !categories.some(c => c.name_en.toLowerCase() === selectedVal.toLowerCase())) {
        const opt = document.createElement('option');
        opt.value = selectedVal;
        opt.textContent = selectedVal;
        opt.selected = true;
        catSelect.appendChild(opt);
      }
    } catch (e) {
      console.error('Error loading blog categories:', e);
    }
  }

  // ---------------------------------------------------------------------------
  // 5B. Blog Categories Studio Management
  // ---------------------------------------------------------------------------
  let cachedCategories = [];
  const categoriesModal = document.getElementById('blog-categories-modal');
  const catTableBody = document.getElementById('categories-table-body');
  const catCountBadge = document.getElementById('categories-count-badge');
  const catNameEnInput = document.getElementById('cat_name_en');
  const catNameArInput = document.getElementById('cat_name_ar');
  const catSlugInput = document.getElementById('cat_slug');
  const catEditIdInput = document.getElementById('category-edit-id');
  const catFormTitle = document.getElementById('cat-form-title');
  const btnSaveCat = document.getElementById('btn-save-category');
  const btnSaveCatText = document.getElementById('btn-save-cat-text');
  const btnCancelCatEdit = document.getElementById('btn-cancel-cat-edit');

  function openCategoriesModal() {
    resetCategoryForm();
    loadCategoriesManagerTable();
    if (categoriesModal) categoriesModal.classList.remove('hidden');
  }

  function closeCategoriesModal() {
    if (categoriesModal) categoriesModal.classList.add('hidden');
    const currentSelected = document.getElementById('category_name')?.value;
    loadCategories(currentSelected);
  }

  function resetCategoryForm() {
    if (catEditIdInput) catEditIdInput.value = '';
    if (catNameEnInput) catNameEnInput.value = '';
    if (catNameArInput) catNameArInput.value = '';
    if (catSlugInput) catSlugInput.value = '';
    if (catFormTitle) catFormTitle.textContent = '+ Add New Category';
    if (btnSaveCatText) btnSaveCatText.textContent = 'Save Category';
    if (btnCancelCatEdit) btnCancelCatEdit.classList.add('hidden');
  }

  catNameEnInput?.addEventListener('input', () => {
    if (!catEditIdInput?.value && catSlugInput) {
      catSlugInput.value = catNameEnInput.value.toLowerCase()
        .replace(/[^\w\s-]/g, '')
        .replace(/[\s_-]+/g, '-')
        .replace(/^-+|-+$/g, '');
    }
  });

  async function loadCategoriesManagerTable() {
    if (!catTableBody) return;
    catTableBody.innerHTML = '<tr><td colspan="5" class="py-8 text-center text-slate-400 font-medium">Loading categories…</td></tr>';

    try {
      const res = await fetch('/visionadmin/api/blog-categories');
      const data = await res.json();
      cachedCategories = data.categories || [];

      if (catCountBadge) {
        catCountBadge.textContent = `${cachedCategories.length} Categories`;
      }

      if (cachedCategories.length === 0) {
        catTableBody.innerHTML = '<tr><td colspan="5" class="py-8 text-center text-slate-400 font-medium">No categories found in database. Add one above!</td></tr>';
        return;
      }

      catTableBody.innerHTML = cachedCategories.map(c => `
        <tr class="hover:bg-slate-50/80 transition">
          <td class="py-3 px-4 font-mono font-bold text-slate-400">#${c.id}</td>
          <td class="py-3 px-4">
            <div class="font-bold text-[#0E1108] text-xs">${escapeHtml(c.name_en)}</div>
            ${c.name_ar ? `<div class="text-[10px] text-slate-400" dir="rtl">${escapeHtml(c.name_ar)}</div>` : ''}
          </td>
          <td class="py-3 px-4 font-mono text-[11px] text-slate-500">
            <span class="px-2 py-0.5 rounded bg-slate-100">${escapeHtml(c.slug)}</span>
          </td>
          <td class="py-3 px-4 text-center">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-blue-50 text-blue-700">
              ${c.blogs_count || 0}
            </span>
          </td>
          <td class="py-3 px-4 text-right space-x-1 whitespace-nowrap">
            <button type="button" onclick="window.editCategory(${c.id})" class="p-1.5 rounded-lg text-slate-500 hover:text-[#1D4ED8] hover:bg-[#EFF6FF] transition cursor-pointer" title="Edit Category">
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <button type="button" onclick="window.deleteCategory(${c.id}, '${escapeHtml(c.name_en)}')" class="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition cursor-pointer" title="Delete Category">
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </td>
        </tr>
      `).join('');

    } catch (e) {
      console.error('Error loading category table:', e);
      catTableBody.innerHTML = '<tr><td colspan="5" class="py-8 text-center text-rose-500 font-medium">Failed to load categories.</td></tr>';
    }
  }

  btnSaveCat?.addEventListener('click', async () => {
    const name_en = catNameEnInput?.value.trim();
    const name_ar = catNameArInput?.value.trim() || name_en;
    const slug = catSlugInput?.value.trim();
    const editId = catEditIdInput?.value;

    if (!name_en) {
      alert('Please enter a category name.');
      catNameEnInput?.focus();
      return;
    }

    try {
      const url = editId ? `/visionadmin/api/blog-categories/${editId}` : '/visionadmin/api/blog-categories';
      const method = editId ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name_en, name_ar, slug })
      });

      const data = await res.json();
      if (data.success) {
        resetCategoryForm();
        loadCategoriesManagerTable();
        loadCategories();
      } else {
        alert(data.error || 'Failed to save category.');
      }
    } catch (e) {
      alert('Network error saving category.');
    }
  });

  btnCancelCatEdit?.addEventListener('click', resetCategoryForm);

  window.editCategory = function(catId) {
    const cat = cachedCategories.find(c => c.id === catId);
    if (!cat) return;

    if (catEditIdInput) catEditIdInput.value = cat.id;
    if (catNameEnInput) catNameEnInput.value = cat.name_en || '';
    if (catNameArInput) catNameArInput.value = cat.name_ar || '';
    if (catSlugInput) catSlugInput.value = cat.slug || '';
    if (catFormTitle) catFormTitle.textContent = `✏️ Edit Category: ${cat.name_en}`;
    if (btnSaveCatText) btnSaveCatText.textContent = 'Update Category';
    if (btnCancelCatEdit) btnCancelCatEdit.classList.remove('hidden');
    catNameEnInput?.focus();
  };

  window.deleteCategory = async function(catId, catName) {
    if (!confirm(`Are you sure you want to delete category "${catName}"?\nArticles in this category will become uncategorized.`)) return;

    try {
      const res = await fetch(`/visionadmin/api/blog-categories/${catId}`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (data.success) {
        loadCategoriesManagerTable();
        loadCategories();
        loadBlogs();
      } else {
        alert(data.error || 'Failed to delete category.');
      }
    } catch (e) {
      alert('Network error deleting category.');
    }
  };

  document.getElementById('btn-manage-categories')?.addEventListener('click', openCategoriesModal);
  document.getElementById('btn-quick-manage-cats')?.addEventListener('click', openCategoriesModal);
  document.getElementById('btn-close-categories-modal')?.addEventListener('click', closeCategoriesModal);
  document.getElementById('btn-done-categories-modal')?.addEventListener('click', closeCategoriesModal);
  document.getElementById('categories-modal-backdrop')?.addEventListener('click', closeCategoriesModal);

  function openModal(isEdit = false, blog = null) {
    if (blogForm) blogForm.reset();
    if (editIdInput) editIdInput.value = isEdit && blog ? blog.id : '';
    if (modalTitle) modalTitle.textContent = isEdit ? 'Edit Blog Article' : 'Create New Blog Article';
    if (saveBtnText) saveBtnText.textContent = isEdit ? 'Save Changes' : 'Publish Article';

    if (isEdit && blog) {
      setVal('title_en', (typeof blog.title === 'object' ? blog.title?.en : blog.title) || '');
      setVal('slug', blog.slug || '');
      setVal('status', blog.status || 'draft');
      setVal('short_description_en', (typeof blog.short_description === 'object' ? blog.short_description?.en : blog.short_description) || '');
      setVal('meta_title_en', (typeof blog.meta_title === 'object' ? blog.meta_title?.en : '') || '');
      setVal('meta_desc_en', (typeof blog.meta_desc === 'object' ? blog.meta_desc?.en : '') || '');

      loadCategories(blog.category_name || null, blog.category_id || null);
      setImagePreview(blog.image || '');

      const contentEnVal = (typeof blog.content === 'object' ? blog.content?.en : blog.content) || '';
      setEditorContent('blog_content_en', contentEnVal);

      // Populate FAQ items
      blogFaqItems = Array.isArray(blog.faqs) ? JSON.parse(JSON.stringify(blog.faqs)) : [];
      renderFaqItems();

    } else {
      setVal('status', 'published');
      loadCategories(null);
      setImagePreview('');

      setEditorContent('blog_content_en', '');

      blogFaqItems = [];
      renderFaqItems();
    }

    if (modal) modal.classList.remove('hidden');

    // Resize active editor after modal animation
    setTimeout(() => {
      if (window.CKEDITOR && CKEDITOR.instances) {
        if (CKEDITOR.instances.blog_content_en) CKEDITOR.instances.blog_content_en.resize();
        if (CKEDITOR.instances.blog_content_ar) CKEDITOR.instances.blog_content_ar.resize();
      }
    }, 100);
  }

  function closeModal() {
    if (modal) modal.classList.add('hidden');
  }

  document.getElementById('btn-create-blog')?.addEventListener('click', () => openModal(false));
  document.getElementById('btn-close-blog-modal')?.addEventListener('click', closeModal);
  document.getElementById('btn-cancel-blog-modal')?.addEventListener('click', closeModal);
  document.getElementById('blog-modal-backdrop')?.addEventListener('click', closeModal);

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
      alert('Please provide an article title.');
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

    const content_en = getEditorContent('blog_content_en');
    const short_desc = getVal('short_description_en');
    const meta_title = getVal('meta_title_en');
    const meta_desc = getVal('meta_desc_en');

    // Sync FAQ repeater values
    syncFaqFromDOM();
    const validFaqs = blogFaqItems.filter(f => {
      const qEn = (f?.question?.en || f?.question || '').trim();
      const aEn = (f?.answer?.en || f?.answer || '').trim();
      return qEn || aEn;
    });

    const payload = {
      title: { en: title_en, ar: title_en },
      content: { en: content_en, ar: content_en },
      short_description: {
        en: short_desc,
        ar: short_desc
      },
      slug: slug,
      category_id: (document.getElementById('category_name')?.selectedOptions[0]?.dataset?.id) ? parseInt(document.getElementById('category_name').selectedOptions[0].dataset.id) : null,
      category_name: getVal('category_name') || null,
      image: imageInput ? imageInput.value.trim() || null : null,
      status: getVal('status') || 'draft',
      meta_title: {
        en: meta_title,
        ar: meta_title
      },
      meta_desc: {
        en: meta_desc,
        ar: meta_desc
      },
      faqs: validFaqs
    };

    if (saveBtn) saveBtn.disabled = true;
    if (saveBtnText) saveBtnText.textContent = 'Saving…';

    try {
      const url = editId ? `/visionadmin/api/blogs/${editId}` : '/visionadmin/api/blogs';
      const method = editId ? 'PUT' : 'POST';

      const res = await fetch(url, {
        method: method,
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to save article');

      window.vaShowToast(data.message || 'Article saved successfully!');
      closeModal();
      loadBlogs();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      if (saveBtn) saveBtn.disabled = false;
      if (saveBtnText) saveBtnText.textContent = editId ? 'Save Changes' : 'Publish Article';
    }
  });

  // ---------------------------------------------------------------------------
  // 8. Global Action Helpers
  // ---------------------------------------------------------------------------
  window.editBlog = async function(id) {
    try {
      const res = await fetch(`/visionadmin/api/blogs/${id}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to fetch article data');
      openModal(true, data.blog);
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  window.deleteBlog = async function(id, title, isHard = false) {
    const executeDelete = async () => {
      try {
        const url = isHard ? `/visionadmin/api/blogs/${id}?hard=1` : `/visionadmin/api/blogs/${id}`;
        const res = await fetch(url, {
          method: 'DELETE'
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to delete article');

        window.vaShowToast(data.message || (isHard ? 'Article deleted permanently.' : 'Article moved to Trash.'));
        loadBlogs();
      } catch (err) {
        window.vaShowToast(`Error: ${err.message}`, 'error');
      }
    };

    if (isHard) {
      // Trigger Glassmorphism Hard Delete Modal
      window.vaConfirmHardDelete({
        title: 'Delete Article Permanently',
        message: `Are you sure you want to permanently purge article "${title}"? All multilingual translations, media links, and database records will be erased forever.`,
        itemName: title || `Blog Article #${id}`,
        confirmText: 'Purge Article',
        onConfirm: executeDelete
      });
    } else {
      if (!confirm(`Are you sure you want to move article "${title}" to Trash?`)) return;
      executeDelete();
    }
  };

  window.restoreBlog = async function(id) {
    try {
      const res = await fetch(`/visionadmin/api/blogs/${id}/restore`, {
        method: 'POST'
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to restore article');

      window.vaShowToast('Article restored successfully.');
      loadBlogs();
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  // Initial Load
  loadBlogs();

  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('open') === 'categories' || window.location.hash === '#categories') {
    openCategoriesModal();
  }
});
