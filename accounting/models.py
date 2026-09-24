from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User

# ==============================================================================
# Audit Log Model (IRD Clause 6.c & 6.j Compliance)
# ==============================================================================

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('LOGIN', 'User Login'),
        ('LOGOUT', 'User Logout'),
        ('CREATE', 'Record Created'),
        ('REPRINT', 'Invoice Reprinted'),
        ('CANCEL', 'Invoice Cancelled'),
        ('TRIGGER_BLOCK', 'Unauthorized DB Modification Blocked'),
    ]

    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='audit_logs', null=True, blank=True)
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

    def is_balanced(self):
        total_debit = sum(item.debit for item in self.entries.all())
        total_credit = sum(item.credit for item in self.entries.all())
        return round(total_debit, 2) == round(total_credit, 2)

    def __str__(self):
        return f"{self.voucher_number} - {self.company.name}"


class JournalEntry(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="entries")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="journal_entries")
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    line_description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.account.name} (Dr: {self.debit}, Cr: {self.credit})"


# ==============================================================================
# 3. Customer & Invoicing
# ==============================================================================

class Customer(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="customers")
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    tax_number = models.CharField(max_length=50, blank=True, verbose_name="Tax / PAN ID")
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class Invoice(models.Model):
    STATUS_CHOICES = [
        ("UNPAID", "Unpaid"),
        ("PAID", "Paid"),
        ("CANCELLED", "Cancelled"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="invoices")
    invoice_number = models.CharField(max_length=50)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Tax percentage (e.g. 13 for 13%)")
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="UNPAID")
    notes = models.TextField(blank=True)
    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_invoices', null=True, blank=True)
    print_count = models.PositiveIntegerField(default=0, verbose_name="Times Printed")
    is_cancelled = models.BooleanField(default=False)
    cancelled_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='cancelled_invoices', null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("company", "invoice_number")

    def __str__(self):
        return f"{self.invoice_number} - {self.customer.name}"


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.description} ({self.quantity} x {self.unit_price})"


# ==============================================================================
# 4. IRD Tax Invoice Templates
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