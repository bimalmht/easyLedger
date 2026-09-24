# EasyLedger Enterprise ERP - System Architecture & Specification

## 1. Executive Summary & Tech Stack
* **Application:** Multi-Tenant Enterprise Double-Entry Accounting & ERP Engine
* **Jurisdiction / Compliance:** Inland Revenue Department (IRD) Nepal — Electronic Billing Procedure, 2074
* **Backend Framework:** Python 3.14 / Django 6.x
* **Database Management System:** PostgreSQL 16+ (Strict ACID compliance, PL/pgSQL database triggers)
* **Frontend:** Django Server-Side Templates, Tailwind CSS, Vanilla JavaScript (strict JSON script decoupling)
* **Authentication & Authorization:** Django Auth, Session-based multi-company isolation via custom Middleware

---

## 2. Multi-Tenancy & Security Model
### 2.1 Isolation Architecture
* **Strategy:** Row-Level Tenancy with Foreign Key constraints (`company_id`).
* **Tenancy Provisioning:**
  * Superusers access `/admin/` to provision `Company` master records.
  * Creating a company triggers the auto-seeding of a default Chart of Accounts (COA) and a default IRD tax invoice template.
  * Superusers assign specific credentials to tenant users via `UserProfile`.
* **Access Control:**
  * Standard tenant credentials lock the user strictly to their registered `Company`.
  * `accounting.middleware.MultiCompanyMiddleware` binds `request.company` on every incoming request.
  * Master tables (`Account`, `Customer`, `InvoiceTemplate`) and transactional records (`Transaction`, `JournalEntry`, `Invoice`, `InvoiceItem`) strictly scope queries using `company=request.company`.

### 2.2 Unbroken Sequence Management
* Sequences are partitioned strictly by `company_id` and monthly periods (`YYYYMM`):
  * **Sales Invoices:** `INV-YYYYMM-XXXX` (e.g., `INV-202609-0001`)
  * **Journal Vouchers:** `JV-YYYYMM-XXXX` (e.g., `JV-202609-0001`)
* No tenant shares transaction counters or series with another tenant.

---

## 3. Nepal IRD E-Billing Compliance (विद्युतीय बीजक कार्यविधि, २०७४)
### 3.1 Immutability & Database-Level Triggers
* **Delete Protection:** PostgreSQL `BEFORE DELETE` triggers (`prevent_financial_deletion()`) block any row deletion on `accounting_invoice`, `accounting_invoiceitem`, `accounting_transaction`, and `accounting_journalentry`.
* **Tamper Protection:** PostgreSQL `BEFORE UPDATE` triggers (`prevent_invoice_tampering()`) raise an unhandled exception if any financial column (`subtotal`, `tax_rate`, `tax_amount`, `grand_total`, `date`, `customer_id`, `invoice_number`) is modified directly via SQL or ORM.
* **Controlled Mutability:** Triggers permit updates strictly on operational metadata fields: `print_count`, `is_cancelled`, `cancelled_by`, `cancellation_reason`, and `cancelled_at`.

### 3.2 Schedule 5 Print & Reprint Controls
* **First Print (`print_count == 0`):**
  * Top-Right Stamp: `Original (खरिदकर्ताको प्रति)`
  * Central Title: `कर बीजक / TAX INVOICE`
* **Subsequent Prints (`print_count >= 1`):**
  * Top-Right Stamp: `COPY OF ORIGINAL (प्रतिलिपि) #<N>`
  * Central Title: `बीजक / INVOICE` (Word "कर / TAX" is legally omitted)
* **Audit Tracking:** Every invoice print triggers an asynchronous ping to increment `print_count` and write an audit event.

### 3.3 Audit Trail & Logging (Clause 6.c & 6.j)
* **Model:** `AuditLog`
* **Tracked Events:** `LOGIN`, `LOGOUT`, `CREATE`, `REPRINT`, `CANCEL`, `TRIGGER_BLOCK`
* **Recorded Parameters:** Tenant (`company`), user, username, timestamp (UTC), table name, primary key/reference ID, client IP address, and operation payload.
* **Inspection UI:** Dedicated frontend report at `/audit-trail/`.

---

## 4. Database Schema Reference (Core Entities)

+-----------------------------------------------------------+
|                          Company                          |
+-----------------------------------------------------------+
| id, name, pan_number (unique), address, phone, email      |
+-----------------------------------------------------------+
| 1
|
| N
+-----------------------------------------------------------+
|                     Invoice / Voucher                     |
+-----------------------------------------------------------+
| id, company_id (FK), invoice_number, date, customer_id    |
| subtotal, tax_rate, tax_amount, grand_total, status       |
| print_count, created_by_id (FK), transaction_id (FK)      |
+-----------------------------------------------------------+
| 1
|
| N
+-----------------------------------------------------------+
|                   InvoiceItem / JournalEntry              |
+-----------------------------------------------------------+
| id, invoice_id (FK), description, qty, unit_price, amount |
+-----------------------------------------------------------+

---

## 5. Enterprise ERP Development Roadmap

### Phase 1: Core Financial Foundation (Completed)
- [x] Multi-tenant Chart of Accounts & double-entry Journal Engine.
- [x] Day Book, General Ledger Statement, Trial Balance, P&L, Balance Sheet.
- [x] Superuser-only company and credential provisioning in Django Admin.
- [x] PostgreSQL migration with anti-tampering triggers.
- [x] Nepal IRD Schedule 5 compliant print templates (A4/A5, Portrait/Landscape).
- [x] Audit Trail system with reprint counter tracking.

### Phase 2: Advanced Sales Invoicing & Receivables (In Progress)
- [ ] Sales Return & Credit Notes (`Schedule 6` compliance).
- [ ] Multi-currency & foreign exchange adjustments.
- [ ] Customer Ledger Aging Analysis (30 / 60 / 90+ days).
- [ ] Payment Receipts & automated settlement against open invoices.

### Phase 3: Procurement & Payables
- [ ] Purchase Requisition & Purchase Order (PO) workflow.
- [ ] Purchase Tax Invoices with VAT tracking.
- [ ] Debit Notes & Purchase Returns.
- [ ] Vendor payment vouchers with TDS (Tax Deducted at Source) entries.

### Phase 4: Inventory & Warehouse Management
- [ ] Multi-warehouse / branch support.
- [ ] Stock valuations (FIFO and Weighted Average Costing).
- [ ] Goods Receipt Notes (GRN) and Delivery Challans.
- [ ] Stock transfer and write-off vouchers with auto-ledger postings.

### Phase 5: Nepal IRD Regulatory Filings & Integrations
- [ ] Real-time IRD API Sync (CBMS - Centralized Billing Monitoring System).
- [ ] VAT Sales Register (खरिद तथा बिक्री खाता - Annex 5 & 7).
- [ ] VAT Purchase Register (Annex 8).
- [ ] Periodic VAT Return reconciliation generator.

## 6. Development & Operations Guidelines
1. **Branching Strategy:** Work on feature branches (`feature/sales-returns`, `feature/inventory-fifo`). Merge into `main` only after DB migrations and trigger integrity pass tests.
2. **Schema Modifications:** Never modify financial tables without verifying trigger functions in `accounting/migrations/`.
3. **Template Rules:** Always enforce strict `box-sizing: border-box` and `@media print` constraints for all printable tax documents.