/**
 * static/visionadmin/storelocator_form.js
 * VisionAdmin Store Locator Form & Visual Opening Hours Interactive Module
 * 
 * Features:
 * 1. Full Store Locator form state & validations matching backend schema.
 * 2. Visual Opening Hours Slider:
 *    - 7 days (Sunday - Saturday)
 *    - Active range timeline bars with drag & resize handles (orange/coral styled)
 *    - Double-click to delete ranges
 *    - 15-minute grid snapping and 00:00 - 24:00 time markers
 *    - Real-time text summary synchronization
 * 3. Asynchronous Image Uploader:
 *    - Uploads to /visionadmin/api/storelocator/upload-image
 *    - Live preview, file path display, and removal
 * 4. Collapsible accordion sections
 * 5. Multi-Store View hierarchy selector
 */

(function () {
  'use strict';

  // Day definitions
  const DAYS = [
    { key: 'sunday', label: 'Sunday', short: 'Sun' },
    { key: 'monday', label: 'Monday', short: 'Mon' },
    { key: 'tuesday', label: 'Tuesday', short: 'Tue' },
    { key: 'wednesday', label: 'Wednesday', short: 'Wed' },
    { key: 'thursday', label: 'Thursday', short: 'Thu' },
    { key: 'friday', label: 'Friday', short: 'Fri' },
    { key: 'saturday', label: 'Saturday', short: 'Sat' }
  ];

  // 3-hour tick marks along the 24-hour timeline
  const TIMELINE_TICKS = [
    { label: '00:00', percent: 0 },
    { label: '03:00', percent: 12.5 },
    { label: '06:00', percent: 25 },
    { label: '09:00', percent: 37.5 },
    { label: '12:00', percent: 50 },
    { label: '15:00', percent: 62.5 },
    { label: '18:00', percent: 75 },
    { label: '21:00', percent: 87.5 },
    { label: '00:00', percent: 100 }
  ];

  /**
   * Helper: inject CSS styles for opening hours slider
   */
  function injectSliderStyles() {
    if (document.getElementById('va-storelocator-slider-styles')) return;
    const style = document.createElement('style');
    style.id = 'va-storelocator-slider-styles';
    style.textContent = `
      .va-hours-track {
        position: relative;
        height: 28px;
        background-color: #F1F5F9;
        border: 1px solid #CBD5E1;
        border-radius: 8px;
        user-select: none;
        touch-action: none;
        cursor: pointer;
      }
      .va-hours-range {
        position: absolute;
        top: 2px;
        bottom: 2px;
        background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
        border: 1px solid #c2410c;
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(234, 88, 12, 0.35);
        color: #FFFFFF;
        font-size: 11px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: grab;
        z-index: 10;
        overflow: hidden;
        user-select: none;
      }
      .va-hours-range:active {
        cursor: grabbing;
      }
      .va-hours-range.is-dragging {
        background: linear-gradient(135deg, #fb923c 0%, #f97316 100%);
        box-shadow: 0 0 0 2px #fff, 0 4px 12px rgba(234, 88, 12, 0.45);
        z-index: 20;
      }
      .va-range-handle {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 10px;
        cursor: ew-resize;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 15;
      }
      .va-range-handle-left {
        left: 0;
      }
      .va-range-handle-right {
        right: 0;
      }
      .va-range-handle::before {
        content: '';
        width: 3px;
        height: 14px;
        background-color: rgba(255, 255, 255, 0.85);
        border-radius: 2px;
      }
      .va-range-handle:hover::before {
        background-color: #FFFFFF;
        width: 4px;
      }
      .va-range-label {
        padding: 0 8px;
        white-space: nowrap;
        pointer-events: none;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
      }
      .va-timeline-ticks {
        position: relative;
        height: 22px;
        margin-top: 4px;
        user-select: none;
      }
      .va-timeline-tick {
        position: absolute;
        transform: translateX(-50%);
        display: flex;
        flex-direction: column;
        align-items: center;
        font-size: 10px;
        font-weight: 700;
        color: #94A3B8;
        line-height: 1;
      }
      .va-timeline-tick-line {
        width: 1px;
        height: 4px;
        background-color: #CBD5E1;
        margin-bottom: 2px;
      }
    `;
    document.head.appendChild(style);
  }

  // Inject styles on load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectSliderStyles);
  } else {
    injectSliderStyles();
  }

  /**
   * Main Alpine Component Factory
   */
  function visionStoreLocatorFormApp(mode = 'create', initialId = null) {
    return {
      mode: mode, // 'create' | 'edit'
      id: initialId ? parseInt(initialId, 10) : null,
      loading: false,
      saving: false,
      daysList: DAYS,
      ticks: TIMELINE_TICKS,

      // Track active drag for opening hours
      activeDrag: null,

      // Collapsible accordion sections
      sections: {
        address: true,
        contact: true,
        storeDetails: true,
        storeViews: true,
        openingHours: true
      },

      // Store Views Hierarchy
      storeViewsTree: [],
      storeViewsLoading: false,

      // Image Upload progress state
      uploading: {
        image: false,
        image_1: false,
        image_2: false,
        image_3: false,
        image_4: false,
        image_5: false,
        store_details_image: false
      },

      // Form validation errors
      errors: {},

      // Form State matching backend schema
      form: {
        id: initialId ? parseInt(initialId, 10) : null,
        // Basic Information
        name: '',
        name_ar: '',
        status: 1,
        category: 'independent_installer',
        is_mobile_van: 0,
        shipping_amount: '0.00',
        installer_sort_order: 0,
        skip_days: 0,
        cutoff_time: '',
        skip_hours: 0,
        coming_soon: 0,
        opening_hours_one: '',
        opening_hours_two: '',

        // Address & Coordinates
        longitude: '',
        latitude: '',
        address_ar: '',
        city_ar: '',
        postcode: '',
        country: 'AE',
        region: '',
        city: 'Dubai',
        address: '',

        // Contact & Communication
        external_link: '',
        phone: '',
        email: '',
        google_map: '',

        // Images
        image: '',
        image_1: '',
        image_2: '',
        image_3: '',
        image_4: '',
        image_5: '',
        store_details_image: '',

        // Store Details & SEO
        intro: '',
        description: '',
        distance: '',
        nearest_station: '',
        url_key: '',
        service_included: '',
        meta_title: '',
        meta_description: '',
        meta_title_ar: '',
        meta_description_ar: '',

        // Store Views (Languages / Locales)
        store_views: ['all'],

        // Weekly schedule JSON: { sunday: [...], monday: [...] }
        schedule_json: {
          sunday: [],
          monday: [],
          tuesday: [],
          wednesday: [],
          thursday: [],
          friday: [],
          saturday: []
        }
      },

      /**
       * Initialization
       */
      async init() {
        this.ensureScheduleStructure();
        this.loadStoreViewsTree();

        if (this.mode === 'edit' && this.id) {
          await this.loadStoreLocatorData();
        } else {
          // Provide default opening hours for standard working week (09:00 - 18:00)
          this.setStandardWeekHours(false);
        }
      },

      initData() {
        return this.init();
      },

      /**
       * Ensure all 7 days exist as arrays in schedule_json
       */
      ensureScheduleStructure() {
        if (!this.form.schedule_json || typeof this.form.schedule_json !== 'object') {
          this.form.schedule_json = {};
        }
        DAYS.forEach(d => {
          if (!Array.isArray(this.form.schedule_json[d.key])) {
            this.form.schedule_json[d.key] = [];
          }
        });
      },

      /**
       * Accordion Toggle Methods
       */
      toggleSection(sectionKey) {
        if (typeof this.sections[sectionKey] !== 'undefined') {
          this.sections[sectionKey] = !this.sections[sectionKey];
        }
      },

      isSectionOpen(sectionKey) {
        return !!this.sections[sectionKey];
      },

      expandAllSections() {
        Object.keys(this.sections).forEach(k => {
          this.sections[k] = true;
        });
      },

      collapseAllSections() {
        Object.keys(this.sections).forEach(k => {
          this.sections[k] = false;
        });
      },

      /**
       * Load existing Store Locator record
       */
      async loadStoreLocatorData() {
        this.loading = true;
        try {
          const res = await fetch(`/visionadmin/api/storelocator/${this.id}`);
          const data = await res.json();
          if (data.success && data.item) {
            const it = data.item;

            // Populate scalar values
            Object.keys(this.form).forEach(k => {
              if (k !== 'schedule_json' && k !== 'store_views' && typeof it[k] !== 'undefined' && it[k] !== null) {
                this.form[k] = it[k];
              }
            });

            // Parse schedule_json
            if (it.schedule_json) {
              let parsed = it.schedule_json;
              if (typeof parsed === 'string') {
                try {
                  parsed = JSON.parse(parsed);
                } catch (e) {
                  parsed = {};
                }
              }
              if (parsed && typeof parsed === 'object') {
                DAYS.forEach(d => {
                  this.form.schedule_json[d.key] = Array.isArray(parsed[d.key]) ? parsed[d.key] : [];
                });
              }
            }
            this.ensureScheduleStructure();

            // Parse store_views
            if (it.store_views) {
              let views = it.store_views;
              if (typeof views === 'string') {
                try {
                  views = JSON.parse(views);
                } catch (e) {
                  views = ['all'];
                }
              }
              this.form.store_views = Array.isArray(views) ? views : ['all'];
            }
          } else {
            this.showToast(data.error || 'Failed to load store locator data.', 'error');
          }
        } catch (err) {
          console.error('Error fetching store locator:', err);
          this.showToast('Network error while loading store locator details.', 'error');
        } finally {
          this.loading = false;
        }
      },

      /**
       * Load Store Views tree
       */
      async loadStoreViewsTree() {
        this.storeViewsLoading = true;
        try {
          const res = await fetch('/visionadmin/api/storelocator/store-views-tree');
          const data = await res.json();
          if (data.success) {
            this.storeViewsTree = data.tree || [];
          }
        } catch (err) {
          console.error('Failed to load store views tree:', err);
        } finally {
          this.storeViewsLoading = false;
        }
      },

      /**
       * Store Views checkbox helpers
       */
      isStoreViewSelected(viewId) {
        if (!Array.isArray(this.form.store_views)) return false;
        if (this.form.store_views.includes('all')) return true;
        return this.form.store_views.includes(Number(viewId)) || this.form.store_views.includes(String(viewId));
      },

      isAllStoreViewsSelected() {
        return Array.isArray(this.form.store_views) && this.form.store_views.includes('all');
      },

      toggleAllStoreViews() {
        if (this.isAllStoreViewsSelected()) {
          this.form.store_views = [];
        } else {
          this.form.store_views = ['all'];
        }
      },

      toggleStoreView(viewId) {
        if (!Array.isArray(this.form.store_views)) {
          this.form.store_views = [];
        }

        const idNum = Number(viewId);

        // If 'all' is currently checked, unpack all views into array minus the unchecked one
        if (this.form.store_views.includes('all')) {
          const allViewIds = [];
          (this.storeViewsTree || []).forEach(w => {
            (w.stores || []).forEach(s => {
              (s.views || []).forEach(v => allViewIds.push(v.id));
            });
          });
          this.form.store_views = allViewIds.filter(id => id !== idNum);
          return;
        }

        const idx = this.form.store_views.indexOf(idNum);
        if (idx > -1) {
          this.form.store_views.splice(idx, 1);
        } else {
          this.form.store_views.push(idNum);
        }
      },

      // =======================================================================
      // OPENING HOURS SLIDER & TIME CALCULATIONS
      // =======================================================================

      /**
       * Convert minutes (0 - 1440) to "HH:MM"
       */
      minutesToTime(mins) {
        mins = Math.max(0, Math.min(1440, Math.round(mins)));
        const h = Math.floor(mins / 60);
        const m = mins % 60;
        return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      },

      /**
       * Convert "HH:MM" to minutes (0 - 1440)
       */
      timeToMinutes(timeStr) {
        if (!timeStr || typeof timeStr !== 'string') return 0;
        const parts = timeStr.trim().split(':');
        if (parts.length < 2) return 0;
        const h = parseInt(parts[0], 10) || 0;
        const m = parseInt(parts[1], 10) || 0;
        return Math.max(0, Math.min(1440, h * 60 + m));
      },

      /**
       * Snap minutes to 15-minute grid
       */
      snapMinutes(mins, step = 15) {
        return Math.max(0, Math.min(1440, Math.round(mins / step) * step));
      },

      /**
       * Sort a day's ranges chronologically
       */
      sortDayRanges(dayKey) {
        if (!this.form.schedule_json[dayKey]) return;
        this.form.schedule_json[dayKey].sort((a, b) => {
          return this.timeToMinutes(a.start) - this.timeToMinutes(b.start);
        });
      },

      /**
       * Real-time formatted summary of active ranges for a day
       * e.g. "09:00 - 13:00, 16:00 - 19:00, 19:00 - 22:00" or "Closed"
       */
      getDayFormattedHours(dayKey) {
        const ranges = this.form.schedule_json[dayKey];
        if (!ranges || ranges.length === 0) {
          return 'Closed';
        }
        return ranges.map(r => `${r.start} - ${r.end}`).join(', ');
      },

      /**
       * Calculate range left percentage (0% to 100%)
       */
      getRangeLeftPercent(range) {
        const startMins = this.timeToMinutes(range.start);
        return Math.max(0, Math.min(100, (startMins / 1440) * 100)).toFixed(3);
      },

      /**
       * Calculate range width percentage (0% to 100%)
       */
      getRangeWidthPercent(range) {
        const startMins = this.timeToMinutes(range.start);
        const endMins = this.timeToMinutes(range.end);
        const diff = Math.max(0, endMins - startMins);
        return Math.max(0.5, Math.min(100, (diff / 1440) * 100)).toFixed(3);
      },

      /**
       * Add a new range to a day
       * Either defaults to 09:00 - 18:00 or appends a 2-hour slot after existing ranges
       */
      addDefaultRange(dayKey) {
        this.ensureScheduleStructure();
        const ranges = this.form.schedule_json[dayKey];

        if (ranges.length === 0) {
          ranges.push({ start: '09:00', end: '18:00' });
        } else {
          // Find max end time
          const maxEndMins = Math.max(...ranges.map(r => this.timeToMinutes(r.end)));
          if (maxEndMins <= 1260) { // before 21:00
            const newStart = maxEndMins;
            const newEnd = Math.min(1440, newStart + 180);
            ranges.push({
              start: this.minutesToTime(newStart),
              end: this.minutesToTime(newEnd)
            });
          } else {
            // Find first available gap >= 60 mins
            let inserted = false;
            for (let t = 0; t <= 1380; t += 30) {
              const checkEnd = t + 120;
              const hasOverlap = ranges.some(r => {
                const s = this.timeToMinutes(r.start);
                const e = this.timeToMinutes(r.end);
                return !(checkEnd <= s || t >= e);
              });
              if (!hasOverlap) {
                ranges.push({
                  start: this.minutesToTime(t),
                  end: this.minutesToTime(checkEnd)
                });
                inserted = true;
                break;
              }
            }
            if (!inserted) {
              this.showToast('No free time slot available on this day.', 'error');
              return;
            }
          }
        }

        this.sortDayRanges(dayKey);
        this.showToast(`Added range for ${dayKey.charAt(0).toUpperCase() + dayKey.slice(1)}`);
      },

      /**
       * Delete an opening hour range (called on double click or button)
       */
      deleteRange(dayKey, index) {
        if (this.form.schedule_json[dayKey] && this.form.schedule_json[dayKey][index]) {
          const removed = this.form.schedule_json[dayKey].splice(index, 1)[0];
          this.showToast(`Deleted ${removed.start} - ${removed.end}`, 'info');
        }
      },

      /**
       * Clear all hours for a day (marks as Closed)
       */
      clearDaySchedule(dayKey) {
        this.form.schedule_json[dayKey] = [];
        this.showToast(`All hours cleared for ${dayKey.charAt(0).toUpperCase() + dayKey.slice(1)}.`, 'info');
      },

      /**
       * Copy schedule from one day to all other days
       */
      copyScheduleToAllDays(sourceDayKey) {
        const sourceRanges = this.form.schedule_json[sourceDayKey] || [];
        DAYS.forEach(d => {
          if (d.key !== sourceDayKey) {
            this.form.schedule_json[d.key] = JSON.parse(JSON.stringify(sourceRanges));
          }
        });
        this.showToast(`Copied ${sourceDayKey.toUpperCase()} hours to all 7 days!`);
      },

      /**
       * Set standard week hours (09:00 - 18:00 Sun - Thu, 09:00 - 13:00 Fri)
       */
      setStandardWeekHours(showNotification = true) {
        this.ensureScheduleStructure();
        DAYS.forEach(d => {
          if (d.key === 'friday') {
            this.form.schedule_json[d.key] = [{ start: '09:00', end: '13:00' }, { start: '16:00', end: '20:00' }];
          } else {
            this.form.schedule_json[d.key] = [{ start: '09:00', end: '18:00' }];
          }
        });
        if (showNotification) {
          this.showToast('Applied standard working hours schedule.');
        }
      },

      /**
       * Aliases for HTML template interoperability
       */
      formatDayHours(dayKey) {
        return this.getDayFormattedHours(dayKey);
      },

      addTimeSlot(dayKey) {
        return this.addDefaultRange(dayKey);
      },

      removeTimeSlot(dayKey, index) {
        return this.deleteRange(dayKey, index);
      },

      clearDayHours(dayKey) {
        return this.clearDaySchedule(dayKey);
      },

      clearAllHours() {
        this.ensureScheduleStructure();
        DAYS.forEach(d => {
          this.form.schedule_json[d.key] = [];
        });
        this.showToast('Cleared all opening hours for all days.', 'info');
      },

      getRangeStyle(range) {
        const left = this.getRangeLeftPercent(range);
        const width = this.getRangeWidthPercent(range);
        return `left: ${left}%; width: ${width}%;`;
      },

      onTrackClick(dayKey, event) {
        return this.handleTrackClick(event, dayKey);
      },

      onRangePointerDown(dayKey, index, event) {
        return this.startRangeDrag(event, dayKey, index, 'move');
      },

      onHandlePointerDown(dayKey, index, side, event) {
        const action = side === 'left' ? 'resize-left' : 'resize-right';
        return this.startRangeDrag(event, dayKey, index, action);
      },

      generateUrlKey() {
        if (this.form.name) {
          this.form.url_key = this.slugify(this.form.name);
        }
      },

      resetForm() {
        if (this.mode === 'edit' && this.id) {
          this.loadStoreLocatorData();
          this.showToast('Form reset to saved state.', 'info');
        } else {
          this.form.name = '';
          this.form.name_ar = '';
          this.form.status = 1;
          this.form.category = 'independent_installer';
          this.form.is_mobile_van = 0;
          this.form.shipping_amount = '0.00';
          this.form.installer_sort_order = 0;
          this.form.skip_days = 0;
          this.form.cutoff_time = '';
          this.form.skip_hours = 0;
          this.form.coming_soon = 0;
          this.form.opening_hours_one = '';
          this.form.opening_hours_two = '';
          this.form.longitude = '';
          this.form.latitude = '';
          this.form.address_ar = '';
          this.form.city_ar = '';
          this.form.postcode = '';
          this.form.country = 'AE';
          this.form.region = '';
          this.form.city = 'Dubai';
          this.form.address = '';
          this.form.external_link = '';
          this.form.phone = '';
          this.form.email = '';
          this.form.google_map = '';
          this.form.image = '';
          this.form.image_1 = '';
          this.form.image_2 = '';
          this.form.image_3 = '';
          this.form.image_4 = '';
          this.form.image_5 = '';
          this.form.store_details_image = '';
          this.form.intro = '';
          this.form.description = '';
          this.form.distance = '';
          this.form.nearest_station = '';
          this.form.url_key = '';
          this.form.service_included = '';
          this.form.meta_title = '';
          this.form.meta_description = '';
          this.form.meta_title_ar = '';
          this.form.meta_description_ar = '';
          this.form.store_views = ['all'];
          this.setStandardWeekHours(false);
          this.errors = {};
          this.showToast('Form reset to defaults.', 'info');
        }
      },

      /**
       * Handle click on the empty timeline track to create a new range
       */
      handleTrackClick(event, dayKey) {
        // Ignore if clicking on a range or handle
        if (event.target.closest('.va-hours-range') || event.target.closest('.va-range-handle')) {
          return;
        }

        const track = event.currentTarget;
        const rect = track.getBoundingClientRect();
        const clickX = event.clientX - rect.left;
        const percent = Math.max(0, Math.min(1, clickX / rect.width));
        const rawMins = percent * 1440;
        const startMins = this.snapMinutes(rawMins);
        const endMins = Math.min(1440, startMins + 180); // default 3-hour duration

        if (endMins - startMins < 30) return;

        // Check overlap with existing ranges
        const ranges = this.form.schedule_json[dayKey] || [];
        const hasOverlap = ranges.some(r => {
          const s = this.timeToMinutes(r.start);
          const e = this.timeToMinutes(r.end);
          return !(endMins <= s || startMins >= e);
        });

        if (hasOverlap) {
          this.showToast('Clicked position overlaps with an existing time slot.', 'error');
          return;
        }

        ranges.push({
          start: this.minutesToTime(startMins),
          end: this.minutesToTime(endMins)
        });
        this.sortDayRanges(dayKey);
        this.showToast(`Added ${this.minutesToTime(startMins)} - ${this.minutesToTime(endMins)}`);
      },

      /**
       * Pointer Drag & Resize Handler for Opening Hours Slider
       */
      startRangeDrag(event, dayKey, index, action) {
        event.preventDefault();
        event.stopPropagation();

        const range = this.form.schedule_json[dayKey][index];
        if (!range) return;

        const track = event.currentTarget.closest('.va-hours-track');
        if (!track) return;

        const trackRect = track.getBoundingClientRect();
        const startMins = this.timeToMinutes(range.start);
        const endMins = this.timeToMinutes(range.end);
        const duration = endMins - startMins;

        this.activeDrag = {
          dayKey,
          index,
          action, // 'move', 'resize-left', 'resize-right'
          startX: event.clientX,
          initialStartMins: startMins,
          initialEndMins: endMins,
          duration: duration,
          trackRect: trackRect
        };

        const targetEl = event.currentTarget.closest('.va-hours-range');
        if (targetEl) targetEl.classList.add('is-dragging');

        const onPointerMove = (e) => {
          if (!this.activeDrag) return;
          const deltaX = e.clientX - this.activeDrag.startX;
          const deltaMins = Math.round((deltaX / this.activeDrag.trackRect.width) * 1440);

          if (this.activeDrag.action === 'move') {
            let newStart = this.snapMinutes(this.activeDrag.initialStartMins + deltaMins);
            newStart = Math.max(0, Math.min(1440 - this.activeDrag.duration, newStart));
            const newEnd = newStart + this.activeDrag.duration;

            range.start = this.minutesToTime(newStart);
            range.end = this.minutesToTime(newEnd);
          } else if (this.activeDrag.action === 'resize-left') {
            let newStart = this.snapMinutes(this.activeDrag.initialStartMins + deltaMins);
            // Minimum 15 mins slot
            newStart = Math.max(0, Math.min(this.activeDrag.initialEndMins - 15, newStart));
            range.start = this.minutesToTime(newStart);
          } else if (this.activeDrag.action === 'resize-right') {
            let newEnd = this.snapMinutes(this.activeDrag.initialEndMins + deltaMins);
            // Minimum 15 mins slot
            newEnd = Math.min(1440, Math.max(this.activeDrag.initialStartMins + 15, newEnd));
            range.end = this.minutesToTime(newEnd);
          }
        };

        const onPointerUp = () => {
          window.removeEventListener('pointermove', onPointerMove);
          window.removeEventListener('pointerup', onPointerUp);
          window.removeEventListener('pointercancel', onPointerUp);

          if (targetEl) targetEl.classList.remove('is-dragging');
          this.sortDayRanges(dayKey);
          this.activeDrag = null;
        };

        window.addEventListener('pointermove', onPointerMove);
        window.addEventListener('pointerup', onPointerUp);
        window.addEventListener('pointercancel', onPointerUp);
      },

      // =======================================================================
      // IMAGE UPLOADER COMPONENT
      // =======================================================================

      /**
       * Upload an image to /visionadmin/api/storelocator/upload-image
       */
      async uploadImage(field, fileInputOrEvent) {
        let file = null;
        let inputElement = null;

        if (fileInputOrEvent instanceof HTMLInputElement) {
          inputElement = fileInputOrEvent;
          file = inputElement.files ? inputElement.files[0] : null;
        } else if (fileInputOrEvent && fileInputOrEvent.target && fileInputOrEvent.target.files) {
          inputElement = fileInputOrEvent.target;
          file = inputElement.files[0];
        } else if (fileInputOrEvent instanceof File) {
          file = fileInputOrEvent;
        }

        if (!file) return;

        // Size check (10MB limit)
        if (file.size > 10 * 1024 * 1024) {
          this.showToast('Image file size must not exceed 10MB.', 'error');
          if (inputElement) inputElement.value = '';
          return;
        }

        // Extension check
        const allowedExts = ['.png', '.jpg', '.jpeg', '.webp', '.svg', '.gif', '.avif'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!allowedExts.includes(ext)) {
          this.showToast(`Invalid file type "${ext}". Allowed: PNG, JPG, JPEG, WEBP, SVG, GIF, AVIF`, 'error');
          if (inputElement) inputElement.value = '';
          return;
        }

        this.uploading[field] = true;
        try {
          const fd = new FormData();
          fd.append('file', file);
          fd.append('image', file);

          const csrfToken = this.getCsrfToken();
          const headers = {};
          if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
          }

          const res = await fetch('/visionadmin/api/storelocator/upload-image', {
            method: 'POST',
            headers: headers,
            body: fd
          });

          const data = await res.json();
          if (data.success && data.url) {
            this.form[field] = data.url;
            this.showToast(data.message || 'Image uploaded successfully!');
          } else {
            this.showToast(data.error || 'Failed to upload image.', 'error');
          }
        } catch (err) {
          console.error('Image upload error:', err);
          this.showToast('Network error while uploading image.', 'error');
        } finally {
          this.uploading[field] = false;
          if (inputElement) inputElement.value = '';
        }
      },

      /**
       * Remove an image field
       */
      removeImage(field) {
        this.form[field] = '';
        this.showToast('Image removed.', 'info');
      },

      /**
       * Image field presence helper
       */
      hasImage(field) {
        return !!(this.form[field] && this.form[field].trim());
      },

      // =======================================================================
      // GEOLOCATION & UTILITY HELPERS
      // =======================================================================

      /**
       * Detect current browser location coordinates
       */
      detectCoordinates() {
        if (!navigator.geolocation) {
          this.showToast('Geolocation is not supported by your browser.', 'error');
          return;
        }
        this.showToast('Detecting current GPS coordinates...', 'info');
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            this.form.latitude = pos.coords.latitude.toFixed(6);
            this.form.longitude = pos.coords.longitude.toFixed(6);
            this.showToast(`Coordinates set: ${this.form.latitude}, ${this.form.longitude}`);
          },
          (err) => {
            this.showToast(`Geolocation error: ${err.message}`, 'error');
          },
          { enableHighAccuracy: true, timeout: 10000 }
        );
      },

      /**
       * Auto-generate URL Key / Slug
       */
      slugify(text) {
        if (!text) return '';
        return text
          .toString()
          .toLowerCase()
          .trim()
          .replace(/[^\w\s-]/g, '')
          .replace(/[\s_-]+/g, '-')
          .replace(/^-+|-+$/g, '');
      },

      onNameInput() {
        if (!this.form.url_key) {
          this.form.url_key = this.slugify(this.form.name);
        }
      },

      /**
       * Extract coordinates if user pastes a Google Maps URL
       */
      onGoogleMapInput() {
        const val = this.form.google_map || '';
        // Match @lat,lng, or q=lat,lng
        const match = val.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/) || val.match(/[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)/);
        if (match && match[1] && match[2]) {
          if (!this.form.latitude) this.form.latitude = match[1];
          if (!this.form.longitude) this.form.longitude = match[2];
          this.showToast(`Coordinates extracted from Google Map link: ${match[1]}, ${match[2]}`);
        }
      },

      // =======================================================================
      // VALIDATION & SAVING
      // =======================================================================

      /**
       * Form field validation
       */
      validateForm() {
        this.errors = {};

        if (!this.form.name || !this.form.name.trim()) {
          this.errors.name = 'Store Name is required.';
        }

        const lat = String(this.form.latitude || '').trim();
        const lng = String(this.form.longitude || '').trim();

        if (!lat) {
          this.errors.latitude = 'Latitude coordinate is required.';
        } else if (isNaN(Number(lat)) || Number(lat) < -90 || Number(lat) > 90) {
          this.errors.latitude = 'Latitude must be between -90 and 90.';
        }

        if (!lng) {
          this.errors.longitude = 'Longitude coordinate is required.';
        } else if (isNaN(Number(lng)) || Number(lng) < -180 || Number(lng) > 180) {
          this.errors.longitude = 'Longitude must be between -180 and 180.';
        }

        return Object.keys(this.errors).length === 0;
      },

      /**
       * Save Store Locator
       * @param {boolean} redirectToList - if true, redirect to /visionadmin/storelocator upon success
       */
      async saveStoreLocator(redirectToList = false) {
        if (!this.validateForm()) {
          const firstErrKey = Object.keys(this.errors)[0];
          this.showToast(this.errors[firstErrKey] || 'Please fix the errors in the form.', 'error');
          const firstInput = document.querySelector(`[name="${firstErrKey}"], [x-model="form.${firstErrKey}"]`);
          if (firstInput) firstInput.focus();
          return;
        }

        // Auto-slugify url_key if empty
        if (!this.form.url_key && this.form.name) {
          this.form.url_key = this.slugify(this.form.name);
        }

        this.saving = true;

        try {
          // Prepare clean payload
          const payload = {
            ...this.form,
            status: this.form.status ? 1 : 0,
            is_mobile_van: this.form.is_mobile_van ? 1 : 0,
            coming_soon: this.form.coming_soon ? 1 : 0,
            shipping_amount: parseFloat(this.form.shipping_amount) || 0.0,
            installer_sort_order: parseInt(this.form.installer_sort_order, 10) || 0,
            skip_days: parseInt(this.form.skip_days, 10) || 0,
            skip_hours: parseInt(this.form.skip_hours, 10) || 0,
            latitude: String(this.form.latitude).trim(),
            longitude: String(this.form.longitude).trim()
          };

          const isEdit = this.mode === 'edit' && this.id;
          const url = isEdit ? `/visionadmin/api/storelocator/${this.id}` : '/visionadmin/api/storelocator';
          const method = isEdit ? 'PUT' : 'POST';

          const csrfToken = this.getCsrfToken();
          const headers = {
            'Content-Type': 'application/json'
          };
          if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
          }

          const res = await fetch(url, {
            method: method,
            headers: headers,
            body: JSON.stringify(payload)
          });

          const data = await res.json();

          if (data.success) {
            this.showToast(data.message || 'Store locator saved successfully!');

            if (redirectToList) {
              window.location.href = data.redirect || '/visionadmin/storelocator';
            } else if (!isEdit && data.id) {
              // Switch mode to edit without reloading the entire page
              this.mode = 'edit';
              this.id = data.id;
              window.history.replaceState(null, '', `/visionadmin/storelocator/${data.id}/edit`);
            }
          } else {
            this.showToast(data.error || 'Failed to save store locator.', 'error');
          }
        } catch (err) {
          console.error('Save error:', err);
          this.showToast('Network error while saving store locator.', 'error');
        } finally {
          this.saving = false;
        }
      },

      /**
       * CSRF token getter
       */
      getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]') || document.querySelector('meta[name="csrf_token"]');
        if (meta) return meta.getAttribute('content') || '';
        return window.csrfToken || '';
      },

      /**
       * Toast Notification Dispatcher
       */
      showToast(message, type = 'success') {
        if (window.showToast) {
          window.showToast(message, type);
          return;
        }

        if (!document || !document.body) {
          console.log(`[Toast ${type}] ${message}`);
          return;
        }

        let container = document.getElementById('va-toast-container');
        if (!container) {
          container = document.createElement('div');
          container.id = 'va-toast-container';
          container.className = 'fixed bottom-5 right-5 z-[999999] flex flex-col gap-2 pointer-events-none';
          document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        const bgClass = type === 'error'
          ? 'bg-rose-600 text-white'
          : type === 'info'
            ? 'bg-slate-800 text-white'
            : 'bg-[#0E1108] text-[#9f7dde] border border-[#9f7dde]/30';

        toast.className = `px-5 py-3 rounded-2xl text-xs font-bold shadow-2xl pointer-events-auto transition-all duration-300 transform translate-y-2 opacity-0 ${bgClass}`;
        toast.textContent = message;
        container.appendChild(toast);

        if (typeof requestAnimationFrame === 'function') {
          requestAnimationFrame(() => {
            toast.classList.remove('translate-y-2', 'opacity-0');
          });
        } else {
          toast.classList.remove('translate-y-2', 'opacity-0');
        }

        setTimeout(() => {
          if (toast.classList) toast.classList.add('opacity-0', 'translate-y-2');
          setTimeout(() => {
            if (toast && typeof toast.remove === 'function') toast.remove();
          }, 300);
        }, 3500);
      }
    };
  }

  // Expose globally
  window.visionStoreLocatorFormApp = visionStoreLocatorFormApp;

  // Register with Alpine if Alpine is already loaded or when it initializes
  if (window.Alpine) {
    window.Alpine.data('visionStoreLocatorFormApp', visionStoreLocatorFormApp);
  } else {
    document.addEventListener('alpine:init', () => {
      window.Alpine.data('visionStoreLocatorFormApp', visionStoreLocatorFormApp);
    });
  }
})();
