/**
 * static/visionadmin/enquiries.js
 * VisionAdmin Customer & WhatsApp Enquiries Manager
 */

(function () {
  'use strict';

  let allEnquiries = [];
  let currentStatusFilter = 'all';
  let currentSearchQuery = '';
  let currentTypeFilter = 'all';
  let activeEnquiry = null;

  // DOM Elements
  const tableBody = document.getElementById('enquiries-table-body');
  const mobileCardsContainer = document.getElementById('enquiries-mobile-cards');
  const emptyState = document.getElementById('enquiries-empty-state');
  const showingCount = document.getElementById('enquiries-showing-count');
  const searchInput = document.getElementById('enquiry-search-input');
  const typeFilter = document.getElementById('enquiry-type-filter');
  const btnRefresh = document.getElementById('btn-refresh-enquiries');
  const btnTruncate = document.getElementById('btn-truncate-enquiries');
  const tabBtns = document.querySelectorAll('.va-tab-btn');

  // Metrics Elements
  const metricTotal = document.getElementById('metric-total');
  const metricNew = document.getElementById('metric-new');
  const metricBanner = document.getElementById('metric-banner');
  const metricWhatsapp = document.getElementById('metric-whatsapp');
  const tabCountAll = document.getElementById('tab-count-all');
  const tabCountNew = document.getElementById('tab-count-new');

  // Modal Elements
  const modal = document.getElementById('modal-enquiry-detail');
  const modalIdBadge = document.getElementById('modal-enquiry-id-badge');
  const modalStatusBadge = document.getElementById('modal-enquiry-status-badge');
  const modalTitle = document.getElementById('modal-enquiry-title');
  const modalCustName = document.getElementById('modal-cust-name');
  const modalCustPhone = document.getElementById('modal-cust-phone');
  const modalCustEmail = document.getElementById('modal-cust-email');
  const modalTyreSize = document.getElementById('modal-tyre-size');
  const modalVehicle = document.getElementById('modal-vehicle');
  const modalCity = document.getElementById('modal-city');
  const modalSpec = document.getElementById('modal-spec');
  const modalMessageBox = document.getElementById('modal-message-box');
  const modalStatusSelect = document.getElementById('modal-status-select');
  const btnCloseModal = document.getElementById('btn-close-enquiry-modal');
  const btnSaveStatus = document.getElementById('btn-modal-save-status');
  const btnDeleteModal = document.getElementById('btn-modal-delete-enquiry');
  const btnWaReply = document.getElementById('btn-modal-wa-reply');

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function getStatusBadge(status) {
    status = parseInt(status, 10);
    switch (status) {
      case 0:
        return `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200 text-[10px] font-black uppercase"><span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>New</span>`;
      case 1:
        return `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200 text-[10px] font-black uppercase"><span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>In Progress</span>`;
      case 2:
        return `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200 text-[10px] font-black uppercase"><span class="w-1.5 h-1.5 rounded-full bg-[#2563FF]"></span>Resolved</span>`;
      case 3:
        return `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200 text-[10px] font-bold uppercase">Closed</span>`;
      default:
        return `<span class="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-[10px]">#${status}</span>`;
    }
  }

  function getSourceBadge(formType, enquiryFor) {
    formType = (formType || '').toLowerCase();
    if (formType.includes('banner')) {
      return `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#EFF6FF] text-[#1D4ED8] text-[10px] font-extrabold"><svg class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M12 8v8"/><path d="M8 12h8"/></svg>Home Banner</span>`;
    } else if (formType.includes('float')) {
      return `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#F3E8FF] text-purple-700 text-[10px] font-extrabold">Floating Widget</span>`;
    } else if (formType.includes('nav')) {
      return `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#EFF6FF] text-blue-700 text-[10px] font-extrabold">Header Nav</span>`;
    } else if (formType.includes('bar')) {
      return `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 text-[10px] font-extrabold">Mobile Bar</span>`;
    }
    return `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 text-[10px] font-bold">WhatsApp CTA</span>`;
  }

  async function loadEnquiries() {
    try {
      if (tableBody) {
        tableBody.innerHTML = `
          <tr>
            <td colspan="7" class="py-12 text-center text-slate-400 font-bold">
              <div class="inline-flex items-center gap-2">
                <svg class="w-5 h-5 animate-spin text-[#2563FF]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10" stroke-opacity="0.2"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>
                Loading customer enquiries...
              </div>
            </td>
          </tr>
        `;
      }

      if (mobileCardsContainer) {
        mobileCardsContainer.innerHTML = `
          <div class="py-12 text-center text-slate-400 font-bold">
            <div class="inline-flex items-center gap-2">
              <svg class="w-5 h-5 animate-spin text-[#2563FF]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10" stroke-opacity="0.2"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>
              Loading customer enquiries...
            </div>
          </div>
        `;
      }

      const resp = await fetch('/visionadmin/api/v1/enquiries', {
        headers: { 'Accept': 'application/json' }
      });

      if (resp.status === 401 || resp.status === 403) {
        window.location.href = `/visionadmin/login?next=${encodeURIComponent(window.location.pathname)}`;
        return;
      }

      if (!resp.ok) {
        let errMsg = `Server returned status ${resp.status}`;
        try {
          const errData = await resp.json();
          if (errData && errData.error) errMsg = errData.error;
        } catch (_) {}
        throw new Error(errMsg);
      }

      const data = await resp.json();

      if (!data.success) {
        throw new Error(data.error || 'Failed to load enquiries');
      }

      allEnquiries = data.enquiries || [];

      // Update metrics
      if (metricTotal) metricTotal.textContent = data.metrics.total || 0;
      if (metricNew) metricNew.textContent = data.metrics.new || 0;
      if (metricBanner) metricBanner.textContent = data.metrics.banner || 0;
      if (metricWhatsapp) metricWhatsapp.textContent = data.metrics.whatsapp_direct || 0;

      if (tabCountAll) tabCountAll.textContent = data.metrics.total || 0;
      if (tabCountNew) tabCountNew.textContent = data.metrics.new || 0;

      renderTable();
    } catch (err) {
      console.error('Error fetching enquiries:', err);
      if (tableBody) {
        tableBody.innerHTML = `
          <tr>
            <td colspan="7" class="py-8 text-center text-rose-500 font-bold">
              <div class="space-y-2">
                <div>Failed to load enquiries: ${escapeHtml(err.message)}</div>
                <button type="button" onclick="window.location.reload()" class="px-3 py-1 bg-rose-100 hover:bg-rose-200 text-rose-800 rounded-lg text-xs font-bold transition-colors">
                  Retry Loading
                </button>
              </div>
            </td>
          </tr>
        `;
      }
      if (mobileCardsContainer) {
        mobileCardsContainer.innerHTML = `
          <div class="py-8 text-center text-rose-500 font-bold p-4 space-y-2">
            <div>Failed to load enquiries: ${escapeHtml(err.message)}</div>
            <button type="button" onclick="window.location.reload()" class="px-3 py-1 bg-rose-100 hover:bg-rose-200 text-rose-800 rounded-lg text-xs font-bold transition-colors">
              Retry Loading
            </button>
          </div>
        `;
      }
    }
  }

  function getFilteredList() {
    return allEnquiries.filter((item) => {
      // 1. Status Filter
      if (currentStatusFilter !== 'all') {
        if (parseInt(item.status, 10) !== parseInt(currentStatusFilter, 10)) {
          return false;
        }
      }

      // 2. Source / Form Type Filter
      if (currentTypeFilter !== 'all') {
        const ft = (item.form_type || '').toLowerCase();
        if (currentTypeFilter === 'banner' && !ft.includes('banner')) return false;
        if (currentTypeFilter === 'whatsapp' && ft.includes('banner')) return false;
      }

      // 3. Search Query
      if (currentSearchQuery) {
        const haystack = [
          item.name,
          item.email,
          item.number,
          item.vehicle,
          item.make,
          item.model,
          item.year,
          item.tyre_size,
          item.city,
          item.message,
          item.spec,
          item.enquiry_for
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();

        if (!haystack.includes(currentSearchQuery.toLowerCase())) {
          return false;
        }
      }

      return true;
    });
  }

  function renderTable() {
    const list = getFilteredList();

    if (showingCount) {
      showingCount.textContent = list.length;
    }

    if (!list.length) {
      if (tableBody) tableBody.innerHTML = '';
      if (mobileCardsContainer) mobileCardsContainer.innerHTML = '';
      if (emptyState) emptyState.classList.remove('hidden');
      return;
    }

    if (emptyState) emptyState.classList.add('hidden');

    const html = list
      .map((item) => {
        const id = item.enquiry_id;
        const name = item.name || 'Storefront Visitor';
        const phone = item.number || '';
        const email = item.email || '';
        const tyreSize = item.tyre_size || '--';
        const vehicle = item.vehicle || (item.make ? `${item.make} ${item.model || ''} ${item.year || ''}`.trim() : '--');
        const city = item.city || '--';
        const spec = item.spec || '--';
        const dateStr = item.created_at || '--';

        const phoneClean = phone ? phone.replace(/[^\d+]/g, '') : '';
        const waLink = phoneClean
          ? `https://wa.me/${phoneClean.replace('+', '')}?text=${encodeURIComponent(`Hi ${name}, thank you for contacting TyresVision.`)}`
          : `https://wa.me/971505069575`;

        return `
        <tr class="hover:bg-[#F8FAF7]/80 transition-colors duration-150 group">
          <!-- ID & Date -->
          <td class="py-4 px-4 sm:px-6">
            <div class="font-black text-[#0E1108]">#${id}</div>
            <div class="text-[11px] text-slate-400 whitespace-nowrap mt-0.5">${escapeHtml(dateStr)}</div>
          </td>

          <!-- Customer & Contact -->
          <td class="py-4 px-4">
            <div class="font-extrabold text-[#0E1108] flex items-center gap-1.5">
              <span>${escapeHtml(name)}</span>
              ${phone ? `
                <a href="${waLink}" target="_blank" title="Chat on WhatsApp" class="text-[#2563FF] hover:text-[#1D4ED8] transition-colors inline-flex items-center">
                  <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.46 1.32 4.96L2 22l5.25-1.38a9.9 9.9 0 004.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91C21.96 6.45 17.5 2 12.04 2zm5.8 14.06c-.24.68-1.42 1.31-1.96 1.36-.54.05-1.04.24-3.52-.73-2.99-1.18-4.86-4.29-5.01-4.49-.15-.2-1.2-1.6-1.2-3.05 0-1.45.76-2.16 1.03-2.46.27-.29.59-.37.78-.37s.39 0 .56.01c.18.01.42-.07.66.5.24.59.83 2.03.9 2.18.07.15.12.32.02.51-.1.2-.15.32-.29.5s-.3.4-.43.53c-.15.15-.3.31-.13.6.17.29.76 1.25 1.62 2.02 1.11.99 2.05 1.3 2.34 1.45.29.15.46.12.63-.07.17-.2.73-.85.92-1.14.2-.29.39-.24.66-.15.27.1 1.71.81 2 .96.29.15.49.22.56.34.07.13.07.75-.17 1.43z"/></svg>
                </a>
              ` : ''}
            </div>
            <div class="text-[11px] text-slate-500 flex flex-col gap-0.5 mt-0.5">
              ${phone ? `<span class="font-mono">${escapeHtml(phone)}</span>` : ''}
              ${email ? `<span class="text-slate-400 truncate max-w-[180px]">${escapeHtml(email)}</span>` : ''}
            </div>
          </td>

          <!-- Vehicle & Tyre Size -->
          <td class="py-4 px-4">
            <div class="inline-flex items-center px-2 py-0.5 rounded-md bg-[#EFF6FF] text-[#1D4ED8] font-black text-xs">
              ${escapeHtml(tyreSize)}
            </div>
            <div class="text-[11px] font-bold text-[#0E1108] truncate max-w-[160px] mt-1">
              ${escapeHtml(vehicle)}
            </div>
          </td>

          <!-- City / Fitting -->
          <td class="py-4 px-4">
            <div class="font-bold text-[#0E1108]">${escapeHtml(city)}</div>
            <div class="text-[11px] text-slate-400 truncate max-w-[140px]">${escapeHtml(spec)}</div>
          </td>

          <!-- Source Type -->
          <td class="py-4 px-4">
            ${getSourceBadge(item.form_type, item.enquiry_for)}
          </td>

          <!-- Status -->
          <td class="py-4 px-4">
            ${getStatusBadge(item.status)}
          </td>

          <!-- Actions -->
          <td class="py-4 px-4 text-right sm:pr-6">
            <div class="inline-flex items-center gap-1.5">
              <button type="button" class="btn-view-lead px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-[#EFF6FF] text-slate-700 hover:text-[#1D4ED8] font-bold text-xs transition-colors cursor-pointer" data-id="${id}">
                View Details
              </button>
              <button type="button" class="btn-delete-lead w-8 h-8 rounded-xl bg-slate-100 hover:bg-rose-50 text-slate-400 hover:text-rose-600 flex items-center justify-center transition-colors cursor-pointer" data-id="${id}" title="Delete enquiry">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </td>
        </tr>
        `;
      })
      .join('');

    const cardsHtml = list
      .map((item) => {
        const id = item.enquiry_id;
        const name = item.name || 'Storefront Visitor';
        const phone = item.number || '';
        const email = item.email || '';
        const tyreSize = item.tyre_size || '--';
        const vehicle = item.vehicle || (item.make ? `${item.make} ${item.model || ''} ${item.year || ''}`.trim() : '--');
        const city = item.city || '--';
        const spec = item.spec || '--';
        const dateStr = item.created_at || '--';

        const phoneClean = phone ? phone.replace(/[^\d+]/g, '') : '';
        const waLink = phoneClean
          ? `https://wa.me/${phoneClean.replace('+', '')}?text=${encodeURIComponent(`Hi ${name}, thank you for contacting TyresVision.`)}`
          : `https://wa.me/971505069575`;

        return `
        <div class="p-3.5 sm:p-4 space-y-2.5 bg-white hover:bg-[#F8FAF7]/60 transition-colors">
          <!-- Card Top: ID, Date, Badges -->
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-2 min-w-0">
              <span class="font-black text-sm text-[#0E1108]">#${id}</span>
              <span class="text-[11px] text-slate-400 font-medium whitespace-nowrap truncate">${escapeHtml(dateStr)}</span>
            </div>
            <div class="flex items-center gap-1.5 flex-wrap justify-end shrink-0">
              ${getStatusBadge(item.status)}
              ${getSourceBadge(item.form_type, item.enquiry_for)}
            </div>
          </div>

          <!-- Customer Info -->
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <div class="font-extrabold text-sm text-[#0E1108] truncate">${escapeHtml(name)}</div>
              <div class="flex items-center gap-3 mt-1 text-xs text-slate-600 flex-wrap">
                ${phone ? `
                  <a href="tel:${escapeHtml(phone)}" class="inline-flex items-center gap-1 text-slate-700 hover:text-[#2563FF] font-mono font-bold">
                    <svg class="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
                    ${escapeHtml(phone)}
                  </a>
                ` : ''}
                ${email ? `
                  <span class="text-slate-400 truncate max-w-[180px] text-[11px]">${escapeHtml(email)}</span>
                ` : ''}
              </div>
            </div>
            ${phone ? `
              <a href="${waLink}" target="_blank" title="Chat on WhatsApp" class="shrink-0 w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 hover:bg-emerald-100 flex items-center justify-center transition-colors shadow-2xs">
                <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.46 1.32 4.96L2 22l5.25-1.38a9.9 9.9 0 004.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91C21.96 6.45 17.5 2 12.04 2zm5.8 14.06c-.24.68-1.42 1.31-1.96 1.36-.54.05-1.04.24-3.52-.73-2.99-1.18-4.86-4.29-5.01-4.49-.15-.2-1.2-1.6-1.2-3.05 0-1.45.76-2.16 1.03-2.46.27-.29.59-.37.78-.37s.39 0 .56.01c.18.01.42-.07.66.5.24.59.83 2.03.9 2.18.07.15.12.32.02.51-.1.2-.15.32-.29.5s-.3.4-.43.53c-.15.15-.3.31-.13.6.17.29.76 1.25 1.62 2.02 1.11.99 2.05 1.3 2.34 1.45.29.15.46.12.63-.07.17-.2.73-.85.92-1.14.2-.29.39-.24.66-.15.27.1 1.71.81 2 .96.29.15.49.22.56.34.07.13.07.75-.17 1.43z"/></svg>
              </a>
            ` : ''}
          </div>

          <!-- Specs Box -->
          <div class="p-2.5 sm:p-3 rounded-xl bg-[#F6F8F3] border border-[#E3E7DE]/80 text-xs space-y-1.5">
            <div class="flex items-center justify-between gap-2">
              <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wide">Tyre Size:</span>
              <span class="inline-flex items-center px-2.5 py-0.5 rounded-md bg-[#EFF6FF] text-[#1D4ED8] font-black text-xs">
                ${escapeHtml(tyreSize)}
              </span>
            </div>
            ${vehicle && vehicle !== '--' ? `
              <div class="flex items-center justify-between gap-2 text-[11px]">
                <span class="text-slate-400 font-medium">Vehicle:</span>
                <span class="font-bold text-[#0E1108] text-right truncate max-w-[200px]">${escapeHtml(vehicle)}</span>
              </div>
            ` : ''}
            ${(city && city !== '--') || (spec && spec !== '--') ? `
              <div class="flex items-center justify-between gap-2 text-[11px]">
                <span class="text-slate-400 font-medium">Location / Fitting:</span>
                <span class="font-semibold text-slate-700 text-right truncate max-w-[200px]">${escapeHtml(city)}${spec && spec !== '--' ? ' • ' + escapeHtml(spec) : ''}</span>
              </div>
            ` : ''}
          </div>

          <!-- Actions -->
          <div class="flex items-center justify-between gap-2 pt-1">
            <button type="button" class="btn-view-lead flex-1 inline-flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#EFF6FF] hover:bg-blue-100 text-[#1D4ED8] font-extrabold text-xs transition-colors cursor-pointer shadow-2xs active:scale-95" data-id="${id}">
              <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
              <span>View Details</span>
            </button>
            <button type="button" class="btn-delete-lead w-9 h-9 rounded-xl bg-slate-100 hover:bg-rose-50 text-slate-400 hover:text-rose-600 flex items-center justify-center transition-colors cursor-pointer shrink-0 active:scale-95" data-id="${id}" title="Delete enquiry">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
        `;
      })
      .join('');

    if (tableBody) {
      tableBody.innerHTML = html;
    }
    if (mobileCardsContainer) {
      mobileCardsContainer.innerHTML = cardsHtml;
    }
    attachRowEvents();
  }

  function attachRowEvents() {
    // View Details Buttons
    document.querySelectorAll('.btn-view-lead').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const id = parseInt(e.currentTarget.getAttribute('data-id'), 10);
        openDetailModal(id);
      });
    });

    // Delete Buttons
    document.querySelectorAll('.btn-delete-lead').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        e.preventDefault();
        const id = parseInt(e.currentTarget.getAttribute('data-id'), 10);
        if (confirm(`Are you sure you want to delete lead #${id}?`)) {
          await deleteEnquiry(id);
        }
      });
    });
  }

  function openDetailModal(id) {
    const item = allEnquiries.find((x) => x.enquiry_id === id);
    if (!item) return;

    activeEnquiry = item;

    if (modalIdBadge) modalIdBadge.textContent = `ENQUIRY #${item.enquiry_id}`;
    if (modalStatusBadge) modalStatusBadge.innerHTML = getStatusBadge(item.status);
    if (modalTitle) modalTitle.textContent = `${item.name || 'Visitor'} — Quotation Lead`;

    if (modalCustName) modalCustName.textContent = item.name || 'Storefront Visitor';
    if (modalCustPhone) modalCustPhone.textContent = item.number || 'Not provided';
    if (modalCustEmail) modalCustEmail.textContent = item.email || 'Not provided';

    if (modalTyreSize) modalTyreSize.textContent = item.tyre_size || '--';
    if (modalVehicle) modalVehicle.textContent = item.vehicle || (item.make ? `${item.make} ${item.model || ''} ${item.year || ''}`.trim() : '--');
    if (modalCity) modalCity.textContent = item.city || '--';
    if (modalSpec) modalSpec.textContent = item.spec || '--';

    if (modalMessageBox) modalMessageBox.textContent = item.message || 'No additional message details.';
    if (modalStatusSelect) modalStatusSelect.value = String(item.status || 0);

    // Direct WhatsApp reply link
    if (btnWaReply) {
      const phoneClean = item.number ? item.number.replace(/[^\d+]/g, '') : '';
      if (phoneClean) {
        btnWaReply.href = `https://wa.me/${phoneClean.replace('+', '')}?text=${encodeURIComponent(`Hi ${item.name || ''}, regarding your tyre enquiry for ${item.tyre_size || 'your vehicle'} on TyresVision:`)}`;
      } else {
        btnWaReply.href = 'https://wa.me/971505069575';
      }
    }

    if (modal) {
      modal.classList.remove('hidden');
    }
  }

  function closeModal() {
    if (modal) {
      modal.classList.add('hidden');
      activeEnquiry = null;
    }
  }

  async function updateStatus(id, newStatus) {
    try {
      const resp = await fetch(`/visionadmin/api/v1/enquiries/${id}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });
      const data = await resp.json();
      if (!data.success) throw new Error(data.error || 'Failed to update status');

      // Update in memory
      const target = allEnquiries.find((x) => x.enquiry_id === id);
      if (target) {
        target.status = parseInt(newStatus, 10);
      }

      closeModal();
      loadEnquiries();
    } catch (err) {
      alert('Error updating status: ' + err.message);
    }
  }

  async function deleteEnquiry(id) {
    try {
      const resp = await fetch(`/visionadmin/api/v1/enquiries/${id}`, {
        method: 'DELETE',
        headers: { 'Accept': 'application/json' }
      });
      const data = await resp.json();
      if (!data.success) throw new Error(data.error || 'Failed to delete lead');

      allEnquiries = allEnquiries.filter((x) => x.enquiry_id !== id);
      closeModal();
      loadEnquiries();
    } catch (err) {
      alert('Error deleting enquiry: ' + err.message);
    }
  }

  async function truncateEnquiries() {
    if (!confirm('Are you sure you want to delete ALL enquiries and truncate the table? This action cannot be undone.')) {
      return;
    }
    try {
      const resp = await fetch('/visionadmin/api/v1/enquiries/truncate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }
      });
      const data = await resp.json();
      if (!data.success) throw new Error(data.error || 'Failed to clear leads');

      allEnquiries = [];
      closeModal();
      loadEnquiries();
    } catch (err) {
      alert('Error clearing enquiries: ' + err.message);
    }
  }

  // ================= EVENT LISTENERS =================
  if (btnRefresh) {
    btnRefresh.addEventListener('click', loadEnquiries);
  }

  if (btnTruncate) {
    btnTruncate.addEventListener('click', truncateEnquiries);
  }

  // Tab Filtering
  tabBtns.forEach((btn) => {
    btn.addEventListener('click', (e) => {
      tabBtns.forEach((b) => {
        b.classList.remove('bg-white', 'text-[#0E1108]', 'shadow-xs', 'font-extrabold');
        b.classList.add('text-slate-600', 'font-bold');
      });
      const target = e.currentTarget;
      target.classList.add('bg-white', 'text-[#0E1108]', 'shadow-xs', 'font-extrabold');
      target.classList.remove('text-slate-600', 'font-bold');

      currentStatusFilter = target.getAttribute('data-status') || 'all';
      renderTable();
    });
  });

  // Search Debounce
  let searchTimeout = null;
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        currentSearchQuery = e.target.value.trim();
        renderTable();
      }, 300);
    });
  }

  // Type Filter (Custom Styled Dropdown)
  const sourceFilterBtn = document.getElementById('source-filter-btn');
  const sourceFilterMenu = document.getElementById('source-filter-menu');
  const sourceFilterChevron = document.getElementById('source-filter-chevron');
  const sourceFilterLabel = document.getElementById('source-filter-label');
  const optionButtons = document.querySelectorAll('.source-option-btn');

  if (sourceFilterBtn && sourceFilterMenu) {
    sourceFilterBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isHidden = sourceFilterMenu.classList.contains('hidden');
      if (isHidden) {
        sourceFilterMenu.classList.remove('hidden');
        if (sourceFilterChevron) sourceFilterChevron.classList.add('rotate-180');
        sourceFilterBtn.setAttribute('aria-expanded', 'true');
      } else {
        sourceFilterMenu.classList.add('hidden');
        if (sourceFilterChevron) sourceFilterChevron.classList.remove('rotate-180');
        sourceFilterBtn.setAttribute('aria-expanded', 'false');
      }
    });

    document.addEventListener('click', (e) => {
      if (!sourceFilterMenu.contains(e.target) && !sourceFilterBtn.contains(e.target)) {
        sourceFilterMenu.classList.add('hidden');
        if (sourceFilterChevron) sourceFilterChevron.classList.remove('rotate-180');
        sourceFilterBtn.setAttribute('aria-expanded', 'false');
      }
    });

    optionButtons.forEach((optBtn) => {
      optBtn.addEventListener('click', () => {
        const val = optBtn.getAttribute('data-value') || 'all';
        const label = optBtn.getAttribute('data-label') || 'All Sources';

        if (sourceFilterLabel) sourceFilterLabel.textContent = label;
        if (typeFilter) typeFilter.value = val;

        optionButtons.forEach((b) => {
          const check = b.querySelector('.option-check');
          if (check) check.classList.add('opacity-0');
        });
        const currentCheck = optBtn.querySelector('.option-check');
        if (currentCheck) currentCheck.classList.remove('opacity-0');

        sourceFilterMenu.classList.add('hidden');
        if (sourceFilterChevron) sourceFilterChevron.classList.remove('rotate-180');
        sourceFilterBtn.setAttribute('aria-expanded', 'false');

        currentTypeFilter = val;
        renderTable();
      });
    });
  }

  // Modal Buttons
  if (btnCloseModal) {
    btnCloseModal.addEventListener('click', closeModal);
  }

  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  if (btnSaveStatus) {
    btnSaveStatus.addEventListener('click', () => {
      if (!activeEnquiry || !modalStatusSelect) return;
      updateStatus(activeEnquiry.enquiry_id, modalStatusSelect.value);
    });
  }

  if (btnDeleteModal) {
    btnDeleteModal.addEventListener('click', () => {
      if (!activeEnquiry) return;
      if (confirm(`Are you sure you want to delete enquiry #${activeEnquiry.enquiry_id}?`)) {
        deleteEnquiry(activeEnquiry.enquiry_id);
      }
    });
  }

  // Initialize on load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadEnquiries);
  } else {
    loadEnquiries();
  }
})();
