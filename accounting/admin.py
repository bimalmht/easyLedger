from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    Company,
    UserProfile,
    Account,
    Transaction,
    JournalEntry,
    Customer,
    Invoice,
    InvoiceItem,
    InvoiceTemplate,
)
from .views import seed_company_default_accounts


# Inline UserProfile inside Django's User Admin
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = "Assigned Company"
    verbose_name_plural = "Assigned Company"
    fk_name = "user"


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ("username", "email", "get_company", "is_staff", "is_superuser")

    def get_company(self, obj):
        return obj.profile.company.name if hasattr(obj, "profile") and obj.profile.company else "-"
    get_company.short_description = "Company"


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "pan_number", "phone", "email", "created_at")
    search_fields = ("name", "pan_number")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Automatically seed standard Chart of Accounts & IRD template on first creation
        if not change:
            seed_company_default_accounts(obj)


# Operational Model Admins (Viewable by Superuser)
@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account_type", "company", "is_active")
    list_filter = ("company", "account_type", "is_active")
    search_fields = ("code", "name")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("voucher_number", "company", "date", "reference")
    list_filter = ("company", "date")
    search_fields = ("voucher_number", "reference", "narration")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "tax_number", "phone")
    list_filter = ("company",)
    search_fields = ("name", "tax_number")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "company", "customer", "date", "grand_total", "status")
    list_filter = ("company", "status")
    search_fields = ("invoice_number", "customer__name")


@admin.register(InvoiceTemplate)
class InvoiceTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "page_size", "is_default")
    list_filter = ("company", "page_size", "is_default")