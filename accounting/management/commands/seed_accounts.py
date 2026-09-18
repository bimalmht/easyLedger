# accounting/management/commands/seed_accounts.py
from django.core.management.base import BaseCommand
from accounting.models import Account, AccountType

DEFAULT_ACCOUNTS = [
    # Assets (1000s)
    {"code": "1010", "name": "Cash on Hand", "account_type": AccountType.ASSET},
    {"code": "1020", "name": "Bank Checking Account", "account_type": AccountType.ASSET},
    {"code": "1030", "name": "Accounts Receivable", "account_type": AccountType.ASSET},
    {"code": "1040", "name": "Inventory Asset", "account_type": AccountType.ASSET},
    
    # Liabilities (2000s)
    {"code": "2010", "name": "Accounts Payable", "account_type": AccountType.LIABILITY},
    {"code": "2020", "name": "Sales Tax / VAT Payable", "account_type": AccountType.LIABILITY},
    {"code": "2030", "name": "Accrued Payroll", "account_type": AccountType.LIABILITY},
    
    # Equity (3000s)
    {"code": "3010", "name": "Owner Capital", "account_type": AccountType.EQUITY},
    {"code": "3020", "name": "Owner Drawings", "account_type": AccountType.EQUITY},
    {"code": "3030", "name": "Retained Earnings", "account_type": AccountType.EQUITY},
    
    # Income / Revenue (4000s)
    {"code": "4010", "name": "Sales Income", "account_type": AccountType.INCOME},
    {"code": "4020", "name": "Service Revenue", "account_type": AccountType.INCOME},
    {"code": "4030", "name": "Discount Received", "account_type": AccountType.INCOME},
    
    # Expenses (5000s)
    {"code": "5010", "name": "Cost of Goods Sold (COGS)", "account_type": AccountType.EXPENSE},
    {"code": "5020", "name": "Office Rent Expense", "account_type": AccountType.EXPENSE},
    {"code": "5030", "name": "Utilities & Internet", "account_type": AccountType.EXPENSE},
    {"code": "5040", "name": "Salaries & Wages", "account_type": AccountType.EXPENSE},
]

class Command(BaseCommand):
    help = "Seeds initial standard Chart of Accounts"

    def handle(self, *args, **kwargs):
        created_count = 0
        for acc in DEFAULT_ACCOUNTS:
            obj, created = Account.objects.get_or_create(
                code=acc["code"],
                defaults={"name": acc["name"], "account_type": acc["account_type"]}
            )
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {created_count} accounts."))