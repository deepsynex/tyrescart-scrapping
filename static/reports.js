// SuperAdmin Scraping Reports page (/reports).
// Displays live and historical logs from logTbl of who triggered scraping, start/end times,
// URLs found, success/blocked counts, and records scraped.
(function () {
  const tableEl = document.getElementById('reports-table');
  if (!tableEl) return;

  const Shared = window.AdminShared;
  const errorEl = document.getElementById('reports-error');
  const loadingEl = document.getElementById('reports-loading');
  const refreshBtn = document.getElementById('reports-refresh-btn');
  const refreshIcon = document.getElementById('reports-refresh-icon');
  const statusFilterEl = document.getElementById('reports-status-filter');

  const statTotalRunsEl = document.getElementById('stat-total-runs');
  const statDataScrapedEl = document.getElementById('stat-data-scraped');
  const statPagesCrawledEl = document.getElementById('stat-pages-crawled');
  const statActiveRunsEl = document.getElementById('stat-active-runs');

  let table = null;
  let reports = [];
  let pollInterval = null;

  function userCellHtml(row) {
    const name = row.userName || 'Admin';
    const userId = row.userId;
    const safeName = Shared.escapeHtml(name);

    return `
      <div class="flex items-center gap-1.5">
        <span class="font-medium text-slate-800 text-sm">${safeName}</span>
        ${userId ? `<span class="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-mono font-semibold text-slate-500">#${userId}</span>` : ''}
      </div>
    `;
  }

  function scraperCellHtml(row) {
    const scraperName = row.siteName || row.scraper || 'Scraper';
    const safeSite = Shared.escapeHtml(scraperName);
    return `
      <div>
        <div class="font-semibold text-slate-800 text-sm">${safeSite}</div>
      </div>
    `;
  }

  function statusBadgeHtml(row) {
    const st = (row.status || '').toUpperCase();
    switch (st) {
      case 'RUNNING':
        return `<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700 border border-blue-200/60"><span class="w-1.5 h-1.5 rounded-full bg-[#2563FF] animate-pulse"></span>RUNNING</span>`;
      case 'SUCCESS':
      case 'FINISHED':
        return `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-100 text-sky-700 border border-sky-200/60">SUCCESS</span>`;
      case 'STOPPED':
      case 'STOP':
        return `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200/60">STOPPED</span>`;
      case 'FAIL':
      case 'FAILED':
      default:
        return `<button type="button" data-action="view-error-detail" data-log-id="${row.id}" class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-700 border border-rose-200/80 hover:bg-rose-200 hover:border-rose-300 transition cursor-pointer" title="Click to view failure reason & details"><svg class="w-3 h-3 text-rose-500 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>FAIL</button>`;
    }
  }

  function messageCellHtml(row) {
    const isRunning = (row.status || '').toUpperCase() === 'RUNNING';
    const isFail = (row.status || '').toUpperCase() === 'FAIL' || (row.status || '').toUpperCase() === 'FAILED';
    const msg = row.errorMessage || '';
    if (isRunning && row.fileId) {
      return `<a href="/tcsadmin/scraperpage?fileId=${row.fileId}" class="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 hover:underline cursor-pointer">Live Progress →</a>`;
    }
    if (isFail) {
      return `
        <button type="button" data-action="view-error-detail" data-log-id="${row.id}" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 transition cursor-pointer max-w-[280px] text-left truncate" title="${Shared.escapeHtml(msg || 'Click to view failure reason')}">
          <svg class="w-3.5 h-3.5 text-rose-500 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <span class="truncate">${Shared.escapeHtml(msg || 'View Failure Reason')}</span>
        </button>
      `;
    }
    if (!msg) return '<span class="text-slate-400">—</span>';
    return `<span class="text-xs text-slate-600 max-w-[280px] inline-block truncate" title="${Shared.escapeHtml(msg)}">${Shared.escapeHtml(msg)}</span>`;
  }

  function updateStatsCards(stats) {
    if (!stats) return;
    if (statTotalRunsEl) statTotalRunsEl.textContent = (stats.totalRuns || 0).toLocaleString();
    if (statDataScrapedEl) statDataScrapedEl.textContent = (stats.totalDataScraped || 0).toLocaleString();
    if (statPagesCrawledEl) statPagesCrawledEl.textContent = (stats.totalUrlsFound || 0).toLocaleString();
    if (statActiveRunsEl) statActiveRunsEl.textContent = (stats.activeRuns || 0).toLocaleString();
  }

  function initTable() {
    table = $(tableEl).DataTable(Shared.commonDataTableOptions({
      data: [],
      order: [[0, 'desc']], // newest run first
      language: {
        search: '',
        searchPlaceholder: 'Search logs…',
        lengthMenu: 'Show _MENU_ logs per page',
        info: 'Showing _START_ to _END_ of _TOTAL_ logs',
        infoEmpty: 'No scraping logs recorded yet',
        infoFiltered: '(filtered from _MAX_ total logs)',
        paginate: { first: 'First', last: 'Last', next: 'Next', previous: 'Previous' },
      },
      columns: [
        {
          data: 'id',
          className: 'font-mono text-xs text-slate-500 font-semibold',
          render: (data) => `#${data}`,
        },
        {
          data: null,
          render: (data, type, row) => (type === 'display' ? scraperCellHtml(row) : (row.siteName || row.scraper || '')),
        },
        {
          data: null,
          render: (data, type, row) => (type === 'display' ? userCellHtml(row) : `${row.userName || 'Admin'} ${row.userId ? '#' + row.userId : ''}`),
        },
        {
          data: null,
          render: (data, type, row) => (type === 'display' ? Shared.dateTimeHtml(row.startTimeRaw) : (row.startTimeRaw || '')),
        },
        {
          data: null,
          render: (data, type, row) => {
            if (type === 'display') {
              return row.endTimeRaw
                ? Shared.dateTimeHtml(row.endTimeRaw)
                : '<span class="inline-flex items-center gap-1.5 text-xs text-[#2563FF] font-semibold"><span class="w-1.5 h-1.5 rounded-full bg-[#2563FF] animate-pulse"></span>Running</span>';
            }
            return row.endTimeRaw || '';
          },
        },
        {
          data: null,
          className: 'font-mono text-xs text-slate-700',
          render: (data, type, row) => (type === 'display' ? `<span class="font-semibold text-slate-700">${Shared.escapeHtml(row.duration || '—')}</span>` : (row.durationSeconds || 0)),
        },
        {
          data: 'dataScraped',
          render: (data, type) => (type === 'display' ? `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200/60">${(data || 0).toLocaleString()}</span>` : (data || 0)),
        },
        {
          data: null,
          render: (data, type, row) => (type === 'display' ? statusBadgeHtml(row) : (row.status || '')),
        },
      ],
    }));
  }

  function showTable() {
    if (loadingEl) loadingEl.classList.add('hidden');
  }

  const REPORTS_CACHE_KEY = 'tyresvision_reports_cache';

  function loadCachedReports() {
    try {
      const raw = localStorage.getItem(REPORTS_CACHE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (data && Array.isArray(data.reports) && data.reports.length > 0) {
        reports = data.reports;
        updateStatsCards(data.stats);
        table.clear();
        table.rows.add(reports);
        table.draw(false);
        showTable();
      }
    } catch (e) {}
  }

  async function loadReports({ silent } = {}) {
    if (!silent && !reports.length) Shared.hideError(errorEl);
    if (refreshBtn && !silent) {
      refreshBtn.disabled = true;
      refreshIcon.classList.add('animate-spin');
    }

    try {
      const statusParam = statusFilterEl ? statusFilterEl.value : '';
      const url = `/tcsadmin/api/reports?perPage=200${statusParam ? `&status=${encodeURIComponent(statusParam)}` : ''}`;
      const response = await fetch(url);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const msg = data.error || 'Failed to load scraper logs.';
        Shared.showError(errorEl, msg);
        if (!silent) Shared.showToast(msg, 'error');
        return;
      }

      reports = data.reports || [];
      try {
        if (!statusParam) {
          localStorage.setItem(REPORTS_CACHE_KEY, JSON.stringify(data));
        }
      } catch (e) {}

      updateStatsCards(data.stats);

      table.clear();
      table.rows.add(reports);
      table.draw(false);

      // If active runs exist, ensure polling is running
      if (data.stats && data.stats.activeRuns > 0) {
        startPolling();
      } else {
        stopPolling();
      }
    } catch (err) {
      Shared.logError('Reports Module Fetch', err);
      Shared.showError(errorEl, 'Network error while loading logs.');
      if (!silent) Shared.showToast('Network error while loading logs.', 'error');
    } finally {
      showTable();
      if (refreshBtn) {
        refreshBtn.disabled = false;
        refreshIcon.classList.remove('animate-spin');
      }
    }
  }

  function startPolling() {
    if (!pollInterval) {
      pollInterval = setInterval(() => {
        loadReports({ silent: true });
      }, 5000);
    }
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
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

  document.addEventListener('DOMContentLoaded', () => {
    initTable();

    refreshBtn?.addEventListener('click', () => {
      Shared.showToast('Refreshing scraper audit logs…', 'info');
      loadReports();
    });

    statusFilterEl?.addEventListener('change', () => {
      const val = statusFilterEl.value;
      Shared.showToast(val ? `Filtering logs: ${val}` : 'Showing all logs', 'info');
      loadReports();
    });

    $(tableEl.tBodies[0]).on('click', 'a[href*="/download"]', function () {
      Shared.showToast('Starting report download…', 'info');
    });

    $(tableEl.tBodies[0]).on('click', 'button[data-action="view-error-detail"]', function (e) {
      e.stopPropagation();
      const logId = Number(this.getAttribute('data-log-id'));
      const log = reports.find((r) => r.id === logId);
      if (log) {
        openLogDetailModal(log);
      }
    });

    loadCachedReports();
    loadReports({ silent: Boolean(reports.length) });
  });
})();
