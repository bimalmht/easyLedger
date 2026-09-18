from django.db import models
from django.utils.translation import gettext_lazy as _

class AccountType(models.TextChoices):
    ASSET = 'ASSET', _('Asset')
    LIABILITY = 'LIABILITY', _('Liability')
    EQUITY = 'EQUITY', _('Equity')
    INCOME = 'INCOME', _('Income')
    EXPENSE = 'EXPENSE', _('Expense')

class Account(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    is_active = models.BooleanField(default=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_accounts')

    def __str__(self):
        return f"{self.code} - {self.name}"

class Transaction(models.Model):
    date = models.DateField()
    voucher_number = models.CharField(max_length=50, unique=True)
    reference = models.CharField(max_length=100, blank=True)
    narration = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def is_balanced(self):
        total_debit = sum(item.debit for item in self.entries.all())
        total_credit = sum(item.credit for item in self.entries.all())
        return round(total_debit, 2) == round(total_credit, 2)

class JournalEntry(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='entries')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='journal_entries')
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    line_description = models.CharField(max_length=255, blank=True)