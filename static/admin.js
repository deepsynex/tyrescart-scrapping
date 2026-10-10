// Wires up every "show password" eye button on the page (Change Password modal,
// admin create/edit user form, reset-password page, etc). A button opts in with
// data-toggle-password="<id of the password input it controls>" and holds its
// own .icon-eye-open/.icon-eye-closed markup, scoped per-button rather than by
// id, so one page can have several password fields each with their own toggle.
// Runs on every page that loads this script, independent of the admin-page
// logic below.
(function () {
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-toggle-password]').forEach((btn) => {
      const input = document.getElementById(btn.getAttribute('data-toggle-password'));
      if (!input) return;

      const eyeOpen = btn.querySelector('.icon-eye-open');
      const eyeClosed = btn.querySelector('.icon-eye-closed');

      btn.addEventListener('click', () => {
        const showing = input.type === 'text';
        input.type = showing ? 'password' : 'text';
        if (eyeOpen) eyeOpen.classList.toggle('hidden', !showing);
        if (eyeClosed) eyeClosed.classList.toggle('hidden', showing);
      });
    });
  });
})();

// Shared helpers used by both the User Management page (below) and
// static/trash.js -- toasts, badges, the View modal, and common DataTable
// options, all in one place so the two pages render identically.
window.AdminShared = (function () {
  const openModal = (el) => el.classList.remove('hidden');
  const closeModal = (el) => el.classList.add('hidden');

  const showError = (el, message) => {
    el.textContent = message;
    el.classList.remove('hidden');
  };
  const hideError = (el) => {
    el.classList.add('hidden');
    el.textContent = '';
  };

  const escapeHtml = (str) => {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  };

  // Structured console error logger for debugging
  const logError = (context, error, extraDetails = null) => {
    console.error(
      `%c[TyresVision Error: ${context}]`,
      'background: #be123c; color: #fff; font-weight: bold; padding: 2px 6px; border-radius: 4px;',
      error,
      extraDetails || ''
    );
  };

  const logWarn = (context, message, extraDetails = null) => {
    console.warn(
      `%c[TyresVision Warning: ${context}]`,
      'background: #d97706; color: #fff; font-weight: bold; padding: 2px 6px; border-radius: 4px;',
      message,
      extraDetails || ''
    );
  };

  // Global uncaught error listener
  window.addEventListener('error', (event) => {
    logError('Uncaught Runtime Error', event.error || event.message, {
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    });
  });

  window.addEventListener('unhandledrejection', (event) => {
    logError('Unhandled Promise Rejection', event.reason);
  });

  // --- Toast notifications: floating confirmations for user clicks & actions ---
  let toastContainer = null;

  function getToastContainer() {
    if (toastContainer) return toastContainer;
    toastContainer = document.createElement('div');
    toastContainer.setAttribute('aria-live', 'polite');
    toastContainer.style.cssText =
      'position:fixed; top:1rem; right:1rem; z-index:9999; display:flex; flex-direction:column; gap:0.5rem; max-width:24rem; pointer-events:none;';
    document.body.appendChild(toastContainer);
    return toastContainer;
  }

  function showToast(message, type = 'success') {
    const container = getToastContainer();

    let bg = '#ecfdf5';
    let border = '#a7f3d0';
    let text = '#047857';
    let iconSvg = '<svg class="w-4 h-4 shrink-0 text-[#2563FF]" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>';

    if (type === 'error') {
      bg = '#fff1f2';
      border = '#fecdd3';
      text = '#be123c';
      iconSvg = '<svg class="w-4 h-4 shrink-0 text-rose-600" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/></svg>';
    } else if (type === 'info') {
      bg = '#eff6ff';
      border = '#bfdbfe';
      text = '#1d4ed8';
      iconSvg = '<svg class="w-4 h-4 shrink-0 text-blue-600" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/></svg>';
    } else if (type === 'warning') {
      bg = '#fffbeb';
      border = '#fde68a';
      text = '#b45309';
      iconSvg = '<svg class="w-4 h-4 shrink-0 text-amber-600" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>';
    }

    const toast = document.createElement('div');
    toast.innerHTML = `
      <div style="display:flex; align-items:center; gap:0.5rem;">
        ${iconSvg}
        <span>${escapeHtml(message)}</span>
      </div>
    `;
    toast.style.cssText = `
      pointer-events: auto;
      padding: 0.75rem 1rem;
      border-radius: 0.75rem;
      font-size: 0.8125rem;
      font-weight: 600;
      line-height: 1.3;
      box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1);
      border: 1px solid ${border};
      background-color: ${bg};
      color: ${text};
      opacity: 0;
      transform: translateY(-6px);
      transition: opacity 0.2s ease, transform 0.2s ease;
    `;
    container.appendChild(toast);

    requestAnimationFrame(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateY(0)';
    });

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-6px)';
      setTimeout(() => toast.remove(), 200);
    }, 3500);
  }

  function initial(row) {
    const source = (row.name || row.email || '?').trim();
    return (source.charAt(0) || '?').toUpperCase();
  }

  function avatarHtml(row) {
    const safeInitial = escapeHtml(initial(row));
    if (row.avatar) {
      const safeUrl = escapeHtml(row.avatar);
      // Initials sit behind the <img>; if the image 404s, onerror hides it and
      // the initials underneath show through -- no broken-image icon.
      return `
        <span class="relative inline-flex w-8 h-8 rounded-full bg-blue-100 text-blue-700 items-center justify-center text-xs font-semibold overflow-hidden align-middle">
          <span class="absolute inset-0 flex items-center justify-center">${safeInitial}</span>
          <img src="${safeUrl}" alt="" class="relative w-8 h-8 rounded-full object-cover" onerror="this.style.display='none'" />
        </span>`;
    }
    return `<span class="inline-flex w-8 h-8 rounded-full bg-blue-100 text-blue-700 items-center justify-center text-xs font-semibold align-middle">${safeInitial}</span>`;
  }

  // Fills the leftmost "#" column with a sequential row number based on
  // actual current display order (after sort + search), continuous across
  // pages (page 2 at 10/page starts at #11, not #1 again). Must be called
  // after every draw (sort/search/page-change all redraw), since a fixed
  // per-row value computed at render time can't reflect where a row ends up
  // once the user sorts by a different column.
  function renumberRows(table, columnIndex) {
    const pageStart = table.page.info().start;
    // page: 'current' is essential -- without it .nodes() returns matching
    // rows across ALL pages (not just the visible one), which would throw
    // the pageStart + i arithmetic off for every page after the first.
    table.column(columnIndex, { page: 'current', order: 'applied', search: 'applied' }).nodes().each((cell, i) => {
      cell.innerHTML = `<span class="text-xs font-medium text-slate-400">#${pageStart + i + 1}</span>`;
    });
  }

  function roleBadgeHtml(role) {
    const classes = role === 'SuperAdmin'
      ? 'bg-violet-100 text-violet-700'
      : role === 'Admin'
        ? 'bg-sky-100 text-sky-700'
        : 'bg-slate-100 text-slate-600';
    return `<span class="px-2 py-0.5 rounded-full text-xs font-semibold ${classes}">${escapeHtml(role)}</span>`;
  }

  // Active -> green, Inactive -> gray, Deleted -> red. The Trash page always
  // passes isDeleted:true rows here, so it always renders the red badge.
  function statusText(row) {
    return row.isDeleted ? 'Deleted' : row.status ? 'Active' : 'Inactive';
  }

  function statusBadgeHtml(row) {
    if (row.isDeleted) return '<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-700">Deleted</span>';
    if (row.status) return '<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700">Active</span>';
    return '<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-200 text-slate-500">Inactive</span>';
  }

  // Takes a UTC ISO timestamp (createdAtRaw/deletedAtRaw -- the server and DB
  // both run in UTC) and converts it to the viewer's own local timezone
  // before formatting, rather than showing raw server time. Without this, a
  // user anywhere ahead of UTC sees timestamps that look hours "in the past".
  function formatLocalDateTime(isoString) {
    if (!isoString) return null;
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return null;
    // en-GB with numeric day/month/year yields "DD/MM/YYYY" -- swap the
    // slashes for dashes to match the DD-MM-YYYY convention used everywhere.
    const dmy = d.toLocaleDateString('en-GB', { timeZone: 'Asia/Kolkata', day: '2-digit', month: '2-digit', year: 'numeric' });
    return {
      datePart: dmy.replace(/\//g, '-'),
      timePart: d.toLocaleTimeString('en-US', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true }),
    };
  }

  function dateTimeText(isoString) {
    const parts = formatLocalDateTime(isoString);
    return parts ? `${parts.datePart}, ${parts.timePart}` : '—';
  }

  // Splits into date + time and colors each differently, so the time isn't
  // lost among the date at a glance.
  function dateTimeHtml(isoString) {
    const parts = formatLocalDateTime(isoString);
    if (!parts) return '<span class="text-slate-400">—</span>';
    return `<span class="text-slate-700 font-medium">${escapeHtml(parts.datePart)}</span> <span class="text-[#2563FF]">${escapeHtml(parts.timePart)}</span>`;
  }

  function openViewModal(row) {
    const modal = document.getElementById('admin-view-modal');
    if (!modal) return;

    document.getElementById('admin-view-name').textContent = row.name || '—';
    document.getElementById('admin-view-email').textContent = row.email || '—';
    document.getElementById('admin-view-role').textContent = row.role || '—';
    document.getElementById('admin-view-status').textContent = statusText(row);
    document.getElementById('admin-view-created').textContent = dateTimeText(row.createdAtRaw);

    const deletedRow = document.getElementById('admin-view-deleted-row');
    if (row.isDeleted) {
      document.getElementById('admin-view-deleted').textContent = dateTimeText(row.deletedAtRaw);
      deletedRow.classList.remove('hidden');
    } else {
      deletedRow.classList.add('hidden');
    }

    const avatarEl = document.getElementById('admin-view-avatar');
    avatarEl.innerHTML = '';
    if (row.avatar) {
      const img = document.createElement('img');
      img.src = row.avatar;
      img.alt = '';
      img.className = 'w-full h-full object-cover';
      img.onerror = () => {
        avatarEl.innerHTML = '';
        avatarEl.textContent = initial(row);
      };
      avatarEl.appendChild(img);
    } else {
      avatarEl.textContent = initial(row);
    }

    openModal(modal);
  }

  // Shared DataTables config: search, sort, paging, page-length selector
  // (10/25/50/100, default 10), responsive collapsing, and First/Prev/Next/Last
  // pagination controls (pagingType: full_numbers).
  function commonDataTableOptions(overrides) {
    return Object.assign(
      {
        pageLength: 10,
        lengthMenu: [10, 25, 50, 100],
        pagingType: 'full_numbers',
        responsive: true,
        autoWidth: false,
        language: {
          search: '',
          searchPlaceholder: 'Search name, email, status…',
          lengthMenu: 'Show _MENU_ per page',
          info: 'Showing _START_ to _END_ of _TOTAL_',
          infoEmpty: 'No users to show',
          infoFiltered: '(filtered from _MAX_ total)',
          paginate: { first: 'First', last: 'Last', next: 'Next', previous: 'Previous' },
        },
      },
      overrides
    );
  }

  return {
    openModal,
    closeModal,
    showError,
    hideError,
    escapeHtml,
    logError,
    logWarn,
    showToast,
    avatarHtml,
    renumberRows,
    roleBadgeHtml,
    statusBadgeHtml,
    statusText,
    dateTimeHtml,
    dateTimeText,
    openViewModal,
    commonDataTableOptions,
  };
})();

// --- User Management ("All Users") page ---
(function () {
  const tableEl = document.getElementById('users-table');
  if (!tableEl) return; // Not on the User Management page.

  const Shared = window.AdminShared;
  const errorEl = document.getElementById('admin-error');
  const newUserBtn = document.getElementById('admin-new-user-btn');
  const loadingEl = document.getElementById('admin-loading');

  const modal = document.getElementById('admin-user-modal');
  const modalTitle = document.getElementById('admin-modal-title');
  const modalError = document.getElementById('admin-modal-error');
  const form = document.getElementById('admin-user-form');
  const idInput = document.getElementById('admin-user-id');
  const nameInput = document.getElementById('admin-user-name');
  const emailInput = document.getElementById('admin-user-email');
  const passwordInput = document.getElementById('admin-user-password');
  const passwordHint = document.getElementById('admin-user-password-hint');
  const roleSelect = document.getElementById('admin-user-role');
  const statusInput = document.getElementById('admin-user-status');
  const submitBtn = document.getElementById('admin-user-submit');
  const submitLabel = document.getElementById('admin-user-submit-label');

  const deleteModal = document.getElementById('admin-delete-modal');
  const deleteText = document.getElementById('admin-delete-text');
  const deleteError = document.getElementById('admin-delete-error');
  const deleteConfirmBtn = document.getElementById('admin-delete-confirm');

  let csrfToken = null;
  let currentRole = null;
  let currentUserId = null;
  let users = [];
  let pendingDeleteId = null;
  let table = null;

  function actionsCellHtml(row) {
    const isSelf = row.userId === currentUserId;
    const canDelete = (currentRole === 'SuperAdmin' || currentRole === 'Admin') && row.role !== 'SuperAdmin' && !isSelf;
    const deleteDisabledReason = row.role === 'SuperAdmin'
      ? 'SuperAdmin accounts can never be deleted'
      : isSelf
        ? 'You cannot delete your own account'
        : '';
    return `
      <div class="flex items-center justify-end gap-3">
        <button type="button" data-action="view" data-id="${row.userId}" class="text-xs font-semibold text-slate-500 hover:underline cursor-pointer">View</button>
        <button type="button" data-action="edit" data-id="${row.userId}" class="text-xs font-semibold text-[#2563FF] hover:underline cursor-pointer">Edit</button>
        <button type="button" data-action="delete" data-id="${row.userId}" ${canDelete ? '' : `disabled title="${deleteDisabledReason}"`}
          class="text-xs font-semibold ${canDelete ? 'text-rose-600 hover:underline cursor-pointer' : 'text-slate-300 cursor-not-allowed'}">Delete</button>
      </div>`;
  }

  function initTable() {
    table = $(tableEl).DataTable(Shared.commonDataTableOptions({
      data: [],
      order: [[1, 'asc']],
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
          data: null,
          render: (data, type, row) => (type === 'display' ? Shared.roleBadgeHtml(row.role) : row.role),
        },
        {
          data: null,
          render: (data, type, row) => (type === 'display' ? Shared.statusBadgeHtml(row) : Shared.statusText(row)),
        },
        {
          data: null,
          render: (data, type, row) => {
            if (type === 'display') return Shared.dateTimeHtml(row.createdAtRaw);
            return row.createdAtRaw || '';
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
      currentUserId = data.user ? data.user.userId : null;
      // Only a SuperAdmin can add a user -- an Admin can still view/edit/delete,
      // so hide the button that would otherwise just 403.
      newUserBtn.classList.toggle('hidden', currentRole !== 'SuperAdmin');
    } catch (err) {
      // Leave currentRole/currentUserId null -- loadUsers() will still run and
      // any action attempted without a CSRF token will just get a clear 403.
    }
  }

  function showTable() {
    loadingEl.classList.add('hidden');
    tableEl.classList.remove('hidden');
  }

  const USERS_CACHE_KEY = 'tyresvision_users_cache';

  function loadCachedUsers() {
    try {
      const raw = localStorage.getItem(USERS_CACHE_KEY);
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

  async function loadUsers({ silent } = {}) {
    if (!silent && !users.length) Shared.hideError(errorEl);
    try {
      const response = await fetch('/tcsadmin/api/admin/users');
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message = data.error || 'Unable to load users.';
        Shared.logError('Admin Load Users', message, { status: response.status });
        Shared.showError(errorEl, message);
        if (!silent) Shared.showToast(message, 'error');
        return;
      }
      users = data.users || [];
      try {
        localStorage.setItem(USERS_CACHE_KEY, JSON.stringify(data));
      } catch (e) {}
      table.clear();
      table.rows.add(users);
      table.draw(false);
    } catch (err) {
      Shared.logError('Admin Load Users Network Error', err);
      Shared.showError(errorEl, 'Network error while loading users.');
      if (!silent) Shared.showToast('Network error while loading users.', 'error');
    } finally {
      showTable();
    }
  }

  function updateRoleOptions(user) {
    roleSelect.innerHTML = '';
    if (user && user.role === 'SuperAdmin') {
      const opt = document.createElement('option');
      opt.value = 'SuperAdmin';
      opt.textContent = 'SuperAdmin';
      roleSelect.appendChild(opt);
      roleSelect.value = 'SuperAdmin';
      roleSelect.disabled = true;
      roleSelect.classList.add('bg-slate-100', 'cursor-not-allowed', 'text-slate-500');
    } else {
      roleSelect.disabled = false;
      roleSelect.classList.remove('bg-slate-100', 'cursor-not-allowed', 'text-slate-500');
      const optUser = document.createElement('option');
      optUser.value = 'User';
      optUser.textContent = 'User';
      const optAdmin = document.createElement('option');
      optAdmin.value = 'Admin';
      optAdmin.textContent = 'Admin';
      roleSelect.appendChild(optUser);
      roleSelect.appendChild(optAdmin);
      roleSelect.value = (user && user.role) ? user.role : 'User';
    }
  }

  function resetForm() {
    form.reset();
    idInput.value = '';
    Shared.hideError(modalError);
    updateRoleOptions(null);
    statusInput.checked = true;
  }

  function openCreateModal() {
    resetForm();
    modalTitle.textContent = 'New User';
    submitLabel.textContent = 'Create User';
    updateRoleOptions(null);
    passwordInput.required = true;
    passwordHint.classList.add('hidden');
    Shared.openModal(modal);
  }

  function openEditModal(user) {
    resetForm();
    modalTitle.textContent = 'Edit User';
    submitLabel.textContent = 'Save Changes';
    idInput.value = user.userId;
    nameInput.value = user.name;
    emailInput.value = user.email;
    updateRoleOptions(user);
    statusInput.checked = !!user.status;
    passwordInput.required = false;
    passwordHint.classList.remove('hidden');
    Shared.openModal(modal);
  }

  async function handleFormSubmit(event) {
    event.preventDefault();
    Shared.hideError(modalError);

    const id = idInput.value;
    const editingUser = id ? usersById.get(Number(id)) : null;
    const selectedRole = (editingUser && editingUser.role === 'SuperAdmin') ? 'SuperAdmin' : roleSelect.value;
    const payload = {
      name: nameInput.value.trim(),
      email: emailInput.value.trim(),
      role: selectedRole,
      status: statusInput.checked,
    };
    if (passwordInput.value) {
      payload.password = passwordInput.value;
    }

    submitBtn.disabled = true;
    Shared.showToast(id ? 'Saving user changes…' : 'Creating new user…', 'info');
    try {
      const response = await fetch(id ? `/tcsadmin/api/admin/users/${id}` : '/tcsadmin/api/admin/users', {
        method: id ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message = data.error || 'Unable to save user.';
        Shared.logError('Save User', message, { id, payload, status: response.status });
        Shared.showError(modalError, message);
        Shared.showToast(message, 'error');
        return;
      }
      Shared.closeModal(modal);
      Shared.showToast(id ? 'User updated successfully.' : 'User created successfully.', 'success');
      await loadUsers();
    } catch (err) {
      Shared.logError('Save User Network Error', err, { id, payload });
      Shared.showError(modalError, 'Network error. Please try again.');
      Shared.showToast('Network error. Please try again.', 'error');
    } finally {
      submitBtn.disabled = false;
    }
  }

  async function handleDeleteConfirm() {
    if (!pendingDeleteId) return;
    Shared.hideError(deleteError);
    deleteConfirmBtn.disabled = true;
    Shared.showToast('Moving user to trash…', 'info');
    try {
      const response = await fetch(`/tcsadmin/api/admin/users/${pendingDeleteId}`, {
        method: 'DELETE',
        headers: { 'X-CSRF-Token': csrfToken },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message = data.error || 'Unable to delete user.';
        Shared.logError('Delete User', message, { userId: pendingDeleteId, status: response.status });
        Shared.showError(deleteError, message);
        Shared.showToast(message, 'error');
        return;
      }
      Shared.closeModal(deleteModal);
      pendingDeleteId = null;
      Shared.showToast('User moved to Trash.', 'success');
      await loadUsers();
    } catch (err) {
      Shared.logError('Delete User Network Error', err, { userId: pendingDeleteId });
      Shared.showError(deleteError, 'Network error. Please try again.');
      Shared.showToast('Network error. Please try again.', 'error');
    } finally {
      deleteConfirmBtn.disabled = false;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    initTable();

    // Wired up synchronously, before the async data load below -- so even if
    // loadMe()/loadUsers() fails, every button already does something instead
    // of silently appearing dead.
    newUserBtn.addEventListener('click', openCreateModal);
    form.addEventListener('submit', handleFormSubmit);
    deleteConfirmBtn.addEventListener('click', handleDeleteConfirm);

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
      if (action === 'edit') {
        openEditModal(user);
        return;
      }
      if (action === 'delete') {
        pendingDeleteId = id;
        deleteText.textContent = `This will move "${user.name}"'s account to Trash. They will no longer be able to log in.`;
        Shared.hideError(deleteError);
        Shared.openModal(deleteModal);
      }
    });

    loadCachedUsers();
    loadMe().then(() => loadUsers({ silent: Boolean(users.length) }));
  });
})();
