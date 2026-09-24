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