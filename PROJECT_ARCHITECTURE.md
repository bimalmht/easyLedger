EasyLedger ERP — Project Architecture & Progress Specification
Document Version: 2.4
Date: September 25, 2026
Jurisdiction: Inland Revenue Department (IRD) Nepal Electronic Billing Compliance
Tech Stack: Python 3.14+ | Django 6.1+ | PostgreSQL 16+ (PL/pgSQL Triggers) | Tailwind CSS | Vanilla JavaScript
1. System Overview & Core Architecture
EasyLedger is a multi-tenant enterprise accounting and billing ERP designed specifically for compliance with Nepal Inland Revenue Department (IRD) Electronic Billing Directives (Clause 6.f, 6.j, 6.m, Schedule 5 Tax Invoices, and Schedule 6 Credit Notes).
Tenancy & Data Isolation Model
•	Company-Isolated Execution: Every primary transaction model (Transaction, JournalEntry, Invoice, CreditNote, Customer, Product, TaxConfiguration, CompanySetting) is strictly foreign-keyed to Company.
•	Row-Level Tenancy Scoping: Database queries in views.py strictly scope reads/writes using request.company resolved by middleware.
•	Master Data Seeding: Upon company registration, standard standard Chart of Accounts (COA codes 1010–5020), standard tax configurations, and default Schedule 5/6 print formats are automatically seeded.
2. Navigation Architecture & Visual Design Language
The navigation follows strict enterprise UX principles with zero visual clutter:
•	Sales: Tax Invoices (/invoices/), New Tax Invoice (/invoices/new/), Credit Notes (/credit-notes/), Issue Credit Note (/credit-notes/new/).
•	Finance: New Journal Voucher (/vouchers/new/), Day Book (/daybook/), Chart of Accounts (/chart-of-accounts/), Trial Balance, Profit & Loss, Balance Sheet.
•	Master: Strictly business master data:
o	Customer Master (/masters/customers/): Full CRUD, PAN/VAT registry, legal VAT-exempt entity toggle, active/inactive flag.
o	Product Master (/masters/products/): Full CRUD, SKU, Harmonized System (HS) code classification, multi-tax tagging (VAT, Excise Duty), active/inactive flag.
o	Tax Configurations (/masters/taxes/): Fiscal year rate setup, VAT, Excise, TDS with linked ledger accounts.
•	Audit Trail: Independent compliance log (/audit-trail/) showing application events and PL/pgSQL database trigger audits.
•	⚙️ Settings (Dedicated Dropdown):
o	System Configuration (/settings/configuration/): Discount toggles (Percentage, Flat Value, 100% Free Items, Promotional Notes) and on-the-fly Master quick-creation controls.
o	Invoice Templates (/templates/): Page layouts, copies, declaration text, and signatures.
o	Credit Note Templates (/templates/credit-notes/): Schedule 6 layout customization.
3. Database Triggers & Compliance Rules (PostgreSQL 16+)
Trigger Name	Target Tables	Operation Intercepted	Action & Enforcement
prevent_financial_deletion()	accounting_invoice, accounting_invoiceitem, accounting_creditnote, accounting_transaction, accounting_journalentry	DELETE	HARD ABORT: Raises a fatal exception blocking all physical deletes to preserve non-tamperable audit ledgers.
prevent_invoice_tampering()	accounting_invoice	UPDATE	IMMUTABILITY ENFORCEMENT: Blocks changes to invoice_number, date, customer_id, gross_subtotal, taxable_subtotal, tax_amount, and grand_total. Only permits operational metadata updates (print_count, is_cancelled, cancellation_reason).
audit_table_change()	accounting_invoice, accounting_invoiceitem, accounting_product, accounting_customer, accounting_companysetting	INSERT, UPDATE, DELETE	DATABASE LOGGING: Automatically logs SQL operations (INSERT, UPDATE, DELETE) with user, timestamp (Asia/Kathmandu), table name, and old/new JSON payloads into accounting_auditlog. Resolves company_id for line items dynamically via the parent invoice.
4. Master Search & In-Line Creation Specifications
Standardized across Sales Invoices, Credit Notes, and Journal Vouchers:
1.	Typable Input with Click-to-Browse: Focusing on the input displays all active master records (Customer, Product, or Account) without forcing the user to type.
2.	Partial Multi-word Real-time Filtering: Filters across code, name, and secondary parameters (PAN, HS Code, Category).
3.	Dropdown In-line Quick Add (+ Create "[name]" in Master): If a typed entry does not exist, an option appears at the bottom of the dropdown to open the creation modal with the typed name pre-filled and an auto-generated standard code.
4.	Immediate Tab / Blur Validation: Moving away (blur/Tab) immediately hides the dropdown menu, compares the field against the confirmed Master ID, and highlights invalid/manual entries with a red border (border-rose-500 bg-rose-50) and an inline message below the input:
o	Customer: "Customer not registered in Master. Select from list or create new."
o	Product: "Product not registered in Master. Select from list or create new."
o	Account: "Account not registered in Master. Select from list or create new."
5.	Form-level Submission Protection: All invoice and voucher forms run client-side validation (validateBeforeSubmit) and server-side Django ORM validation, rejecting any submission containing unlinked or manual entities.
6.	Inactive Entity Filtration: Inactive products, customers, and accounts are filtered out (is_active=True) from autocomplete endpoints. Deleting records referenced in past transactions is prevented via foreign-key protection (on_delete=models.PROTECT).
5. Print Layout Specifications (A4 / A5 True Dimensions)
•	Paper Dimensions: Dynamically injects @page { size: A4 portrait; margin: 8mm 10mm; } in @media print to prevent browser fallbacks to default printer presets.
•	Vertical Distribution (No Bottom Void): .print-sheet utilizes CSS flex column styling (display: flex; flex-direction: column; justify-content: space-between; height: calc(297mm - 16mm);), pinning seller/buyer data and line items to the top and signatures/audit timestamps firmly to the bottom.
•	Print Footprint & Clone Tracking (Clause 6.f):
o	First Issuance (print_count == 0): Displays ORIGINAL (खरिदकर्ताको प्रति) and कर बीजक / TAX INVOICE.
o	Subsequent Prints (print_count >= 1): Displays COPY OF ORIGINAL (प्रतिलिपि) #N and बीजक / INVOICE.
o	Asynchronous tracking via ?print=true writes a REPRINT event to accounting_auditlog with timestamp and user details.
6. Implementation Roadmap & Upcoming Phase
Phase 1: Core Foundation & Sales Compliance (Completed)
•	[x] Row-level multi-tenancy with auto-seeding.
•	[x] Schedule 5 Tax Invoices & Schedule 6 Credit Notes with automated double-entry ledger posting.
•	[x] PL/pgSQL database triggers for delete prevention, immutability, and change audits.
•	[x] Unified Master Data navigation and full CRUD Product/Customer/Tax modules with active toggles.
•	[x] Typable master search with click-to-browse, blur validation, and modal quick-add.
•	[x] IRD A4/A5 single-sheet print layouts with reprint counter tracking.
Phase 2: Receivables, Aging & Settlements (Next Focus)
•	[ ] Customer Ledger Aging Analysis: Real-time aged receivables bucketed into < 30 Days, 30–60 Days, 60–90 Days, and > 90+ Days.
•	[ ] Payment Receipts (CR Vouchers): Cash/Bank collection vouchers with line-item settlement against open tax invoices (FIFO and manual allocation).
•	[ ] Customer Outstanding Statements: Shareable customer account statements detailing invoiced amounts, received payments, credit note adjustments, and closing balance.

