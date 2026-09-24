# EasyLedger Enterprise ERP - System Architecture & Specification

## 1. Executive Summary & Tech Stack
* **Application:** Multi-Tenant Enterprise Double-Entry Accounting & ERP Engine
* **Jurisdiction / Compliance:** Inland Revenue Department (IRD) Nepal — Electronic Billing Procedure, 2074 (विद्युतीय बीजक कार्यविधि, २०७४)
* **Backend Framework:** Python 3.14 / Django 6.x
* **Database Management System:** PostgreSQL 16+ (Strict ACID compliance, PL/pgSQL database triggers)
* **Frontend:** Django Server-Side Templates, Tailwind CSS, Vanilla JavaScript (Multi-word search & dynamic DOM reconciliation)
* **Authentication & Tenancy:** Django Auth, Session & Credential-driven multi-company isolation via custom Middleware

---

## 2. Multi-Tenancy & Security Architecture
### 2.1 Credential-Based Row-Level Tenancy
* **Segregated Administration:** Superusers exclusively access Django Admin (`/admin/`) to provision `Company` master records and user accounts.
* **Auto-Seeding:** Saving a new `Company` via Django Admin automatically provisions:
  * Standard Chart of Accounts (COA) mapped to assets, liabilities, equity, revenue, and expense types.
  * Default Nepal IRD Schedule 5 compliant print template.
* **Access Control & Routing:**
  * `accounting.middleware.MultiCompanyMiddleware` binds `request.company` based on user credentials.
  * Non-superusers are strictly bound to their assigned firm via `UserProfile`.
  * Superusers access `/admin/` directly, respecting `next` redirection parameters.
* **Isolated Transaction Series:**
  * **Sales Invoices:** `INV-YYYYMM-XXXX` (Partitioned strictly by `company_id`)
  * **Journal Vouchers:** `JV-YYYYMM-XXXX` (Partitioned strictly by `company_id`)

---

## 3. Nepal IRD E-Billing Compliance (विद्युतीय बीजक कार्यविधि, २०७४)
### 3.1 Immutability & Database-Level Triggers
* **Delete Prevention (Clause 6.b):** PostgreSQL `BEFORE DELETE` triggers (`prevent_financial_deletion()`) reject deletion attempts on `accounting_invoice`, `accounting_invoiceitem`, `accounting_transaction`, and `accounting_journalentry`.
* **Tamper Prevention (Clause 6.k):** PostgreSQL `BEFORE UPDATE` triggers (`prevent_invoice_tampering()`) reject unauthorized updates to financial figures (`gross_subtotal`, `taxable_subtotal`, `tax_rate`, `tax_amount`, `grand_total`, `date`, `customer_id`, `invoice_number`).
* **Controlled Mutability:** Triggers allow system updates strictly on operational metadata: `print_count`, `is_cancelled`, `cancelled_by`, `cancellation_reason`, and `cancelled_at`.

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

### 3.3 Audit Trail & Logging (Clause 6.c & 6.j)
* **Model:** `AuditLog`
* **Tracked Events:** `LOGIN`, `LOGOUT`, `CREATE`, `REPRINT`, `CANCEL`, `TRIGGER_BLOCK`
* **Inspection UI:** Dedicated reporting view at `/audit-trail/` filtered by `company_id`.

---

## 4. Master Data & Sales Configuration Subsystems
### 4.1 Master Menu & Navigation
* Centralized **Master** dropdown menu housing:
  * **Tax Configuration** (`/masters/taxes/`)
  * **Product Master** (`/masters/products/`)
  * **Chart of Accounts** (`/chart-of-accounts/`)
  * **Invoice Templates** (`/templates/`)

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
| N
+-------------------------------------------------------------+
|                         InvoiceItem                         |
+-------------------------------------------------------------+
| id, invoice_id (FK), product_id (FK), description, hs_code  |
| quantity, unit_price, amount, is_free, promo_badge          |
+-------------------------------------------------------------+
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

### Phase 2: Advanced Sales Invoicing & Receivables (Next Sprint)
- [ ] Sales Return & Credit Notes (`Schedule 6` compliance).
- [ ] Customer Ledger Aging Analysis (30 / 60 / 90+ days).
- [ ] Payment Receipts & automated settlement against open invoices.
- [ ] Automated email/PDF dispatch of invoices to customer contacts.

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