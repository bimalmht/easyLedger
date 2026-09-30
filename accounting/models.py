import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator

# ==============================================================================
# 1. Company & User Profile (Row-Level Tenancy)
# ==============================================================================

class Company(models.Model):
    name = models.CharField(max_length=200, verbose_name="Company / Firm Name")
    pan_number = models.CharField(max_length=20, unique=True, verbose_name="PAN / VAT Number")
    address = models.CharField(max_length=255, default="Kathmandu, Nepal")
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (PAN: {self.pan_number})"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='staff_members', null=True, blank=True)

    def __str__(self):
        comp_name = self.company.name if self.company else "Superadmin / Unassigned"
        return f"{self.user.username} ({comp_name})"


# ==============================================================================
# 2. Chart of Accounts & General Ledger
# ==============================================================================

class AccountType(models.TextChoices):
    ASSET = "ASSET", _("Asset")
    LIABILITY = "LIABILITY", _("Liability")
    EQUITY = "EQUITY", _("Equity")
    INCOME = "INCOME", _("Income")
    EXPENSE = "EXPENSE", _("Expense")


class Account(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="accounts")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=150)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    is_active = models.BooleanField(default=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_accounts",
    )

    class Meta:
        unique_together = ("company", "code")
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.company.name})"


class Transaction(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="transactions")
    date = models.DateField()
    voucher_number = models.CharField(max_length=50)
    reference = models.CharField(max_length=100, blank=True)
    narration = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("company", "voucher_number")
        ordering = ["-date", "-id"]

    def is_balanced(self):
        total_debit = sum(item.debit for item in self.entries.all())
        total_credit = sum(item.credit for item in self.entries.all())
        return round(total_debit, 2) == round(total_credit, 2)

    def __str__(self):
        return f"{self.voucher_number} - {self.company.name}"


class JournalEntry(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="entries")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="journal_entries")
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    line_description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.account.name} (Dr: {self.debit}, Cr: {self.credit})"


# Aliases so views referencing Voucher / VoucherEntry remain backwards compatible
Voucher = Transaction
VoucherEntry = JournalEntry


# ==============================================================================
# 3. Tax Configuration
# ==============================================================================

class TaxType(models.TextChoices):
    VAT = "VAT", _("Value Added Tax (VAT)")
    EXCISE = "EXCISE", _("Excise Duty")
    TDS = "TDS", _("Tax Deducted at Source (TDS)")
    OTHER = "OTHER", _("Other Indirect Tax")


class TaxConfiguration(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="taxes")
    name = models.CharField(max_length=100, help_text="e.g., VAT 13%, Excise Duty 5%, TDS 1.5%")
    tax_type = models.CharField(max_length=20, choices=TaxType.choices, default=TaxType.VAT)
    rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage rate (e.g., 13.00)")
    fiscal_year = models.CharField(max_length=20, default="2083/084", help_text="Applicable Nepalese Fiscal Year")
    ledger_account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tax_configs",
        help_text="Associated Liability or Asset Ledger"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("company", "name", "fiscal_year")

    def __str__(self):
        return f"{self.name} ({self.rate}%) - {self.fiscal_year} [{self.company.name}]"


# ==============================================================================
# 4. Master: Warehouse, Product, Customer & Supplier
# ==============================================================================

class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="warehouses")
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    address = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("company", "code")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Product(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="products")
    code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=200, help_text="Full product title, e.g. Asian Paints Apex Ultima")
    hs_code = models.CharField(max_length=50, blank=True, verbose_name="HS Code")
    unit = models.CharField(max_length=20, default="Pcs")
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    purchase_rate = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'), help_text="Standard/Default Cost Rate")
    taxes = models.ManyToManyField(TaxConfiguration, blank=True, related_name="products")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("company", "name")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class Customer(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="customers")
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    tax_number = models.CharField(max_length=50, blank=True, verbose_name="PAN / VAT ID")
    address = models.TextField(blank=True)
    is_vat_exempt = models.BooleanField(default=False, verbose_name="VAT Exempt Entity")
    applicable_taxes = models.ManyToManyField(TaxConfiguration, blank=True, related_name="customers")
    ledger_account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_ledgers",
        help_text="Accounts Receivable (Sundry Debtors)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Active Status")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class Supplier(models.Model):
    """Supplier Master positioned directly above Customer in Master hierarchy"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="suppliers")
    name = models.CharField(max_length=255)
    pan_vat_number = models.CharField(max_length=9, db_index=True)
    contact_person = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=25, blank=True)
    address = models.CharField(max_length=255)
    is_vat_exempt = models.BooleanField(default=False, verbose_name="VAT Exempt Entity")
    applicable_taxes = models.ManyToManyField('TaxConfiguration', blank=True, related_name="suppliers")
    ledger_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="supplier_ledgers",
        help_text="Associated Accounts Payable (Sundry Creditors) account"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("company", "pan_vat_number")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (PAN: {self.pan_vat_number})"


class OtherChargeMaster(models.Model):
    """Master registry for ancillary purchase charges (Freight, Labor, Clearing Charges)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="other_charges")
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    default_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="charge_masters",
        help_text="Associated COA expense/clearing account"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("company", "code")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


# ==============================================================================
# 5. Inventory & Immutable Stock Ledger
# ==============================================================================

class StockLedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        OPENING = "OPENING", _("Opening Stock")
        PURCHASE = "PURCHASE", _("Purchase Invoice")
        PURCHASE_RETURN = "PURCHASE_RETURN", _("Debit Note")
        SALES = "SALES", _("Sales Invoice")
        SALES_RETURN = "SALES_RETURN", _("Credit Note")
        ADJUSTMENT = "ADJUSTMENT", _("Stock Adjustment")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="stock_ledger_entries")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_entries")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_entries")
    entry_date = models.DateField(db_index=True)
    entry_type = models.CharField(max_length=20, choices=EntryType.choices)
    reference_id = models.UUIDField(null=True, blank=True)
    reference_number = models.CharField(max_length=100)
    
    in_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    out_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))
    
    balance_quantity = models.DecimalField(max_digits=14, decimal_places=3)
    balance_value = models.DecimalField(max_digits=16, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["entry_date", "created_at"]
        indexes = [
            models.Index(fields=["company", "product", "warehouse", "entry_date"]),
        ]


# ==============================================================================
# 6. Sales Invoicing & Multi-Tier Discounts
# ==============================================================================

class Invoice(models.Model):
    STATUS_CHOICES = [
        ("UNPAID", "Unpaid"),
        ("PAID", "Paid"),
        ("CANCELLED", "Cancelled"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="invoices")
    invoice_number = models.CharField(max_length=50)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    
    # Standardized Dates: date (canonical legacy field) & invoice_date_bs
    date = models.DateField(default=timezone.now, db_index=True)
    due_date = models.DateField(null=True, blank=True)
    invoice_date_bs = models.CharField(
        max_length=10, 
        blank=True, 
        verbose_name="Invoice Date (BS)",
        help_text="Format: YYYY-MM-DD"
    )

    # Subtotals & Discounts
    gross_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    percent_discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    percent_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    value_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    free_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    taxable_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="UNPAID")
    notes = models.TextField(blank=True)
    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice",
    )

    # Backwards-compatibility property alias: invoice.invoice_date points to invoice.date
    @property
    def invoice_date(self):
        return self.date

    @invoice_date.setter
    def invoice_date(self, value):
        self.date = value

    # IRD Audit & Immutability Fields
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_invoices", null=True, blank=True)
    print_count = models.PositiveIntegerField(default=0, verbose_name="Times Printed")
    is_cancelled = models.BooleanField(default=False)
    cancelled_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="cancelled_invoices", null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("company", "invoice_number")

    def __str__(self):
        return f"{self.invoice_number} - {self.customer.name}"


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    description = models.CharField(max_length=200)
    hs_code = models.CharField(max_length=20, blank=True, default="-")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    is_free = models.BooleanField(default=False)
    promo_badge = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.description} ({self.quantity} x {self.unit_price})"


# ==============================================================================
# 7. Purchase Invoicing & Landed Cost Engine
# ==============================================================================

class PurchaseInvoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="purchase_invoices")
    invoice_number = models.CharField(max_length=100, db_index=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_invoices")
    supplier_invoice_no = models.CharField(max_length=100)
    supplier_invoice_date = models.DateField(db_index=True)
    supplier_invoice_date_bs = models.CharField(
        max_length=10, 
        blank=True, 
        verbose_name="Supplier Bill Date (BS)",
        help_text="Format: YYYY-MM-DD"
    )
    nepali_date = models.CharField(max_length=10, blank=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="purchases")

    # Customs Reference
    customs_declaration_no = models.CharField(max_length=100, blank=True, null=True)
    customs_date = models.DateField(blank=True, null=True)

    # Subtotals & Financial Totals
    gross_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_discount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    taxable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    non_taxable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    excise_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    
    # Other Charges & Landed Valuation
    total_other_charges = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_inventory_landed_cost = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))

    transaction = models.OneToOneField(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_invoice")
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("company", "invoice_number")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.invoice_number} - {self.supplier.name}"


class PurchaseInvoiceItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="purchase_items")
    
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    rate = models.DecimalField(max_digits=14, decimal_places=4, validators=[MinValueValidator(Decimal('0.0001'))])
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    is_taxable = models.BooleanField(default=True)
    excise_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    excise_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('13.00'))
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)

    # Landed Cost tracking
    allocated_other_charge = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))
    landing_cost_total = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    landing_cost_per_unit = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))


class PurchaseInvoiceOtherCharge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_invoice = models.ForeignKey(PurchaseInvoice, on_delete=models.CASCADE, related_name="other_charges")
    charge_master = models.ForeignKey(OtherChargeMaster, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    remarks = models.CharField(max_length=255, blank=True)


# ==============================================================================
# 8. Sales Return & Credit Note (Nepal IRD Schedule 6 / अनुसूची-६)
# ==============================================================================

class CreditNote(models.Model):
    RETURN_REASONS = [
        ("GOODS_RETURN", "Goods Returned by Customer"),
        ("DAMAGED_EXPIRED", "Damaged or Expired Goods"),
        ("RATE_DIFFERENCE", "Price / Rate Discrepancy Correction"),
        ("DISCOUNT_POST_SALE", "Post-Sale Discount / Rebate"),
        ("OTHER", "Other Regulatory Adjustment"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="credit_notes")
    credit_note_number = models.CharField(max_length=50)
    original_invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="credit_notes")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="credit_notes")
    date = models.DateField(default=timezone.now)
    credit_note_date_bs = models.CharField(max_length=10, blank=True)
    reason = models.CharField(max_length=50, choices=RETURN_REASONS, default="GOODS_RETURN")
    reason_details = models.TextField(blank=True)

    taxable_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_note"
    )

    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_credit_notes", null=True, blank=True)
    print_count = models.PositiveIntegerField(default=0, verbose_name="Times Printed")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("company", "credit_note_number")
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.credit_note_number} (Ref: {self.original_invoice.invoice_number})"


class CreditNoteItem(models.Model):
    credit_note = models.ForeignKey(CreditNote, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    description = models.CharField(max_length=200)
    hs_code = models.CharField(max_length=20, blank=True, default="-")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def __str__(self):
        return f"{self.description} ({self.quantity} x {self.unit_price})"


# ==============================================================================
# 9. Templates, Settings & Audit Logs
# ==============================================================================

class InvoiceTemplate(models.Model):
    PAGE_SIZE_CHOICES = [
        ("A4_PORTRAIT", "A4 Portrait (210mm x 297mm)"),
        ("A4_LANDSCAPE", "A4 Landscape (297mm x 210mm)"),
        ("A5_PORTRAIT", "A5 Portrait (148mm x 210mm)"),
        ("A5_LANDSCAPE", "A5 Landscape (210mm x 148mm)"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="templates")
    title = models.CharField(max_length=100, default="Standard Nepal IRD Tax Invoice")
    page_size = models.CharField(max_length=20, choices=PAGE_SIZE_CHOICES, default="A4_PORTRAIT")
    is_default = models.BooleanField(default=False)
    show_hs_code = models.BooleanField(default=True)
    show_nepali_header = models.BooleanField(default=True, verbose_name="Show 'कर बीजक'")
    header_subtitle = models.CharField(max_length=150, default="Schedule 5 (Rule 17), VAT Rules 2053")
    invoice_copy_text = models.CharField(max_length=50, default="Original (खरिदकर्ताको प्रति)")
    declaration_text = models.TextField(default="We certify that this invoice reflects the actual price of goods/services described.")
    terms_and_conditions = models.TextField(default="1. Goods once sold are not returnable.\n2. Payment is due within 30 days.")
    footer_signature_label = models.CharField(max_length=100, default="Authorized Signatory / अधिकृत हस्ताक्षर")

    def save(self, *args, **kwargs):
        if self.is_default:
            InvoiceTemplate.objects.filter(company=self.company).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.get_page_size_display()}) - {self.company.name}"


class CreditNoteTemplate(models.Model):
    PAGE_SIZE_CHOICES = [
        ("A4_PORTRAIT", "A4 Portrait (210mm x 297mm)"),
        ("A4_LANDSCAPE", "A4 Landscape (297mm x 210mm)"),
        ("A5_PORTRAIT", "A5 Portrait (148mm x 210mm)"),
        ("A5_LANDSCAPE", "A5 Landscape (210mm x 148mm)"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="credit_note_templates")
    title = models.CharField(max_length=100, default="Standard Nepal IRD Schedule 6 Credit Note")
    page_size = models.CharField(max_length=20, choices=PAGE_SIZE_CHOICES, default="A4_PORTRAIT")
    is_default = models.BooleanField(default=False)
    show_hs_code = models.BooleanField(default=True)
    header_subtitle = models.CharField(
        max_length=150, 
        default="अनुसूची–६ (नियम १७ सँग सम्बन्धित) / Schedule 6 (Rule 17), VAT Rules 2053"
    )
    declaration_text = models.TextField(
        default="We certify that this credit note reflects the actual return or price adjustment of goods/services described."
    )
    terms_and_conditions = models.TextField(
        blank=True,
        default="1. Credit adjustment subject to reconciliation.\n2. Applicable against subsequent invoices."
    )
    footer_signature_label = models.CharField(max_length=100, default="Authorized Signatory / अधिकृत हस्ताक्षर")

    def save(self, *args, **kwargs):
        if self.is_default:
            CreditNoteTemplate.objects.filter(company=self.company).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.get_page_size_display()}) - {self.company.name}"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('LOGIN', 'User Login'),
        ('LOGOUT', 'User Logout'),
        ('CREATE', 'Record Created'),
        ('REPRINT', 'Invoice Reprinted'),
        ('CANCEL', 'Invoice Cancelled'),
        ('TRIGGER_BLOCK', 'Unauthorized DB Modification Blocked'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='audit_logs', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    username = models.CharField(max_length=150)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    table_name = models.CharField(max_length=100)
    record_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.username} - {self.action} on {self.table_name}"


class CompanySetting(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="settings")
    
    # Feature Flags: Sales Invoicing Discounts
    enable_percent_discount = models.BooleanField(default=True, verbose_name="Enable % Discount")
    enable_value_discount = models.BooleanField(default=True, verbose_name="Enable Value Discount")
    enable_free_item_discount = models.BooleanField(default=True, verbose_name="Enable Free Item (100% Free) Option")
    enable_promotions = models.BooleanField(default=True, verbose_name="Enable Promotional Badges")

    # Feature Flags: Master Creation Workflow
    allow_quick_customer_creation = models.BooleanField(
        default=True, 
        verbose_name="Allow creating Customers directly during Invoicing"
    )
    allow_quick_product_creation = models.BooleanField(
        default=True, 
        verbose_name="Allow creating Products directly during Invoicing"
    )

    def __str__(self):
        return f"Settings - {self.company.name}"
    
# ==============================================================================
# 10. Purchase Return & Debit Note (Nepal IRD Schedule 8 / अनुसूची–८)
# ==============================================================================

class DebitNote(models.Model):
    RETURN_REASONS = [
        ("GOODS_RETURN", "Goods Returned to Supplier"),
        ("DAMAGED_EXPIRED", "Damaged, Defective or Expired Goods"),
        ("RATE_DIFFERENCE", "Price / Rate Overcharge Correction"),
        ("DISCOUNT_POST_PURCHASE", "Post-Purchase Rebate / Discount"),
        ("OTHER", "Other Regulatory Adjustment"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="debit_notes")
    debit_note_number = models.CharField(max_length=50, db_index=True)
    original_purchase_invoice = models.ForeignKey(
        PurchaseInvoice, on_delete=models.PROTECT, related_name="debit_notes"
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="debit_notes")
    date = models.DateField(default=timezone.now, db_index=True)
    debit_note_date_bs = models.CharField(max_length=10, blank=True, help_text="Format: YYYY-MM-DD")
    reason = models.CharField(max_length=50, choices=RETURN_REASONS, default="GOODS_RETURN")
    reason_details = models.TextField(blank=True)

    # Financial breakdown
    taxable_subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    excise_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('13.00'))
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_inventory_cost_reversed = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))

    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debit_note"
    )
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_debit_notes", null=True, blank=True)
    print_count = models.PositiveIntegerField(default=0, verbose_name="Times Printed")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("company", "debit_note_number")
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.debit_note_number} (Ref: {self.original_purchase_invoice.invoice_number})"


class DebitNoteItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    debit_note = models.ForeignKey(DebitNote, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="debit_note_items")
    description = models.CharField(max_length=200)
    hs_code = models.CharField(max_length=20, blank=True, default="-")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    rate = models.DecimalField(max_digits=14, decimal_places=4, validators=[MinValueValidator(Decimal('0.0001'))])
    original_unit_landed_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'))
    taxable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    excise_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    vat_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self):
        return f"{self.description} ({self.quantity} @ {self.rate})"


class DebitNoteTemplate(models.Model):
    PAGE_SIZE_CHOICES = [
        ("A4_PORTRAIT", "A4 Portrait (210mm x 297mm)"),
        ("A4_LANDSCAPE", "A4 Landscape (297mm x 210mm)"),
        ("A5_PORTRAIT", "A5 Portrait (148mm x 210mm)"),
        ("A5_LANDSCAPE", "A5 Landscape (210mm x 148mm)"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="debit_note_templates")
    title = models.CharField(max_length=100, default="Standard Nepal IRD Schedule 8 Debit Note")
    page_size = models.CharField(max_length=20, choices=PAGE_SIZE_CHOICES, default="A4_PORTRAIT")
    is_default = models.BooleanField(default=False)
    show_hs_code = models.BooleanField(default=True)
    header_subtitle = models.CharField(
        max_length=150, 
        default="अनुसूची–८ (नियम १७ सँग सम्बन्धित) / Schedule 8 (Rule 17), VAT Rules 2053"
    )
    declaration_text = models.TextField(
        default="We certify that this debit note reflects the actual return or price adjustment of goods/services described."
    )
    terms_and_conditions = models.TextField(
        blank=True,
        default="1. Debit adjustment subject to vendor ledger reconciliation.\n2. Applicable against outstanding payable bills."
    )
    footer_signature_label = models.CharField(max_length=100, default="Authorized Signatory / अधिकृत हस्ताक्षर")

    def save(self, *args, **kwargs):
        if self.is_default:
            DebitNoteTemplate.objects.filter(company=self.company).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.get_page_size_display()}) - {self.company.name}"