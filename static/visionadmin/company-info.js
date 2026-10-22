// static/visionadmin/company-info.js - Contact Info Controller

document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('company-info-form');
  const btnSave = document.getElementById('btn-save-company');
  const saveIcon = document.getElementById('save-icon');
  const saveSpinner = document.getElementById('save-spinner');

  // Input fields
  const waNumInput = document.getElementById('whatsapp_number');
  const waDisplayInput = document.getElementById('whatsapp_display_number');
  const phoneDisplayInput = document.getElementById('phone_number');
  const phoneCallInput = document.getElementById('phone_call_number');

  // Preview elements
  const linkWaPreview = document.getElementById('link-wa-preview');
  const linkCallPreview = document.getElementById('link-call-preview');
  const previewHeaderBtn = document.getElementById('preview-header-btn');
  const previewPhoneDisplay = document.getElementById('preview-phone-display');
  const previewWaBtn = document.getElementById('preview-wa-btn');
  const previewWaDisplay = document.getElementById('preview-wa-display');

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function showToast(message, isError = false) {
    let toast = document.getElementById('va-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'va-toast';
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.className = `fixed bottom-5 right-5 z-50 transform transition-all duration-300 translate-y-0 opacity-100 flex items-center gap-3 px-5 py-3.5 rounded-2xl shadow-2xl border text-sm font-bold ${
      isError
        ? 'bg-rose-50 border-rose-200 text-rose-800'
        : 'bg-emerald-50 border-emerald-200 text-emerald-800'
    }`;
    setTimeout(() => {
      toast.className = 'fixed bottom-5 right-5 z-50 transform transition-all duration-300 translate-y-20 opacity-0 pointer-events-none flex items-center gap-3 px-5 py-3.5 rounded-2xl shadow-2xl border text-sm font-bold';
    }, 4000);
  }

  function cleanDigits(val) {
    return (val || '').toString().replace(/[^\d]/g, '');
  }

  function cleanTel(val) {
    val = (val || '').toString().trim();
    const hasPlus = val.startsWith('+');
    const digits = val.replace(/[^\d]/g, '');
    return (hasPlus ? '+' : '') + digits;
  }

  function updatePreview() {
    const rawWa = waNumInput ? waNumInput.value.trim() : '';
    const cleanWa = cleanDigits(rawWa) || '971505069575';
    const waDisplay = waDisplayInput ? waDisplayInput.value.trim() : '';
    const phoneDisplay = phoneDisplayInput ? phoneDisplayInput.value.trim() : '';
    const rawCall = phoneCallInput ? phoneCallInput.value.trim() : '';
    const cleanCall = cleanTel(rawCall) || '+971505069575';

    if (linkWaPreview) linkWaPreview.textContent = `https://wa.me/${cleanWa}`;
    if (linkCallPreview) linkCallPreview.textContent = `tel:${cleanCall}`;

    if (previewHeaderBtn) previewHeaderBtn.href = `tel:${cleanCall}`;
    if (previewPhoneDisplay) previewPhoneDisplay.textContent = phoneDisplay || '+971 50 506 9575';

    if (previewWaBtn) previewWaBtn.href = `https://wa.me/${cleanWa}`;
    if (previewWaDisplay) previewWaDisplay.textContent = waDisplay || `+${cleanWa}`;
  }

  // Bind input listeners
  [waNumInput, waDisplayInput, phoneDisplayInput, phoneCallInput].forEach(input => {
    if (input) {
      input.addEventListener('input', updatePreview);
    }
  });

  // Auto-sync call number when display phone is edited if call number is empty
  if (phoneDisplayInput && phoneCallInput) {
    phoneDisplayInput.addEventListener('blur', function () {
      if (!phoneCallInput.value.trim()) {
        phoneCallInput.value = cleanTel(phoneDisplayInput.value);
        updatePreview();
      }
    });
  }

  // Auto-sync WhatsApp display when WhatsApp number is typed
  if (waNumInput && waDisplayInput) {
    waNumInput.addEventListener('blur', function () {
      if (!waDisplayInput.value.trim() && waNumInput.value.trim()) {
        waDisplayInput.value = '+' + cleanDigits(waNumInput.value);
        updatePreview();
      }
    });
  }

  async function loadContactInfo() {
    try {
      const res = await fetch('/visionadmin/api/company-info', {
        headers: { 'Accept': 'application/json' }
      });
      const data = await res.json();
      if (data && (data.company_info || data.compyinfo)) {
        const info = data.company_info || data.compyinfo;
        if (waNumInput) waNumInput.value = info.whatsapp_number || '971505069575';
        if (waDisplayInput) waDisplayInput.value = info.whatsapp_display_number || info.whatsapp_display || '+971 50 506 9575';
        if (phoneDisplayInput) phoneDisplayInput.value = info.phone_number || info.phone || '+971 50 506 9575';
        if (phoneCallInput) phoneCallInput.value = info.phone_call_number || info.phone_call || '+971505069575';
        updatePreview();
      }
    } catch (err) {
      console.error('Failed to load contact info:', err);
      showToast('Failed to load contact info from server', true);
    }
  }

  async function saveContactInfo() {
    if (!btnSave) return;
    
    // UI state
    btnSave.disabled = true;
    if (saveIcon) saveIcon.classList.add('hidden');
    if (saveSpinner) saveSpinner.classList.remove('hidden');

    const payload = {
      whatsapp_number: cleanDigits(waNumInput ? waNumInput.value : ''),
      whatsapp_display_number: waDisplayInput ? waDisplayInput.value.trim() : '',
      phone_number: phoneDisplayInput ? phoneDisplayInput.value.trim() : '',
      phone_call_number: cleanTel(phoneCallInput ? phoneCallInput.value : '')
    };

    try {
      const res = await fetch('/visionadmin/api/company-info', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': getCsrfToken()
        },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(data.message || 'Contact info saved successfully!');
        if (data.company_info) {
          const info = data.company_info;
          if (waNumInput) waNumInput.value = info.whatsapp_number;
          if (waDisplayInput) waDisplayInput.value = info.whatsapp_display_number;
          if (phoneDisplayInput) phoneDisplayInput.value = info.phone_number;
          if (phoneCallInput) phoneCallInput.value = info.phone_call_number;
          updatePreview();
        }
      } else {
        showToast(data.message || 'Failed to save configuration', true);
      }
    } catch (err) {
      console.error('Error saving contact info:', err);
      showToast('Error saving configuration: ' + err.message, true);
    } finally {
      btnSave.disabled = false;
      if (saveIcon) saveIcon.classList.remove('hidden');
      if (saveSpinner) saveSpinner.classList.add('hidden');
    }
  }

  if (btnSave) {
    btnSave.addEventListener('click', saveContactInfo);
  }

  // Initial load
  loadContactInfo();
});
