# EasyLedger ERP — Project Architecture & Progress Specification
**Document Version:** 4.0  
**Date:** October 01, 2026  
**Jurisdiction:** Inland Revenue Department (IRD) Nepal Electronic Billing Directives (Schedule 5 Tax Invoices, Schedule 6 Credit Notes, Schedule 7 Purchase Register, and Schedule 8 Debit Notes / Purchase Returns)  
**Tech Stack:** Python 3.14+ | Django 6.1+ | PostgreSQL 16+ (PL/pgSQL Triggers) | Tailwind CSS | Vanilla JavaScript  

---

## 1. System Overview & Core Architecture
EasyLedger is an enterprise-grade multi-tenant ERP engineered for complete statutory compliance with Nepal IRD electronic billing, perpetual inventory capitalization, and double-entry general ledger regulations.

### Tenancy & Data Isolation Model
- **Single-App Unified Architecture:** Domain models (`Company`, `Customer`, `Supplier`, `Product`, `OtherChargeMaster`, `Warehouse`, `StockLedgerEntry`, `Invoice`, `CreditNote`, `PurchaseInvoice`, `DebitNote`, `DebitNoteTemplate`, `FiscalYear`, `DocumentSequence`, `Transaction`, `JournalEntry`) reside within the `accounting` app.
- **Strict Row-Level Tenancy:** Models inherit multi-tenant foreign keys pointing directly to `Company`. Every query in `views.py` is scoped via `request.company` (populated via custom company middleware).
- **Master Data Seeding:** Upon company registration, the standard Chart of Accounts (COA codes 1010–5020, Inventory 1040, VAT Input 1050), tax configurations (VAT 13%, Excise 5%), and default Schedule 5/6 print formats are automatically seeded.
- **Active Master Protection:** Entities tied to financial or stock records cannot be deleted (`models.PROTECT`). Setting `is_active=False` hides them from new autocomplete dropdowns while safeguarding historical registers.

---

## 2. Navigation Architecture & Visual Design Language
Maintains an executive Tailwind CSS design language (`max-w-5xl` / `max-w-7xl`, `rounded-xl`, `border-slate-200`, `shadow-sm`, `bg-indigo-600`, `font-mono` numerals, `text-xs` typography):

- **Sales:** Tax Invoices (`/invoices/`), New Tax Invoice (`/invoices/new/`), Credit Notes (`/credit-notes/`), Issue Credit Note (`/credit-notes/new/`).
- **Purchase:** Purchase Invoices (`/purchases/`), New Purchase Invoice (`/purchases/create/`), Debit Notes (`/debit-notes/`), Issue Debit Note (`/debit-notes/create/`).
- **Reports (Dedicated Statutory Menu):**
  - **Purchase Register (Schedule 7 / अनुसूची ७ - खरिद खाता)** (`/reports/purchase-register/`): Formatted with Company Name, PAN, and date range in top metadata rows for Excel export.
  - **Sales Register (Schedule 5 / अनुसूची ५ - बिक्री खाता)** (`/reports/sales-register/`): Formatted with Company Name, PAN, and date range in top metadata rows for Excel export.
  - **Sales Return Register (Schedule 6 / अनुसूची ६ - क्रेडिट नोट खाता)** (`/reports/sales-return-register/`): Compliant with Annex 6 credit note tracking.
  - **Purchase Return Register (Schedule 8 / अनुसूची ८ - डेबिट नोट खाता)** (`/reports/purchase-return-register/`): Compliant with Annex 8 debit note tracking.
  - **Inventory Valuation Summary (स्टक सारांश तथा मूल्याङ्कन प्रतिवेदन)** (`/inventory/summary/`): Real-time perpetual inventory balances, unit landed costs, and asset valuation.
- **Finance:** New Journal Voucher (`/vouchers/new/`), Day Book (`/daybook/`), Chart of Accounts (`/coa/`), Trial Balance, Profit & Loss, Balance Sheet.
- **Master:**
  - **Supplier Master** (`/suppliers/`): Auto-sequential coding (`SUP-XXXX`), full CRUD, 9-digit PAN/VAT registry, default 13% VAT pre-check, contact person, phone, address, and active toggle.
  - **Customer Master** (`/masters/customers/`): Auto-sequential coding (`CUST-XXXX`), full CRUD, PAN/VAT registry, default 13% VAT pre-check, legal VAT-exempt entity toggle, active toggle.
  - **Product Master** (`/masters/products/`): Auto-sequential coding (`PRD-XXXX`), full CRUD, Code/SKU, HS Code classification, cost rate, multi-tax tagging (default 13% VAT pre-check, Excise Duty), active toggle.
  - **Other Charges Master** (`/other-charges/`): Full CRUD, Code, Name (Freight, Labor, Agent Handling, Custom Clearance), settlement clearing ledger linking.
  - **Tax Configurations** (`/masters/taxes/`): Fiscal year setup, rates for VAT, Excise, TDS with linked ledger accounts.
- **Audit Trail:** Compliance log (`/audit-trail/`) auditing user logins, invoice issuance, reprint logs, and database trigger operations.
- **Settings:**
  - **System Configuration** (`/settings/configuration/`): Discount toggles (Percentage, Flat Value, 100% Free Items, Promotional Notes) and on-the-fly Master quick-creation controls.
  - **Voucher & Invoice Series** (`/settings/voucher-series/`): IRD-compliant fiscal year prefix schemes, active FY detection, sequential padding, and live sequence tracking.
  - **Print Formats** (`/templates/`, `/templates/credit-notes/`): Schedule 5 and Schedule 6 A4/A5 layouts.

---

## 3. Database Triggers & Compliance Rules (PostgreSQL 16+)

| Trigger Name | Target Tables | Operation Intercepted | Action & Enforcement |
| :--- | :--- | :--- | :--- |
| `prevent_financial_deletion()` | `accounting_invoice`, `accounting_invoiceitem`, `accounting_creditnote`, `accounting_purchaseinvoice`, `accounting_debitnote`, `accounting_transaction`, `accounting_journalentry` | DELETE | **HARD ABORT:** Raises a fatal exception blocking physical deletes to preserve non-tamperable audit ledgers. |
| `prevent_invoice_tampering()` | `accounting_invoice`, `accounting_purchaseinvoice`, `accounting_creditnote`, `accounting_debitnote` | UPDATE | **IMMUTABILITY ENFORCEMENT:** Blocks changes to serial numbers, dates, party IDs, taxable subtotal, and tax amounts once locked (`is_locked=True`). |
| `prevent_stock_ledger_tampering()` | `accounting_stockledgerentry` | UPDATE, DELETE | **APPEND-ONLY LEDGER:** Stock ledger entries cannot be updated or deleted. Prior-period corrections must be handled strictly via compensating `ADJUSTMENT` entries. |
| `audit_table_change()` | All master & transactional tables | INSERT, UPDATE, DELETE | **DATABASE LOGGING:** Automatically logs SQL operations with user, timestamp (Asia/Kathmandu), table name, and old/new JSON payloads into `accounting_auditlog`. |

---

## 4. Master Search, Autocomplete & Automatic Coding Standards
1. **Auto-Sequential Master Coding:**
   - Products auto-generate sequential SKUs (`PRD-0001`, `PRD-0002`, etc.) in views and quick-add modals.
   - Customers and Suppliers auto-sequence as `CUST-XXXX` and `SUP-XXXX`.
2. **Default 13% VAT Enforcement:**
   - All creation forms (Product Master, Customer Master, Supplier Master) and transactional Quick-Add Modals have **VAT 13% pre-checked by default**.
   - Users can manually uncheck VAT if an entity or product is legally exempt or zero-rated.
3. **Separation of Concerns:** Client JavaScript is served from external scripts (`static/js/sales_invoice.js`, `static/js/purchase_invoice.js`) reading configurations via DOM `data-*` attributes.
4. **Z-Index Floating & Overflow Protection:** Product dropdowns use `z-[100]` with `overflow-visible` parent wrappers to prevent clipping inside single-row tables.
5. **On-the-Fly Modals:** Submitting quick-add modals persists records via API endpoints (`/api/customers/quick-create/`, `/api/suppliers/quick-create/`, `/api/products/quick-create/`, `/api/other-charges/quick-create/`) without page refresh.
6. **Immediate Blur / Tab Validation:** Leaving fields without selecting a verified record highlights inputs in red (`border-rose-500 bg-rose-50`) and halts submission.

---

## 5. Sequence Engine & Fiscal Year Operations (Nepal IRD Compliance)
- **IRD Prefix & Serial Standard:**
  - Vouchers follow the strict format: `PREFIX-FYCODE-NUMBER` (e.g., `INV-8384-000001`, `PINV-8384-000001`, `CN-8384-000001`, `DN-8384-000001`, `JV-8384-000001`).
- **Dynamic Bikram Sambat Fiscal Year Detection:**
  - Evaluated on every transaction date:
    - If BS Month >= 4 (Shrawan–Chaitra): Current BS Year is Base Year (Y / Y+1).
    - If BS Month <= 3 (Baishakh–Ashadh): Current BS Year is Trailing Year (Y-1 / Y).
  - Operates across calendar boundaries without manual database resets.
- **Atomic Concurrency:** Uses `select_for_update()` on `DocumentSequence` to guarantee consecutive, unbroken, collision-free numbering.
- **Automated Year-End Closing Engine:**
  - `close_fiscal_year()` zeroes out nominal ledgers (Category 4000 Income via Debit, Category 5000 Expense via Credit).
  - Posts automated closing voucher `YEC-FYCODE` to **Retained Earnings / Reserves (`3010`)**.
  - Marks `FiscalYear.is_closed = True`, locking transactions in the closed period from further modification.

---

## 6. Purchase & Sales Returns (Debit & Credit Notes)
- **Schedule 6 Sales Return (Credit Note):**
  - Links directly to original Tax Invoice reference.
  - Reverses sales revenue and Output VAT.
  - Re-ingests returned stock into the inventory ledger at the original landed cost.
  - Feeds into Annex 6 Sales Return Register.
- **Schedule 8 Purchase Return (Debit Note):**
  - Links directly to original Vendor Bill reference.
  - Reverses Accounts Payable liability and claimed Input VAT.
  - Relieves physical inventory at the exact original unit landed cost.
  - Posts outward `StockLedgerEntry` (`entry_type='PURCHASE_RETURN'`).
  - Feeds into Annex 8 Purchase Return Register.

---

## 7. Inventory Valuation, Perpetual Stock & Negative Billing Guard
- **Real-Time Stock Availability in Sales Invoicing:**
  - Autocomplete queries compute live balance quantities directly from `StockLedgerEntry`.
  - Sales invoice rows display dynamic badges (`In Stock: X` or `Out of Stock (0)`).
- **Double-Layered Negative Inventory Prevention:**
  - **Client-Side:** Input constraints restrict quantity to available stock; exceeding quantities triggers red highlights and blocks submission.
  - **Server-Side Atomic Lock:** `invoice_create_view` runs `select_for_update()` verification across `StockLedgerEntry` prior to commit, rolling back transactions that exceed warehouse balances.
- **Perpetual Outward Deduction:** Committing an invoice automatically creates outward `StockLedgerEntry` records (`entry_type='SALES'`), deducting quantities and cost of goods sold.
- **Prior-Period Error Rectification & Opening Stock Engine:**
  - Dedicated `/inventory/adjust/` workflow for initial opening stock or year-end discrepancy corrections.
  - Physical count variations post compensating `ADJUSTMENT` entries to `StockLedgerEntry` and balanced General Ledger journals against **Account 3020 (Prior Period Reserve / Stock Adjustment)** without mutating historical records.

---

## 8. Implementation Roadmap & Current Status

### Phase 1: Core Foundation & Sales Billing (Completed)
- [x] Row-level multi-tenancy with auto-seeding.
- [x] Schedule 5 Tax Invoices & Schedule 6 Credit Notes with automated double-entry posting.
- [x] PL/pgSQL database triggers for delete prevention, immutability, and change audits.
- [x] Master Data CRUD modules (Customer, Product, Tax Configurations) with active toggles.
- [x] Master autocomplete with click-to-browse, blur validation, and modal quick-add.
- [x] IRD A4/A5 single-sheet print layouts with reprint counter tracking.

### Phase 2: Purchase & Landed Cost Engine (Completed)
- [x] Supplier Master CRUD and Quick-Create integration.
- [x] Other Charges Master (Freight, Labor, Customs) with landed cost apportionment.
- [x] Purchase Invoice Form & Receiving Voucher Print with dual BS/AD date tracking.
- [x] Inward Stock Ledger mutations and automated balanced double-entry GL vouchers.

### Phase 3: Returns, Tax Registers & Fiscal Year Engine (Completed)
- [x] Schedule 8 Debit Notes (Purchase Returns) with landed cost reversals.
- [x] Statutory Annex 5 (Sales), Annex 6 (Sales Return), Annex 7 (Purchase), and Annex 8 (Purchase Return) registers.
- [x] Client-side Excel export with company identity metadata (Name, PAN, filtered period).
- [x] Dynamic IRD Fiscal Year numbering (`PREFIX-FYCODE-NUMBER`) and auto-reset engine.
- [x] Automated Fiscal Year-End closing workflow to Retained Earnings (`3010`).
- [x] Master auto-code generation (`PRD-XXXX`, `CUST-XXXX`, `SUP-XXXX`).
- [x] Default 13% VAT enforcement across all creation forms and quick modals.

### Phase 4: Inventory Management & Negative Stock Guard (Completed)
- [x] Real-time live stock display on product selection in sales invoices.
- [x] Client and server-side atomic guards preventing negative billing.
- [x] Automatic outward `StockLedgerEntry` generation on invoice submission.
- [x] Perpetual stock summary and valuation report (`/inventory/summary/`).
- [x] Prior-period opening stock rectification and adjustment engine (`/inventory/adjust/`).

### Phase 5: Receivables, Aging Analysis & Settlements (Next Priority)
- [ ] Customer Ledger Aging Analysis (<30, 30–60, 60–90, 90+ days).
- [ ] Payment Receipts (Cash/Bank collection) with allocation/settlement against open tax invoices.
- [ ] Customer and Vendor Outstanding Reconciliation Statements.
- [ ] Automated Bank Reconciliation Statement (BRS) module.