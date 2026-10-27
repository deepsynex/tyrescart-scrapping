/**
 * Tyrescart product sync: GraphQL -> IndexedDB -> compare with local DB -> review -> import.
 * Remote pages are staged in IndexedDB (ProductSyncDB) so a reload can resume the review
 * without re-downloading 9k products. Writes always go through the server, which re-fetches
 * the chosen SKUs from Tyrescart itself.
 *
 * The full catalog and diff live in plain closure variables, not Alpine state: making ~9k
 * records reactive froze the page. Alpine only sees counts and the current page of rows.
 */
(function () {
  const DB_NAME = 'ProductSyncDB';
  const DB_VERSION = 1;
  const STORE_REMOTE = 'remote_products';
  const STORE_META = 'sync_meta';
  const COMPARE_CHUNK = 1000;
  const IMPORT_CHUNK = 50;
  const PAGE_SIZE = 50;
  const FIELDS_KEY = 'psync.activeFields';

  let dbPromise = null;

  function openDB() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve) => {
      if (!window.indexedDB) return resolve(null);
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORE_REMOTE)) db.createObjectStore(STORE_REMOTE, { keyPath: 'sku' });
        if (!db.objectStoreNames.contains(STORE_META)) db.createObjectStore(STORE_META, { keyPath: 'key' });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    });
    return dbPromise;
  }

  function txDone(tx) {
    return new Promise((resolve) => {
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => resolve(false);
      tx.onabort = () => resolve(false);
    });
  }

  const idb = {
    async putMany(items) {
      const db = await openDB();
      if (!db) return false;
      const tx = db.transaction(STORE_REMOTE, 'readwrite');
      const store = tx.objectStore(STORE_REMOTE);
      items.forEach((it) => store.put(it));
      return txDone(tx);
    },
    async getAll() {
      const db = await openDB();
      if (!db) return [];
      return new Promise((resolve) => {
        const req = db.transaction(STORE_REMOTE, 'readonly').objectStore(STORE_REMOTE).getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => resolve([]);
      });
    },
    async getMeta(key) {
      const db = await openDB();
      if (!db) return null;
      return new Promise((resolve) => {
        const req = db.transaction(STORE_META, 'readonly').objectStore(STORE_META).get(key);
        req.onsuccess = () => resolve(req.result ? req.result.value : null);
        req.onerror = () => resolve(null);
      });
    },
    async setMeta(key, value) {
      const db = await openDB();
      if (!db) return false;
      const tx = db.transaction(STORE_META, 'readwrite');
      // JSON round-trip strips Alpine reactive proxies, which IndexedDB can't structured-clone.
      tx.objectStore(STORE_META).put({ key, value: JSON.parse(JSON.stringify(value)) });
      return txDone(tx);
    },
    async clear() {
      const db = await openDB();
      if (!db) return false;
      const tx = db.transaction([STORE_REMOTE, STORE_META], 'readwrite');
      tx.objectStore(STORE_REMOTE).clear();
      tx.objectStore(STORE_META).clear();
      return txDone(tx);
    },
  };

  function csrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  async function postJson(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
      body: JSON.stringify(body),
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* non-JSON error page */ }
    if (!res.ok || data.success === false) {
      throw new Error(data.error || `Request failed (HTTP ${res.status}).`);
    }
    return data;
  }

  function loadActiveFields(fields) {
    try {
      const saved = JSON.parse(localStorage.getItem(FIELDS_KEY) || 'null');
      if (Array.isArray(saved)) {
        const known = new Set(fields.map((f) => f.key));
        return saved.filter((k) => known.has(k));
      }
    } catch (e) { /* storage unavailable */ }
    return fields.filter((f) => f.default_on).map((f) => f.key);
  }

  const ENUM_LABELS = {
    stock_status: { in_stock: 'In stock', out_of_stock: 'Out of stock', backorder: 'Backorder' },
    status: { active: 'Enabled', inactive: 'Disabled' },
    visibility: { visible: 'Catalog, Search', catalog: 'Catalog', search: 'Search', not_visible: 'Not visible' },
  };

  function fmt(key, v) {
    if (v === null || v === undefined || v === '') return '—';
    if (typeof v === 'boolean') return v ? 'Yes' : 'No';
    if (ENUM_LABELS[key] && ENUM_LABELS[key][v]) return ENUM_LABELS[key][v];
    if (key === 'price' || key === 'price_per_item') return 'AED ' + Number(v).toLocaleString();
    const s = String(v);
    return s.length > 140 ? s.slice(0, 140) + '…' : s;
  }

  function productSyncApp() {
    // Non-reactive working set.
    let remote = {};
    let diff = { new: [], update: [], unchanged_count: 0 };
    let filtered = [];
    const selected = new Set(); // "n:SKU" | "u:SKU"
    let activeSet = new Set();
    let restorePromise = null;

    return {
      open: false,
      phase: 'idle', // idle | fetching | comparing | review | importing
      error: '',
      progress: { page: 0, totalPages: 0, fetched: 0, total: 0, compared: 0 },
      fetchedAt: null,

      categories: [],
      category: 'tyres',
      syncedCategory: '',

      fields: [],
      activeFields: [],
      fieldCounts: {},
      fieldsOpen: false,

      counts: { new: 0, update: 0, unchanged: 0 },
      tab: 'update',
      search: '',
      pageNo: 1,
      totalPages: 1,
      filteredCount: 0,
      pageRows: [],
      allFilteredSelected: false,
      selectedCount: 0,
      selectedNew: 0,
      selectedUpdate: 0,

      importProgress: { done: 0, total: 0 },
      importResult: null,

      initSync() {
        this.$watch('search', () => { this.pageNo = 1; this.refresh(); });
        restorePromise = Promise.all([this.loadCategories(), this.restoreSaved()]);
      },

      async loadCategories() {
        try {
          const res = await fetch('/visionadmin/api/products/sync/categories');
          const data = await res.json();
          if (data.success) {
            this.categories = data.categories;
            if (!this.syncedCategory) this.category = data.default;
          }
        } catch (e) { /* dropdown falls back to the default category */ }
      },

      categoryLabel(key) {
        const c = this.categories.find((x) => x.key === key);
        return c ? c.label : key;
      },

      async restoreSaved() {
        const saved = await idb.getMeta('diff');
        if (!saved) return;
        this.syncedCategory = (await idb.getMeta('category')) || 'tyres';
        this.category = this.syncedCategory;
        const items = await idb.getAll();
        remote = Object.fromEntries(items.map((it) => [it.sku, it]));
        diff = saved;
        this.fields = (await idb.getMeta('fields')) || [];
        this.setActiveFields(loadActiveFields(this.fields));
        this.fetchedAt = await idb.getMeta('fetchedAt');
        this.computeFieldCounts();
        this.phase = 'review';
        this.tab = diff.new.length ? 'new' : 'update';
        this.refresh();
      },

      get hasPending() {
        return this.phase === 'review' && (this.counts.new + this.counts.update) > 0;
      },

      async openModal() {
        this.open = true;
        document.documentElement.style.overflow = 'hidden';
        if (restorePromise) await restorePromise;
      },

      closeModal() {
        if (this.phase === 'fetching' || this.phase === 'comparing' || this.phase === 'importing') return;
        this.open = false;
        this.fieldsOpen = false;
        document.documentElement.style.overflow = '';
      },

      resetState() {
        remote = {};
        diff = { new: [], update: [], unchanged_count: 0 };
        filtered = [];
        selected.clear();
        this.importResult = null;
        this.search = '';
        this.pageNo = 1;
        this.refresh();
      },

      async startSync() {
        this.error = '';
        this.resetState();
        this.progress = { page: 0, totalPages: 0, fetched: 0, total: 0, compared: 0 };
        this.phase = 'fetching';
        try {
          await idb.clear();
          let page = 1;
          let totalPages = 1;
          do {
            const res = await fetch(`/visionadmin/api/products/sync/fetch?page=${page}&category=${encodeURIComponent(this.category)}`);
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data.success) throw new Error(data.error || `Fetching page ${page} failed (HTTP ${res.status}).`);
            if (page === 1) {
              this.fields = data.fields || [];
              this.setActiveFields(loadActiveFields(this.fields));
              this.progress.total = data.total_count || 0;
            }
            totalPages = (data.page_info && data.page_info.total_pages) || 1;
            await idb.putMany(data.items);
            data.items.forEach((it) => { remote[it.sku] = it; });
            this.progress.page = page;
            this.progress.totalPages = totalPages;
            this.progress.fetched += data.items.length;
            page += 1;
          } while (page <= totalPages);

          this.phase = 'comparing';
          const all = Object.values(remote);
          const merged = { new: [], update: [], unchanged_count: 0 };
          for (let i = 0; i < all.length; i += COMPARE_CHUNK) {
            const part = await postJson('/visionadmin/api/products/sync/compare', { items: all.slice(i, i + COMPARE_CHUNK) });
            merged.new.push(...part.new);
            merged.update.push(...part.update);
            merged.unchanged_count += part.unchanged_count;
            this.progress.compared = Math.min(all.length, i + COMPARE_CHUNK);
          }
          diff = merged;
          this.fetchedAt = Date.now();
          await idb.setMeta('diff', merged);
          await idb.setMeta('fields', this.fields);
          await idb.setMeta('fetchedAt', this.fetchedAt);
          await idb.setMeta('category', this.category);
          this.syncedCategory = this.category;
          this.computeFieldCounts();
          this.phase = 'review';
          this.tab = merged.new.length ? 'new' : 'update';
          this.refresh();
        } catch (e) {
          this.error = e.message || 'Sync failed.';
          this.phase = 'idle';
        }
      },

      // ---- derived data (recomputed explicitly, not via reactive getters) ----
      activeChanges(u) {
        return Object.keys(u.changes || {}).filter((k) => activeSet.has(k));
      },

      updateRows() {
        return diff.update.filter((u) => u.in_trash || this.activeChanges(u).length);
      },

      refresh() {
        const updates = this.updateRows();
        this.counts = {
          new: diff.new.length,
          update: updates.length,
          unchanged: diff.unchanged_count + (diff.update.length - updates.length),
        };

        const q = this.search.trim().toLowerCase();
        const rows = this.tab === 'new' ? diff.new : updates;
        filtered = !q ? rows : rows.filter((r) => {
          const rec = remote[r.sku] || {};
          return r.sku.toLowerCase().includes(q)
            || (rec.name || '').toLowerCase().includes(q)
            || (rec.brand || '').toLowerCase().includes(q);
        });
        this.filteredCount = filtered.length;
        this.totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
        if (this.pageNo > this.totalPages) this.pageNo = this.totalPages;

        const prefix = this.tab === 'new' ? 'n:' : 'u:';
        const start = (this.pageNo - 1) * PAGE_SIZE;
        this.pageRows = filtered.slice(start, start + PAGE_SIZE).map((r) => this.viewRow(r, prefix));
        this.syncSelectionState();
      },

      viewRow(r, prefix) {
        const rec = remote[r.sku] || {};
        const changes = r.changes
          ? this.activeChanges(r).map((k) => ({
              key: k, label: this.fieldLabel(k), old: fmt(k, r.changes[k][0]), new: fmt(k, r.changes[k][1]),
            }))
          : [];
        return {
          id: prefix + r.sku,
          sku: r.sku,
          name: rec.name || r.sku,
          brand: rec.brand || '—',
          size: rec.tyre_size || '—',
          price: fmt('price', rec.price),
          inStock: rec.stock_status === 'in_stock',
          image: rec.image_url || '',
          imageState: rec.image ? 'local' : (rec.image_downloadable ? 'download' : 'none'),
          inTrash: !!r.in_trash,
          changes,
          expanded: false,
          selected: selected.has(prefix + r.sku),
        };
      },

      computeFieldCounts() {
        const counts = {};
        diff.update.forEach((u) => Object.keys(u.changes || {}).forEach((k) => { counts[k] = (counts[k] || 0) + 1; }));
        this.fieldCounts = counts;
      },

      // ---- navigation ---------------------------------------------------
      setTab(tab) {
        this.tab = tab;
        this.pageNo = 1;
        if (this.search) this.search = ''; else this.refresh();
      },

      goPage(n) {
        this.pageNo = Math.min(Math.max(1, n), this.totalPages);
        this.refresh();
        this.$nextTick(() => { const w = document.querySelector('.psync-table-wrap'); if (w) w.scrollTop = 0; });
      },

      // ---- field filter -------------------------------------------------
      setActiveFields(keys) {
        this.activeFields = keys;
        activeSet = new Set(keys);
      },

      isFieldActive(key) { return this.activeFields.includes(key); },

      toggleField(key) {
        const next = this.isFieldActive(key) ? this.activeFields.filter((k) => k !== key) : [...this.activeFields, key];
        this.setActiveFields(next);
        try { localStorage.setItem(FIELDS_KEY, JSON.stringify(next)); } catch (e) { /* ignore */ }
        const valid = new Set(this.updateRows().map((u) => 'u:' + u.sku));
        [...selected].forEach((k) => { if (k.startsWith('u:') && !valid.has(k)) selected.delete(k); });
        this.pageNo = 1;
        this.refresh();
      },

      fieldLabel(key) {
        const f = this.fields.find((x) => x.key === key);
        return f ? f.label : key;
      },

      // ---- selection ----------------------------------------------------
      syncSelectionState() {
        let n = 0; let u = 0;
        selected.forEach((k) => { if (k.startsWith('n:')) n++; else u++; });
        this.selectedNew = n;
        this.selectedUpdate = u;
        this.selectedCount = n + u;
        const prefix = this.tab === 'new' ? 'n:' : 'u:';
        this.allFilteredSelected = filtered.length > 0 && filtered.every((r) => selected.has(prefix + r.sku));
      },

      toggleRow(row) {
        if (selected.has(row.id)) selected.delete(row.id); else selected.add(row.id);
        row.selected = selected.has(row.id);
        this.syncSelectionState();
      },

      toggleAllFiltered() {
        const prefix = this.tab === 'new' ? 'n:' : 'u:';
        const select = !this.allFilteredSelected;
        filtered.forEach((r) => { if (select) selected.add(prefix + r.sku); else selected.delete(prefix + r.sku); });
        this.pageRows.forEach((row) => { row.selected = select; });
        this.syncSelectionState();
      },

      fmtDate(ts) { return ts ? new Date(ts).toLocaleString() : ''; },

      // ---- import -------------------------------------------------------
      async importSelected() {
        if (!selected.size) return;
        const updatesBySku = Object.fromEntries(diff.update.map((u) => [u.sku, u]));
        const rows = [...selected].map((k) => {
          const sku = k.slice(2);
          if (k.startsWith('n:')) return { sku };
          const u = updatesBySku[sku];
          return { sku, fields: u ? this.activeChanges(u) : [] };
        });

        this.phase = 'importing';
        this.error = '';
        this.fieldsOpen = false;
        this.importProgress = { done: 0, total: rows.length };
        const result = { created: 0, updated: 0, restored: 0, skipped: 0, images_downloaded: 0, failed: [] };
        const doneSkus = new Set();
        try {
          for (let i = 0; i < rows.length; i += IMPORT_CHUNK) {
            const chunk = rows.slice(i, i + IMPORT_CHUNK);
            const res = await postJson('/visionadmin/api/products/sync/import', { rows: chunk });
            result.created += res.created;
            result.updated += res.updated;
            result.restored += res.restored;
            result.skipped += res.skipped;
            result.images_downloaded += res.images_downloaded || 0;
            result.failed.push(...res.failed);
            const failedSkus = new Set(res.failed.map((f) => f.sku));
            chunk.forEach((r) => { if (!failedSkus.has(r.sku)) doneSkus.add(r.sku); });
            this.importProgress.done = Math.min(rows.length, i + IMPORT_CHUNK);
          }
        } catch (e) {
          this.error = `Import stopped: ${e.message} Products imported before this point are saved.`;
        }

        diff.new = diff.new.filter((n) => !doneSkus.has(n.sku));
        diff.update = diff.update.filter((u) => !doneSkus.has(u.sku));
        diff.unchanged_count += doneSkus.size;
        [...selected].forEach((k) => { if (doneSkus.has(k.slice(2))) selected.delete(k); });
        await idb.setMeta('diff', diff);
        this.computeFieldCounts();

        this.importResult = result;
        this.phase = 'review';
        this.refresh();
        window.dispatchEvent(new CustomEvent('products-synced'));
        const ok = result.created + result.updated;
        if (ok) this.toast(`Imported ${ok} product${ok === 1 ? '' : 's'} from Tyrescart.`, 'success');
        if (result.failed.length) this.toast(`${result.failed.length} product(s) failed to import.`, 'error');
      },

      async discard() {
        await idb.clear();
        this.resetState();
        this.syncedCategory = '';
        this.phase = 'idle';
        this.closeModal();
      },

      toast(message, type) {
        const el = document.getElementById('va-toast');
        if (!el) return;
        el.textContent = message;
        el.className = 'fixed bottom-5 right-5 z-50 transform transition-all duration-300 translate-y-0 opacity-100 flex items-center gap-3 px-5 py-3 rounded-2xl shadow-2xl border text-sm font-bold ' +
          (type === 'success' ? 'bg-[#0E1108] text-[#2563FF] border-[#2563FF]/40' : 'bg-rose-900 text-white border-rose-700');
        setTimeout(() => {
          el.className = 'fixed bottom-5 right-5 z-50 transform transition-all duration-300 translate-y-20 opacity-0 pointer-events-none flex items-center gap-3 px-5 py-3 rounded-2xl shadow-xl border text-sm font-semibold';
        }, 3500);
      },
    };
  }

  window.productSyncApp = productSyncApp;
})();
