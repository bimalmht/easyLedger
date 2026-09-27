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
  const btn = document.getElementById('btnSaveSup');
  btn.disabled = true;
  btn.innerText = 'Saving...';

  const formData = new FormData();
  formData.append('name', document.getElementById('modalSupName').value.trim());
  formData.append('pan_vat_number', document.getElementById('modalSupPan').value.trim());
  formData.append('address', document.getElementById('modalSupAddress').value.trim());
  formData.append('phone', document.getElementById('modalSupPhone').value.trim());

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

  // Store product-tagged tax rates on the row
  tr.dataset.vatRate = p.vat_rate !== undefined ? p.vat_rate : 13.0;
  tr.dataset.exciseRate = p.excise_rate !== undefined ? p.excise_rate : 0.0;

  // Store hidden inputs for form post
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

        // Always show persistent Quick Create product footer
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
      // Reload cache and re-populate the charge row
      loadOtherChargesMaster(() => {
        // Update all select dropdowns on screen
        document.querySelectorAll('.chargeSelect').forEach(sel => {
          const opt = document.createElement('option');
          opt.value = newCharge.id;
          opt.textContent = `${newCharge.name} (${newCharge.code})`;
          sel.insertBefore(opt, sel.lastElementChild);
        });
        // If no rows exist or last select has no charge, add/select it
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

  // Include "+ Create new in Master" as the final option in the dropdown
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

  // A. Compute line items using product-specific rates
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

  // B. Sum other charges
  let totalOtherCharges = 0;
  document.querySelectorAll('.chargeAmount').forEach(inp => {
    totalOtherCharges += parseFloat(inp.value) || 0;
  });

  // C. Apportion other charges to compute unit landed cost
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

  // D. Update Summary Box
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

document.addEventListener('DOMContentLoaded', () => {
  loadOtherChargesMaster();
  addPurchaseRow();
});