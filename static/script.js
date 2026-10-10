// ==============================================================================
// Scraper Live Progress Controller (with SSE Webhook Stream & User-Ownership)
// ==============================================================================

(function () {
  const urlStatusList = document.getElementById('url-status-list');
  const scraperBlockedScreen = document.getElementById('scraper-blocked-screen');
  const scraperMainContent = document.getElementById('scraper-main-content');

  // Only run this script if on the scraper live progress page
  if (!urlStatusList && !scraperBlockedScreen) {
    return;
  }

  const startButton = document.getElementById('start-scraper');
  const stopButton = document.getElementById('stop-scraper');
  const downloadButton = document.getElementById('download-report');
  const statusElement = document.getElementById('scraper-status');
  const statusDot = document.getElementById('status-dot');
  const progressBar = document.getElementById('progress-bar');
  const progressPercentage = document.getElementById('progress-percentage');
  const progressCaption = document.getElementById('progress-caption');
  const fileScraperSwitcher = document.getElementById('file-scraper-switcher');
  const fileScraperNameEl = document.getElementById('file-scraper-name');
  const headerTitleEl = document.getElementById('scraper-header-title');
  const headerSubtitleEl = document.getElementById('scraper-header-subtitle');
  const headerEdgeEl = document.getElementById('header-edge');
  const headerTelemetryEl = document.getElementById('header-telemetry');
  const completionSummaryEl = document.getElementById('completion-summary');

  // Stat cards
  const statTotalUrls = document.getElementById('stat-total-urls');
  const statCompleted = document.getElementById('stat-completed');
  const statCompletedPct = document.getElementById('stat-completed-pct');
  const statRunning = document.getElementById('stat-running');
  const statRunningLabel = document.getElementById('stat-running-label');
  const statPending = document.getElementById('stat-pending');
  const statBlocked = document.getElementById('stat-blocked');
  const statProducts = document.getElementById('stat-products');

  // Stop confirmation modal
  const stopConfirmModal = document.getElementById('stop-confirm-modal');
  const stopConfirmProceed = document.getElementById('stop-confirm-proceed');

  // Extract fileId from query parameters or resolve dynamically
  let fileScraperId = new URLSearchParams(window.location.search).get('fileId');

  let currentJobId = null;
  let isCurrentRunning = false;
  let statusIntervalId = null;
  let activeEventSource = null;
  let fileScraperCsrfToken = null;
  const collapsedRoots = new Set();
  const expandedRoots = new Set();

  const isRootExpanded = (rootUrl, childCount) => {
    if (expandedRoots.has(rootUrl)) return true;
    if (collapsedRoots.has(rootUrl)) return false;
    // Default: auto-expand small lists (<= 10 items); keep large lists (> 10 items) collapsed initially
    return childCount > 0 && childCount <= 10;
  };

  let lastKnownStatuses = [];

  const resolveFileScraperId = async () => {
    if (fileScraperId) return fileScraperId;
    try {
      const res = await fetch('/tcsadmin/api/files?perPage=1');
      if (res.ok) {
        const data = await res.json();
        if (data.files && data.files.length > 0) {
          fileScraperId = String(data.files[0].fileId);
          try {
            const newUrl = new URL(window.location.href);
            newUrl.searchParams.set('fileId', fileScraperId);
            window.history.replaceState({}, '', newUrl);
          } catch (e) {}
          loadStateFromLocalStorage();
          return fileScraperId;
        }
      }
    } catch (e) {}
    return null;
  };

  const closeEventSource = () => {
    if (activeEventSource) {
      activeEventSource.close();
      activeEventSource = null;
    }
  };

  const stopStatusPolling = () => {
    if (statusIntervalId !== null) {
      clearInterval(statusIntervalId);
      statusIntervalId = null;
    }
  };

  const startStatusPolling = () => {
    if (statusIntervalId === null && !activeEventSource) {
      statusIntervalId = setInterval(refreshProgress, 3500);
    }
  };

  const setStatus = (text, toneClass, dotClass) => {
    if (statusElement) {
      statusElement.textContent = text;
      statusElement.className = `status-text ${toneClass}`;
    }
    if (statusDot) {
      statusDot.className = `status-dot ${dotClass || 'is-static'}`;
    }
    if (headerEdgeEl) {
      headerEdgeEl.className = `header-edge ${toneClass}`;
    }
  };

  // Live telemetry readout under the header subtitle: site / job id /
  // processed count -- only ever real fields already on hand, never
  // fabricated, and hidden entirely once there's nothing meaningful to show.
  const renderHeaderTelemetry = (statusRes, stats) => {
    if (!headerTelemetryEl) return;
    const segments = [];
    const site = statusRes.site_name || statusRes.siteName;
    if (site) segments.push({ text: site, cls: '' });
    if (currentJobId) segments.push({ text: `job ${String(currentJobId).slice(0, 8)}`, cls: 'seg-accent' });
    if (stats && stats.totalUrls > 0) {
      segments.push({
        text: `${stats.completed.toLocaleString()}/${stats.totalUrls.toLocaleString()} processed`,
        cls: isCurrentRunning ? 'seg-live' : '',
      });
    }

    headerTelemetryEl.textContent = '';
    if (!segments.length) {
      headerTelemetryEl.classList.add('hidden');
      return;
    }
    headerTelemetryEl.classList.remove('hidden');
    segments.forEach((seg, i) => {
      if (i > 0) {
        const sep = document.createElement('span');
        sep.textContent = ' · ';
        sep.style.opacity = '0.5';
        headerTelemetryEl.appendChild(sep);
      }
      const span = document.createElement('span');
      if (seg.cls) span.className = seg.cls;
      span.textContent = seg.text;
      headerTelemetryEl.appendChild(span);
    });
  };

  const showBlockedScreen = () => {
    closeEventSource();
    if (scraperBlockedScreen) scraperBlockedScreen.classList.remove('hidden');
    if (scraperMainContent) scraperMainContent.classList.add('hidden');
  };

  const showMainProgress = () => {
    if (scraperBlockedScreen) scraperBlockedScreen.classList.add('hidden');
    if (scraperMainContent) scraperMainContent.classList.remove('hidden');
  };

  const updateControls = (state) => {
    const isRunning = state.status === 'RUNNING' || state.running === true;
    if (startButton) {
      startButton.disabled = isRunning;
      startButton.style.display = isRunning ? 'none' : 'inline-flex';
    }
    if (stopButton) {
      stopButton.disabled = !isRunning;
      stopButton.style.display = isRunning ? 'inline-flex' : 'none';
    }
    if (downloadButton) {
      const downloadUrl = fileScraperId ? `/tcsadmin/api/files/${fileScraperId}/download` : '/tcsadmin/download-output';
      if (state.output_available || state.outputAvailable) {
        downloadButton.href = downloadUrl;
        downloadButton.style.display = 'inline-flex';
      } else {
        downloadButton.href = '#';
        downloadButton.style.display = 'none';
      }
    }
  };

  // ==============================================================================
  // Dashboard stats: total/completed/running/pending/blocked/products, progress %
  // -- derived only from real fields already present in the status response;
  // "completed" has no direct field, so it's the remainder after
  // pending/running/blocked, which always reconciles against total_urls.
  // ==============================================================================
  // Some status sources (the older per-file endpoint used when a job has no
  // job_id) don't populate total_urls/pending/running_count/blocked at all,
  // while the per-URL list (lastKnownStatuses) is always real and current --
  // it's what actually drives the URL Queue rows. When the summary comes
  // back empty, derive the same numbers from that real per-URL data instead
  // of showing false zeros.
  const deriveStatsFromStatuses = (statuses) => {
    let pending = 0, running = 0, done = 0, blocked = 0, products = 0;
    statuses.forEach((item) => {
      if (item.type === 'product') products += 1;
      const s = (item.status || 'pending').toLowerCase();
      if (s === 'running') running += 1;
      else if (s === 'done' || s === 'success') done += 1;
      else if (s === 'blocked' || s === 'failed') blocked += 1;
      else pending += 1;
    });
    return { totalUrls: statuses.length, totalProducts: products, pending, running, blocked, completed: done };
  };

  const computeStats = (state) => {
    let totalUrls = state.total_urls || 0;
    let totalProducts = state.total_product_urls || state.total_products || 0;
    let pending = state.pending || 0;
    let running = state.running_count !== undefined ? state.running_count : (state.running ? 1 : 0);
    let blocked = state.blocked || 0;
    const writtenToXlsx = state.written_to_xlsx || 0;
    const mainUrlDone = state.main_url_done || 0;
    const productUrlDone = state.product_url_done || 0;
    let completed = Math.max(0, totalUrls - pending - running - blocked);

    if (totalUrls === 0 && lastKnownStatuses.length > 0) {
      const derived = deriveStatsFromStatuses(lastKnownStatuses);
      totalUrls = derived.totalUrls;
      totalProducts = totalProducts || derived.totalProducts;
      pending = derived.pending;
      running = derived.running;
      blocked = derived.blocked;
      completed = derived.completed;
    }

    const st = (state.status || '').toUpperCase();
    let pct = Math.min(100, Math.max(0, state.progress_percent || 0));
    if (!state.progress_percent && totalUrls > 0) pct = Math.round((completed / totalUrls) * 100);
    if (st === 'SUCCESS') pct = 100;

    return { totalUrls, totalProducts, pending, running, blocked, writtenToXlsx, mainUrlDone, productUrlDone, completed, pct };
  };

  const setNumber = (el, value) => {
    if (!el) return;
    const formatted = Number(value || 0).toLocaleString();
    if (el.textContent !== formatted) {
      el.textContent = formatted;
      el.classList.remove('num-flash');
      void el.offsetWidth;
      el.classList.add('num-flash');
    }
  };

  const renderDashboard = (state) => {
    const s = computeStats(state);

    setNumber(statTotalUrls, s.totalUrls);
    setNumber(statCompleted, s.completed);
    setNumber(statRunning, s.running);
    setNumber(statPending, s.pending);
    setNumber(statBlocked, s.blocked);
    setNumber(statProducts, s.totalProducts);

    if (statCompletedPct) {
      const pct = s.totalUrls > 0 ? Math.round((s.completed / s.totalUrls) * 100) : 0;
      statCompletedPct.textContent = `${pct}%`;
    }
    if (statRunningLabel) statRunningLabel.classList.toggle('hidden', !isCurrentRunning || s.running === 0);

    if (progressBar) progressBar.style.width = `${s.pct}%`;
    if (progressPercentage) progressPercentage.textContent = `${s.pct}%`;
    if (progressCaption) {
      progressCaption.textContent = `${s.completed.toLocaleString()} completed · ${s.running.toLocaleString()} running · ${s.pending.toLocaleString()} pending · ${s.blocked.toLocaleString()} blocked`;
    }

    return s;
  };

  const getStatusIcon = (status) => {
    const st = (status || '').toLowerCase();
    switch (st) {
      case 'running':
        return `
          <svg class="icon-running" viewBox="0 0 50 50" width="22" height="22" aria-hidden="true">
            <circle cx="25" cy="25" r="20" fill="none" stroke="#2563EB" stroke-width="4" stroke-linecap="round" stroke-dasharray="31.4 62.8" transform="rotate(-90 25 25)"></circle>
            <circle cx="25" cy="25" r="20" fill="none" stroke="#BFDBFE" stroke-width="4" stroke-linecap="round" stroke-dasharray="1 62.8" transform="rotate(-90 25 25)">
              <animateTransform attributeName="transform" type="rotate" values="0 25 25;360 25 25" dur="1s" repeatCount="indefinite" />
            </circle>
          </svg>
        `;
      case 'done':
      case 'success':
        return `
          <svg class="icon-done" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <circle cx="12" cy="12" r="10" fill="#10B981" opacity="0.16" />
            <path d="M7 13.5l3 3 7-7" fill="none" stroke="#10B981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <animate attributeName="stroke-dasharray" from="0 20" to="20 0" dur="0.4s" fill="ze" />
            </path>
          </svg>
        `;
      case 'blocked':
      case 'failed':
        return `
          <svg class="icon-blocked" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <circle cx="12" cy="12" r="10" fill="#EF4444" opacity="0.16" />
            <path d="M9 9l6 6M15 9l-6 6" fill="none" stroke="#EF4444" stroke-width="2.5" stroke-linecap="round">
              <animate attributeName="opacity" values="0;1;1" dur="0.4s" fill="ze" />
            </path>
          </svg>
        `;
      default:
        return `
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <circle cx="12" cy="12" r="9" fill="none" stroke="#9CA3AF" stroke-width="2" />
          </svg>
        `;
    }
  };

  const copyButton = (url, size = 'p-2') => `
    <button class="btncopy flex items-center justify-center rounded-xl ${size} transition cursor-pointer" type="button" data-url="${url}" title="Copy URL" aria-label="Copy URL">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M8 8V5C8 3.89543 8.89543 3 10 3H19C20.1046 3 21 3.89543 21 5V14C21 15.1046 20.1046 16 19 16H16"/> <rect x="3" y="8" width="13" height="13" rx="2"/>
      </svg>
    </button>
  `;

  const chevronIcon = (expanded) => `
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="transition-transform duration-200 ${expanded ? 'rotate-90' : ''}">
      <polyline points="9 6 15 12 9 18"></polyline>
    </svg>
  `;

  const typeTag = (type) => {
    if (type === 'listing') {
      return '<span class="tag-pagination inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold">Pagination</span>';
    }
    if (type === 'product') {
      return '<span class="tag-product inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold">Product</span>';
    }
    return '';
  };

  const buildUrlTree = (statuses) => {
    const roots = new Map();
    const children = [];

    statuses.forEach((item) => {
      const isRoot = !item.parent || item.parent === item.url;
      if (isRoot) {
        roots.set(item.url, { ...item, children: [] });
      } else {
        children.push(item);
      }
    });

    const orphans = [];
    children.forEach((item) => {
      const root = roots.get(item.parent);
      if (root) {
        root.children.push(item);
      } else {
        orphans.push(item);
      }
    });

    return [...roots.values(), ...orphans.map((item) => ({ ...item, children: [] }))];
  };

  // Single source of truth for a root's *displayed* status -- used by both
  // rendering and the status filter, so "Completed" in the filter always
  // matches what the queue itself shows as done.
  const effectiveRootStatus = (root) => {
    let status = (root.status || 'pending').toLowerCase();
    const hasChildren = root.children && root.children.length > 0;
    const doneCount = hasChildren ? root.children.filter((c) => (c.status || '').toLowerCase() === 'done').length : 0;

    if (isCurrentRunning) {
      if (hasChildren) {
        const allChildrenFinished = root.children.every((c) => {
          const s = (c.status || '').toLowerCase();
          return s === 'done' || s === 'blocked';
        });
        if (!allChildrenFinished || status === 'running') {
          status = 'running';
        } else if (allChildrenFinished) {
          status = 'done';
        }
      }
    } else {
      if (status === 'running') {
        status = (doneCount > 0 || (root.status || '').toLowerCase() === 'done') ? 'done' : 'pending';
      } else if (hasChildren) {
        const allChildrenFinished = root.children.every((c) => {
          const s = (c.status || '').toLowerCase();
          return s === 'done' || s === 'blocked';
        });
        if (allChildrenFinished || (root.status || '').toLowerCase() === 'done' || doneCount > 0) {
          status = 'done';
        }
      }
    }
    return status;
  };

  const renderChildRow = (item) => {
    let status = (item.status || 'pending').toLowerCase();
    if (!isCurrentRunning && status === 'running') {
      status = 'pending';
    }
    const isXlsx = !!item.written_to_xlsx;
    return `
      <li class="child-url-item flex items-start gap-3 px-3.5 py-2.5 transition-colors" data-url="${item.url}">
        <div class="mt-0.5 shrink-0 status-icon">${getStatusIcon(status)}</div>
        <div class="min-w-0 flex-1 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div class="min-w-0 flex flex-wrap items-center gap-2">
            <p class="mono-url break-all text-sm">${item.url}</p>
            ${typeTag(item.type)}
            ${isXlsx ? '<span class="tag-xlsx inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-bold">Written to XLSX</span>' : ''}
          </div>
          <div class="flex shrink-0 items-center gap-2">
            ${copyButton(item.url, 'p-1.5')}
          </div>
        </div>
      </li>
    `;
  };

  const renderRootNode = (root) => {
    const status = effectiveRootStatus(root);
    const hasChildren = root.children && root.children.length > 0;
    const expanded = hasChildren && isRootExpanded(root.url, root.children.length);
    const doneCount = hasChildren ? root.children.filter((c) => (c.status || '').toLowerCase() === 'done').length : 0;
    const rootPct = hasChildren ? Math.round((doneCount / root.children.length) * 100) : (status === 'done' ? 100 : 0);

    return `
      <li class="root-url-item overflow-hidden" data-url="${root.url}">
        <div class="root-header flex items-start gap-3.5 px-4 sm:px-5 py-3.5 ${hasChildren ? 'is-toggleable select-none' : ''}" data-url="${root.url}">
          ${hasChildren
        ? `<button type="button" class="tree-toggle mt-0.5 flex h-7 w-7 items-center justify-center rounded-lg cursor-pointer transition ${expanded ? 'is-open' : ''}" data-url="${root.url}" aria-expanded="${expanded}" aria-label="Toggle product list">${chevronIcon(expanded)}</button>`
        : '<span class="w-[28px] shrink-0"></span>'}
          <div class="mt-0.5 shrink-0 status-icon">${getStatusIcon(status)}</div>
          <div class="min-w-0 flex-1">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div class="min-w-0">
                <p class="mono-url break-all text-sm sm:text-base font-bold leading-snug">${root.url}</p>
                ${hasChildren ? `<span class="mt-1.5 inline-flex items-center root-child-count px-3 py-0.5 text-xs sm:text-sm font-semibold rounded-full">${doneCount}/${root.children.length} products done</span>` : ''}
              </div>
              <div class="flex shrink-0 items-center gap-3">
                ${hasChildren ? `<span class="text-xs font-bold mono" style="color: var(--cyan);">${rootPct}%</span>` : ''}
                ${copyButton(root.url)}
              </div>
            </div>
            ${hasChildren ? `<div class="progress-track mt-2.5" style="height:6px;"><div class="progress-fill" style="width:${rootPct}%;height:100%;"></div></div>` : ''}
          </div>
        </div>
        ${hasChildren ? `
          <ul class="child-list space-y-2 px-4 sm:px-5 py-3.5 pl-9 sm:pl-14 ${expanded ? '' : 'hidden'}">
            ${root.children.slice(0, 100).map(renderChildRow).join('')}
            ${root.children.length > 100 ? `<li class="rounded-xl px-3.5 py-2.5 text-xs text-center" style="border: 1px dashed var(--border); color: var(--text-lo);">… and <strong>${root.children.length - 100}</strong> more product URLs (${root.children.length} total)</li>` : ''}
          </ul>
        ` : ''}
      </li>
    `;
  };

  // Every branch below fully replaces urlStatusList's innerHTML, which would
  // otherwise reset scroll to the top on every throttled re-render while a
  // scrape is actively discovering new URLs -- making it impossible to
  // scroll to a row and click its copy button before the list jumps back.
  // Capturing/restoring scrollTop around the assignment keeps the viewport
  // stable across renders.
  const setUrlListHtml = (html) => {
    const previousScrollTop = urlStatusList.scrollTop;
    urlStatusList.innerHTML = html;
    urlStatusList.scrollTop = previousScrollTop;
  };

  const renderUrlTreeList = (statuses) => {
    if (!urlStatusList) return;
    lastKnownStatuses = statuses || [];

    if (!lastKnownStatuses.length) {
      if (isCurrentRunning) {
        setUrlListHtml(`
          <li class="loading-banner rounded-2xl p-5 text-sm flex items-start gap-3.5">
            <svg class="w-5 h-5 animate-spin shrink-0 mt-0.5" style="color: var(--amber);" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
            </svg>
            <div class="space-y-1">
              <p class="font-semibold">Scraper is running. Please wait…</p>
              <p class="text-xs" style="color: var(--text-mid);">The crawler is actively running on the server. URLs and progress will stream below.</p>
            </div>
          </li>
        `);
      } else {
        setUrlListHtml(`
          <li class="flex flex-col items-center justify-center gap-3 py-12 text-center">
            <span class="empty-state-icon w-14 h-14 rounded-full flex items-center justify-center">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
            </span>
            <p class="text-sm font-semibold" style="color: var(--text-mid);">No URLs available</p>
            <p class="text-xs max-w-xs" style="color: var(--text-lo);">Your scraper has not received any URLs yet. Start a run to see live queue activity here.</p>
          </li>
        `);
      }
      return;
    }

    const tree = buildUrlTree(lastKnownStatuses);

    const MAX_ROOTS = 50;
    const visibleTree = tree.slice(0, MAX_ROOTS);
    const hidden = tree.length - visibleTree.length;
    const html = visibleTree.map(renderRootNode).join('');
    const moreHtml = hidden > 0
      ? `<li class="rounded-2xl px-4 py-3 text-sm text-center" style="border: 1px dashed var(--border); color: var(--text-lo);">… and <strong>${hidden}</strong> more root URLs (total: ${tree.length})</li>`
      : '';
    setUrlListHtml(html + moreHtml);
  };

  // ==============================================================================
  // Header state (Running / Completed / Stopped / Failed) + completion summary
  // ==============================================================================
  const updateHeaderState = (statusRes, stats) => {
    const st = (statusRes.status || '').toUpperCase();

    if (isCurrentRunning) {
      setStatus('Running', 'tone-live', 'is-live');
      if (headerSubtitleEl) headerSubtitleEl.textContent = 'Monitor your scraper activity and URL queue in real time.';
      if (completionSummaryEl) completionSummaryEl.classList.add('hidden');
      return;
    }

    if (st === 'STOPPED') {
      setStatus('Stopped', 'tone-warn', 'is-static');
      if (headerSubtitleEl) headerSubtitleEl.textContent = 'Scraper stopped by user.';
      renderCompletionSummary(stats, 'stopped');
    } else if (st === 'SUCCESS' || statusRes.done) {
      setStatus('Completed', 'tone-live', 'is-static');
      if (headerSubtitleEl) headerSubtitleEl.textContent = 'Scraping completed successfully.';
      renderCompletionSummary(stats, 'success');
    } else if (st === 'FAILED' || st === 'FAIL') {
      setStatus('Failed', 'tone-danger', 'is-danger');
      if (headerSubtitleEl) headerSubtitleEl.textContent = 'Scraper encountered an error.';
      renderCompletionSummary(stats, 'failed', statusRes.error_message || statusRes.errorMessage);
    } else {
      setStatus('Idle', 'tone-idle', 'is-static');
      if (headerSubtitleEl) headerSubtitleEl.textContent = 'Monitor your scraper activity and URL queue in real time.';
      if (completionSummaryEl) completionSummaryEl.classList.add('hidden');
    }
  };

  // Explicit literal classes per kind (not string-interpolated) so every class
  // this can ever render is statically present in this file.
  const COMPLETION_TONE_CLASSES = {
    failed: 'tone-failed',
    stopped: 'tone-stopped',
    success: 'tone-success',
  };
  const COMPLETION_TEXT_COLOR = {
    failed: 'var(--rose)',
    stopped: 'var(--amber)',
    success: 'var(--emerald)',
  };

  const renderCompletionSummary = (stats, kind, errorMessage) => {
    if (!completionSummaryEl) return;
    const toneClass = COMPLETION_TONE_CLASSES[kind] || COMPLETION_TONE_CLASSES.success;
    const icon = kind === 'failed'
      ? '<path d="M12 9v4M12 17h.01"/><circle cx="12" cy="12" r="10"/>'
      : kind === 'stopped'
        ? '<rect x="6" y="6" width="12" height="12" rx="2"/>'
        : '<path d="M20 6 9 17l-5-5"/>';

    completionSummaryEl.classList.remove('hidden');
    completionSummaryEl.innerHTML = `
      <div class="flex items-start gap-3.5">
        <span class="completion-icon ${toneClass} w-9 h-9 rounded-full flex items-center justify-center shrink-0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${icon}</svg>
        </span>
        <div class="min-w-0 flex-1 flex flex-wrap items-center gap-x-6 gap-y-1.5 text-sm">
          <span class="font-bold" style="color: var(--text-hi);">${stats.totalUrls.toLocaleString()} URLs processed</span>
          <span style="color: var(--text-lo);">${stats.totalProducts.toLocaleString()} products found</span>
          <span style="color: var(--text-lo);">${stats.blocked.toLocaleString()} blocked</span>
          ${errorMessage ? `<span class="basis-full" style="color: ${COMPLETION_TEXT_COLOR.failed};">${errorMessage}</span>` : ''}
        </div>
      </div>
    `;
  };

  const updateUiState = (statusRes) => {
    if (!statusRes) return;
    if (fileScraperSwitcher && (statusRes.site_name || statusRes.siteName)) {
      fileScraperNameEl.textContent = `Scraper: ${statusRes.site_name || statusRes.siteName}`;
      fileScraperSwitcher.classList.remove('hidden');
    }

    const st = (statusRes.status || '').toUpperCase();
    isCurrentRunning = st === 'RUNNING' || statusRes.running === true;

    const stats = renderDashboard(statusRes);
    renderHeaderTelemetry(statusRes, stats);
    updateHeaderState(statusRes, stats);
    updateControls(statusRes);
  };

  // ==============================================================================
  // SSE Webhook Client (Real-time Push Stream)
  // ==============================================================================

  const getCacheKey = () => fileScraperId ? `tyresvision_scraper_cache_file_${fileScraperId}` : null;

  const saveStateToLocalStorage = (summary, statuses) => {
    const key = getCacheKey();
    if (!key) return;
    try {
      const data = {
        summary: summary || {},
        statuses: (statuses && statuses.length) ? statuses : (lastKnownStatuses || []),
        timestamp: Date.now(),
      };
      localStorage.setItem(key, JSON.stringify(data));
    } catch (e) {
      console.warn('[LocalStorage] Save failed:', e);
    }
  };

  const loadStateFromLocalStorage = () => {
    const key = getCacheKey();
    if (!key) return false;
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return false;
      const data = JSON.parse(raw);
      if (data && data.summary) {
        updateUiState(data.summary);
        if (Array.isArray(data.statuses) && data.statuses.length > 0) {
          renderUrlTreeList(data.statuses);
        }
        return true;
      }
    } catch (e) {
      console.warn('[LocalStorage] Load failed:', e);
    }
    return false;
  };

  const startEventSource = (jobId) => {
    if (!jobId || (activeEventSource && activeEventSource._jobId === jobId)) {
      return;
    }
    closeEventSource();
    stopStatusPolling();

    try {
      const es = new EventSource(`/tcsadmin/api/scraper/job/${jobId}/events`);
      es._jobId = jobId;
      activeEventSource = es;

      es.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          handleSsePayload(payload);
        } catch (err) {
          console.error('[SSE Parse Error]:', err);
        }
      };

      es.onerror = () => {
        closeEventSource();
        startStatusPolling();
      };
    } catch (e) {
      console.warn('[SSE Connection Failed, falling back to polling]:', e);
      startStatusPolling();
    }
  };

  let treeRenderTimeout = null;
  let lastTreeRenderTime = 0;
  const TREE_RENDER_THROTTLE_MS = 1000;

  const scheduleThrottledTreeRender = () => {
    const now = Date.now();
    const elapsed = now - lastTreeRenderTime;
    if (elapsed >= TREE_RENDER_THROTTLE_MS) {
      lastTreeRenderTime = now;
      if (treeRenderTimeout) {
        clearTimeout(treeRenderTimeout);
        treeRenderTimeout = null;
      }
      renderUrlTreeList(lastKnownStatuses);
    } else if (!treeRenderTimeout) {
      treeRenderTimeout = setTimeout(() => {
        lastTreeRenderTime = Date.now();
        treeRenderTimeout = null;
        renderUrlTreeList(lastKnownStatuses);
      }, TREE_RENDER_THROTTLE_MS - elapsed);
    }
  };

  const updateUrlItemInPlace = (item) => {
    if (!urlStatusList || !item || !item.url) return false;
    try {
      const escapedUrl = CSS.escape(item.url);
      const el = urlStatusList.querySelector(`[data-url="${escapedUrl}"]`);
      if (!el) return false;
      const statusIcon = el.querySelector('.status-icon');
      if (statusIcon) {
        statusIcon.innerHTML = getStatusIcon((item.status || 'pending').toLowerCase());
      }
      return true;
    } catch (e) {
      return false;
    }
  };

  const handleSsePayload = (payload) => {
    if (!payload) return;

    if (payload.type === 'snapshot') {
      updateUiState(payload.summary || {});
      renderUrlTreeList(payload.statuses || []);
      saveStateToLocalStorage(payload.summary || {}, payload.statuses || []);
    } else if (payload.type === 'url_update') {
      updateUiState(payload.summary || {});
      if (payload.url) {
        const idx = lastKnownStatuses.findIndex((u) => u.url === payload.url.url);
        if (idx >= 0) {
          lastKnownStatuses[idx] = payload.url;
          // In-place update: 0ms, 0 flicker, never destroys copy button or resets expanded state
          const updatedInPlace = updateUrlItemInPlace(payload.url);
          if (!updatedInPlace) {
            scheduleThrottledTreeRender();
          }
        } else {
          lastKnownStatuses.push(payload.url);
          scheduleThrottledTreeRender();
        }
        saveStateToLocalStorage(payload.summary || {}, lastKnownStatuses);
      }
    } else if (payload.type === 'status') {
      const st = (payload.status || '').toUpperCase();
      updateUiState(payload);
      saveStateToLocalStorage(payload, lastKnownStatuses);
      if (payload.done || ['SUCCESS', 'STOPPED', 'FAILED', 'FAIL'].includes(st)) {
        if (treeRenderTimeout) {
          clearTimeout(treeRenderTimeout);
          treeRenderTimeout = null;
        }
        renderUrlTreeList(lastKnownStatuses);
        closeEventSource();
        stopStatusPolling();
        refreshProgress();
      }
    }
  };

  // ==============================================================================
  // Fallback Polling / Initial Loader
  // ==============================================================================

  const refreshProgress = async () => {
    try {
      if (fileScraperId) {
        const activeRes = await fetch(`/tcsadmin/api/scraper/file/${fileScraperId}/active-job`);
        if (activeRes.ok) {
          const activeInfo = await activeRes.json();
          if (activeInfo.already_running && !activeInfo.is_owner) {
            showBlockedScreen();
            closeEventSource();
            stopStatusPolling();
            return;
          }

          showMainProgress();
          currentJobId = activeInfo.job_id || null;
          const isRunning = Boolean(activeInfo.has_active_job && activeInfo.job_id);

          const statusEndpoint = currentJobId
            ? `/tcsadmin/api/scraper/job/${currentJobId}/status`
            : `/tcsadmin/api/files/${fileScraperId}/status`;
          const urlsEndpoint = currentJobId
            ? `/tcsadmin/api/scraper/job/${currentJobId}/urls`
            : `/tcsadmin/api/files/${fileScraperId}/url-statuses`;

          const [statusRes, urlsRes] = await Promise.all([
            fetch(statusEndpoint).then((r) => (r.ok ? r.json() : null)),
            fetch(urlsEndpoint).then((r) => (r.ok ? r.json() : null)),
          ]);

          if (statusRes) {
            // Update the URL list (and lastKnownStatuses) before computing
            // stats -- computeStats() falls back to deriving totals from
            // lastKnownStatuses when the summary is empty, so it must see
            // the fresh list, not the stale one from before this poll.
            const statuses = Array.isArray(urlsRes)
              ? urlsRes
              : urlsRes && Array.isArray(urlsRes.statuses)
              ? urlsRes.statuses
              : [];
            renderUrlTreeList(statuses);
            updateUiState(statusRes);
            saveStateToLocalStorage(statusRes, statuses);
          } else {
            const rawStatus = activeInfo.status || (isRunning ? 'RUNNING' : 'IDLE');
            isCurrentRunning = isRunning;
            setStatus(isRunning ? 'Running' : (rawStatus === 'STOPPED' ? 'Stopped' : 'Idle'), isRunning ? 'tone-live' : 'tone-idle', isRunning ? 'is-live' : 'is-static');
            updateControls({ running: isRunning, status: rawStatus });
          }

          if (isRunning) {
            startEventSource(currentJobId);
          } else {
            closeEventSource();
            stopStatusPolling();
          }
          return;
        }
      }

      if (!currentJobId && !fileScraperId) {
        stopStatusPolling();
        closeEventSource();
        setStatus('Idle', 'tone-idle', 'is-static');
        return;
      }

      const statusEndpoint = currentJobId
        ? `/tcsadmin/api/scraper/job/${currentJobId}/status`
        : `/tcsadmin/api/files/${fileScraperId}/status`;

      const urlsEndpoint = currentJobId
        ? `/tcsadmin/api/scraper/job/${currentJobId}/urls`
        : `/tcsadmin/api/files/${fileScraperId}/url-statuses`;

      const [statusRes, urlsRes] = await Promise.all([
        fetch(statusEndpoint).then((r) => (r.ok ? r.json() : null)),
        fetch(urlsEndpoint).then((r) => (r.ok ? r.json() : null)),
      ]);

      if (!statusRes) {
        stopStatusPolling();
        closeEventSource();
        setStatus('Idle', 'tone-idle', 'is-static');
        return;
      }

      const statuses = Array.isArray(urlsRes)
        ? urlsRes
        : urlsRes && Array.isArray(urlsRes.statuses)
        ? urlsRes.statuses
        : [];
      renderUrlTreeList(statuses);
      updateUiState(statusRes);
      saveStateToLocalStorage(statusRes, statuses);

      if (isCurrentRunning && currentJobId) {
        startEventSource(currentJobId);
        startStatusPolling();
      } else {
        closeEventSource();
        stopStatusPolling();
      }
    } catch (error) {
      console.error('[TyresVision Scraper Refresh Error]:', error);
    }
  };

  const ensureFileScraperCsrfToken = async () => {
    if (fileScraperCsrfToken) return fileScraperCsrfToken;
    try {
      const response = await fetch('/tcsadmin/api/me');
      if (response.ok) {
        const data = await response.json();
        fileScraperCsrfToken = data.csrfToken;
      }
    } catch (error) {
      console.error(error);
    }
    return fileScraperCsrfToken;
  };

  if (startButton) {
    startButton.addEventListener('click', async () => {
      if (!fileScraperId) {
        await resolveFileScraperId();
      }
      if (!fileScraperId) return;
      startButton.disabled = true;
      startButton.innerHTML = '<span>Starting…</span>';
      if (window.AdminShared) {
        window.AdminShared.showToast('Starting scraper… please wait', 'info');
      }

      try {
        const token = await ensureFileScraperCsrfToken();
        const res = await fetch(`/tcsadmin/api/files/${fileScraperId}/start`, {
          method: 'POST',
          headers: { 'X-CSRF-Token': token },
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.success) {
          const errMsg = data.message || data.error || 'Unable to start scraper.';
          if (window.AdminShared) window.AdminShared.showToast(errMsg, 'warning');
          await refreshProgress();
          return;
        }
        if (window.AdminShared) window.AdminShared.showToast('Scraper started successfully!', 'success');
        currentJobId = data.job_id;
        isCurrentRunning = true;
        setStatus('Running', 'tone-live', 'is-live');
        updateControls({ running: true, status: 'RUNNING' });
        startEventSource(currentJobId);
        startStatusPolling();
        await refreshProgress();
      } catch (err) {
        if (window.AdminShared) window.AdminShared.showToast('Failed to start scraper.', 'error');
      } finally {
        if (startButton) {
          startButton.disabled = false;
          startButton.innerHTML = `
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            <span>Start Scraper</span>
          `;
        }
      }
    });
  }

  const doStopScraper = async () => {
    stopButton.disabled = true;
    if (window.AdminShared) {
      window.AdminShared.showToast('Stopping scraper… please wait', 'warning');
    }

    try {
      const token = await ensureFileScraperCsrfToken();
      let stopEndpoint;
      if (currentJobId) {
        stopEndpoint = `/tcsadmin/api/scraper/job/${currentJobId}/stop`;
      } else if (fileScraperId) {
        stopEndpoint = `/tcsadmin/api/files/${fileScraperId}/stop`;
      } else {
        stopEndpoint = '/tcsadmin/stop-scraper';
      }

      const response = await fetch(stopEndpoint, {
        method: 'POST',
        headers: { 'X-CSRF-Token': token },
      });

      if (!response.ok) throw new Error('Failed to stop scraper');

      isCurrentRunning = false;
      closeEventSource();
      stopStatusPolling();
      setStatus('Stopped', 'tone-warn', 'is-static');
      updateControls({ running: false, status: 'STOPPED' });

      if (window.AdminShared) {
        window.AdminShared.showToast('Scraper stopped successfully.', 'success');
      }
    } catch (error) {
      if (window.AdminShared) {
        window.AdminShared.logError('Stop Scraper Button', error, { fileScraperId, currentJobId });
        window.AdminShared.showToast(error.message || 'Unable to stop scraper.', 'error');
      }
    } finally {
      stopButton.disabled = true;
      await refreshProgress();
    }
  };

  if (stopButton && stopConfirmModal) {
    stopButton.addEventListener('click', (e) => {
      e.preventDefault();
      stopConfirmModal.classList.remove('hidden');
    });
  }
  if (stopConfirmProceed) {
    stopConfirmProceed.addEventListener('click', () => {
      stopConfirmModal.classList.add('hidden');
      doStopScraper();
    });
  }

  if (urlStatusList) {
    urlStatusList.addEventListener('click', async (e) => {
      const button = e.target.closest('.btncopy');
      if (!button) return;
      e.stopPropagation();

      const url = button.getAttribute('data-url') || button.dataset.url;
      if (!url) return;

      let copied = false;
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(url);
          copied = true;
        }
      } catch (err) {
        copied = false;
      }

      if (!copied) {
        try {
          const textarea = document.createElement('textarea');
          textarea.value = url;
          textarea.style.position = 'fixed';
          textarea.style.top = '0';
          textarea.style.left = '0';
          textarea.style.opacity = '0';
          textarea.style.pointerEvents = 'none';
          document.body.appendChild(textarea);
          textarea.focus();
          textarea.select();
          copied = document.execCommand('copy');
          document.body.removeChild(textarea);
        } catch (err) {
          copied = false;
        }
      }

      if (copied) {
        if (!button.dataset.originalHtml) {
          button.dataset.originalHtml = button.innerHTML;
          button.dataset.originalClass = button.className;
        }

        button.innerHTML = `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        `;
        button.className = `${button.dataset.originalClass} is-copied`;
        button.title = 'Copied!';

        if (window.AdminShared && typeof window.AdminShared.showToast === 'function') {
          window.AdminShared.showToast('URL copied to clipboard!', 'success');
        }

        clearTimeout(button._resetTimeout);
        button._resetTimeout = setTimeout(() => {
          button.innerHTML = button.dataset.originalHtml;
          button.className = button.dataset.originalClass;
          button.title = 'Copy URL';
        }, 1500);
      } else {
        if (window.AdminShared && typeof window.AdminShared.showToast === 'function') {
          window.AdminShared.showToast('Failed to copy URL', 'error');
        }
      }
    });

    const toggleAllBtn = document.getElementById('toggle-all-urls');
    const toggleAllLabel = document.getElementById('toggle-all-label');

    if (toggleAllBtn) {
      toggleAllBtn.addEventListener('click', () => {
        const rootLis = urlStatusList.querySelectorAll('li.root-url-item');
        if (!rootLis.length) return;

        // Determine if we should collapse or expand based on current state
        const childLists = urlStatusList.querySelectorAll('.child-list');
        const anyVisible = Array.from(childLists).some((cl) => !cl.classList.contains('hidden'));
        const shouldCollapse = anyVisible;

        rootLis.forEach((rootLi) => {
          const childList = rootLi.querySelector('.child-list');
          if (!childList) return;
          const toggleBtn = rootLi.querySelector('.tree-toggle');
          const header = rootLi.querySelector('.root-header');
          const url = (header && header.dataset.url) || (toggleBtn && toggleBtn.dataset.url);

          if (shouldCollapse) {
            childList.classList.add('hidden');
            if (toggleBtn) {
              toggleBtn.setAttribute('aria-expanded', 'false');
              toggleBtn.classList.remove('is-open');
              toggleBtn.innerHTML = chevronIcon(false);
            }
            if (url) {
              collapsedRoots.add(url);
              expandedRoots.delete(url);
            }
          } else {
            childList.classList.remove('hidden');
            if (toggleBtn) {
              toggleBtn.setAttribute('aria-expanded', 'true');
              toggleBtn.classList.add('is-open');
              toggleBtn.innerHTML = chevronIcon(true);
            }
            if (url) {
              expandedRoots.add(url);
              collapsedRoots.delete(url);
            }
          }
        });

        if (toggleAllLabel) {
          toggleAllLabel.textContent = shouldCollapse ? 'Expand All' : 'Collapse All';
        }
      });
    }

    urlStatusList.addEventListener('click', (e) => {
      // Don't toggle when clicking copy button, hyperlinks, or inputs
      if (e.target.closest('.btncopy') || e.target.closest('a') || e.target.closest('button:not(.tree-toggle)')) return;

      const headerOrToggle = e.target.closest('.tree-toggle') || e.target.closest('.root-header');
      if (!headerOrToggle) return;

      const rootLi = headerOrToggle.closest('li.root-url-item') || headerOrToggle.closest('li');
      if (!rootLi) return;

      const childList = rootLi.querySelector('.child-list');
      if (!childList) return;

      const toggleBtn = rootLi.querySelector('.tree-toggle');
      const url = (headerOrToggle.dataset && headerOrToggle.dataset.url) || (toggleBtn && toggleBtn.dataset.url);

      // Direct DOM state check: if currently hidden, we are expanding; if open, collapsing
      const isCurrentlyHidden = childList.classList.contains('hidden');
      const willBeExpanded = isCurrentlyHidden;

      if (willBeExpanded) {
        childList.classList.remove('hidden');
      } else {
        childList.classList.add('hidden');
      }

      if (toggleBtn) {
        toggleBtn.setAttribute('aria-expanded', String(willBeExpanded));
        toggleBtn.classList.toggle('is-open', willBeExpanded);
        toggleBtn.innerHTML = chevronIcon(willBeExpanded);
      }

      if (url) {
        if (willBeExpanded) {
          expandedRoots.add(url);
          collapsedRoots.delete(url);
        } else {
          collapsedRoots.add(url);
          expandedRoots.delete(url);
        }
      }
    });
  }

  // Initial bootstrap on /scraperpage
  const initPage = async () => {
    // 1. Immediately render default placeholders so UI is never blank
    renderDashboard({});
    renderUrlTreeList([]);
    updateControls({ running: false, status: 'IDLE' });

    // 2. Resolve scraper fileId if not in URL params
    if (!fileScraperId) {
      await resolveFileScraperId();
    }

    // 3. Preload cached state if available
    loadStateFromLocalStorage();

    // 4. Fetch live server progress
    await refreshProgress();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPage);
  } else {
    initPage();
  }
})();
