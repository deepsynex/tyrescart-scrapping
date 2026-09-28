/**
 * static/visionadmin/storelocator.js
 * Store Locator & Fitment Centers management controller for VisionAdmin
 */

function visionStoreLocatorApp() {
  return {
    items: [],
    metrics: { total: 0, active: 0, inactive: 0, trash: 0 },
    cities: [],
    loading: false,
    activeTab: 'active', // 'active' | 'trash'
    isTrash: 0,

    searchQuery: '',
    selectedCity: 'all',
    statusFilter: 'all',

    currentPage: 1,
    perPage: 20,
    totalItems: 0,
    totalPages: 1,

    initData() {
      this.loadData(1);
    },

    async loadData(page = 1) {
      this.loading = true;
      this.currentPage = page;

      try {
        const params = new URLSearchParams({
          page: this.currentPage,
          per_page: this.perPage,
          trash: this.isTrash ? '1' : '0'
        });

        if (this.searchQuery && this.searchQuery.trim()) {
          params.append('query', this.searchQuery.trim());
        }
        if (this.selectedCity && this.selectedCity !== 'all') {
          params.append('city', this.selectedCity);
        }
        if (this.statusFilter !== 'all') {
          params.append('status', this.statusFilter);
        }

        const res = await fetch(`/visionadmin/api/storelocator?${params.toString()}`);
        const data = await res.json();

        if (data.success || data.items) {
          this.items = data.items || [];
          this.totalItems = data.total || 0;
          this.totalPages = data.total_pages || 1;
          if (data.metrics) {
            this.metrics = data.metrics;
          }
          if (data.cities && Array.isArray(data.cities)) {
            this.cities = data.cities;
          }
        } else {
          this.showToast(data.error || 'Failed to load store locations.', 'error');
        }
      } catch (err) {
        console.error('Error fetching store locations:', err);
        this.showToast('Network error while loading store locations.', 'error');
      } finally {
        this.loading = false;
      }
    },

    resetFilters() {
      this.searchQuery = '';
      this.selectedCity = 'all';
      this.statusFilter = 'all';
      this.loadData(1);
    },

    async toggleStatus(item) {
      const nextStatus = item.status ? 0 : 1;
      const originalStatus = item.status;
      item.status = nextStatus; // optimistic UI

      try {
        const res = await fetch(`/visionadmin/api/storelocator/${item.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: nextStatus })
        });
        const data = await res.json();
        if (data.success) {
          this.showToast(nextStatus ? `Store "${item.name}" enabled.` : `Store "${item.name}" disabled.`, 'success');
          // refresh metrics
          if (this.metrics) {
            if (nextStatus) {
              this.metrics.active++;
              this.metrics.inactive = Math.max(0, this.metrics.inactive - 1);
            } else {
              this.metrics.inactive++;
              this.metrics.active = Math.max(0, this.metrics.active - 1);
            }
          }
        } else {
          item.status = originalStatus;
          this.showToast(data.error || 'Failed to update status.', 'error');
        }
      } catch (err) {
        item.status = originalStatus;
        this.showToast('Network error updating status.', 'error');
      }
    },

    async moveToTrash(item) {
      if (!confirm(`Are you sure you want to move "${item.name}" to trash?`)) {
        return;
      }

      try {
        const res = await fetch(`/visionadmin/api/storelocator/${item.id}`, {
          method: 'DELETE'
        });
        const data = await res.json();
        if (data.success) {
          this.showToast(data.message || 'Store moved to trash.', 'success');
          this.loadData(this.currentPage);
        } else {
          this.showToast(data.error || 'Failed to move store to trash.', 'error');
        }
      } catch (err) {
        this.showToast('Network error deleting store.', 'error');
      }
    },

    async restoreItem(item) {
      try {
        const res = await fetch(`/visionadmin/api/storelocator/${item.id}/restore`, {
          method: 'POST'
        });
        const data = await res.json();
        if (data.success) {
          this.showToast(data.message || 'Store restored successfully.', 'success');
          this.loadData(this.currentPage);
        } else {
          this.showToast(data.error || 'Failed to restore store.', 'error');
        }
      } catch (err) {
        this.showToast('Network error restoring store.', 'error');
      }
    },

    async purgeItem(item) {
      if (!confirm(`Permanently delete "${item.name}"? This action CANNOT be undone.`)) {
        return;
      }

      try {
        const res = await fetch(`/visionadmin/api/storelocator/${item.id}?purge=1`, {
          method: 'DELETE'
        });
        const data = await res.json();
        if (data.success) {
          this.showToast(data.message || 'Store permanently deleted.', 'success');
          this.loadData(this.currentPage);
        } else {
          this.showToast(data.error || 'Failed to permanently delete store.', 'error');
        }
      } catch (err) {
        this.showToast('Network error purging store.', 'error');
      }
    },

    showToast(message, type = 'info') {
      if (window.AdminShared && window.AdminShared.showToast) {
        window.AdminShared.showToast(message, type);
      } else if (window.showToast) {
        window.showToast(message, type);
      } else {
        alert(message);
      }
    }
  };
}
