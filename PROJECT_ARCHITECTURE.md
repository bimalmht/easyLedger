# EasyLedger ERP — Project Architecture & Progress Specification
**Document Version:** 3.0  
**Date:** September 27, 2026  
**Jurisdiction:** Inland Revenue Department (IRD) Nepal Electronic Billing Directives (Schedule 5 Tax Invoices, Schedule 6 Credit Notes, and Schedule 7 Purchase Register)  
**Tech Stack:** Python 3.14+ | Django 6.1+ | PostgreSQL 16+ (PL/pgSQL Triggers) | Tailwind CSS | Vanilla JavaScript  

---

## 1. System Overview & Core Architecture
EasyLedger is an enterprise-grade multi-tenant ERP engineered for complete statutory compliance with Nepal IRD electronic billing, inventory capitalization, and general ledger regulations.

### Tenancy & Data Isolation Model
- **Single-App Unified Architecture:** All domain models (`Company`, `Customer`, `Supplier`, `Product`, `OtherChargeMaster`, `Warehouse`, `StockLedgerEntry`, `Invoice`, `CreditNote`, `PurchaseInvoice`, `Transaction`, `JournalEntry`) reside within the `accounting` app.
- **Strict Row-Level Tenancy:** Models inherit multi-tenant foreign keys pointing directly to `Company`. Every query in `views.py` is scoped via `request.company` (populated via custom company middleware).
- **Master Data Seeding:** Upon company registration, the standard Chart of Accounts (COA codes 1010–5020, Inventory 1040, VAT Input 1050), tax configurations (VAT 13%, Excise 5%), and default Schedule 5/6 print formats are automatically seeded.
- **Active Master Protection:** Entities tied to financial or stock records cannot be deleted (`models.PROTECT`). Setting `is_active=False` hides them from new autocomplete dropdowns while safeguarding historical registers.

---

## 2. Navigation Architecture & Visual Design Language
Maintains an executive Tailwind CSS design language (`max-w-5xl`, `rounded-xl`, `border-slate-200`, `shadow-sm`, `bg-indigo-600`, `font-mono` numerals, `text-xs` typography):

- **Sales:** Tax Invoices (`/invoices/`), New Tax Invoice (`/invoices/new/`), Credit Notes (`/credit-notes/`), Issue Credit Note (`/credit-notes/new/`).
- **Purchase:** Purchase Invoices (`/purchases/`), New Purchase Invoice (`/purchases/create/`).
- **Finance:** New Journal Voucher (`/vouchers/new/`), Day Book (`/daybook/`), Chart of Accounts (`/coa/`), Trial Balance, Profit & Loss, Balance Sheet.
- **Master:**
  - **Supplier Master** (`/suppliers/`): Placed directly above Customer Master. Full CRUD, 9-digit PAN/VAT registry, contact person, phone, address, and active toggle.
  - **Customer Master** (`/masters/customers/`): Full CRUD, PAN/VAT registry, legal VAT-exempt entity toggle, active toggle.
  - **Product Master** (`/masters/products/`): Full CRUD, Code/SKU, HS Code classification, cost rate, multi-tax tagging (VAT, Excise Duty), active toggle.
  - **Other Charges Master** (`/other-charges/`): Full CRUD, Code, Name (Freight, Labor, Agent Handling, Custom Clearance), settlement clearing ledger linking.
  - **Tax Configurations** (`/masters/taxes/`): Fiscal year setup, rates for VAT, Excise, TDS with linked ledger accounts.
- **Audit Trail:** Compliance log (`/audit-trail/`) auditing user logins, invoice issuance, reprint logs, and database trigger operations.
- **⚙️ Settings:**
  - **System Configuration** (`/settings/configuration/`): Discount toggles (Percentage, Flat Value, 100% Free Items, Promotional Notes) and on-the-fly Master quick-creation controls.
  - **Print Formats** (`/templates/`, `/templates/credit-notes/`): Schedule 5 and Schedule 6 A4/A5 layouts.

---

## 3. Database Triggers & Compliance Rules (PostgreSQL 16+)
| Trigger Name | Target Tables | Operation Intercepted | Action & Enforcement |
| :--- | :--- | :--- | :--- |
| `prevent_financial_deletion()` | `accounting_invoice`, `accounting_invoiceitem`, `accounting_creditnote`, `accounting_purchaseinvoice`, `accounting_transaction`, `accounting_journalentry` | DELETE | **HARD ABORT:** Raises a fatal exception blocking all physical deletes to preserve non-tamperable audit ledgers. |
| `prevent_invoice_tampering()` | `accounting_invoice`, `accounting_purchaseinvoice` | UPDATE | **IMMUTABILITY ENFORCEMENT:** Blocks changes to serial numbers, dates, party IDs, taxable subtotal, and tax amounts once locked (`is_locked=True`). |
| `prevent_stock_ledger_tampering()` | `accounting_stockledgerentry` | UPDATE, DELETE | **APPEND-ONLY LEDGER:** Stock ledger entries cannot be updated or deleted. Prior-period corrections must be handled strictly via compensating `ADJUSTMENT` entries. |
| `audit_table_change()` | All master & transactional tables | INSERT, UPDATE, DELETE | **DATABASE LOGGING:** Automatically logs SQL operations with user, timestamp (Asia/Kathmandu), table name, and old/new JSON payloads into `accounting_auditlog`. |

---

## 4. Master Search, Autocomplete & Quick-Create Standards
Standardized identically across Sales Invoices (`sales_invoice.js`) and Purchase Invoices (`purchase_invoice.js`):
1. **Separation of Concerns:** All client JavaScript is served from external scripts (`static/js/sales_invoice.js`, `static/js/purchase_invoice.js`) and reads configurations via DOM `data-*` attributes, eliminating template syntax errors.
2. **Click-to-Browse with Instant Filter:** Focusing on party or product inputs loads active master records without requiring typing.
3. **Sticky Quick-Add Option:** Dropdowns always render a sticky bottom action (`+ Create new [party/product/charge] in Master`).
4. **On-the-Fly Modals:** Clicking quick-add opens a clean modal. Submitting saves the record via an API (`/api/customers/quick-create/`, `/api/suppliers/quick-create/`, `/api/products/quick-create/`, `/api/other-charges/quick-create/`), returns the record, selects it immediately, and clears error states without page refresh.
5. **Loss-of-Focus Protection:** Dropdown options use `onmousedown="event.preventDefault()"` to prevent blur events from prematurely closing dropdowns before click registration.
6. **Immediate Blur / Tab Validation:** Leaving the field without selecting a verified record highlights the box in red (`border-rose-500 bg-rose-50`) with an inline warning message. Form submission is blocked until all lines contain verified Master IDs.
7. **Number Box Ergonomics:** Native browser input spinners (`-webkit-inner-spin-button`) are suppressed via CSS, and columns (`w-24`, `w-28`) are sized to prevent clipping decimals (e.g., `1.00`, `0.00`).

---

## 5. Purchase Invoicing & Inventory Landed Cost Engine
- **Statutory Taxes & Duties Hierarchy:**
  - Product-level taxes are read dynamically from the Product Master.
  - Line Gross = $\text{Qty} \times \text{Rate}$
  - Taxable Base = $\max(0, \text{Line Gross} - \text{Discount})$
  - Line Excise = $\text{Taxable Base} \times \frac{\text{Excise Rate}}{100}$ *(Only applied if Excise Duty is tagged on that product)*
  - Line VAT = $(\text{Taxable Base} + \text{Excise}) \times \frac{\text{VAT Rate}}{100}$ *(Only applied if VAT is tagged)*
  - Line Total = $\text{Taxable Base} + \text{Excise} + \text{VAT}$
- **Landed Cost Apportionment:**
  - Additional charges (Freight, Labor, Handling, Customs fees) are selected from `OtherChargeMaster`.
  - Apportioned to line items by taxable base ratio:
    $$\text{Line Ratio} = \frac{\text{Item Taxable Base}}{\sum \text{Item Taxable Base}}$$
    $$\text{Allocated Charge} = \text{Total Other Charges} \times \text{Line Ratio}$$
    $$\text{Total Landed Cost} = \text{Taxable Base} + \text{Excise Amount} + \text{Allocated Charge}$$
    $$\text{Unit Landed Cost} = \frac{\text{Total Landed Cost}}{\text{Quantity}}$$
  *(Input VAT is excluded from capitalized landed cost as it is reclaimed as a tax credit under IRD directives).*
- **Automated Double-Entry Accounting Voucher:**
  - **Debit:** Inventory Asset Account (`1040`) at Total Landed Cost
  - **Debit:** VAT Input Tax Receivable (`1050`) at Total VAT Amount
  - **Credit:** Supplier Accounts Payable (`2010` / Supplier Ledger) at Bill Payable Amount
  - **Credit:** Ancillary Expense Clearing Accounts at Apportioned Other Charge Amounts
- **Stock Ledger Mutation:** Automatically creates immutable inward `StockLedgerEntry` records (`entry_type='PURCHASE'`), maintaining running moving weighted average quantities and balances per product and warehouse.

---

## 6. Implementation Roadmap & Current Status

### Phase 1: Core Foundation & Sales Billing (Completed)
- [x] Row-level multi-tenancy with auto-seeding.
- [x] Schedule 5 Tax Invoices & Schedule 6 Credit Notes with automated double-entry posting.
- [x] PL/pgSQL database triggers for delete prevention, immutability, and change audits.
- [x] Master Data CRUD modules (Customer, Product, Tax Configurations) with active toggles.
- [x] Master autocomplete with click-to-browse, blur validation, and modal quick-add.
- [x] IRD A4/A5 single-sheet print layouts with reprint counter tracking.

### Phase 2: Purchase & Landed Cost Engine (Completed)
- [x] Supplier Master CRUD and Quick-Create integration positioned above Customer Master.
- [x] Other Charges Master (Freight, Labor, Commission) with quick-add modal.
- [x] Purchase Invoice Form & Register compliant with Nepal IRD Purchase Register requirements.
- [x] Product-specific dynamic Excise (5%) and VAT (13%) computation driven by Tax Configurations.
- [x] Real-time landed cost apportionment into Unit Landed Cost.
- [x] Inward Stock Ledger mutations and automated balanced double-entry GL vouchers.

### Phase 3: Inventory Valuation, Opening Stock & Stock Ledger (Next Priority)
- [ ] **Inventory Opening Balance Entry UI:** Entry screen per product and warehouse to establish opening quantities and cost valuation with equity/reserve double-entry posting.
- [ ] **Stock Ledger Report & Valuation:** Item-wise real-time stock register (Opening, Inward, Outward, Balance) with moving weighted average valuation and landed cost visibility.
- [ ] **Prior-Period Stock Adjustment Workflow:** Secure compensating `ADJUSTMENT` entries to rectify opening stock or historical discrepancies without mutating immutable audit logs.
- [ ] **Warehouse Transfer & Stock Journal:** Moving stock across locations.

### Phase 4: Receivables, Aging Analysis & Settlements (Shifted to Follow Inventory)
- [ ] Customer Ledger Aging Analysis (<30, 30–60, 60–90, 90+ days).
- [ ] Payment Receipts (Cash/Bank collection) with allocation/settlement against open tax invoices.
- [ ] Customer Outstanding Statements.


We are building "EasyLedger ERP", an enterprise-grade multi-tenant web application compliant with Nepal IRD Electronic Billing Directives (Schedule 5 Tax Invoices, Schedule 6 Credit Notes, and Schedule 7 Purchase Register).

### Tech Stack & Established Patterns
- Python 3.14, Django 6.1, PostgreSQL 16+ with PL/pgSQL triggers (`prevent_financial_deletion`, `prevent_invoice_tampering`, `prevent_stock_ledger_tampering`, `audit_table_change`), Tailwind CSS, Vanilla JS.
- Single-App Architecture: All models live in `accounting.models`, all views in `accounting.views`, and static scripts in `static/js/` (e.g., `sales_invoice.js`, `purchase_invoice.js`).
- Multi-tenancy: Strictly scoped by `request.company`.
- Master Autocomplete Standard: All master selections (Supplier, Customer, Product, Other Charges, Account) use typable inputs with click-to-browse loading, partial search, sticky "+ Create new in Master" options with standalone modals, blur/Tab immediate red inline validation, and submit-blocking for unconfirmed entries.
- Purchase & Inventory: Real-time landed cost allocation (Trade Discount, product-tagged Excise & VAT from Master, and capitalized Other Charges like Freight & Labor) with automated inward `StockLedgerEntry` and double-entry General Ledger transactions.
- Active Master Protection: Records tied to financial/stock entries cannot be deleted (`models.PROTECT`); they must be marked inactive (`is_active=False`) to hide them from new transactions.
- Navigation Hierarchy:
  - Sales (Tax Invoices, Credit Notes)
  - Purchase (Purchase Invoices)
  - Inventory (Opening Stock, Stock Status, Stock Ledger)
  - Finance (Vouchers, Daybook, COA, Financial Reports)
  - Master (Supplier Master, Customer Master, Product Master, Other Charges Master, Tax Configurations)
  - Audit Trail (IRD compliance logs)
  - ⚙️ Settings (System Configuration, Invoice Templates, Credit Note Templates)

### Current State
Phase 1 (Sales Billing, Credit Notes, Masters, Vouchers, Triggers, Print Templates) and Phase 2 (Supplier Master, Other Charges Master, Purchase Invoices, and Landed Cost Engine) are fully implemented, verified, and operational.

### Today's Goal (Phase 3: Inventory Opening & Valuation)
1. **Inventory Opening Stock Entry:**
   - Dedicated UI to record opening quantities and unit costs per warehouse for existing products.
   - Generates opening `StockLedgerEntry` records (`entry_type='OPENING'`) with automated double-entry posting: Debit Inventory Asset Account (`1040`), Credit Inventory Opening Reserve / Equity.
2. **Prior-Period Adjustment Engine:**
   - Safe compensating `ADJUSTMENT` entries to rectify opening stock or counts after months without mutating immutable historical records.
3. **Product-Wise Stock Valuation & Inventory Ledger Report:**
   - Real-time stock status showing Opening, Inward (Purchases), Outward (Sales), Balance Quantity, Product-wise Landed Cost, and Total Valuation.

Please maintain all existing colors (`indigo-600`, `slate-100` through `slate-900`, `rose-600`), Tailwind classes, typography (`text-xs`, `font-mono`), design consistency, and multi-tenant security standards. Let's begin!