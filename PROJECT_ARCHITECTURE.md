# EasyLedger Enterprise ERP - System Architecture & Specification

## 1. Executive Summary & Tech Stack
* **Application:** Multi-Tenant Enterprise Double-Entry Accounting & ERP Engine
* **Jurisdiction / Compliance:** Inland Revenue Department (IRD) Nepal — Electronic Billing Procedure, 2074 (विद्युतीय बीजक कार्यविधि, २०७४)
* **Backend Framework:** Python 3.14 / Django 6.x
* **Database Management System:** PostgreSQL 16+ (Strict ACID compliance, PL/pgSQL database triggers)
* **Frontend:** Django Server-Side Templates, Tailwind CSS (Mobile-first responsive drawer & viewports), Vanilla JavaScript
* **Authentication & Tenancy:** Django Auth, Session & Credential-driven multi-company isolation via custom Middleware

---

## 2. Multi-Tenancy & Security Architecture
### 2.1 Credential-Based Row-Level Tenancy
* **Segregated Administration:** Superusers exclusively access Django Admin (`/admin/`) to provision `Company` master records and user accounts.
* **Auto-Seeding:** Saving a new `Company` via Django Admin automatically provisions:
  * Standard Chart of Accounts (COA) mapped to assets, liabilities, equity, revenue, and expense types.
  * Default Nepal IRD Schedule 5 compliant print template (`InvoiceTemplate`).
  * Default Nepal IRD Schedule 6 compliant print template (`CreditNoteTemplate`).
* **Access Control & Routing:**
  * `accounting.middleware.MultiCompanyMiddleware` binds `request.company` based on user credentials.
  * Non-superusers are strictly bound to their assigned firm via `UserProfile`.
  * Superusers access `/admin/` directly, respecting `next` redirection parameters.
* **Isolated Transaction Series:**
  * **Sales Invoices:** `INV-YYYYMM-XXXX` (Partitioned strictly by `company_id`)
  * **Credit Notes:** `CN-YYYYMM-XXXX` (Partitioned strictly by `company_id`)
  * **Journal Vouchers:** `JV-YYYYMM-XXXX` (Partitioned strictly by `company_id`)

---

## 3. Nepal IRD E-Billing Compliance (विद्युतीय बीजक कार्यविधि, २०७४)
### 3.1 Immutability & Database-Level Triggers
* **Delete Prevention (Clause 6.b):** PostgreSQL `BEFORE DELETE` triggers (`prevent_financial_deletion()`) reject deletion attempts on:
  * `accounting_invoice`
  * `accounting_invoiceitem`
  * `accounting_creditnote`
  * `accounting_creditnoteitem`
  * `accounting_transaction`
  * `accounting_journalentry`
* **Tamper Prevention (Clause 6.k):** PostgreSQL `BEFORE UPDATE` triggers:
  * `prevent_invoice_tampering()` rejects unauthorized updates to invoice financial figures (`gross_subtotal`, `taxable_subtotal`, `tax_rate`, `tax_amount`, `grand_total`, `date`, `customer_id`, `invoice_number`).
  * `prevent_creditnote_tampering()` rejects modifications to credit note figures, customer linkage, or referenced invoice associations (`credit_note_number`, `taxable_subtotal`, `tax_rate`, `tax_amount`, `grand_total`, `customer_id`, `original_invoice_id`, `date`).
* **Controlled Mutability:** Triggers permit updates strictly on operational metadata: `print_count`, `is_cancelled`, `cancelled_by`, `cancellation_reason`, and `cancelled_at`.

### 3.2 Schedule 5 Print & Reprint Controls (Clause 6.f)
* **First Print (`print_count == 0`):**
  * Top-Right Header: `Original (खरिदकर्ताको प्रति)`
  * Central Document Title: `कर बीजक / TAX INVOICE`
* **Subsequent Prints (`print_count >= 1`):**
  * Top-Right Header: `COPY OF ORIGINAL (प्रतिलिपि) #<N>`
  * Central Document Title: `बीजक / INVOICE` (Word "कर / TAX" is legally omitted)
* **Audit Trail Integration:** Every print action makes an asynchronous API call to increment `print_count` and generate an `AuditLog` entry.
* **Invoice Metadata Footer:**
  * `Prepared / Received By`: Username of the invoice creator.
  * `Created Date`: Date of invoice issuance.
  * `Printed By`: Username of the currently logged-in user triggering the print.
  * `Print Date & Time`: Exact server timestamp of printing.

### 3.3 Schedule 6 Credit Notes (नियम १७ - अनुसूची-६)
* **Mandatory Invoice Reference:** Must reference the original tax invoice number and original date.
* **Mandatory Reason Classification:** Explicitly captures legal adjustment rationale (`Goods Returned by Customer`, `Damaged or Expired Goods`, `Price / Rate Discrepancy Correction`, `Post-Sale Discount / Rebate`, `Other Regulatory Adjustment`).
* **Automated Accounting Reversal:**
  * Debit: **Sales Return** (or Sales Revenue)
  * Debit: **VAT Payable / Output Tax** (reversing output tax liability)
  * Credit: **Accounts Receivable** (reducing customer balance)
* **Reprint Handling:** First print tagged `Original (खरिदकर्ताको प्रति)`, subsequent prints tagged `COPY OF ORIGINAL (प्रतिलिपि) #<N>`.

### 3.4 Audit Trail & Logging (Clause 6.c & 6.j)
* **Model:** `AuditLog`
* **Tracked Events:** `LOGIN`, `LOGOUT`, `CREATE`, `REPRINT`, `CANCEL`, `TRIGGER_BLOCK`
* **Inspection UI:** Dedicated reporting view at `/audit-trail/` filtered by `company_id`.

---

## 4. ERP Modular Navigation & Master Data
### 4.1 Global Responsive Navigation
Grouped into functional enterprise modules with mobile drawer support:
* **Sales:**
  * Tax Invoices (`/invoices/`)
  * New Tax Invoice (`/invoices/new/`)
  * Credit Notes / Schedule 6 (`/credit-notes/`)
  * Issue Credit Note (`/credit-notes/new/`)
* **Finance:**
  * New Voucher JV (`/vouchers/new/`)
  * Day Book (`/daybook/`)
  * Chart of Accounts (`/chart-of-accounts/`)
  * Trial Balance (`/trial-balance/`)
  * Profit & Loss (`/profit-loss/`)
  * Balance Sheet (`/balance-sheet/`)
* **Master:**
  * Tax Configuration (`/masters/taxes/`)
  * Product Master (`/masters/products/`)
  * Invoice Templates (`/templates/`)
  * Credit Note Templates (`/templates/credit-notes/`)
* **Audit Trail:** Single-click regulatory inspection (`/audit-trail/`).

### 4.2 Tax Configuration Engine
* **Model:** `TaxConfiguration`
* **Attributes:** Scoped per `company`, tax type (`VAT`, `EXCISE`, `TDS`, `OTHER`), percentage rate, applicable Nepalese Fiscal Year (e.g., `2083/084`), and ledger account link.
* **Tagging Rules:**
  * Tagged directly to Products (e.g., Excise Duty on specific goods, VAT on standard goods).
  * Tagged directly to Customers/Suppliers (including VAT-exempt entity handling).
  * Auto-applied during billing without manual rate entry.

### 4.3 Multi-Keyword Fuzzy Search Engine
* Tokenized search queries splitting input by whitespace to match all words in any order.
* **Product Search (`/api/products/search/?q=`):** Matches against `name`, `code`, and `hs_code`.
* **Customer Search (`/api/customers/search/?q=`):** Matches against `name`, `tax_number` (PAN), and `phone`.

### 4.4 Configurable Multi-Tier Discount Engine
* **Percentage Discount:** Applied against gross line totals.
* **Flat Value Discount:** Applied as a fixed currency amount deduction.
* **Free Product Goods (100% Discount):** Designated via line-item flags (e.g., "Buy 10 get 1 free"); line amount is calculated and explicitly reflected as `FREE Discount` in the summary.
* **Promotional Items:** Highlighted with badges (e.g., `Pilot Pen Free Promo`) next to the product description without affecting financial discount summaries.
* **Print Alignment:** Itemized display in invoice summary:
  * `Taxable Subtotal` (Gross Amount)
  * `% Discount`
  * `Value Discount`
  * `FREE Discount`
  * `Total Discount`
  * `Taxable Amount`
  * `VAT (13%)`
  * `Grand Total`

---

## 5. Database Schema Reference
+-------------------------------------------------------------+
|                           Company                           |
+-------------------------------------------------------------+
| id, name, pan_number (unique), address, phone, email        |
+-------------------------------------------------------------+
| 1
|
+-------------------------------+
| N                             | N
+-----------------------------+ +-----------------------------+
|      TaxConfiguration       | |           Product           |
+-----------------------------+ +-----------------------------+
| id, company_id (FK), name   | | id, company_id (FK), name   |
| tax_type, rate, fiscal_year | | hs_code, unit, selling_price|
| ledger_account_id (FK)      | | taxes (M2M)                 |
+-----------------------------+ +-----------------------------+
|                               |
+---------------+---------------+
| N
+-------------------------------------------------------------+
|                           Invoice                           |
+-------------------------------------------------------------+
| id, company_id (FK), invoice_number, customer_id (FK), date |
| gross_subtotal, percent_discount_rate, percent_discount_amt |
| value_discount_amount, free_discount_amount, total_discount |
| taxable_subtotal, tax_rate, tax_amount, grand_total, status |
| print_count, created_by_id (FK), transaction_id (FK)        |
+-------------------------------------------------------------+
| 1
+-------------------------------+
| N                             | 1
+-----------------------------+ +-----------------------------+
|         InvoiceItem         | |         CreditNote          |
+-----------------------------+ +-----------------------------+
| id, invoice_id (FK)         | | id, company_id (FK), date   |
| product_id (FK), description| | credit_note_number          |
| hs_code, quantity           | | original_invoice_id (FK)    |
| unit_price, amount, is_free | | customer_id (FK), reason    |
| promo_badge                 | | taxable_subtotal, tax_rate  |
+-----------------------------+ | tax_amount, grand_total     |
| print_count, transaction_id |
+-----------------------------+
| 1
| N
+-----------------------------+
|       CreditNoteItem        |
+-----------------------------+
| id, credit_note_id (FK)     |
| product_id (FK), description|
| hs_code, quantity           |
| unit_price, amount          |
+-----------------------------+
## 6. Enterprise ERP Development Roadmap

### Phase 1: Core Financial & Compliance Foundation (Completed)
- [x] Multi-tenant Chart of Accounts & double-entry Journal Engine.
- [x] Day Book, General Ledger Statement, Trial Balance, P&L, Balance Sheet.
- [x] Superuser-only company and credential provisioning in Django Admin.
- [x] PostgreSQL migration with anti-tampering triggers (`prevent_financial_deletion`, `prevent_invoice_tampering`).
- [x] Nepal IRD Schedule 5 compliant print templates (single-sheet A4 fit, reprint counter, "Original" vs "Copy of Original").
- [x] Audit Trail subsystem (`AuditLog`) capturing all events and client IPs.
- [x] Master Menu structure (Tax Configuration & Product Master).
- [x] Fiscal-year scoped Tax Configuration with product/customer tagging.
- [x] Multi-word fuzzy search for products and customers.
- [x] Multi-tier discount system (`%`, flat value, free goods, and promotional items).

### Phase 2: Advanced Sales Invoicing & Receivables (In Progress)
- [x] Sales Return & Credit Notes (`Schedule 6` compliance & automated voucher posting).
- [x] Credit Note customizable print templates (`CreditNoteTemplate`) with page format switches (A4/A5).
- [x] Mobile-responsive ERP navigation (Sales, Finance, Master, Audit Trail) and clean dashboard layout.
- [ ] Customer Ledger Aging Analysis (30 / 60 / 90+ days).
- [ ] Customer Payment Receipts & automated settlement against open invoices.
- [ ] Automated email/PDF dispatch of invoices and credit notes to customer contacts.

### Phase 3: Procurement & Payables
- [ ] Purchase Requisition & Purchase Order (PO) workflow.
- [ ] Purchase Tax Invoices with VAT and TDS tracking.
- [ ] Debit Notes & Purchase Returns.
- [ ] Vendor payment vouchers with TDS ledger entries.

### Phase 4: Inventory & Warehouse Management
- [ ] Multi-warehouse / branch storage management.
- [ ] Stock valuations (FIFO and Weighted Average Costing).
- [ ] Goods Receipt Notes (GRN) and Delivery Challans.
- [ ] Stock transfer and write-off vouchers with auto-ledger postings.

### Phase 5: Nepal IRD Regulatory Filings & Integrations
- [ ] Real-time IRD API Sync (CBMS - Centralized Billing Monitoring System).
- [ ] VAT Sales Register (बिक्री खाता - Annex 5 & 7).
- [ ] VAT Purchase Register (खरिद खाता - Annex 8).
- [ ] Periodic VAT Return reconciliation generator.