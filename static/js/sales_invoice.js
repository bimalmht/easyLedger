/**
 * EasyLedger ERP - Sales Invoice Engine
 */

document.addEventListener('DOMContentLoaded', () => {
  // Read configuration passed via data attributes on #sales-invoice-config
  const configEl = document.getElementById('sales-invoice-config');
  const allowQuickCustomer = configEl?.dataset.allowQuickCustomer === 'true';
  const allowQuickProduct = configEl?.dataset.allowQuickProduct === 'true';
  const enableFree = configEl?.dataset.enableFree === 'true';
  const enablePromo = configEl?.dataset.enablePromo === 'true';

  let targetRowForNewProduct = null;
  let confirmedCustomerName = "";

  // =============================================================================
  // 1. Customer Search & Immediate Validation
  // =============================================================================
  const custInput = document.getElementById('customerSearchInput');
  const custResults = document.getElementById('customerResults');
  const custId = document.getElementById('selectedCustomerId');
  const custMeta = document.getElementById('customerMeta');
  const custErr = document.getElementById('customerError');

  function fetchAndRenderCustomers(query = '') {
    fetch(`/api/customers/search/?q=${encodeURIComponent(query)}`)
      .then(r => r.json())
      .then(data => {
        custResults.innerHTML = '';
        let hasExactMatch = false;

        if (data.results && data.results.length > 0) {
          data.results.forEach(c => {
            if (c.name.trim().toLowerCase() === query.trim().toLowerCase()) {
              hasExactMatch = true;
            }
            const div = document.createElement('div');
            div.className = 'p-2.5 hover:bg-slate-100 cursor-pointer border-b border-slate-100 transition-colors';
            div.innerHTML = `<div class="font-bold text-slate-800">${c.name}</div><div class="text-[11px] text-slate-500 font-mono">PAN: ${c.tax_number} | ${c.address}</div>`;
            div.onmousedown = (e) => e.preventDefault();
            div.onclick = () => {
              selectCustomer(c);
              custResults.classList.add('hidden');
            };
            custResults.appendChild(div);
          });
        }

        if (allowQuickCustomer) {
          const createDiv = document.createElement('div');
          createDiv.className = 'p-2.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold cursor-pointer text-xs border-t border-indigo-200 flex items-center justify-between sticky bottom-0';
          createDiv.innerHTML = `<span>+ Create new customer ${query ? `"${query}" ` : ''}in Master</span><span class="text-[10px] bg-indigo-200 text-indigo-800 px-1.5 py-0.5 rounded">Quick Add</span>`;
          createDiv.onmousedown = (e) => e.preventDefault();
          createDiv.onclick = () => {
            custResults.classList.add('hidden');
            openCustomerModal(query);
          };
          custResults.appendChild(createDiv);
        } else if (!data.results || data.results.length === 0) {
          custResults.innerHTML = '<div class="p-3 text-slate-400">No customers found</div>';
        }

        custResults.classList.remove('hidden');
      });
  }

  if (custInput) {
    custInput.addEventListener('focus', function() {
      fetchAndRenderCustomers(this.value.trim());
    });

    custInput.addEventListener('input', function() {
      const currentVal = this.value.trim();
      if (currentVal !== confirmedCustomerName) {
        custId.value = '';
        custMeta.innerText = '';
      }
      fetchAndRenderCustomers(currentVal);
    });

    custInput.addEventListener('blur', function() {
      setTimeout(() => {
        custResults.classList.add('hidden');
        const val = this.value.trim();
        if (val && (!custId.value || val !== confirmedCustomerName)) {
          this.classList.add('border-rose-500', 'bg-rose-50');
          custErr.innerText = "Customer not registered in Master. Select from list or create new.";
          custErr.classList.remove('hidden');
        } else {
          this.classList.remove('border-rose-500', 'bg-rose-50');
          custErr.classList.add('hidden');
        }
      }, 200);
    });
  }

  function selectCustomer(c) {
    custInput.value = c.name;
    confirmedCustomerName = c.name;
    custId.value = c.id;
    custMeta.innerText = `PAN: ${c.tax_number} | Address: ${c.address}`;
    custErr.classList.add('hidden');
    custInput.classList.remove('border-rose-500', 'bg-rose-50');
  }

  // Quick Customer Modal Handlers
  window.openCustomerModal = function(prefillName = '') {
    document.getElementById('modalCustName').value = prefillName;
    document.getElementById('customerModal').classList.remove('hidden');
    if (prefillName) {
      document.getElementById('modalCustPan').focus();
    } else {
      document.getElementById('modalCustName').focus();
    }
  };

  window.closeCustomerModal = function() {
    document.getElementById('customerModal').classList.add('hidden');
    document.getElementById('quickCustomerForm').reset();
  };

  window.submitQuickCustomer = function(e) {
    e.preventDefault();
    const btn = document.getElementById('btnSaveCust');
    btn.disabled = true;
    btn.innerText = 'Saving...';

    const formData = new FormData();
    formData.append('name', document.getElementById('modalCustName').value.trim());
    formData.append('tax_number', document.getElementById('modalCustPan').value.trim());
    formData.append('address', document.getElementById('modalCustAddress').value.trim());
    formData.append('phone', document.getElementById('modalCustPhone').value.trim());

    fetch('/api/customers/quick-create/', {
      method: 'POST',
      headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },
      body: formData
    })
    .then(r => r.json())
    .then(res => {
      btn.disabled = false;
      btn.innerText = 'Save to Master & Select';
      if (res.status === 'success') {
        selectCustomer(res.customer);
        closeCustomerModal();
      } else {
        alert(res.message);
      }
    })
    .catch(err => {
      btn.disabled = false;
      btn.innerText = 'Save to Master & Select';
      alert("Failed to connect to server: " + err);
    });
  };

  // =============================================================================
  // 2. Product Search & Modal Creation
  // =============================================================================
  window.openProductModal = function(prefillName = '', trElement = null) {
    targetRowForNewProduct = trElement;
    document.getElementById('modalProdName').value = prefillName;
    document.getElementById('productModal').classList.remove('hidden');
    if (prefillName) {
      document.getElementById('modalProdPrice').focus();
    } else {
      document.getElementById('modalProdName').focus();
    }
  };

  window.closeProductModal = function() {
    document.getElementById('productModal').classList.add('hidden');
    document.getElementById('quickProductForm').reset();
    targetRowForNewProduct = null;
  };

  window.submitQuickProduct = function(e) {
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
            addInvoiceRow();
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
      alert("Failed to connect to server: " + err);
    });
  };

  function applyProductToRow(p, tr) {
    const pInput = tr.querySelector('.productSearch');
    const pErr = tr.querySelector('.productError');
    pInput.value = p.name;
    pInput.dataset.confirmedName = p.name;
    pInput.classList.remove('border-rose-500', 'bg-rose-50');
    if (pErr) pErr.classList.add('hidden');

    tr.querySelector('.productId').value = p.id;
    tr.querySelector('.productDesc').value = p.name;
    tr.querySelector('.price').value = parseFloat(p.unit_price || 0).toFixed(2);
    tr.querySelector('.hsCode').value = p.hs_code || '-';
    calculateTotals();
  }

  window.addInvoiceRow = function() {
    const tbody = document.getElementById('itemsBody');
    const tr = document.createElement('tr');
    tr.className = 'border-b border-slate-100';
    tr.innerHTML = `
      <td class="p-2 relative overflow-visible">
        <input type="text" placeholder="Click to choose or type..." autocomplete="off" class="productSearch w-full border border-slate-300 rounded p-2 text-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500">
        <input type="hidden" name="product_id[]" class="productId">
        <input type="hidden" name="description[]" class="productDesc">
        <p class="productError hidden text-[10.5px] text-rose-600 font-semibold mt-0.5 leading-tight"></p>
        <div class="productDropdown hidden absolute left-0 top-full mt-1 w-80 bg-white border border-slate-300 rounded-lg shadow-2xl z-50 max-h-56 overflow-y-auto"></div>
      </td>
      <td class="p-2"><input type="text" name="hs_code[]" class="hsCode w-full border border-slate-300 rounded p-2 text-xs text-center" value="-"></td>
      <td class="p-2"><input type="number" step="0.01" min="0.01" name="quantity[]" value="1.00" oninput="calculateTotals()" class="qty w-full border border-slate-300 rounded p-2 text-xs text-right font-mono"></td>
      <td class="p-2"><input type="number" step="0.01" min="0" name="unit_price[]" value="0.00" oninput="calculateTotals()" class="price w-full border border-slate-300 rounded p-2 text-xs text-right font-mono"></td>
      ${enableFree ? `
        <td class="p-2 text-center">
          <input type="checkbox" onchange="this.nextElementSibling.value = this.checked ? '1' : '0'; calculateTotals();" class="freeCheck rounded text-indigo-600">
          <input type="hidden" name="is_free[]" value="0">
        </td>
      ` : `<input type="hidden" name="is_free[]" value="0">`}
      ${enablePromo ? `
        <td class="p-2"><input type="text" name="promo_badge[]" placeholder="e.g. Pilot Pen Free" class="w-full border border-slate-300 rounded p-2 text-xs font-sans"></td>
      ` : `<input type="hidden" name="promo_badge[]" value="">`}
      <td class="p-2 text-right font-mono lineAmount">0.00</td>
      <td class="p-2 text-center"><button type="button" onclick="this.closest('tr').remove(); calculateTotals();" class="text-rose-500 font-bold hover:text-rose-700 text-sm">&times;</button></td>
    `;
    tbody.appendChild(tr);
    bindProductSearch(tr);
  };

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
              itemDiv.innerHTML = `<div class="font-bold text-slate-800">${p.name}</div><div class="text-slate-500 font-mono">Rs. ${p.unit_price} | HS: ${p.hs_code}</div>`;
              itemDiv.onmousedown = (e) => e.preventDefault();
              itemDiv.onclick = () => {
                applyProductToRow(p, tr);
                pDropdown.classList.add('hidden');
              };
              pDropdown.appendChild(itemDiv);
            });
          }

          if (allowQuickProduct) {
            const createDiv = document.createElement('div');
            createDiv.className = 'p-2.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold cursor-pointer text-xs border-t border-indigo-200 flex items-center justify-between sticky bottom-0';
            createDiv.innerHTML = `<span>+ Create new product ${q ? `"${q}" ` : ''}in Master</span><span class="text-[10px] bg-indigo-200 text-indigo-800 px-1.5 py-0.5 rounded">Quick Add</span>`;
            createDiv.onmousedown = (e) => e.preventDefault();
            createDiv.onclick = () => {
              pDropdown.classList.add('hidden');
              openProductModal(q, tr);
            };
            pDropdown.appendChild(createDiv);
          } else if (!data.results || data.results.length === 0) {
            pDropdown.innerHTML = '<div class="p-3 text-slate-400">No products found</div>';
          }

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
  // 3. Totals Recalculation Engine
  // =============================================================================
  window.calculateTotals = function() {
    let grossSubtotal = 0;
    let freeTotal = 0;

    document.querySelectorAll('#itemsBody tr').forEach(row => {
      const qty = parseFloat(row.querySelector('.qty').value) || 0;
      const price = parseFloat(row.querySelector('.price').value) || 0;
      const isFree = row.querySelector('.freeCheck') ? row.querySelector('.freeCheck').checked : false;
      const amt = qty * price;

      row.querySelector('.lineAmount').innerText = amt.toFixed(2);
      if (isFree) {
        freeTotal += amt;
      } else {
        grossSubtotal += amt;
      }
    });

    const pctBox = document.getElementById('enablePct');
    const valBox = document.getElementById('enableVal');
    const pctRate = (pctBox && pctBox.checked) ? (parseFloat(document.getElementById('percentDiscountRate').value) || 0) : 0;
    const valDiscount = (valBox && valBox.checked) ? (parseFloat(document.getElementById('valueDiscountAmount').value) || 0) : 0;

    const pctAmt = (grossSubtotal * (pctRate / 100));
    const totalDiscount = pctAmt + valDiscount + freeTotal;
    const taxable = Math.max(0, grossSubtotal - (pctAmt + valDiscount));
    const taxRate = 13.0;
    const taxAmt = taxable * (taxRate / 100);
    const grand = taxable + taxAmt;

    document.getElementById('displayGross').innerText = grossSubtotal.toFixed(2);
    document.getElementById('displayPctAmt').innerText = pctAmt > 0 ? `-${pctAmt.toFixed(2)}` : "-0.00";
    document.getElementById('displayValAmt').innerText = valDiscount > 0 ? `-${valDiscount.toFixed(2)}` : "-0.00";
    document.getElementById('displayFreeAmt').innerText = freeTotal > 0 ? `-${freeTotal.toFixed(2)}` : "-0.00";
    document.getElementById('displayTotalDiscount').innerText = totalDiscount > 0 ? `-${totalDiscount.toFixed(2)}` : "-0.00";
    document.getElementById('displayTaxable').innerText = taxable.toFixed(2);
    document.getElementById('displayTax').innerText = taxAmt.toFixed(2);
    document.getElementById('displayGrand').innerText = grand.toFixed(2);
  };

  window.toggleDiscountFields = function() {
    const pctBox = document.getElementById('enablePct');
    const valBox = document.getElementById('enableVal');
    if (pctBox) document.getElementById('pctFieldContainer').classList.toggle('hidden', !pctBox.checked);
    if (valBox) document.getElementById('valFieldContainer').classList.toggle('hidden', !valBox.checked);
    calculateTotals();
  };

  // =============================================================================
  // 4. Form Submit Validation
  // =============================================================================
  window.validateBeforeSubmit = function(e) {
    if (!custId.value || custInput.value.trim() !== confirmedCustomerName) {
      e.preventDefault();
      custInput.classList.add('border-rose-500', 'bg-rose-50');
      custErr.innerText = "Customer not registered in Master. Select from list or click '+ Create new customer'.";
      custErr.classList.remove('hidden');
      custInput.focus();
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
  };

  // Close dropdowns on outside click
  document.addEventListener('click', function(e) {
    if (!e.target.closest('#customerSearchInput') && !e.target.closest('#customerResults')) {
      custResults.classList.add('hidden');
    }
    document.querySelectorAll('#itemsBody tr').forEach(tr => {
      if (!tr.contains(e.target)) {
        const dd = tr.querySelector('.productDropdown');
        if (dd) dd.classList.add('hidden');
      }
    });
  });

  // Initialize first row
  addInvoiceRow();
});