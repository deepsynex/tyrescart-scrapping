// Trash page: lists soft-deleted users only. Restore is a SuperAdmin-only
// action (enforced server-side too) -- an Admin can still view the Trash and
// see who's in it, just can't restore anyone.
(function () {
  const tableEl = document.getElementById('trash-table');
  if (!tableEl) return; // Not on the Trash page.

  const Shared = window.AdminShared;
  const errorEl = document.getElementById('trash-error');
  const loadingEl = document.getElementById('trash-loading');

  const restoreModal = document.getElementById('trash-restore-modal');
  const restoreText = document.getElementById('trash-restore-text');
  const restoreError = document.getElementById('trash-restore-error');
  const restoreConfirmBtn = document.getElementById('trash-restore-confirm');

  let csrfToken = null;
  let currentRole = null;
  let users = [];
  let pendingId = null;
  let table = null;

  function actionsCellHtml(row) {
    const canAct = currentRole === 'SuperAdmin';
    const disabledAttr = canAct ? '' : 'disabled title="Only a SuperAdmin can restore this account"';
    const enabledClass = 'hover:underline cursor-pointer';
    const disabledClass = 'text-slate-300 cursor-not-allowed';
    return `
      <div class="flex items-center justify-end gap-3">
        <button type="button" data-action="view" data-id="${row.userId}" class="text-xs font-semibold text-slate-500 hover:underline cursor-pointer">View</button>
        <button type="button" data-action="restore" data-id="${row.userId}" ${disabledAttr}
          class="text-xs font-semibold ${canAct ? `text-[#2563FF] ${enabledClass}` : disabledClass}">Restore</button>
      </div>`;
  }

  function initTable() {
    table = $(tableEl).DataTable(Shared.commonDataTableOptions({
      data: [],
      order: [[3, 'desc']],
      language: Object.assign({}, Shared.commonDataTableOptions({}).language, {
        emptyTable: 'Trash is empty.',
        zeroRecords: 'No matching users found.',
      }),
      columns: [
        {
          data: null, orderable: false, searchable: false, className: 'text-center',
          render: () => '',
        },
        {
          data: null,
          render: (data, type, row) => (type === 'display' ? Shared.escapeHtml(row.name) : row.name),
        },
        {
          data: null,
          render: (data, type, row) => (type === 'display' ? Shared.escapeHtml(row.email) : row.email),
        },
        {
          // Trash always shows the Deleted state, per spec.
          data: null,
          render: (data, type, row) => (type === 'display' ? Shared.statusBadgeHtml(row) : 'Deleted'),
        },
        {
          data: null,
          render: (data, type, row) => {
            if (type === 'display') return Shared.dateTimeHtml(row.deletedAtRaw);
            return row.deletedAtRaw || '';
          },
        },
        {
          data: null, orderable: false, searchable: false, className: 'text-right',
          render: (data, type, row) => (type === 'display' ? actionsCellHtml(row) : ''),
        },
      ],
    }));
    table.on('draw', () => Shared.renumberRows(table, 0));
  }

  async function loadMe() {
    try {
      const response = await fetch('/tcsadmin/api/me');
      if (!response.ok) return;
      const data = await response.json();
      csrfToken = data.csrfToken;
      currentRole = data.user ? data.user.role : null;
    } catch (err) {
      // Leave currentRole null -- loadTrash() will still run and any action
      // attempted without a CSRF token will just get a clear 403.
    }
  }

  function showTable() {
    loadingEl.classList.add('hidden');
    tableEl.classList.remove('hidden');
  }

  const TRASH_CACHE_KEY = 'tyresvision_trash_cache';

  function loadCachedTrash() {
    try {
      const raw = localStorage.getItem(TRASH_CACHE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (data && Array.isArray(data.users) && data.users.length > 0) {
        users = data.users;
        table.clear();
        table.rows.add(users);
        table.draw(false);
        showTable();
      }
    } catch (e) {}
  }

  async function loadTrash({ silent } = {}) {
    if (!silent && !users.length) Shared.hideError(errorEl);
    try {
      const response = await fetch('/tcsadmin/api/admin/users/trash');
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message = data.error || 'Unable to load trash.';
        Shared.logError('Trash Load', message, { status: response.status });
        Shared.showError(errorEl, message);
        if (!silent) Shared.showToast(message, 'error');
        return;
      }
      users = data.users || [];
      try {
        localStorage.setItem(TRASH_CACHE_KEY, JSON.stringify(data));
      } catch (e) {}
      table.clear();
      table.rows.add(users);
      table.draw(false);
    } catch (err) {
      Shared.logError('Trash Load Network Error', err);
      Shared.showError(errorEl, 'Network error while loading trash.');
      if (!silent) Shared.showToast('Network error while loading trash.', 'error');
    } finally {
      showTable();
    }
  }

  async function handleRestoreConfirm() {
    if (!pendingId) return;
    Shared.hideError(restoreError);
    restoreConfirmBtn.disabled = true;
    Shared.showToast('Restoring user account…', 'info');
    try {
      const response = await fetch(`/tcsadmin/api/admin/users/${pendingId}/recover`, {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrfToken },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message = data.error || 'Unable to restore user.';
        Shared.logError('Restore User', message, { userId: pendingId, status: response.status });
        Shared.showError(restoreError, message);
        Shared.showToast(message, 'error');
        return;
      }
      Shared.closeModal(restoreModal);
      pendingId = null;
      Shared.showToast('User restored successfully to active accounts.', 'success');
      await loadTrash();
    } catch (err) {
      Shared.logError('Restore User Network Error', err, { userId: pendingId });
      Shared.showError(restoreError, 'Network error. Please try again.');
      Shared.showToast('Network error. Please try again.', 'error');
    } finally {
      restoreConfirmBtn.disabled = false;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    initTable();

    // Wired up synchronously, before the async data load below -- so even if
    // loadMe()/loadTrash() fails, every button already does something instead
    // of silently appearing dead.
    restoreConfirmBtn.addEventListener('click', handleRestoreConfirm);

    $(tableEl.tBodies[0]).on('click', 'button[data-action]', function () {
      const btn = this;
      if (btn.disabled) return;
      const action = btn.getAttribute('data-action');
      const id = btn.getAttribute('data-id');
      const user = users.find((u) => String(u.userId) === id);
      if (!user) return;

      if (action === 'view') {
        Shared.openViewModal(user);
        return;
      }
      if (action === 'restore') {
        pendingId = id;
        restoreText.textContent = `"${user.name}" will be restored and able to log in again.`;
        Shared.hideError(restoreError);
        Shared.openModal(restoreModal);
      }
    });

    loadCachedTrash();
    loadMe().then(() => loadTrash({ silent: Boolean(users.length) }));
  });
})();
