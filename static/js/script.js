/* ==========================================================================
   EasyLedger Unified Client Script
   ========================================================================== */

// Helper to retrieve CSRF token from cookie or DOM
function getCsrfToken() {
  const metaToken = document.querySelector('[name=csrfmiddlewaretoken]');
  if (metaToken) return metaToken.value;

  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  return cookieValue || '';
}

/* ==========================================================================
   1. Journal Voucher & Account Quick-Create Logic
   ========================================================================== */

let voucherAccounts = [];

function initVoucherForm() {
  const accountsScriptTag = document.getElementById('accounts-data');
  if (!accountsScriptTag) return; // Not on the voucher form page

  voucherAccounts = JSON.parse(accountsScriptTag.textContent || '[]');

  // Attach dynamic rows on initial load
  addRow();
  addRow();
}

function getAccountOptionsHTML(selectedId = null) {
  return voucherAccounts
    .map(a => `<option value="${a.id}" ${String(a.id) === String(selectedId) ? 'selected' : ''}>${a.name}</option>`)
    .join('');
}

function createVoucherRowHTML(selectedId = null) {
  return `
    <tr class="entry-row hover:bg-slate-50/60 transition-colors">
      <td class="py-2.5 px-4">
        <select name="account[]" required class="account-select w-full text-sm border border-slate-300 rounded-md px-2.5 py-2 focus:ring-1 focus:ring-indigo-500 bg-white">
          ${getAccountOptionsHTML(selectedId)}
        </select>
      </td>
      <td class="py-2.5 px-4">
        <input type="text" name="line_description[]" placeholder="Line memo" class="w-full text-sm border border-slate-300 rounded-md px-2.5 py-2">
      </td>
      <td class="py-2.5 px-4">
        <input type="number" name="debit[]" step="0.01" min="0" value="0.00" oninput="calculateVoucherTotals(this, 'debit')" class="debit-input text-right w-full font-mono text-sm border border-slate-300 rounded-md px-2.5 py-2">
      </td>
      <td class="py-2.5 px-4">
        <input type="number" name="credit[]" step="0.01" min="0" value="0.00" oninput="calculateVoucherTotals(this, 'credit')" class="credit-input text-right w-full font-mono text-sm border border-slate-300 rounded-md px-2.5 py-2">
      </td>
      <td class="py-2.5 px-3 text-center">
        <button type="button" onclick="removeVoucherRow(this)" title="Remove Line" class="text-slate-400 hover:text-rose-600 transition-colors text-lg font-bold">&times;</button>
      </td>
    </tr>
  `;
}

function addRow(selectedId = null) {
  const tbody = document.getElementById('entryRows');
  if (tbody) tbody.insertAdjacentHTML('beforeend', createVoucherRowHTML(selectedId));
}

function removeVoucherRow(btn) {
  const rows = document.querySelectorAll('.entry-row');
  if (rows.length > 2) {
    btn.closest('tr').remove();
    calculateVoucherTotals();
  } else {
    alert('A transaction must contain at least two entries.');
  }
}

function calculateVoucherTotals(inputElement = null, type = null) {
  if (inputElement && parseFloat(inputElement.value) > 0) {
    const row = inputElement.closest('tr');
    if (type === 'debit') row.querySelector('.credit-input').value = '0.00';
    if (type === 'credit') row.querySelector('.debit-input').value = '0.00';
  }

  let totalDebit = 0;
  let totalCredit = 0;

  document.querySelectorAll('.debit-input').forEach(i => totalDebit += parseFloat(i.value || 0));
  document.querySelectorAll('.credit-input').forEach(i => totalCredit += parseFloat(i.value || 0));

  const totalDebitElem = document.getElementById('totalDebit');
  const totalCreditElem = document.getElementById('totalCredit');
  const badge = document.getElementById('balanceBadge');
  const saveBtn = document.getElementById('saveBtn');

  if (totalDebitElem) totalDebitElem.textContent = totalDebit.toFixed(2);
  if (totalCreditElem) totalCreditElem.textContent = totalCredit.toFixed(2);

  const isBalanced = Math.abs(totalDebit - totalCredit) < 0.001 && totalDebit > 0;

  if (badge && saveBtn) {
    if (isBalanced) {
      badge.className = 'px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800';
      badge.textContent = 'Balanced';
      saveBtn.disabled = false;
      saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    } else {
      badge.className = 'px-3 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-800';
      badge.textContent = `Unbalanced (${(totalDebit - totalCredit).toFixed(2)})`;
      saveBtn.disabled = true;
      saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
    }
  }
}

// --- Account Master Modal Logic ---

async function fetchNextCode() {
  const typeSelect = document.getElementById('m_type');
  const codeInput = document.getElementById('m_code');
  if (!typeSelect || !codeInput) return;

  const endpoint = typeSelect.dataset.nextCodeUrl;
  const type = typeSelect.value;
  if (!type || !endpoint) return;

  codeInput.value = 'Loading...';
  try {
    const res = await fetch(`${endpoint}?account_type=${encodeURIComponent(type)}`);
    const data = await res.json();
    codeInput.value = (res.ok && data.status === 'success') ? data.next_code : '';
  } catch (err) {
    codeInput.value = '';
  }
}

function openAccountModal() {
  const modal = document.getElementById('accountModal');
  const alertBox = document.getElementById('modalAlert');
  const form = document.getElementById('quickAccountForm');
  if (!modal) return;

  if (alertBox) alertBox.classList.add('hidden');
  if (form) form.reset();
  modal.classList.remove('hidden');

  fetchNextCode();
  setTimeout(() => document.getElementById('m_name')?.focus(), 100);
}

function closeAccountModal() {
  document.getElementById('accountModal')?.classList.add('hidden');
}

async function submitAccountMaster() {
  const form = document.getElementById('quickAccountForm');
  const endpoint = form?.dataset.createUrl;
  const code = document.getElementById('m_code')?.value.trim();
  const name = document.getElementById('m_name')?.value.trim();
  const account_type = document.getElementById('m_type')?.value.trim();
  const alertBox = document.getElementById('modalAlert');
  const btn = document.getElementById('modalSaveBtn');

  if (!name || !account_type || !endpoint) return;

  btn.disabled = true;
  btn.textContent = 'Saving...';

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken()
      },
      body: JSON.stringify({ code, name, account_type })
    });

    const res = await response.json();

    if (response.ok && res.status === 'success') {
      voucherAccounts.push({ id: res.account.id, name: res.account.display_text });

      document.querySelectorAll('.account-select').forEach(select => {
        const currentVal = select.value;
        const opt = document.createElement('option');
        opt.value = res.account.id;
        opt.textContent = res.account.display_text;
        select.appendChild(opt);
        select.value = currentVal;
      });

      addRow(res.account.id);
      closeAccountModal();
    } else {
      if (alertBox) {
        alertBox.textContent = res.message || 'Error creating account';
        alertBox.className = 'mb-3 p-2.5 text-xs rounded-lg font-medium bg-rose-50 text-rose-700 border border-rose-200 block';
      }
    }
  } catch (err) {
    if (alertBox) {
      alertBox.textContent = 'Network or server error occurred.';
      alertBox.className = 'mb-3 p-2.5 text-xs rounded-lg font-medium bg-rose-50 text-rose-700 border border-rose-200 block';
    }
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save & Add';
  }
}

/* ==========================================================================
   2. Sales Invoicing & Customer Modal Logic
   ========================================================================== */

function initInvoiceForm() {
  const invoiceTable = document.getElementById('invoiceRows');
  if (!invoiceTable) return; // Not on the invoice form page

  addInvoiceRow();
}

function createInvoiceRowHTML() {
  return `
    <tr class="inv-row hover:bg-slate-50/60 transition-colors">
      <td class="py-2.5 px-4">
        <input type="text" name="description[]" required placeholder="Service or product description" class="w-full text-sm border border-slate-300 rounded-md px-2.5 py-2">
      </td>
      <td class="py-2.5 px-4">
        <input type="number" step="0.01" min="0.01" value="1.00" name="quantity[]" oninput="calculateInvoiceTotals()" class="row-qty text-right w-full font-mono text-sm border border-slate-300 rounded-md px-2.5 py-2">
      </td>
      <td class="py-2.5 px-4">
        <input type="number" step="0.01" min="0.00" value="0.00" name="unit_price[]" oninput="calculateInvoiceTotals()" class="row-price text-right w-full font-mono text-sm border border-slate-300 rounded-md px-2.5 py-2">
      </td>
      <td class="py-2.5 px-4 text-right font-mono font-medium text-slate-800 row-amount">
        0.00
      </td>
      <td class="py-2.5 px-3 text-center">
        <button type="button" onclick="removeInvoiceRow(this)" title="Remove Item" class="text-slate-400 hover:text-rose-600 text-lg font-bold">&times;</button>
      </td>
    </tr>
  `;
}

function addInvoiceRow() {
  const tbody = document.getElementById('invoiceRows');
  if (tbody) tbody.insertAdjacentHTML('beforeend', createInvoiceRowHTML());
}

function removeInvoiceRow(btn) {
  const rows = document.querySelectorAll('.inv-row');
  if (rows.length > 1) {
    btn.closest('tr').remove();
    calculateInvoiceTotals();
  }
}

function calculateInvoiceTotals() {
  let subtotal = 0;
  document.querySelectorAll('.inv-row').forEach(row => {
    const q = parseFloat(row.querySelector('.row-qty').value || 0);
    const p = parseFloat(row.querySelector('.row-price').value || 0);
    const rowAmt = q * p;
    row.querySelector('.row-amount').textContent = rowAmt.toFixed(2);
    subtotal += rowAmt;
  });

  const taxRate = parseFloat(document.getElementById('taxRateInput')?.value || 0);
  const tax = subtotal * (taxRate / 100);
  const grand = subtotal + tax;

  const subtotalDisplay = document.getElementById('subtotalDisplay');
  const taxDisplay = document.getElementById('taxDisplay');
  const grandTotalDisplay = document.getElementById('grandTotalDisplay');

  if (subtotalDisplay) subtotalDisplay.textContent = subtotal.toFixed(2);
  if (taxDisplay) taxDisplay.textContent = tax.toFixed(2);
  if (grandTotalDisplay) grandTotalDisplay.textContent = grand.toFixed(2);
}

// --- Customer Modal Logic ---

function openCustomerModal() {
  const modal = document.getElementById('customerModal');
  const form = document.getElementById('newCustomerForm');
  if (!modal) return;

  if (form) form.reset();
  modal.classList.remove('hidden');
  setTimeout(() => document.getElementById('custName')?.focus(), 100);
}

function closeCustomerModal() {
  document.getElementById('customerModal')?.classList.add('hidden');
}

async function submitCustomer() {
  const form = document.getElementById('newCustomerForm');
  const endpoint = form?.dataset.createUrl;
  const name = document.getElementById('custName')?.value.trim();
  const tax_number = document.getElementById('custTax')?.value.trim();
  const phone = document.getElementById('custPhone')?.value.trim();
  const address = document.getElementById('custAddress')?.value.trim();
  const saveBtn = document.getElementById('custSaveBtn');

  if (!name || !endpoint) return;

  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving...';

  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken()
      },
      body: JSON.stringify({ name, tax_number, phone, address })
    });
    const data = await res.json();
    if (res.ok && data.status === 'success') {
      const select = document.getElementById('customerSelect');
      if (select) {
        const opt = document.createElement('option');
        opt.value = data.customer.id;
        opt.textContent = data.customer.name;
        opt.selected = true;
        select.appendChild(opt);
      }
      closeCustomerModal();
    } else {
      alert(data.message || 'Failed to create customer.');
    }
  } catch (err) {
    alert('Network or server error.');
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save Customer';
  }
}

/* ==========================================================================
   4. Chart of Accounts (COA) Search Filter Logic
   ========================================================================== */

function filterAccounts() {
  const input = document.getElementById('coaSearch');
  if (!input) return;

  const filter = input.value.toLowerCase();
  const rows = document.querySelectorAll('.account-row');

  rows.forEach(row => {
    const text = row.textContent.toLowerCase();
    row.style.display = text.includes(filter) ? '' : 'none';
  });
}

/* ==========================================================================
   3. Global Page Initialization
   ========================================================================== */

window.addEventListener('DOMContentLoaded', () => {
  initVoucherForm();
  initInvoiceForm();
});