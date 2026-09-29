/**
 * EasyLedger ERP - Purchase Invoice Engine
 */

const VAT_RATE = 13.00;
const EXCISE_RATE = 5.00;

let confirmedSupplierName = "";
let targetRowForNewProduct = null;
let otherChargesMasterCache = [];

// =============================================================================
// 1. Supplier Search & Immediate Blur Validation
// =============================================================================
const supInput = document.getElementById('supplierSearchInput');
const supResults = document.getElementById('supplierResults');
const supId = document.getElementById('selectedSupplierId');
const supMeta = document.getElementById('supplierMeta');
const supErr = document.getElementById('supplierError');

function fetchAndRenderSuppliers(query = '') {
  fetch(`/api/suppliers/search/?q=${encodeURIComponent(query)}`)
    .then(r => r.json())
    .then(data => {
      supResults.innerHTML = '';

      if (data.results && data.results.length > 0) {
        data.results.forEach(s => {
          const div = document.createElement('div');
          div.className = 'p-2.5 hover:bg-slate-100 cursor-pointer border-b border-slate-100 transition-colors';
          div.innerHTML = `<div class="font-bold text-slate-800">${s.name}</div><div class="text-[11px] text-slate-500 font-mono">PAN: ${s.pan} | ${s.address}</div>`;
          div.onmousedown = (e) => e.preventDefault();
          div.onclick = () => {
            selectSupplier(s);
            supResults.classList.add('hidden');
          };
          supResults.appendChild(div);
        });
      }

      // Always show "+ Create new supplier in Master" at bottom
      const createDiv = document.createElement('div');
      createDiv.className = 'p-2.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold cursor-pointer text-xs border-t border-indigo-200 flex items-center justify-between sticky bottom-0';
      createDiv.innerHTML = `<span>+ Create new supplier ${query ? `"${query}" ` : ''}in Master</span><span class="text-[10px] bg-indigo-200 text-indigo-800 px-1.5 py-0.5 rounded">Quick Add</span>`;
      createDiv.onmousedown = (e) => e.preventDefault();
      createDiv.onclick = () => {
        supResults.classList.add('hidden');
        openSupplierModal(query);
      };
      supResults.appendChild(createDiv);

      supResults.classList.remove('hidden');
    })
    .catch(err => console.error("Supplier Search error:", err));
}

if (supInput) {
  supInput.addEventListener('focus', function() {
    fetchAndRenderSuppliers(this.value.trim());
  });

  supInput.addEventListener('input', function() {
    const currentVal = this.value.trim();
    if (currentVal !== confirmedSupplierName) {
      supId.value = '';
      supMeta.innerText = '';
    }
    fetchAndRenderSuppliers(currentVal);
  });

  supInput.addEventListener('blur', function() {
    setTimeout(() => {
      supResults.classList.add('hidden');
      const val = this.value.trim();
      if (val && (!supId.value || val !== confirmedSupplierName)) {
        this.classList.add('border-rose-500', 'bg-rose-50');
        supErr.innerText = "Supplier not registered in Master. Select from list or create new.";
        supErr.classList.remove('hidden');
      } else {
        this.classList.remove('border-rose-500', 'bg-rose-50');
        supErr.classList.add('hidden');
      }
    }, 200);
  });
}

function selectSupplier(s) {
  supInput.value = s.name;
  confirmedSupplierName = s.name;
  supId.value = s.id;
  supMeta.innerText = `PAN: ${s.pan} | Address: ${s.address}`;
  supErr.classList.add('hidden');
  supInput.classList.remove('border-rose-500', 'bg-rose-50');
}

function openSupplierModal(prefillName = '') {
  document.getElementById('modalSupName').value = prefillName;
  document.getElementById('supplierModal').classList.remove('hidden');
  if (prefillName) {
    document.getElementById('modalSupPan').focus();
  } else {
    document.getElementById('modalSupName').focus();
  }
}

function closeSupplierModal() {
  document.getElementById('supplierModal').classList.add('hidden');
  document.getElementById('quickSupplierForm').reset();
}

function submitQuickSupplier(e) {
  e.preventDefault();
  const panInput = document.getElementById('modalSupPan');
  const panVal = panInput.value.trim();
  const panErr = document.getElementById('modalSupPanErr');

  if (!/^\d{9}$/.test(panVal)) {
    panInput.classList.add('border-rose-500', 'bg-rose-50');
    if (panErr) {
      panErr.innerText = "PAN / VAT must be exactly 9 numeric digits.";
      panErr.classList.remove('hidden');
    } else {
      alert("PAN / VAT must be exactly 9 numeric digits.");
    }
    panInput.focus();
    return;
  } else {
    panInput.classList.remove('border-rose-500', 'bg-rose-50');
    if (panErr) panErr.classList.add('hidden');
  }

  const btn = document.getElementById('btnSaveSup');
  btn.disabled = true;
  btn.innerText = 'Saving...';

  const formData = new FormData();
  formData.append('name', document.getElementById('modalSupName').value.trim());
  formData.append('pan_vat_number', panVal);
  formData.append('contact_person', document.getElementById('modalSupContact').value.trim());
  formData.append('phone', document.getElementById('modalSupPhone').value.trim());
  formData.append('email', document.getElementById('modalSupEmail').value.trim());
  formData.append('address', document.getElementById('modalSupAddress').value.trim());
  formData.append('is_vat_exempt', document.getElementById('modalSupExempt').checked);
  formData.append('apply_vat', document.getElementById('modalSupVat').checked);
  formData.append('apply_excise', document.getElementById('modalSupExcise').checked);

  fetch('/api/suppliers/quick-create/', {
    method: 'POST',
    headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },
    body: formData
  })
  .then(r => r.json())
  .then(res => {
    btn.disabled = false;
    btn.innerText = 'Save to Master & Select';
    if (res.status === 'success') {
      selectSupplier(res.supplier);
      closeSupplierModal();
    } else {
      alert(res.message);
    }
  })
  .catch(err => {
    btn.disabled = false;
    btn.innerText = 'Save to Master & Select';
    alert("Server error: " + err);
  });
}

// =============================================================================
// 2. Product Search & Quick Product Modal
// =============================================================================
function openProductModal(prefillName = '', trElement = null) {
  targetRowForNewProduct = trElement;
  document.getElementById('modalProdName').value = prefillName;
  document.getElementById('productModal').classList.remove('hidden');
  if (prefillName) {
    document.getElementById('modalProdPrice').focus();
  } else {
    document.getElementById('modalProdName').focus();
  }
}

function closeProductModal() {
  document.getElementById('productModal').classList.add('hidden');
  document.getElementById('quickProductForm').reset();
  targetRowForNewProduct = null;
}

function submitQuickProduct(e) {
  e.preventDefault();
  const btn = document.getElementById('btnSaveProd');
  btn.disabled = true;
  btn.innerText = 'Saving...';

  const formData = new FormData();
  formData.append('name', document.getElementById('modalProdName').value.trim());
  formData.append('hs_code', document.getElementById('modalProdHs').value.trim());
  formData.append('selling_price', document.getElementById('modalProdPrice').value.trim());
  formData.append('apply_vat', document.getElementById('modalProdVat').checked);
  formData.append('apply_excise', document.getElementById('modalProdExcise').checked);

  fetch('/api/products/quick-create/', {
    method: 'POST',
    headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },
    body: formData
  })
  .then(r => r.json())
  .then(res => {
    btn.disabled = false;
    btn.innerText = 'Save to Master & Use';
    if (res.status === 'success') {
      const p = res.product;
      let targetRow = targetRowForNewProduct;

      if (!targetRow) {
        const rows = document.querySelectorAll('#itemsBody tr');
        for (let r of rows) {
          if (!r.querySelector('.productId').value) {
            targetRow = r;
            break;
          }
        }
        if (!targetRow) {
          addPurchaseRow();
          const allRows = document.querySelectorAll('#itemsBody tr');
          targetRow = allRows[allRows.length - 1];
        }
      }

      applyProductToRow(p, targetRow);
      closeProductModal();
    } else {
      alert(res.message);
    }
  })
  .catch(err => {
    btn.disabled = false;
    btn.innerText = 'Save to Master & Use';
    alert("Server error: " + err);
  });
}

function applyProductToRow(p, tr) {
  const pInput = tr.querySelector('.productSearch');
  const pErr = tr.querySelector('.productError');
  pInput.value = p.name;
  pInput.dataset.confirmedName = p.name;
  pInput.classList.remove('border-rose-500', 'bg-rose-50');
  if (pErr) pErr.classList.add('hidden');

  tr.querySelector('.productId').value = p.id;
  tr.querySelector('.price').value = parseFloat(p.unit_price || 0).toFixed(2);

  tr.dataset.vatRate = p.vat_rate !== undefined ? p.vat_rate : 13.0;
  tr.dataset.exciseRate = p.excise_rate !== undefined ? p.excise_rate : 0.0;

  tr.querySelector('.lineExciseRate').value = tr.dataset.exciseRate;
  tr.querySelector('.lineVatRate').value = tr.dataset.vatRate;

  calculateTotals();
}

function addPurchaseRow() {
  const tbody = document.getElementById('itemsBody');
  const tr = document.createElement('tr');
  tr.className = 'border-b border-slate-100';
  tr.dataset.vatRate = "13.0";
  tr.dataset.exciseRate = "0.0";

  tr.innerHTML = `
    <td class="p-2 relative overflow-visible">
      <input type="text" placeholder="Click to choose or type..." autocomplete="off" class="productSearch w-full border border-slate-300 rounded p-2 text-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
      <input type="hidden" name="product_id[]" class="productId">
      <input type="hidden" name="excise_rate[]" class="lineExciseRate" value="0.0">
      <input type="hidden" name="vat_rate[]" class="lineVatRate" value="13.0">
      <p class="productError hidden text-[10.5px] text-rose-600 font-semibold mt-0.5 leading-tight"></p>
      <div class="productDropdown hidden absolute left-0 top-full mt-1 w-80 bg-white border border-slate-300 rounded-lg shadow-2xl z-50 max-h-56 overflow-y-auto"></div>
    </td>
    <td class="p-2"><input type="number" step="0.01" min="0.01" name="qty[]" value="1.00" oninput="calculateTotals()" class="qty w-full border border-slate-300 rounded p-2 text-xs text-right font-mono"></td>
    <td class="p-2"><input type="number" step="0.01" min="0" name="rate[]" value="0.00" oninput="calculateTotals()" class="price w-full border border-slate-300 rounded p-2 text-xs text-right font-mono"></td>
    <td class="p-2"><input type="number" step="0.01" min="0" name="discount[]" value="0.00" oninput="calculateTotals()" class="discount w-full border border-slate-300 rounded p-2 text-xs text-right font-mono"></td>
    <td class="p-2 text-right font-mono lineTaxable">0.00</td>
    <td class="p-2 text-right font-mono lineExcise">0.00</td>
    <td class="p-2 text-right font-mono lineVat">0.00</td>
    <td class="p-2 text-right font-mono font-bold lineTotal">0.00</td>
    <td class="p-2 text-right font-mono font-bold text-indigo-700 bg-indigo-50/50 lineLanded">0.0000</td>
    <td class="p-2 text-center"><button type="button" onclick="this.closest('tr').remove(); calculateTotals();" class="text-rose-500 font-bold hover:text-rose-700 text-sm">&times;</button></td>
  `;
  tbody.appendChild(tr);
  bindProductSearch(tr);
}

function bindProductSearch(tr) {
  const pInput = tr.querySelector('.productSearch');
  const pDropdown = tr.querySelector('.productDropdown');
  const pId = tr.querySelector('.productId');
  const pErr = tr.querySelector('.productError');

  function fetchAndRenderProducts(q = '') {
    fetch(`/api/products/search/?q=${encodeURIComponent(q)}`)
      .then(r => r.json())
      .then(data => {
        pDropdown.innerHTML = '';

        if (data.results && data.results.length > 0) {
          data.results.forEach(p => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'p-2.5 hover:bg-slate-100 cursor-pointer border-b border-slate-100 text-[11px] transition-colors';
            itemDiv.innerHTML = `<div class="font-bold text-slate-800">${p.name}</div><div class="text-slate-500 font-mono">Rate: Rs. ${p.unit_price} | HS: ${p.hs_code}</div>`;
            itemDiv.onmousedown = (e) => e.preventDefault();
            itemDiv.onclick = () => {
              applyProductToRow(p, tr);
              pDropdown.classList.add('hidden');
            };
            pDropdown.appendChild(itemDiv);
          });
        }

        const createDiv = document.createElement('div');
        createDiv.className = 'p-2.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold cursor-pointer text-xs border-t border-indigo-200 flex items-center justify-between sticky bottom-0';
        createDiv.innerHTML = `<span>+ Create new product ${q ? `"${q}" ` : ''}in Master</span><span class="text-[10px] bg-indigo-200 text-indigo-800 px-1.5 py-0.5 rounded">Quick Add</span>`;
        createDiv.onmousedown = (e) => e.preventDefault();
        createDiv.onclick = () => {
          pDropdown.classList.add('hidden');
          openProductModal(q, tr);
        };
        pDropdown.appendChild(createDiv);

        pDropdown.classList.remove('hidden');
      });
  }

  pInput.addEventListener('focus', function() {
    fetchAndRenderProducts(this.value.trim());
  });

  pInput.addEventListener('input', function() {
    const currentVal = this.value.trim();
    if (currentVal !== (pInput.dataset.confirmedName || '')) {
      pId.value = '';
    }
    fetchAndRenderProducts(currentVal);
  });

  pInput.addEventListener('blur', function() {
    setTimeout(() => {
      pDropdown.classList.add('hidden');
      const val = this.value.trim();
      if (val && (!pId.value || val !== (this.dataset.confirmedName || ''))) {
        this.classList.add('border-rose-500', 'bg-rose-50');
        pErr.innerText = "Product not registered in Master. Select from list or create new.";
        pErr.classList.remove('hidden');
      } else {
        this.classList.remove('border-rose-500', 'bg-rose-50');
        pErr.classList.add('hidden');
      }
    }, 200);
  });
}

// =============================================================================
// 3. Other Charges Master & Quick Modal
// =============================================================================
const chargesContainer = document.getElementById('chargesContainer');

function loadOtherChargesMaster(callback) {
  fetch('/api/other-charges/list/')
    .then(r => r.json())
    .then(data => {
      otherChargesMasterCache = data.results || [];
      if (callback) callback();
    })
    .catch(err => console.error("Error loading other charges master:", err));
}

window.openChargeModal = function() {
  document.getElementById('chargeModal').classList.remove('hidden');
  document.getElementById('modalChgName').focus();
};

window.closeChargeModal = function() {
  document.getElementById('chargeModal').classList.add('hidden');
  document.getElementById('quickChargeForm').reset();
};

window.submitQuickCharge = function(e) {
  e.preventDefault();
  const btn = document.getElementById('btnSaveChg');
  btn.disabled = true;
  btn.innerText = 'Saving...';

  const formData = new FormData();
  formData.append('name', document.getElementById('modalChgName').value.trim());
  formData.append('code', document.getElementById('modalChgCode').value.trim());

  fetch('/api/other-charges/quick-create/', {
    method: 'POST',
    headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },
    body: formData
  })
  .then(r => r.json())
  .then(res => {
    btn.disabled = false;
    btn.innerText = 'Save to Master & Use';
    if (res.status === 'success') {
      const newCharge = res.charge;
      loadOtherChargesMaster(() => {
        document.querySelectorAll('.chargeSelect').forEach(sel => {
          const opt = document.createElement('option');
          opt.value = newCharge.id;
          opt.textContent = `${newCharge.name} (${newCharge.code})`;
          sel.insertBefore(opt, sel.lastElementChild);
        });
        const lastRow = document.querySelector('.chargeRow:last-child');
        if (lastRow) {
          lastRow.querySelector('.chargeSelect').value = newCharge.id;
        } else {
          addChargeRow(newCharge.id);
        }
        calculateTotals();
      });
      closeChargeModal();
    } else {
      alert(res.message);
    }
  })
  .catch(err => {
    btn.disabled = false;
    btn.innerText = 'Save to Master & Use';
    alert("Connection error: " + err);
  });
};

function addChargeRow(selectedChargeId = null) {
  const row = document.createElement('div');
  row.className = 'flex items-center space-x-2 chargeRow';

  let optionsHtml = otherChargesMasterCache.map(c => 
    `<option value="${c.id}" ${selectedChargeId === c.id ? 'selected' : ''}>${c.name} (${c.code})</option>`
  ).join('');

  if (otherChargesMasterCache.length === 0) {
    optionsHtml = '<option value="">No charges configured in Master</option>';
  }

  optionsHtml += '<option value="__CREATE_NEW__" class="font-bold text-indigo-600 bg-indigo-50">+ Create new in Master</option>';

  row.innerHTML = `
    <select name="other_charge_id[]" onchange="handleChargeSelectChange(this)" class="chargeSelect w-1/2 p-2 border border-slate-300 rounded-lg text-xs bg-white focus:ring-1 focus:ring-indigo-500">
      ${optionsHtml}
    </select>
    <input type="number" step="0.01" min="0" placeholder="Amount (Rs.)" name="other_charge_amount[]" value="0.00" oninput="calculateTotals()"
           class="chargeAmount w-1/3 p-2 text-right border border-slate-300 rounded-lg text-xs font-mono focus:ring-1 focus:ring-indigo-500">
    <button type="button" onclick="this.closest('.chargeRow').remove(); calculateTotals();" class="text-rose-500 font-bold hover:text-rose-700 px-2 text-sm">&times;</button>
  `;

  chargesContainer.appendChild(row);
  calculateTotals();
}

window.handleChargeSelectChange = function(sel) {
  if (sel.value === '__CREATE_NEW__') {
    sel.value = '';
    openChargeModal();
  }
};

// =============================================================================
// 4. Totals Recalculation Engine
// =============================================================================
function calculateTotals() {
  let grossSubtotal = 0;
  let totalDiscount = 0;
  let totalTaxable = 0;
  let totalExcise = 0;
  let totalVat = 0;

  const rows = document.querySelectorAll('#itemsBody tr');

  rows.forEach(row => {
    const qty = parseFloat(row.querySelector('.qty').value) || 0;
    const rate = parseFloat(row.querySelector('.price').value) || 0;
    const disc = parseFloat(row.querySelector('.discount').value) || 0;

    const rowExciseRate = parseFloat(row.dataset.exciseRate) || 0.0;
    const rowVatRate = parseFloat(row.dataset.vatRate) || 0.0;

    const gross = qty * rate;
    const taxable = Math.max(0, gross - disc);
    const excise = taxable * (rowExciseRate / 100.0);
    const vat = (taxable + excise) * (rowVatRate / 100.0);
    const lineTotal = taxable + excise + vat;

    row.querySelector('.lineTaxable').innerText = taxable.toFixed(2);
    row.querySelector('.lineExcise').innerText = excise.toFixed(2);
    row.querySelector('.lineVat').innerText = vat.toFixed(2);
    row.querySelector('.lineTotal').innerText = lineTotal.toFixed(2);

    grossSubtotal += gross;
    totalDiscount += disc;
    totalTaxable += taxable;
    totalExcise += excise;
    totalVat += vat;
  });

  let totalOtherCharges = 0;
  document.querySelectorAll('.chargeAmount').forEach(inp => {
    totalOtherCharges += parseFloat(inp.value) || 0;
  });

  rows.forEach(row => {
    const qty = parseFloat(row.querySelector('.qty').value) || 0;
    const taxable = parseFloat(row.querySelector('.lineTaxable').innerText) || 0;
    const excise = parseFloat(row.querySelector('.lineExcise').innerText) || 0;

    let allocatedCharge = 0;
    if (totalTaxable > 0) {
      allocatedCharge = totalOtherCharges * (taxable / totalTaxable);
    }

    const totalLandedCost = taxable + excise + allocatedCharge;
    const unitLanded = qty > 0 ? (totalLandedCost / qty) : 0;
    row.querySelector('.lineLanded').innerText = unitLanded.toFixed(4);
  });

  const grandTotal = totalTaxable + totalExcise + totalVat + totalOtherCharges;

  document.getElementById('displayGross').innerText = grossSubtotal.toFixed(2);
  document.getElementById('displayDiscount').innerText = totalDiscount > 0 ? `-${totalDiscount.toFixed(2)}` : "-0.00";
  document.getElementById('displayTaxable').innerText = totalTaxable.toFixed(2);
  document.getElementById('displayExcise').innerText = totalExcise.toFixed(2);
  document.getElementById('displayVat').innerText = totalVat.toFixed(2);
  document.getElementById('displayOtherCharges').innerText = totalOtherCharges.toFixed(2);
  document.getElementById('displayGrand').innerText = grandTotal.toFixed(2);
}

// =============================================================================
// 5. Submit Validation & Outside Click Closers
// =============================================================================
function validateBeforeSubmit(e) {
  if (!supId.value || supInput.value.trim() !== confirmedSupplierName) {
    e.preventDefault();
    supInput.classList.add('border-rose-500', 'bg-rose-50');
    supErr.innerText = "Supplier not registered in Master. Select from list or click '+ Create new supplier'.";
    supErr.classList.remove('hidden');
    supInput.focus();
    return false;
  }

  const rows = document.querySelectorAll('#itemsBody tr');
  let hasValidRow = false;

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const pInput = row.querySelector('.productSearch');
    const pId = row.querySelector('.productId');
    const pErr = row.querySelector('.productError');
    const pVal = pInput.value.trim();

    if (pVal) {
      if (!pId.value || pVal !== (pInput.dataset.confirmedName || '')) {
        e.preventDefault();
        pInput.classList.add('border-rose-500', 'bg-rose-50');
        pErr.innerText = "Product not registered in Master. Select from list or click '+ Create in Master'.";
        pErr.classList.remove('hidden');
        pInput.focus();
        return false;
      }
      hasValidRow = true;
    }
  }

  if (!hasValidRow) {
    e.preventDefault();
    alert("Please add at least one registered product from the Master.");
    return false;
  }

  return true;
}

document.addEventListener('click', function(e) {
  if (!e.target.closest('#supplierSearchInput') && !e.target.closest('#supplierResults')) {
    supResults.classList.add('hidden');
  }
  document.querySelectorAll('#itemsBody tr').forEach(tr => {
    if (!tr.contains(e.target)) {
      const dd = tr.querySelector('.productDropdown');
      if (dd) dd.classList.add('hidden');
    }
  });
});

// =============================================================================
// 6. Multi-Instance Bikram Sambat (BS) <-> Gregorian (AD) Date Engine
// =============================================================================
const BS_MONTH_NAMES = [
  "Baishakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin",
  "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra"
];

function initNepaliDatePickers() {
  document.querySelectorAll('.nepali-datepicker-group').forEach(group => {
    const bsInput = group.querySelector('.bs-date-input');
    const toggleBtn = group.querySelector('.bs-picker-toggle');
    const dropdown = group.querySelector('.bs-calendar-dropdown');
    const errElem = group.querySelector('.bs-date-error');
    const adInputSelector = group.dataset.adTarget;
    const adInput = adInputSelector ? document.querySelector(adInputSelector) : null;

    if (!bsInput || !dropdown) return;

    dropdown.innerHTML = `
      <div class="flex items-center justify-between gap-1 mb-2 pb-2 border-b border-slate-100">
        <select class="bs-year-select border border-slate-200 rounded px-1.5 py-1 text-slate-700 font-bold focus:ring-1 focus:ring-indigo-500"></select>
        <select class="bs-month-select border border-slate-200 rounded px-1.5 py-1 text-slate-700 font-bold focus:ring-1 focus:ring-indigo-500">
          ${BS_MONTH_NAMES.map((name, idx) => `<option value="${idx + 1}">${name}</option>`).join('')}
        </select>
      </div>
      <div class="grid grid-cols-7 gap-1 text-center font-bold text-[10px] text-slate-400 mb-1">
        <span>Su</span><span>Mo</span><span>Tu</span><span>We</span><span>Th</span><span>Fr</span><span class="text-rose-500">Sa</span>
      </div>
      <div class="bs-days-grid grid grid-cols-7 gap-1 font-mono text-[11px] text-center min-h-[140px]"></div>
    `;

    const yearSelect = dropdown.querySelector('.bs-year-select');
    const monthSelect = dropdown.querySelector('.bs-month-select');
    const daysGrid = dropdown.querySelector('.bs-days-grid');

    for (let y = 2095; y >= 2000; y--) {
      const opt = document.createElement('option');
      opt.value = y;
      opt.textContent = y;
      yearSelect.appendChild(opt);
    }

    function showError(msg) {
      bsInput.classList.add('border-rose-500', 'bg-rose-50');
      if (errElem) {
        errElem.innerText = msg;
        errElem.classList.remove('hidden');
      }
    }

    function clearError() {
      bsInput.classList.remove('border-rose-500', 'bg-rose-50');
      if (errElem) {
        errElem.classList.add('hidden');
        errElem.innerText = '';
      }
    }

    function validateAndSync() {
      const val = bsInput.value.trim();
      if (!val) {
        if (bsInput.hasAttribute('required')) {
          showError("Bikram Sambat (BS) date is mandatory.");
          return false;
        }
        clearError();
        if (adInput) adInput.value = '';
        return true;
      }

      const match = val.match(/^(\d{4})-(\d{2})-(\d{2})$/);
      if (!match) {
        showError("Invalid format. Use YYYY-MM-DD (e.g. 2083-06-13).");
        return false;
      }

      const y = parseInt(match[1], 10);
      const m = parseInt(match[2], 10);
      const d = parseInt(match[3], 10);

      if (y < 2000 || y > 2095) {
        showError(`Year ${y} out of range (2000-2095 BS).`);
        return false;
      }
      if (m < 1 || m > 12) {
        showError("Month must be between 01 and 12.");
        return false;
      }

      const maxDays = window.NepaliDateEngine.getMonthDays(y, m);
      if (d < 1 || d > maxDays) {
        showError(`Month ${String(m).padStart(2, '0')}/${y} has only ${maxDays} days.`);
        return false;
      }

      const adEquivalent = window.NepaliDateEngine.bsToAd(val);
      if (!adEquivalent) {
        showError("Conversion error for this date.");
        return false;
      }

      clearError();
      if (adInput) {
        adInput.value = adEquivalent;
      }
      return true;
    }

    function renderGrid(year, month, selectedDay) {
      daysGrid.innerHTML = '';
      const totalDays = window.NepaliDateEngine.getMonthDays(year, month);
      const startDayOfWeek = window.NepaliDateEngine.getBsDayOfWeek(year, month, 1);

      for (let i = 0; i < startDayOfWeek; i++) {
        const blank = document.createElement('span');
        blank.className = 'py-1';
        daysGrid.appendChild(blank);
      }

      for (let day = 1; day <= totalDays; day++) {
        const btn = document.createElement('button');
        btn.type = 'button';
        const dayOfWeek = (startDayOfWeek + day - 1) % 7;
        const isSat = dayOfWeek === 6;

        let btnClass = 'py-1 rounded hover:bg-indigo-100 hover:text-indigo-700 transition-colors ';
        if (day === selectedDay) {
          btnClass += 'bg-indigo-600 text-white font-bold ';
        } else if (isSat) {
          btnClass += 'text-rose-600 font-semibold ';
        } else {
          btnClass += 'text-slate-700 ';
        }

        btn.className = btnClass;
        btn.textContent = day;

        btn.onmousedown = (e) => e.preventDefault();
        btn.onclick = () => {
          const formatted = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
          bsInput.value = formatted;
          validateAndSync();
          dropdown.classList.add('hidden');
          bsInput.focus();
        };

        daysGrid.appendChild(btn);
      }
    }

    function syncGridFromInput() {
      let y = 2083, m = 6, d = 1;
      const parts = bsInput.value.split('-').map(Number);
      if (parts.length === 3 && !isNaN(parts[0])) {
        y = parts[0];
        m = parts[1];
        d = parts[2];
      }
      yearSelect.value = y;
      monthSelect.value = m;
      renderGrid(y, m, d);
    }

    bsInput.addEventListener('blur', validateAndSync);
    bsInput.addEventListener('input', () => {
      if (bsInput.value.length === 10) {
        validateAndSync();
      } else {
        clearError();
      }
    });

    if (toggleBtn) {
      toggleBtn.onclick = (e) => {
        e.stopPropagation();
        document.querySelectorAll('.bs-calendar-dropdown').forEach(d => {
          if (d !== dropdown) d.classList.add('hidden');
        });
        dropdown.classList.toggle('hidden');
        if (!dropdown.classList.contains('hidden')) {
          syncGridFromInput();
        }
      };
    }

    yearSelect.addEventListener('change', () => {
      renderGrid(parseInt(yearSelect.value), parseInt(monthSelect.value), 1);
    });
    monthSelect.addEventListener('change', () => {
      renderGrid(parseInt(yearSelect.value), parseInt(monthSelect.value), 1);
    });

    if (adInput) {
      adInput.addEventListener('change', () => {
        if (adInput.value) {
          const bsEquivalent = window.NepaliDateEngine.adToBs(adInput.value);
          if (bsEquivalent) {
            bsInput.value = bsEquivalent;
            clearError();
          }
        }
      });

      if (!adInput.value) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0');
        const dd = String(today.getDate()).padStart(2, '0');
        adInput.value = `${yyyy}-${mm}-${dd}`;
      }
      if (!bsInput.value && adInput.value) {
        bsInput.value = window.NepaliDateEngine.adToBs(adInput.value);
      }
    }
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.nepali-datepicker-group')) {
      document.querySelectorAll('.bs-calendar-dropdown').forEach(d => d.classList.add('hidden'));
    }
  });
}

// =============================================================================
// Initialization on Page Ready
// =============================================================================
document.addEventListener('DOMContentLoaded', () => {
  loadOtherChargesMaster();
  addPurchaseRow();
  initNepaliDatePickers();

  const invoiceForm = document.getElementById('purchaseInvoiceForm');
  if (invoiceForm) {
    invoiceForm.addEventListener('submit', function(e) {
      if (!validateBeforeSubmit(e)) return;

      let allValid = true;
      document.querySelectorAll('.nepali-datepicker-group .bs-date-input').forEach(inp => {
        if (inp.hasAttribute('required') && !inp.value.trim()) {
          inp.classList.add('border-rose-500', 'bg-rose-50');
          allValid = false;
        }
      });

      if (!allValid) {
        e.preventDefault();
        alert("Please ensure all required Bikram Sambat (BS) date fields are filled correctly.");
      }
    });
  }
});