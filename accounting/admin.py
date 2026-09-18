from django.contrib import admin
from .models import Account, Transaction, JournalEntry

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'is_active')
    list_filter = ('account_type', 'is_active')
    search_fields = ('code', 'name')
    ordering = ('code',)

class JournalEntryInline(admin.TabularInline):
    model = JournalEntry
    extra = 2
    fields = ('account', 'debit', 'credit', 'line_description')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('voucher_number', 'date', 'reference', 'narration', 'created_at')
    search_fields = ('voucher_number', 'reference', 'narration')
    inlines = [JournalEntryInline]