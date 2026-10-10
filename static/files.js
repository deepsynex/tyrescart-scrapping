// File/Scraper Management page (/files). Mirrors static/admin.js's structure
// (DataTables + window.AdminShared helpers for modals/toasts/escaping) so this
// page renders and behaves consistently with User Management/Trash, rather
// than inventing a second UI pattern.
(function () {
  const tableEl = document.getElementById('files-table');
  if (!tableEl) return; // Not on the /files page.

  const Shared = window.AdminShared;
  const errorEl = document.getElementById('files-error');
  const loadingEl = document.getElementById('files-loading');
  const newBtn = document.getElementById('files-new-btn');
  const refreshBtn = document.getElementById('files-refresh-btn');
  const refreshIcon = document.getElementById('files-refresh-icon');
  const zipBtn = document.getElementById('files-download-zip-btn');

  const modal = document.getElementById('files-modal');
  const modalTitle = document.getElementById('files-modal-title');
  const modalError = document.getElementById('files-modal-error');
  const form = document.getElementById('files-form');
  const idInput = document.getElementById('files-form-id');
  const siteNameInput = document.getElementById('files-form-site-name');
  const logoInput = document.getElementById('files-form-logo');
  const submitBtn = document.getElementById('files-form-submit');
  const submitLabel = document.getElementById('files-form-submit-label');

  const deleteModal = document.getElementById('files-delete-modal');
  const deleteTitle = deleteModal ? deleteModal.querySelector('h3') : null;
  const deleteText = document.getElementById('files-delete-text');
  const deleteError = document.getElementById('files-delete-error');
  const deleteConfirmBtn = document.getElementById('files-delete-confirm');

  // --- URLs: paste a list directly into the textarea, or upload a CSV --
  const urlsTextarea = document.getElementById('files-form-urls');
  const urlsCsvInput = document.getElementById('files-form-urls-csv');
  const urlsSpinner = document.getElementById('files-form-urls-spinner');
  const urlsStatus = document.getElementById('files-form-urls-status');
  const URLS_STATUS_DEFAULT = "A CSV's URL column (or first column) is converted into the list above -- review it before saving.";

  // --- Python File: upload-only now ---
  const currentFileNote = document.getElementById('files-form-current-file');
  const currentFileNameEl = document.getElementById('files-form-current-file-name');
  const uploadPanel = document.getElementById('files-form-upload-panel');
  const noAccessNote = document.getElementById('files-form-no-access');
  const uploadInput = document.getElementById('files-form-upload');
  const uploadStatus = document.getElementById('files-form-upload-status');
  const uploadSpinner = document.getElementById('files-form-upload-spinner');
  const submitSpinner = document.getElementById('files-form-submit-spinner');

  let csrfToken = (typeof window !== 'undefined' && window.__CSRF_TOKEN__) ? window.__CSRF_TOKEN__ : null;
  let currentRole = (typeof window !== 'undefined' && window.__CURRENT_USER_ROLE__) ? window.__CURRENT_USER_ROLE__ : null;
  let files = [];
  let filesById = new Map();
  let table = null;
  let pendingDeleteId = null;
  let inFlightStarts = new Map(); // file_id -> 'start'|'stop'
  let inFlightToggles = new Set(); // file_id
  let uploadedFileName = null;

  const canUploadScripts = () => {
    const role = ((currentRole || (typeof window !== 'undefined' ? window.__CURRENT_USER_ROLE__ : null)) || '').toString().trim().toLowerCase();
    return role === 'superadmin' || role === 'admin';
  };
  let lastFilesSnapshot = null;

  function logoCellHtml(row) {
    if (row.logo) {
      const safeUrl = Shared.escapeHtml(row.logo);
      return `<img src="${safeUrl}" alt="" class="w-8 h-8 rounded-lg object-cover border border-slate-200" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'inline-flex w-8 h-8 rounded-lg bg-slate-100 items-center justify-center text-slate-400 text-xs',textContent:'?'}))" />`;
    }
    return '<span class="inline-flex w-8 h-8 rounded-lg bg-slate-100 items-center justify-center text-slate-400 text-xs">?</span>';
  }

  function createdByCellHtml(row) {
    const name = row.createdByName || 'Admin';
    const safeName = Shared.escapeHtml(name);
    const initial = (name.trim()[0] || 'U').toUpperCase();
    return `
      <div class="flex items-center gap-2">
        <span class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-700 border border-slate-200">${initial}</span>
        <span class="font-medium text-slate-800">${safeName}</span>
      </div>
    `;
  }

  function statusBadgeHtml(row) {
    if (row.working) {
      if (row.is_owner) {
        return `<a href="/tcsadmin/scraperpage?fileId=${row.fileId}" class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700 hover:bg-emerald-200 transition-colors" title="Click to view your live progress"><span class="w-1.5 h-1.5 rounded-full bg-[#2563FF] animate-pulse"></span>Running</a>`;
      }
      return `<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200/80" title="This scraper is currently being used by another user">In Use</span>`;
    }
    return `<span class="px-2 py-0.5 rounded-full text-xs font-semibold ${row.isEnabled ? 'bg-slate-200 text-slate-500' : 'bg-slate-100 text-slate-400'}">${row.isEnabled ? 'Not Running' : 'Disabled'}</span>`;
  }

  function actionsCellHtml(row) {
    const busyAction = inFlightStarts.get(row.fileId);
    const isOtherRunning = row.working && !row.is_owner;
    const busy = !row.isEnabled || !!busyAction || isOtherRunning;

    let startStopBtn = '';
    let viewLiveBtn = '';

    if (row.working) {
      if (row.is_owner) {
        const startStopLabel = busyAction === 'stop' ? 'Stopping…' : 'Stop';
        startStopBtn = `<button type="button" data-action="stop" data-id="${row.fileId}" ${busyAction === 'stop' ? 'disabled' : ''} class="text-xs font-semibold ${busyAction === 'stop' ? 'text-slate-300 cursor-not-allowed' : 'text-rose-600 hover:underline cursor-pointer'}">${startStopLabel}</button>`;
        viewLiveBtn = `<a href="/tcsadmin/scraperpage?fileId=${row.fileId}" class="text-xs font-semibold text-indigo-600 hover:underline cursor-pointer">View Progress</a>`;
      } else {
        startStopBtn = `<button type="button" disabled class="text-xs font-semibold text-slate-400 cursor-not-allowed" title="This scraper is currently being used by another user.">In Use</button>`;
      }
    } else {
      const startStopLabel = busyAction === 'start' ? 'Please wait…' : 'Start';
      const startStopDisabled = !row.isEnabled ? 'disabled title="Enable scraper before starting"' : (busy ? 'disabled' : '');
      startStopBtn = `<button type="button" data-action="start" data-id="${row.fileId}" ${startStopDisabled} class="text-xs font-semibold ${busy ? 'text-slate-400 cursor-not-allowed' : 'text-[#2563FF] hover:underline cursor-pointer'}">${startStopLabel}</button>`;
    }

    const downloadBtn = row.outputAvailable && !row.working
      ? `<a href="/tcsadmin/api/files/${row.fileId}/download" class="text-xs font-semibold text-[#2563FF] hover:text-blue-700 hover:underline cursor-pointer" title="Download output Excel">Download</a>`
      : '';
    const logBtn = `<button type="button" data-action="view-logs" data-id="${row.fileId}" class="text-xs font-semibold text-indigo-600 hover:underline cursor-pointer">Log</button>`;

    const canManage = canUploadScripts();
    const editBtn = canManage
      ? `<button type="button" data-action="edit" data-id="${row.fileId}" ${row.working ? 'disabled title="Stop the scraper before editing it"' : ''} class="text-xs font-semibold ${row.working ? 'text-slate-300 cursor-not-allowed' : 'text-slate-600 hover:underline cursor-pointer'}">Edit</button>`
      : '';
    const deleteBtn = canManage
      ? `<button type="button" data-action="delete" data-id="${row.fileId}" ${row.working ? 'disabled title="Stop the scraper before deleting it"' : ''} class="text-xs font-semibold ${row.working ? 'text-slate-300 cursor-not-allowed' : 'text-rose-600 hover:underline cursor-pointer'}">Delete</button>`
      : '';

    return `
      <div class="flex items-center justify-end gap-3">
        ${downloadBtn}
        ${viewLiveBtn}
        ${startStopBtn}
        ${logBtn}
        ${editBtn}
        ${deleteBtn}
      </div>`;
  }

  function enabledToggleHtml(row) {
    const isBusy = inFlightToggles.has(row.fileId);
    const checked = row.isEnabled ? 'checked' : '';
    const canManage = canUploadScripts();
    const disabled = !canManage || row.working || isBusy ? 'disabled' : '';
    const title = !canManage
      ? 'Only Admins can enable or disable scrapers'
      : (row.working ? 'Stop scraper before disabling' : (row.isEnabled ? 'Enabled (click to disable)' : 'Disabled (click to enable)'));
    return `
      <div class="flex items-center justify-center">
        <label class="relative inline-flex items-center ${!canManage || row.working || isBusy ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}" title="${title}">
          <input type="checkbox" data-action="toggle-status" data-id="${row.fileId}" class="sr-only peer" ${checked} ${disabled}>
          <div class="w-9 h-5 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-600"></div>
        </label>
      </div>
    `;
  }

  function updateZipButtonState(anyRunning, hasAnyOutput) {
    if (!zipBtn) return;
    if (anyRunning) {
      zipBtn.classList.add('opacity-50', 'pointer-events-none', 'cursor-not-allowed', 'bg-slate-400');
      zipBtn.classList.remove('bg-slate-900', 'hover:bg-slate-800');
      zipBtn.setAttribute('title', 'Scraping is in progress. Please wait until all scrapers finish before downloading ZIP.');
      zipBtn.innerHTML = `
        <svg class="w-4 h-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        <span>Scraping In Progress…</span>
      `;
    } else if (!hasAnyOutput) {
      zipBtn.classList.add('opacity-50', 'pointer-events-none', 'cursor-not-allowed', 'bg-slate-400');
      zipBtn.classList.remove('bg-slate-900', 'hover:bg-slate-800');
      zipBtn.setAttribute('title', 'No completed scraper reports available to download.');
      zipBtn.innerHTML = `
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
        <span>Download ZIP</span>
      `;
    } else {
      zipBtn.classList.remove('opacity-50', 'pointer-events-none', 'cursor-not-allowed', 'bg-slate-400');
      zipBtn.classList.add('bg-slate-900', 'hover:bg-slate-800');
      zipBtn.setAttribute('title', 'Download a ZIP archive containing Excel reports for all finished scrapers');
      zipBtn.innerHTML = `
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
        <span>Download ZIP</span>
      `;
    }
  }

  function initTable() {
    table = $(tableEl).DataTable(Shared.commonDataTableOptions({
      data: [],
      order: [[1, 'asc']],
      language: {
        search: '',
        searchPlaceholder: 'Search scrapers, created by…',
        lengthMenu: 'Show _MENU_ per page',
        info: 'Showing _START_ to _END_ of _TOTAL_',
        infoEmpty: 'No scrapers to show',
        infoFiltered: '(filtered from _MAX_ total)',
        paginate: { first: 'First', last: 'Last', next: 'Next', previous: 'Previous' },
      },
      columns: [
        {
          data: null, orderable: false, searchable: false,
          render: (data, type, row) => (type === 'display' ? logoCellHtml(row) : ''),
        },
        {
          data: null,
          render: (data, type, row) => (type === 'display' ? Shared.escapeHtml(row.siteName) : row.siteName),
        },
        {
          data: null,
          render: (data, type, row) => (type === 'display' ? createdByCellHtml(row) : (row.createdByName || '')),
        },
        {
          data: null,
          render: (data, type, row) => (type === 'display' ? statusBadgeHtml(row) : (row.working ? 'Running' : 'Not Running')),
        },
        {
          data: null,
          render: (data, type, row) => (type === 'display' ? Shared.dateTimeHtml(row.createDateRaw) : (row.createDateRaw || '')),
        },
        {
          data: null,
          render: (data, type, row) => (type === 'display' ? Shared.dateTimeHtml(row.updateDateRaw) : (row.updateDateRaw || '')),
        },
        {
          data: null,
          render: (data, type, row) => (type === 'display' ? (row.lastUsedRaw ? Shared.dateTimeHtml(row.lastUsedRaw) : '<span class="text-xs text-slate-400 font-medium">—</span>') : (row.lastUsedRaw || '')),
        },
        {
          data: null, orderable: false, searchable: false, className: 'text-right',
          render: (data, type, row) => (type === 'display' ? actionsCellHtml(row) : ''),
        },
        {
          data: null, orderable: false, searchable: false, className: 'text-center',
          render: (data, type, row) => (type === 'display' ? enabledToggleHtml(row) : (row.isEnabled ? 1 : 0)),
        },
      ],
    }));
  }

  function showTable() {
    loadingEl.classList.add('hidden');
    tableEl.classList.remove('hidden');
  }

  async function loadMe() {
    try {
      const response = await fetch('/tcsadmin/api/me');
      if (!response.ok) return;
      const data = await response.json();
      csrfToken = data.csrfToken;
      const previousRole = currentRole;
      currentRole = data.user ? data.user.role : null;
      window.__CURRENT_USER_ROLE__ = currentRole;
      newBtn?.classList.toggle('hidden', !canUploadScripts());
      uploadPanel?.classList.toggle('hidden', !canUploadScripts());
      noAccessNote?.classList.toggle('hidden', canUploadScripts());
      if (table && files.length && previousRole !== currentRole) {
        table.rows().invalidate().draw(false);
      }
    } catch (err) {}
  }

  let pollFilesInterval = null;

  function stopFilesPolling() {
    if (pollFilesInterval) {
      clearInterval(pollFilesInterval);
      pollFilesInterval = null;
    }
  }

  function startFilesPolling(intervalMs = 5000) {
    if (pollFilesInterval) return;
    pollFilesInterval = setInterval(() => {
      if (document.hidden) return;
      loadFiles({ silent: true });
    }, intervalMs);
  }

  const FILES_CACHE_KEY = 'tyresvision_files_cache';

  function loadCachedFiles() {
    try {
      const raw = localStorage.getItem(FILES_CACHE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (data && Array.isArray(data.files) && data.files.length > 0) {
        files = data.files;
        filesById = new Map(files.map((f) => [f.fileId, f]));
        lastFilesSnapshot = JSON.stringify(files);
        table.clear();
        table.rows.add(files);
        table.draw(false);
        showTable();
        updateZipButtonState(data.anyRunning, data.hasAnyOutput);
      }
    } catch (e) {}
  }

  async function loadFiles({ silent } = {}) {
    if (!silent && !files.length) Shared.hideError(errorEl);
    if (refreshBtn && !silent) {
      refreshBtn.disabled = true;
      refreshIcon.classList.add('animate-spin');
    }
    try {
      const response = await fetch('/tcsadmin/api/files?perPage=100');
      if (response.status === 401) {
        window.location.href = '/tcsadmin/login';
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message = data.error || 'Unable to load scrapers.';
        Shared.showError(errorEl, message);
        if (!silent) Shared.showToast(message, 'error');
        return;
      }
      files = data.files || [];
      filesById = new Map(files.map((f) => [f.fileId, f]));
      try {
        localStorage.setItem(FILES_CACHE_KEY, JSON.stringify(data));
      } catch (e) {}

      // Sync working states with browser IndexedDB
      if (window.IDBStorage) {
        try {
          const idbStates = await window.IDBStorage.getAllWorkingStates();
          for (const f of files) {
            const idbEntry = idbStates.get(f.fileId);
            if (f.working) {
              window.IDBStorage.setWorkingState(f.fileId, true, { siteName: f.siteName });
            } else if (idbEntry && idbEntry.working && !f.working) {
              window.IDBStorage.setWorkingState(f.fileId, false, { siteName: f.siteName });
            }
          }
        } catch (e) {}
      }

      updateZipButtonState(data.anyRunning, data.hasAnyOutput);

      // Only poll when a scraper is actively running
      if (data.anyRunning) {
        startFilesPolling(5000);
      } else {
        stopFilesPolling();
      }

      const snapshot = JSON.stringify(files);
      if (snapshot !== lastFilesSnapshot) {
        lastFilesSnapshot = snapshot;
        table.clear();
        table.rows.add(files);
        table.draw(false);
      }
    } catch (err) {
      Shared.showError(errorEl, 'Network error while loading scrapers.');
      if (!silent) Shared.showToast('Network error while loading scrapers.', 'error');
    } finally {
      showTable();
      if (refreshBtn) {
        refreshBtn.disabled = false;
        refreshIcon.classList.remove('animate-spin');
      }
    }
  }

  // --- Create/Edit modal ---
  function resetForm() {
    form.reset();
    idInput.value = '';
    Shared.hideError(modalError);
    uploadedFileName = null;
    currentFileNote.classList.add('hidden');
    if (uploadInput) uploadInput.value = '';
    if (uploadStatus) {
      uploadStatus.textContent = 'Uploads a .py file into the scrapers/ folder. Re-uploading the same file name updates that scraper’s code in place.';
      uploadStatus.className = 'text-[11px] text-slate-400';
    }
    if (urlsCsvInput) urlsCsvInput.value = '';
    if (urlsStatus) {
      urlsStatus.textContent = URLS_STATUS_DEFAULT;
      urlsStatus.className = '';
    }
  }

  function openCreateModal() {
    resetForm();
    modalTitle.textContent = 'Add New Scraper';
    submitLabel.textContent = 'Add Scraper';
    Shared.openModal(modal);
  }

  function openEditModal(file) {
    resetForm();
    modalTitle.textContent = 'Edit Scraper';
    submitLabel.textContent = 'Save Changes';
    idInput.value = file.fileId;
    siteNameInput.value = file.siteName;
    logoInput.value = file.logo || '';
    urlsTextarea.value = (file.urls || []).join('\n');
    uploadedFileName = file.pythonFilePath;
    currentFileNameEl.textContent = file.pythonFilePath;
    currentFileNote.classList.remove('hidden');
    Shared.openModal(modal);
  }

  async function handleUrlsCsvUpload(file) {
    if (!file) return;
    urlsCsvInput.disabled = true;
    urlsSpinner.classList.remove('hidden');
    urlsStatus.textContent = 'Uploading… please wait';
    urlsStatus.className = 'text-slate-500';
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await fetch('/tcsadmin/api/files/parse-urls', {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrfToken },
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        urlsStatus.textContent = data.error || 'Unable to process that CSV.';
        urlsStatus.className = 'text-rose-600';
        return;
      }
      urlsTextarea.value = data.urls.join('\n');
      urlsStatus.textContent = `Imported ${data.urls.length} URL(s) from the CSV -- review the list above before saving.`;
      urlsStatus.className = 'text-[#2563FF]';
    } catch (err) {
      urlsStatus.textContent = 'Network error during upload.';
      urlsStatus.className = 'text-rose-600';
    } finally {
      urlsCsvInput.disabled = false;
      urlsSpinner.classList.add('hidden');
    }
  }

  async function handleScriptUpload(file) {
    if (!file) return;
    uploadInput.disabled = true;
    uploadSpinner.classList.remove('hidden');
    uploadStatus.textContent = 'Uploading… please wait';
    uploadStatus.className = 'text-[11px] text-slate-500';
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await fetch('/tcsadmin/api/files/upload-script', {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrfToken },
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        uploadStatus.textContent = data.error || 'Upload failed.';
        uploadStatus.className = 'text-[11px] text-rose-600';
        return;
      }
      uploadedFileName = data.fileName;
      uploadStatus.textContent = `Uploaded: ${data.fileName}`;
      uploadStatus.className = 'text-[11px] text-[#2563FF]';
    } catch (err) {
      uploadStatus.textContent = 'Network error during upload.';
      uploadStatus.className = 'text-[11px] text-rose-600';
    } finally {
      uploadInput.disabled = false;
      uploadSpinner.classList.add('hidden');
    }
  }

  function setSubmitLoading(isLoading, idleLabel) {
    submitBtn.disabled = isLoading;
    submitSpinner.classList.toggle('hidden', !isLoading);
    submitLabel.textContent = isLoading ? 'Processing…' : idleLabel;
  }

  function markFieldError(el) {
    if (!el) return;
    el.classList.add('field-error');
    el.classList.remove('field-shake');
    void el.offsetWidth;
    el.classList.add('field-shake');
  }

  function clearFieldError(el) {
    if (el) el.classList.remove('field-error', 'field-shake');
  }

  [siteNameInput, urlsTextarea].forEach((el) => {
    el?.addEventListener('input', () => clearFieldError(el));
  });
  uploadInput?.addEventListener('change', () => clearFieldError(uploadInput));

  async function handleFormSubmit(event) {
    event.preventDefault();
    Shared.hideError(modalError);
    clearFieldError(siteNameInput);
    clearFieldError(urlsTextarea);
    clearFieldError(uploadInput);

    const id = idInput.value;
    const idleLabel = submitLabel.textContent;

    let hasError = false;
    if (!siteNameInput.value.trim()) {
      markFieldError(siteNameInput);
      hasError = true;
    }
    if (!urlsTextarea.value.trim()) {
      markFieldError(urlsTextarea);
      hasError = true;
    }
    if (!uploadedFileName) {
      markFieldError(uploadInput);
      hasError = true;
    }
    if (hasError) {
      Shared.showError(modalError, 'Please fix the highlighted field(s) below.');
      return;
    }

    const payload = {
      siteName: siteNameInput.value.trim(),
      urlsText: urlsTextarea.value,
      pythonFilePath: uploadedFileName,
      logo: logoInput.value.trim(),
    };

    setSubmitLoading(true, idleLabel);
    try {
      const response = await fetch(id ? `/tcsadmin/api/files/${id}` : '/tcsadmin/api/files', {
        method: id ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message = data.error || 'Unable to save scraper.';
        Shared.showError(modalError, message);
        Shared.showToast(message, 'error');
        const lower = message.toLowerCase();
        if (lower.includes('url')) markFieldError(urlsTextarea);
        else if (lower.includes('site name')) markFieldError(siteNameInput);
        else if (lower.includes('python') || lower.includes('file')) markFieldError(uploadInput);
        return;
      }
      Shared.closeModal(modal);
      Shared.showToast(id ? 'Scraper updated successfully.' : 'Scraper registered successfully.', 'success');
      await loadFiles();
    } catch (err) {
      Shared.logError('Save Scraper Form', err, { id, payload });
      Shared.showError(modalError, 'Network error. Please try again.');
      Shared.showToast('Network error. Please try again.', 'error');
    } finally {
      setSubmitLoading(false, idleLabel);
    }
  }

  async function handleDeleteConfirm() {
    if (!pendingDeleteId) return;
    Shared.hideError(deleteError);
    deleteConfirmBtn.disabled = true;
    try {
      const response = await fetch(`/tcsadmin/api/files/${pendingDeleteId}`, {
        method: 'DELETE',
        headers: { 'X-CSRF-Token': csrfToken },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message = data.error || 'Unable to delete scraper.';
        Shared.logError('Delete Scraper', message, { fileId: pendingDeleteId, status: response.status });
        Shared.showError(deleteError, message);
        Shared.showToast(message, 'error');
        return;
      }
      if (window.IDBStorage) {
        await window.IDBStorage.clearWorkingState(pendingDeleteId);
      }
      Shared.closeModal(deleteModal);
      pendingDeleteId = null;
      Shared.showToast(data.message || 'Scraper and its Python file were deleted.', 'success');
      await loadFiles();
    } catch (err) {
      Shared.logError('Delete Scraper Network Error', err, { fileId: pendingDeleteId });
      Shared.showError(deleteError, 'Network error. Please try again.');
      Shared.showToast('Network error. Please try again.', 'error');
    } finally {
      deleteConfirmBtn.disabled = false;
    }
  }

  async function toggleFileStatus(fileId, enable) {
    const file = filesById.get(fileId);
    if (file && file.working) {
      Shared.showToast('Stop this scraper before disabling it.', 'warning');
      table.draw(false);
      return;
    }
    inFlightToggles.add(fileId);
    if (file) {
      file.isEnabled = enable;
      file.isDeleted = !enable;
    }
    table.draw(false);

    if (!csrfToken) {
      await loadMe();
    }
    try {
      const response = await fetch(`/tcsadmin/api/files/${fileId}/toggle-status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken || '' },
        body: JSON.stringify({ enabled: enable }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.success) {
        const err = data.error || 'Unable to update status.';
        Shared.logError('Toggle Scraper Status', err, { fileId, enable, status: response.status });
        Shared.showToast(err, 'error');
        if (file) {
          file.isEnabled = !enable;
          file.isDeleted = enable;
        }
        return;
      }
      Shared.showToast(data.message || (enable ? 'Scraper enabled.' : 'Scraper disabled.'), 'success');
      await loadFiles({ silent: true });
    } catch (err) {
      Shared.logError('Toggle Scraper Status Network Error', err, { fileId, enable });
      Shared.showToast('Network error while updating status.', 'error');
      if (file) {
        file.isEnabled = !enable;
        file.isDeleted = enable;
      }
    } finally {
      inFlightToggles.delete(fileId);
      table.draw(false);
    }
  }

  // --- Log Drawer Modal (Bottom-to-Top Animation) ---
  const logModal = document.getElementById('files-log-modal');
  const logBackdrop = document.getElementById('files-log-backdrop');
  const logDrawer = document.getElementById('files-log-drawer');
  const logCloseBtn = document.getElementById('files-log-close');
  const logTitle = document.getElementById('files-log-title');
  const logSubtitle = document.getElementById('files-log-subtitle');
  const logLoading = document.getElementById('files-log-loading');
  const logList = document.getElementById('files-log-list');
  const logEmpty = document.getElementById('files-log-empty');

  function loadCachedScraperLogs(fileId) {
    try {
      const raw = localStorage.getItem(`tyresvision_scraper_logs_${fileId}`);
      if (!raw) return false;
      const data = JSON.parse(raw);
      const logs = (data && data.logs) || [];
      if (logs.length > 0) {
        currentDrawerLogs = new Map(logs.map((l) => [l.id, l]));
        if (logLoading) logLoading.classList.add('hidden');
        if (logList) {
          logList.classList.remove('hidden');
          logList.innerHTML = logs.map(renderLogCardHtml).join('');
        }
        return true;
      }
    } catch (e) {}
    return false;
  }

  function openLogDrawer(file) {
    if (!logModal || !logDrawer || !logBackdrop) return;
    if (logTitle) logTitle.textContent = `Scraper Logs — ${file?.siteName || 'Scraper'}`;
    if (logSubtitle) logSubtitle.textContent = `Execution history for ${file?.siteName || 'this scraper'}`;

    const hasCache = loadCachedScraperLogs(file.fileId);
    if (!hasCache) {
      if (logLoading) logLoading.classList.remove('hidden');
      if (logList) {
        logList.classList.add('hidden');
        logList.innerHTML = '';
      }
      if (logEmpty) logEmpty.classList.add('hidden');
    }

    logModal.classList.remove('hidden');
    void logDrawer.offsetHeight;

    requestAnimationFrame(() => {
      logBackdrop.classList.remove('opacity-0');
      logBackdrop.classList.add('opacity-100');
      logDrawer.classList.remove('translate-y-full');
      logDrawer.classList.add('translate-y-0');
    });

    fetchScraperLogs(file.fileId);
  }

  function closeLogDrawer() {
    if (!logModal || !logDrawer || !logBackdrop) return;
    logDrawer.classList.remove('translate-y-0');
    logDrawer.classList.add('translate-y-full');
    logBackdrop.classList.remove('opacity-100');
    logBackdrop.classList.add('opacity-0');

    setTimeout(() => {
      logModal.classList.add('hidden');
    }, 300);
  }

  let currentDrawerLogs = new Map();

  async function fetchScraperLogs(fileId) {
    try {
      const response = await fetch(`/tcsadmin/api/files/${fileId}/logs`);
      const data = await response.json().catch(() => ({}));
      if (logLoading) logLoading.classList.add('hidden');

      const logs = (data && data.logs) || [];
      currentDrawerLogs = new Map(logs.map((l) => [l.id, l]));
      try {
        localStorage.setItem(`tyresvision_scraper_logs_${fileId}`, JSON.stringify(data));
      } catch (e) {}

      if (!logs.length) {
        if (logEmpty) {
          logEmpty.textContent = 'No logs recorded for this scraper yet.';
          logEmpty.classList.remove('hidden');
        }
        if (logList) logList.classList.add('hidden');
        return;
      }

      // Sort logs so that RUNNING sessions and newest/latest runs are always at the top
      logs.sort((a, b) => {
        const aRunning = (a.status || '').toUpperCase() === 'RUNNING';
        const bRunning = (b.status || '').toUpperCase() === 'RUNNING';
        if (aRunning && !bRunning) return -1;
        if (!aRunning && bRunning) return 1;
        return (Number(b.id) || 0) - (Number(a.id) || 0);
      });

      if (logList) {
        logList.classList.remove('hidden');
        logList.innerHTML = logs.map(renderLogCardHtml).join('');
      }
    } catch (err) {
      Shared.logError('Fetch Scraper Logs', err, { fileId });
      if (logLoading) logLoading.classList.add('hidden');
      if (logEmpty && !currentDrawerLogs.size) {
        logEmpty.textContent = 'Failed to load logs. Please try again.';
        logEmpty.classList.remove('hidden');
      }
    }
  }

  function renderLogCardHtml(log) {
    const st = (log.status || '').toUpperCase();
    let badgeClass = 'bg-slate-100 text-slate-700 border-slate-200';
    let statusLabel = st;
    if (st === 'RUNNING') {
      badgeClass = 'bg-blue-100 text-blue-700 border-blue-200';
      statusLabel = '<span class="w-1.5 h-1.5 rounded-full bg-[#2563FF] animate-pulse"></span>RUNNING';
    } else if (st === 'SUCCESS' || st === 'FINISHED') {
      badgeClass = 'bg-sky-100 text-sky-700 border-sky-200';
      statusLabel = 'SUCCESS';
    } else if (st === 'STOPPED' || st === 'STOP') {
      badgeClass = 'bg-amber-100 text-amber-800 border-amber-200';
      statusLabel = 'STOPPED';
    } else {
      badgeClass = 'bg-rose-100 text-rose-700 border-rose-200';
      statusLabel = 'FAIL';
    }

    const startTime = log.startTime || '—';
    const duration = log.duration || '—';
    const itemsScraped = (log.dataScraped || 0).toLocaleString();
    const errorMsg = log.errorMessage;
    const userName = log.userName || 'Admin';
    const userId = log.userId;

    let actionSection = '';
    if (st === 'FAIL') {
      actionSection = `
        <button type="button" data-action="view-error-detail" data-log-id="${log.id}" class="mt-2.5 w-full flex items-center justify-between gap-2 text-xs rounded-xl bg-rose-50 border border-rose-200/80 text-rose-900 px-3.5 py-2.5 font-medium hover:bg-rose-100/90 hover:border-rose-300 transition cursor-pointer text-left group">
          <div class="flex items-center gap-2 min-w-0">
            <svg class="w-4 h-4 text-rose-500 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span class="truncate"><strong>Failed:</strong> ${Shared.escapeHtml(errorMsg || 'Click to view why this scraper failed')}</span>
          </div>
          <span class="inline-flex items-center text-[11px] font-bold text-rose-700 underline shrink-0 group-hover:text-rose-900">View Reason →</span>
        </button>
      `;
    } else if (errorMsg && (st === 'STOPPED' || st === 'STOP')) {
      actionSection = `
        <div class="mt-2.5 text-xs rounded-xl bg-amber-50/80 border border-amber-200/70 text-amber-800 px-3 py-2 font-medium flex items-center gap-2">
          <svg class="w-3.5 h-3.5 text-amber-600 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
          <span>${Shared.escapeHtml(errorMsg)}</span>
        </div>
      `;
    } else if (errorMsg) {
      actionSection = `
        <div class="mt-2.5 text-xs rounded-xl bg-slate-100 border border-slate-200 text-slate-700 px-3 py-2 font-medium">
          ${Shared.escapeHtml(errorMsg)}
        </div>
      `;
    }

    return `
      <div class="bg-slate-50 border border-slate-200/80 rounded-2xl p-4 transition-all hover:border-slate-300 hover:shadow-xs">
        <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
          <div class="flex items-center gap-2">
            <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold border ${badgeClass}">
              ${statusLabel}
            </span>
            <span class="font-mono text-xs text-slate-500 font-semibold">#${log.id}</span>
          </div>
          <div class="flex items-center gap-3 text-xs text-slate-500">
            <span>By: <strong class="text-slate-700">${Shared.escapeHtml(userName)}</strong>${userId ? ` <span class="inline-flex items-center rounded bg-slate-200/70 px-1 py-0.2 text-[9px] font-mono text-slate-600">#${userId}</span>` : ''}</span>
            <span>Started: <strong class="text-slate-700">${Shared.escapeHtml(startTime)}</strong></span>
            <span>Duration: <strong class="text-slate-700">${Shared.escapeHtml(duration)}</strong></span>
          </div>
        </div>

        <div class="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div class="flex items-center gap-2 text-slate-600">
            <span class="font-semibold text-slate-900">${itemsScraped}</span> items / products scraped
          </div>
          ${log.status === 'RUNNING' && log.fileId ? `<a href="/tcsadmin/scraperpage?fileId=${log.fileId}" class="font-semibold text-indigo-600 hover:underline">View Live Progress →</a>` : ''}
        </div>

        ${actionSection}
      </div>
    `;
  }

  // --- Log Detail / Failure Modal Management ---
  const logDetailModal = document.getElementById('log-detail-modal');
  const logDetailTitle = document.getElementById('log-detail-title');
  const logDetailSubtitle = document.getElementById('log-detail-subtitle');
  const logDetailStatusPill = document.getElementById('log-detail-status-pill');
  const logDetailUser = document.getElementById('log-detail-user');
  const logDetailDuration = document.getElementById('log-detail-duration');
  const logDetailUrlsFound = document.getElementById('log-detail-urls-found');
  const logDetailUrlsSuccess = document.getElementById('log-detail-urls-success');
  const logDetailUrlsBlocked = document.getElementById('log-detail-urls-blocked');
  const logDetailReasonText = document.getElementById('log-detail-reason-text');
  const logDetailExplanation = document.getElementById('log-detail-explanation');
  const logDetailRawError = document.getElementById('log-detail-raw-error');
  const logDetailCopyBtn = document.getElementById('log-detail-copy-btn');

  function openLogDetailModal(log) {
    if (!logDetailModal || !log) return;

    if (logDetailTitle) logDetailTitle.textContent = `${log.siteName || log.scraper || 'Scraper'} — Failure Report`;
    if (logDetailSubtitle) logDetailSubtitle.textContent = `Log Run #${log.id} • Started: ${log.startTime || '—'}`;

    if (logDetailStatusPill) {
      logDetailStatusPill.textContent = log.status || 'FAIL';
      logDetailStatusPill.className = 'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-700';
    }

    if (logDetailUser) logDetailUser.textContent = `${log.userName || 'Admin'} #${log.userId || '—'}`;
    if (logDetailDuration) logDetailDuration.textContent = log.duration || '—';

    if (logDetailUrlsFound) logDetailUrlsFound.textContent = (log.noOfUrlFound || 0).toLocaleString();
    if (logDetailUrlsSuccess) logDetailUrlsSuccess.textContent = (log.totalSuccessUrl || 0).toLocaleString();
    if (logDetailUrlsBlocked) logDetailUrlsBlocked.textContent = (log.totalBlockUrl || 0).toLocaleString();

    const rawError = log.errorMessage || 'No detailed error message recorded.';
    if (logDetailRawError) logDetailRawError.textContent = rawError;

    if (logDetailReasonText) {
      logDetailReasonText.textContent = rawError;
    }

    if (logDetailExplanation) {
      const errLower = rawError.toLowerCase();
      if (errLower.includes('blocked') || (log.totalBlockUrl > 0 && log.totalSuccessUrl === 0)) {
        logDetailExplanation.textContent = 'The target website anti-bot protection (Cloudflare / WAF / HTTP 403) blocked automated scraper requests before product data could be extracted.';
      } else if (errLower.includes('6 hours') || errLower.includes('timeout')) {
        logDetailExplanation.textContent = 'The crawler was terminated because it exceeded the maximum safety execution limit of 6 hours.';
      } else if (errLower.includes('server restarted')) {
        logDetailExplanation.textContent = 'The crawler process was interrupted because the application web server was restarted.';
      } else if (errLower.includes('return code') || errLower.includes('exit code')) {
        logDetailExplanation.textContent = 'The Python scraper process encountered an unhandled exception or terminated with a non-zero exit code.';
      } else {
        logDetailExplanation.textContent = 'The crawler encountered an unhandled exception during execution and could not complete data extraction.';
      }
    }

    if (logDetailCopyBtn) {
      logDetailCopyBtn.textContent = 'Copy Error';
      logDetailCopyBtn.onclick = () => {
        navigator.clipboard.writeText(rawError).then(() => {
          logDetailCopyBtn.textContent = 'Copied!';
          setTimeout(() => { logDetailCopyBtn.textContent = 'Copy Error'; }, 1500);
        });
      };
    }

    Shared.openModal(logDetailModal);
  }

  function closeLogDetailModal() {
    if (logDetailModal) Shared.closeModal(logDetailModal);
  }

  document.querySelectorAll('[data-close-log-detail]').forEach((btn) => {
    btn.addEventListener('click', closeLogDetailModal);
  });

  // --- Start / Stop ---
  async function startFile(fileId) {
    const file = filesById.get(fileId);
    if (file && file.working) {
      Shared.showToast('This scraper is currently being used by another user.', 'warning');
      return;
    }
    Shared.showToast(`Starting scraper "${file?.siteName || 'Scraper'}"… please wait`, 'info');
    inFlightStarts.set(fileId, 'start');
    table.draw(false);
    let started = false;
    try {
      if (!csrfToken) {
        await loadMe();
      }
      const response = await fetch(`/tcsadmin/api/files/${fileId}/start`, {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrfToken },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.success) {
        const errMsg = data.message || data.error || (response.status === 409 ? 'This scraper is currently being used by another user.' : 'Unable to start scraper.');
        Shared.logError('Start Scraper', errMsg, { fileId, status: response.status });
        Shared.showToast(errMsg, 'warning');
        return;
      }
      started = true;
      if (window.IDBStorage) {
        await window.IDBStorage.setWorkingState(fileId, true, { siteName: file?.siteName });
      }
      Shared.showToast('Scraper started successfully. Redirecting…', 'success');
    } catch (err) {
      Shared.logError('Start Scraper Network Error', err, { fileId });
      Shared.showToast('Network error while starting the scraper.', 'error');
    } finally {
      inFlightStarts.delete(fileId);
      table.draw(false);
      if (started) {
        window.location.href = `/tcsadmin/scraperpage?fileId=${fileId}`;
      } else {
        await loadFiles({ silent: true });
      }
    }
  }

  async function stopFile(fileId) {
    Shared.showToast('Stopping scraper…', 'warning');
    inFlightStarts.set(fileId, 'stop');
    table.draw(false);
    try {
      const response = await fetch(`/tcsadmin/api/files/${fileId}/stop`, {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrfToken },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.success) {
        const errMsg = (data && data.message) || 'Unable to stop scraper.';
        Shared.logError('Stop Scraper', errMsg, { fileId, status: response.status });
        Shared.showToast(errMsg, 'error');
        return;
      }
      if (window.IDBStorage) {
        await window.IDBStorage.setWorkingState(fileId, false);
      }
      Shared.showToast('Scraper stopped.', 'success');
    } catch (err) {
      Shared.logError('Stop Scraper Network Error', err, { fileId });
      Shared.showToast('Network error while stopping the scraper.', 'error');
    } finally {
      inFlightStarts.delete(fileId);
      table.draw(false);
      await loadFiles({ silent: true });
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    initTable();

    newBtn?.addEventListener('click', openCreateModal);
    refreshBtn?.addEventListener('click', () => loadFiles());
    form?.addEventListener('submit', handleFormSubmit);
    deleteConfirmBtn?.addEventListener('click', handleDeleteConfirm);

    uploadInput?.addEventListener('change', () => handleScriptUpload(uploadInput.files[0]));
    urlsCsvInput?.addEventListener('change', () => handleUrlsCsvUpload(urlsCsvInput.files[0]));

    // Log drawer close events
    logCloseBtn?.addEventListener('click', closeLogDrawer);
    logBackdrop?.addEventListener('click', closeLogDrawer);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && logModal && !logModal.classList.contains('pointer-events-none')) {
        closeLogDrawer();
      }
    });

    $(tableEl).on('change', 'input[data-action="toggle-status"]', function () {
      const id = Number(this.getAttribute('data-id'));
      const isChecked = this.checked;
      toggleFileStatus(id, isChecked);
    });

    $(tableEl.tBodies[0]).on('click', 'button[data-action]', function () {
      const btn = this;
      if (btn.disabled) return;
      const action = btn.getAttribute('data-action');
      const id = Number(btn.getAttribute('data-id'));
      const file = filesById.get(id);
      if (!file) return;

      if (action === 'start') { startFile(id); return; }
      if (action === 'stop') { stopFile(id); return; }
      if (action === 'edit') { openEditModal(file); return; }
      if (action === 'view-logs') { openLogDrawer(file); return; }

      if (action === 'delete') {
        pendingDeleteId = id;
        if (deleteTitle) deleteTitle.textContent = 'Delete Scraper?';
        deleteText.textContent = `This permanently deletes "${file.siteName}" and removes its file (${file.pythonFilePath}) from the server.`;
        deleteConfirmBtn.textContent = 'Delete';
        deleteConfirmBtn.className = 'flex-1 rounded-xl bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-rose-700 cursor-pointer';
        Shared.hideError(deleteError);
        Shared.openModal(deleteModal);
        return;
      }
    });

    document.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-action="view-error-detail"]');
      if (!btn) return;
      const logId = Number(btn.getAttribute('data-log-id'));
      const log = currentDrawerLogs.get(logId);
      if (log) {
        openLogDetailModal(log);
      }
    });

    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) {
        loadFiles({ silent: true });
      }
    });

    loadCachedFiles();
    loadMe().then(() => loadFiles({ silent: Boolean(files.length) }));
  });
})();
