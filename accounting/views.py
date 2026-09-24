from decimal import Decimal
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q

from .models import (
    AuditLog,
    Company,
    UserProfile,
    Account,
    Transaction,
    JournalEntry,
    AccountType,
    Customer,
    Invoice,
    InvoiceItem,
    InvoiceTemplate,
    TaxConfiguration,
    Product,
    Customer,
)

# ==============================================================================
# Helper Functions
# ==============================================================================

CATEGORY_PREFIX_MAP = {
    AccountType.ASSET: 1000,
    AccountType.LIABILITY: 2000,
    AccountType.EQUITY: 3000,
    AccountType.INCOME: 4000,
    AccountType.EXPENSE: 5000,
}

def get_next_account_code(company, account_type):
    base_prefix = CATEGORY_PREFIX_MAP.get(account_type, 1000)
    existing_accounts = Account.objects.filter(company=company, account_type=account_type)
    
    numeric_codes = []
    for acc in existing_accounts:
        try:
            numeric_codes.append(int(acc.code))
        except ValueError:
            continue

    return str(max(numeric_codes) + 10) if numeric_codes else str(base_prefix + 10)


def seed_company_default_accounts(company):
    """Seed standard Chart of Accounts & default Nepal IRD tax invoice template."""
    default_accounts = [
        {"code": "1010", "name": "Cash on Hand", "account_type": AccountType.ASSET},
        {"code": "1020", "name": "Bank Checking Account", "account_type": AccountType.ASSET},
        {"code": "1030", "name": "Accounts Receivable", "account_type": AccountType.ASSET},
        {"code": "2010", "name": "Accounts Payable", "account_type": AccountType.LIABILITY},
        {"code": "2020", "name": "Sales Tax / VAT Payable", "account_type": AccountType.LIABILITY},
        {"code": "3010", "name": "Owner Capital", "account_type": AccountType.EQUITY},
        {"code": "4010", "name": "Sales Income", "account_type": AccountType.INCOME},
        {"code": "5010", "name": "Cost of Goods Sold (COGS)", "account_type": AccountType.EXPENSE},
        {"code": "5020", "name": "Office Rent Expense", "account_type": AccountType.EXPENSE},
    ]
    for acc in default_accounts:
        Account.objects.get_or_create(company=company, code=acc["code"], defaults=acc)

    InvoiceTemplate.objects.get_or_create(
        company=company,
        title="Standard Nepal IRD Tax Invoice (A4)",
        defaults={'page_size': 'A4_PORTRAIT', 'is_default': True}
    )


def number_to_words(n):
    """Nepali system Lakh/Crore integer conversion to words."""
    try:
        n = int(round(Decimal(n)))
    except Exception:
        return "Zero"

    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def convert_below_thousand(num):
        word = ""
        if num >= 100:
            word += units[num // 100] + " Hundred "
            num %= 100
        if 10 <= num <= 19:
            word += teens[num - 10] + " "
        elif num >= 20:
            word += tens[num // 10] + " "
            word += units[num % 10] + " "
        elif num > 0:
            word += units[num] + " "
        return word.strip()

    if n == 0:
        return "Zero Only"

    crore = n // 10000000
    n %= 10000000
    lakh = n // 100000
    n %= 100000
    thousand = n // 1000
    n %= 1000
    remainder = n

    parts = []
    if crore > 0:
        parts.append(convert_below_thousand(crore) + " Crore")
    if lakh > 0:
        parts.append(convert_below_thousand(lakh) + " Lakh")
    if thousand > 0:
        parts.append(convert_below_thousand(thousand) + " Thousand")
    if remainder > 0:
        parts.append(convert_below_thousand(remainder))

    return " ".join(parts).strip() + " Only"


# ==============================================================================
# Authentication & Superuser Company Provisioning
# ==============================================================================

def login_view(request):
    redirect_to = request.POST.get('next') or request.GET.get('next') or ''

    # If already logged in:
    if request.user.is_authenticated:
        if redirect_to:
            return redirect(redirect_to)
        if request.user.is_superuser:
            return redirect('/admin/')
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")

            # Check if a specific destination was requested (e.g., /admin/)
            if redirect_to:
                return redirect(redirect_to)

            # Superusers default to Django Admin, regular users default to ERP Dashboard
            if user.is_superuser:
                return redirect('/admin/')
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'accounting/login.html', {
        'form': form,
        'next': redirect_to
    })


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')

# ==============================================================================
# Isolated Financial Views (All Scoped strictly to request.company)
# ==============================================================================

def dashboard_view(request):
    comp = request.company
    if not comp:
        return redirect('company-create')

    accounts = Account.objects.filter(company=comp, is_active=True).annotate(
        total_debit=Sum('journal_entries__debit'),
        total_credit=Sum('journal_entries__credit')
    )

    cash_bank_balance = Decimal('0.00')
    receivables_balance = Decimal('0.00')
    payables_balance = Decimal('0.00')
    total_income = Decimal('0.00')
    total_expense = Decimal('0.00')

    for acc in accounts:
        d = acc.total_debit or Decimal('0.00')
        c = acc.total_credit or Decimal('0.00')

        if acc.account_type == AccountType.ASSET:
            if 'cash' in acc.name.lower() or 'bank' in acc.name.lower():
                cash_bank_balance += (d - c)
            elif 'receivable' in acc.name.lower():
                receivables_balance += (d - c)
        elif acc.account_type == AccountType.LIABILITY:
            if 'payable' in acc.name.lower():
                payables_balance += (c - d)
        elif acc.account_type == AccountType.INCOME:
            total_income += (c - d)
        elif acc.account_type == AccountType.EXPENSE:
            total_expense += (d - c)

    net_profit = total_income - total_expense
    recent_transactions = Transaction.objects.filter(company=comp).prefetch_related('entries__account').order_by('-date', '-id')[:5]

    return render(request, 'accounting/dashboard.html', {
        'cash_bank_balance': cash_bank_balance,
        'receivables_balance': receivables_balance,
        'payables_balance': payables_balance,
        'net_profit': net_profit,
        'recent_transactions': recent_transactions,
    })


def daybook_view(request):
    transactions = Transaction.objects.filter(company=request.company).prefetch_related('entries__account').order_by('-date', '-id')
    return render(request, 'accounting/daybook.html', {'transactions': transactions})


def voucher_create_view(request):
    comp = request.company

    def get_voucher_context():
        accounts = Account.objects.filter(company=comp, is_active=True).order_by('code')
        accounts_data = [{'id': acc.id, 'name': f"{acc.code} - {acc.name}"} for acc in accounts]
        return {
            'accounts': accounts,
            'accounts_data': accounts_data,
            'account_types': AccountType.choices
        }

    if request.method == 'POST':
        date = request.POST.get('date')
        reference = request.POST.get('reference', '')
        narration = request.POST.get('narration', '')

        account_ids = request.POST.getlist('account[]')
        descriptions = request.POST.getlist('line_description[]')
        debits = request.POST.getlist('debit[]')
        credits = request.POST.getlist('credit[]')

        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')
        valid_entries = []

        for acc_id, desc, deb, cred in zip(account_ids, descriptions, debits, credits):
            d_val = Decimal(deb or '0.00')
            c_val = Decimal(cred or '0.00')

            if d_val == Decimal('0.00') and c_val == Decimal('0.00'):
                continue

            total_debit += d_val
            total_credit += c_val
            valid_entries.append({
                'account_id': acc_id,
                'description': desc,
                'debit': d_val,
                'credit': c_val
            })

        if len(valid_entries) < 2:
            messages.error(request, 'A voucher must have at least two entries.')
            return render(request, 'accounting/voucher_form.html', get_voucher_context())

        if total_debit != total_credit or total_debit == Decimal('0.00'):
            messages.error(request, f'Debit ({total_debit}) and Credit ({total_credit}) must be equal and non-zero.')
            return render(request, 'accounting/voucher_form.html', get_voucher_context())

        with transaction.atomic():
            # Company-isolated voucher numbering series
            year_month = timezone.now().strftime('%Y%m')
            count = Transaction.objects.filter(company=comp, voucher_number__startswith=f"JV-{year_month}").count() + 1
            voucher_number = f"JV-{year_month}-{count:04d}"

            txn = Transaction.objects.create(
                company=comp,
                date=date,
                voucher_number=voucher_number,
                reference=reference,
                narration=narration
            )

            for item in valid_entries:
                account = get_object_or_404(Account, id=item['account_id'], company=comp)
                JournalEntry.objects.create(
                    transaction=txn,
                    account=account,
                    debit=item['debit'],
                    credit=item['credit'],
                    line_description=item['description']
                )

        messages.success(request, f'Voucher {voucher_number} posted successfully!')
        return redirect('daybook')

    return render(request, 'accounting/voucher_form.html', get_voucher_context())


def coa_view(request):
    comp = request.company
    accounts = Account.objects.filter(company=comp, is_active=True).annotate(
        total_debit=Sum('journal_entries__debit'),
        total_credit=Sum('journal_entries__credit')
    ).order_by('code')

    grouped_accounts = {}
    for choice in AccountType.choices:
        grouped_accounts[choice[0]] = {'label': choice[1], 'accounts': []}

    for acc in accounts:
        d = acc.total_debit or Decimal('0.00')
        c = acc.total_credit or Decimal('0.00')

        if acc.account_type in [AccountType.ASSET, AccountType.EXPENSE]:
            balance = d - c
            balance_type = 'Dr' if balance >= 0 else 'Cr'
        else:
            balance = c - d
            balance_type = 'Cr' if balance >= 0 else 'Dr'

        acc.calculated_balance = abs(balance)
        acc.balance_nature = balance_type
        grouped_accounts[acc.account_type]['accounts'].append(acc)

    return render(request, 'accounting/coa.html', {'grouped_accounts': grouped_accounts})


def ledger_statement_view(request, account_id):
    account = get_object_or_404(Account, id=account_id, company=request.company)
    entries = JournalEntry.objects.filter(
        account=account,
        transaction__company=request.company
    ).select_related('transaction').order_by('transaction__date', 'transaction__id')

    running_balance = Decimal('0.00')
    ledger_lines = []

    for item in entries:
        if account.account_type in [AccountType.ASSET, AccountType.EXPENSE]:
            running_balance += (item.debit - item.credit)
            balance_nature = 'Dr' if running_balance >= 0 else 'Cr'
        else:
            running_balance += (item.credit - item.debit)
            balance_nature = 'Cr' if running_balance >= 0 else 'Dr'

        ledger_lines.append({
            'date': item.transaction.date,
            'voucher_number': item.transaction.voucher_number,
            'narration': item.line_description or item.transaction.narration,
            'debit': item.debit,
            'credit': item.credit,
            'balance': abs(running_balance),
            'balance_nature': balance_nature
        })

    return render(request, 'accounting/ledger_statement.html', {
        'account': account,
        'ledger_lines': ledger_lines,
        'final_balance': abs(running_balance),
        'final_nature': 'Dr' if (running_balance >= 0 and account.account_type in [AccountType.ASSET, AccountType.EXPENSE]) or (running_balance < 0 and account.account_type not in [AccountType.ASSET, AccountType.EXPENSE]) else 'Cr'
    })


def trial_balance_view(request):
    comp = request.company
    accounts = Account.objects.filter(company=comp, is_active=True).annotate(
        total_debit=Sum('journal_entries__debit'),
        total_credit=Sum('journal_entries__credit')
    ).order_by('code')

    tb_rows = []
    grand_debit = Decimal('0.00')
    grand_credit = Decimal('0.00')

    for acc in accounts:
        d = acc.total_debit or Decimal('0.00')
        c = acc.total_credit or Decimal('0.00')

        if d == Decimal('0.00') and c == Decimal('0.00'):
            continue

        net = d - c
        debit_balance = net if net > 0 else Decimal('0.00')
        credit_balance = abs(net) if net < 0 else Decimal('0.00')

        grand_debit += debit_balance
        grand_credit += credit_balance

        tb_rows.append({
            'account': acc,
            'debit_balance': debit_balance,
            'credit_balance': credit_balance,
        })

    return render(request, 'accounting/trial_balance.html', {
        'tb_rows': tb_rows,
        'grand_debit': grand_debit,
        'grand_credit': grand_credit,
        'is_balanced': (grand_debit == grand_credit),
    })


def profit_loss_view(request):
    comp = request.company
    accounts = Account.objects.filter(
        company=comp,
        is_active=True,
        account_type__in=[AccountType.INCOME, AccountType.EXPENSE]
    ).annotate(
        total_debit=Sum('journal_entries__debit'),
        total_credit=Sum('journal_entries__credit')
    ).order_by('code')

    income_rows = []
    expense_rows = []
    total_income = Decimal('0.00')
    total_expense = Decimal('0.00')

    for acc in accounts:
        d = acc.total_debit or Decimal('0.00')
        c = acc.total_credit or Decimal('0.00')

        if acc.account_type == AccountType.INCOME:
            net_income = c - d
            if net_income != Decimal('0.00'):
                income_rows.append({'account': acc, 'amount': net_income})
                total_income += net_income
        elif acc.account_type == AccountType.EXPENSE:
            net_expense = d - c
            if net_expense != Decimal('0.00'):
                expense_rows.append({'account': acc, 'amount': net_expense})
                total_expense += net_expense

    return render(request, 'accounting/profit_loss.html', {
        'income_rows': income_rows,
        'expense_rows': expense_rows,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': total_income - total_expense,
    })


def balance_sheet_view(request):
    comp = request.company
    accounts = Account.objects.filter(company=comp, is_active=True).annotate(
        total_debit=Sum('journal_entries__debit'),
        total_credit=Sum('journal_entries__credit')
    ).order_by('code')

    assets = []
    liabilities = []
    equity = []

    total_assets = Decimal('0.00')
    total_liabilities = Decimal('0.00')
    total_equity_base = Decimal('0.00')
    total_income = Decimal('0.00')
    total_expense = Decimal('0.00')

    for acc in accounts:
        d = acc.total_debit or Decimal('0.00')
        c = acc.total_credit or Decimal('0.00')

        if acc.account_type == AccountType.ASSET:
            bal = d - c
            if bal != Decimal('0.00'):
                assets.append({'account': acc, 'amount': bal})
                total_assets += bal
        elif acc.account_type == AccountType.LIABILITY:
            bal = c - d
            if bal != Decimal('0.00'):
                liabilities.append({'account': acc, 'amount': bal})
                total_liabilities += bal
        elif acc.account_type == AccountType.EQUITY:
            bal = c - d
            if bal != Decimal('0.00'):
                equity.append({'account': acc, 'amount': bal})
                total_equity_base += bal
        elif acc.account_type == AccountType.INCOME:
            total_income += (c - d)
        elif acc.account_type == AccountType.EXPENSE:
            total_expense += (d - c)

    current_period_earnings = total_income - total_expense
    total_equity_and_reserves = total_equity_base + current_period_earnings
    total_liabilities_and_equity = total_liabilities + total_equity_and_reserves

    return render(request, 'accounting/balance_sheet.html', {
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_equity_base': total_equity_base,
        'current_period_earnings': current_period_earnings,
        'total_equity_and_reserves': total_equity_and_reserves,
        'total_liabilities_and_equity': total_liabilities_and_equity,
        'is_balanced': abs(total_assets - total_liabilities_and_equity) < Decimal('0.01'),
    })


# ==============================================================================
# Invoices & Templates (Company-Scoped Series)
# ==============================================================================

def invoice_list_view(request):
    invoices = Invoice.objects.filter(company=request.company).select_related('customer').order_by('-date', '-id')
    return render(request, 'accounting/invoice_list.html', {'invoices': invoices})


def invoice_detail_view(request, invoice_id):
    invoice = get_object_or_404(
        Invoice.objects.select_related('customer', 'transaction', 'created_by').prefetch_related('items'),
        id=invoice_id,
        company=request.company
    )

    # 1. Handle Print Action Trigger
    if request.GET.get('print') == 'true':
        invoice.print_count += 1
        invoice.save(update_fields=['print_count'])

        AuditLog.objects.create(
            company=request.company,
            user=request.user,
            username=request.user.username,
            action='REPRINT' if invoice.print_count > 1 else 'CREATE',
            table_name='Invoice',
            record_id=invoice.invoice_number,
            ip_address=request.META.get('REMOTE_ADDR'),
            details=f"Invoice {invoice.invoice_number} printed by {request.user.username}. Total prints: {invoice.print_count}"
        )
        return JsonResponse({'status': 'success', 'print_count': invoice.print_count})

    # 2. IRD Title & Header Formatting
    # First issuance (print_count == 0): "Original" & "कर बीजक / TAX INVOICE"
    # Second print onward (print_count >= 1): "Copy of Original" & "बीजक / INVOICE"
    if invoice.print_count == 0:
        copy_text = "Original (खरिदकर्ताको प्रति)"
        invoice_title_nepali = "कर बीजक"
        invoice_title_english = "TAX INVOICE"
        is_duplicate_copy = False
    else:
        copy_text = f"COPY OF ORIGINAL (प्रतिलिपि) #{invoice.print_count}"
        invoice_title_nepali = "बीजक"
        invoice_title_english = "INVOICE"
        is_duplicate_copy = True

    template = InvoiceTemplate.objects.filter(company=request.company, is_default=True).first() or \
               InvoiceTemplate.objects.filter(company=request.company).first()
    all_templates = InvoiceTemplate.objects.filter(company=request.company)

    return render(request, 'accounting/invoice_detail.html', {
        'invoice': invoice,
        'company': request.company,
        'template': template,
        'all_templates': all_templates,
        'amount_in_words': number_to_words(invoice.grand_total),
        'copy_text': copy_text,
        'invoice_title_nepali': invoice_title_nepali,
        'invoice_title_english': invoice_title_english,
        'is_duplicate_copy': is_duplicate_copy,
        'print_timestamp': timezone.now(),
    })


def template_list_view(request):
    templates = InvoiceTemplate.objects.filter(company=request.company)
    return render(request, 'accounting/template_list.html', {'templates': templates, 'company': request.company})


def template_edit_view(request, template_id=None):
    comp = request.company
    template = get_object_or_404(InvoiceTemplate, id=template_id, company=comp) if template_id else None

    if request.method == 'POST':
        comp.name = request.POST.get('comp_name', comp.name)
        comp.pan_number = request.POST.get('comp_pan', comp.pan_number)
        comp.address = request.POST.get('comp_address', comp.address)
        comp.phone = request.POST.get('comp_phone', comp.phone)
        comp.save()

        if not template:
            template = InvoiceTemplate(company=comp)

        template.title = request.POST.get('title')
        template.page_size = request.POST.get('page_size')
        template.is_default = request.POST.get('is_default') == 'on'
        template.show_hs_code = request.POST.get('show_hs_code') == 'on'
        template.show_nepali_header = request.POST.get('show_nepali_header') == 'on'
        template.header_subtitle = request.POST.get('header_subtitle', '')
        template.invoice_copy_text = request.POST.get('invoice_copy_text', '')
        template.declaration_text = request.POST.get('declaration_text', '')
        template.terms_and_conditions = request.POST.get('terms_and_conditions', '')
        template.footer_signature_label = request.POST.get('footer_signature_label', '')
        template.save()

        messages.success(request, "Template saved successfully.")
        return redirect('template-list')

    return render(request, 'accounting/template_form.html', {
        'template': template,
        'company': comp,
        'page_size_choices': InvoiceTemplate.PAGE_SIZE_CHOICES,
    })


# ==============================================================================
# Asynchronous APIs (Company-Scoped)
# ==============================================================================

@require_POST
def account_quick_create_api(request):
    try:
        data = json.loads(request.body)
        account_type = data.get('account_type', '').strip()
        code = data.get('code', '').strip()
        name = data.get('name', '').strip()

        if not name or not account_type:
            return JsonResponse({'status': 'error', 'message': 'Account name and category are required.'}, status=400)

        if not code:
            code = get_next_account_code(request.company, account_type)

        if Account.objects.filter(company=request.company, code=code).exists():
            return JsonResponse({'status': 'error', 'message': f'Account code {code} already exists in your company.'}, status=400)

        new_acc = Account.objects.create(
            company=request.company,
            code=code,
            name=name,
            account_type=account_type,
            is_active=True
        )

        return JsonResponse({
            'status': 'success',
            'account': {
                'id': new_acc.id,
                'code': new_acc.code,
                'name': new_acc.name,
                'display_text': f"{new_acc.code} - {new_acc.name}"
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_GET
def get_next_code_api(request):
    account_type = request.GET.get('account_type', '').strip()
    if not account_type:
        return JsonResponse({'status': 'error', 'message': 'Account type is required.'}, status=400)

    next_code = get_next_account_code(request.company, account_type)
    return JsonResponse({'status': 'success', 'next_code': next_code})


@require_POST
def customer_quick_create_api(request):
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        tax_number = data.get('tax_number', '').strip()
        phone = data.get('phone', '').strip()
        address = data.get('address', '').strip()

        if not name:
            return JsonResponse({'status': 'error', 'message': 'Customer name is required.'}, status=400)

        customer = Customer.objects.create(
            company=request.company,
            name=name,
            tax_number=tax_number,
            phone=phone,
            address=address
        )
        return JsonResponse({
            'status': 'success',
            'customer': {
                'id': customer.id,
                'name': customer.name
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
def audit_trail_view(request):
    """Clause 6.j: Front-End view to audit all activities and database actions."""
    logs = AuditLog.objects.filter(company=request.company).order_by('-timestamp')[:200]
    return render(request, 'accounting/audit_trail.html', {'logs': logs})

# ==============================================================================
# Tax Master Views
# ==============================================================================

def tax_list_view(request):
    taxes = TaxConfiguration.objects.filter(company=request.company).order_by('-fiscal_year', 'name')
    return render(request, 'accounting/tax_list.html', {'taxes': taxes})


def tax_create_edit_view(request, tax_id=None):
    comp = request.company
    tax = get_object_or_404(TaxConfiguration, id=tax_id, company=comp) if tax_id else None
    accounts = Account.objects.filter(company=comp, is_active=True).order_by('code')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        tax_type = request.POST.get('tax_type', 'VAT')
        rate = Decimal(request.POST.get('rate') or '0.00')
        fiscal_year = request.POST.get('fiscal_year', '').strip()
        ledger_account_id = request.POST.get('ledger_account')

        ledger_account = Account.objects.filter(id=ledger_account_id, company=comp).first() if ledger_account_id else None

        if not tax:
            tax = TaxConfiguration(company=comp)

        tax.name = name
        tax.tax_type = tax_type
        tax.rate = rate
        tax.fiscal_year = fiscal_year
        tax.ledger_account = ledger_account
        tax.is_active = request.POST.get('is_active') == 'on'
        tax.save()

        messages.success(request, f"Tax configuration '{tax.name}' saved successfully.")
        return redirect('tax-list')

    return render(request, 'accounting/tax_form.html', {
        'tax': tax,
        'accounts': accounts,
        'tax_types': TaxType.choices
    })


# ==============================================================================
# Product Master Views
# ==============================================================================

def product_list_view(request):
    products = Product.objects.filter(company=request.company).prefetch_related('taxes').order_by('name')
    return render(request, 'accounting/product_list.html', {'products': products})


def product_create_edit_view(request, product_id=None):
    comp = request.company
    product = get_object_or_404(Product, id=product_id, company=comp) if product_id else None
    taxes = TaxConfiguration.objects.filter(company=comp, is_active=True).order_by('name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        hs_code = request.POST.get('hs_code', '').strip()
        unit = request.POST.get('unit', 'Pcs').strip()
        selling_price = Decimal(request.POST.get('selling_price') or '0.00')
        selected_tax_ids = request.POST.getlist('taxes')

        if not product:
            product = Product(company=comp)

        product.name = name
        product.code = code
        product.hs_code = hs_code
        product.unit = unit
        product.selling_price = selling_price
        product.is_active = request.POST.get('is_active') == 'on'
        product.save()

        product.taxes.set(TaxConfiguration.objects.filter(id__in=selected_tax_ids, company=comp))
        messages.success(request, f"Product '{product.name}' saved successfully.")
        return redirect('product-list')

    return render(request, 'accounting/product_form.html', {
        'product': product,
        'taxes': taxes
    })


# ==============================================================================
# Fuzzy Multi-Part Search APIs
# ==============================================================================

@require_GET
def product_search_api(request):
    """Searches products across all partial words in any order."""
    query = request.GET.get('q', '').strip()
    words = query.split()

    qs = Product.objects.filter(company=request.company, is_active=True)
    for word in words:
        qs = qs.filter(Q(name__icontains=word) | Q(code__icontains=word) | Q(hs_code__icontains=word))

    results = []
    for p in qs[:20]:
        applicable_tax = p.taxes.filter(is_active=True).first()
        results.append({
            'id': p.id,
            'name': p.name,
            'hs_code': p.hs_code or '-',
            'unit_price': float(p.selling_price),
            'tax_rate': float(applicable_tax.rate) if applicable_tax else 0.0,
            'tax_name': applicable_tax.name if applicable_tax else 'No Tax'
        })
    return JsonResponse({'status': 'success', 'results': results})


@require_GET
def customer_search_api(request):
    """Searches customers across all partial words in any order."""
    query = request.GET.get('q', '').strip()
    words = query.split()

    qs = Customer.objects.filter(company=request.company)
    for word in words:
        qs = qs.filter(Q(name__icontains=word) | Q(tax_number__icontains=word) | Q(phone__icontains=word))

    results = []
    for c in qs[:20]:
        results.append({
            'id': c.id,
            'name': c.name,
            'tax_number': c.tax_number or 'N/A',
            'address': c.address or '',
            'is_vat_exempt': c.is_vat_exempt
        })
    return JsonResponse({'status': 'success', 'results': results})


# ==============================================================================
# Refined Invoice Creation Engine (Auto-Tax & Configurable Discounts)
# ==============================================================================

def invoice_create_view(request):
    comp = request.company

    if request.method == 'POST':
        customer_id = request.POST.get('customer_id')
        date = request.POST.get('date')
        due_date = request.POST.get('due_date') or None
        notes = request.POST.get('notes', '')

        # Discount parameters
        percent_rate = Decimal(request.POST.get('percent_discount_rate') or '0.00')
        value_discount = Decimal(request.POST.get('value_discount_amount') or '0.00')

        # Line items
        product_ids = request.POST.getlist('product_id[]')
        descriptions = request.POST.getlist('description[]')
        hs_codes = request.POST.getlist('hs_code[]')
        quantities = request.POST.getlist('quantity[]')
        unit_prices = request.POST.getlist('unit_price[]')
        is_free_flags = request.POST.getlist('is_free[]')
        promo_badges = request.POST.getlist('promo_badge[]')

        gross_subtotal = Decimal('0.00')
        free_discount_total = Decimal('0.00')
        line_items = []
        max_applied_tax_rate = Decimal('0.00')

        customer = get_object_or_404(Customer, id=customer_id, company=comp)

        for i in range(len(descriptions)):
            desc = descriptions[i].strip()
            qty = Decimal(quantities[i] or '0.00')
            price = Decimal(unit_prices[i] or '0.00')
            p_id = product_ids[i] if i < len(product_ids) and product_ids[i] else None
            h_code = hs_codes[i] if i < len(hs_codes) else ''
            is_free = (is_free_flags[i] == '1') if i < len(is_free_flags) else False
            promo = promo_badges[i].strip() if i < len(promo_badges) else ''

            if not desc or qty <= 0:
                continue

            line_amt = round(qty * price, 2)

            if is_free:
                # Value of free goods is calculated and added to the FREE discount line
                free_discount_total += line_amt
            else:
                gross_subtotal += line_amt

            # Check product's tagged tax rate
            if p_id and not customer.is_vat_exempt:
                p_obj = Product.objects.filter(id=p_id, company=comp).first()
                if p_obj:
                    for t in p_obj.taxes.filter(is_active=True):
                        if t.rate > max_applied_tax_rate:
                            max_applied_tax_rate = t.rate

            line_items.append({
                'product_id': p_id,
                'description': desc,
                'hs_code': h_code,
                'quantity': qty,
                'unit_price': price,
                'amount': line_amt,
                'is_free': is_free,
                'promo_badge': promo
            })

        if not line_items:
            messages.error(request, "Invoice must contain at least one line item.")
            return redirect('invoice-create')

        # Fallback to default VAT rate if customer is not exempt and no explicit product tax was assigned
        if max_applied_tax_rate == Decimal('0.00') and not customer.is_vat_exempt:
            default_tax = TaxConfiguration.objects.filter(company=comp, tax_type=TaxType.VAT, is_active=True).first()
            if default_tax:
                max_applied_tax_rate = default_tax.rate

        # Calculate discounts
        pct_discount_amt = round(gross_subtotal * (percent_rate / Decimal('100.00')), 2)
        total_discount_calculated = pct_discount_amt + value_discount + free_discount_total

        taxable_subtotal = max(Decimal('0.00'), gross_subtotal - (pct_discount_amt + value_discount))
        tax_amount = round(taxable_subtotal * (max_applied_tax_rate / Decimal('100.00')), 2)
        grand_total = taxable_subtotal + tax_amount

        with transaction.atomic():
            ym = timezone.now().strftime('%Y%m')
            inv_count = Invoice.objects.filter(company=comp, invoice_number__startswith=f"INV-{ym}").count() + 1
            invoice_number = f"INV-{ym}-{inv_count:04d}"

            jv_count = Transaction.objects.filter(company=comp, voucher_number__startswith=f"JV-{ym}").count() + 1
            jv_number = f"JV-{ym}-{jv_count:04d}"

            txn = Transaction.objects.create(
                company=comp,
                date=date,
                voucher_number=jv_number,
                reference=invoice_number,
                narration=f"Tax Invoice {invoice_number} issued to {customer.name}"
            )

            ar_acc = Account.objects.filter(company=comp, code='1030').first()
            sales_acc = Account.objects.filter(company=comp, code='4010').first()
            tax_acc = Account.objects.filter(company=comp, code='2020').first()

            JournalEntry.objects.create(
                transaction=txn,
                account=ar_acc,
                debit=grand_total,
                credit=Decimal('0.00'),
                line_description=f"Receivable from {customer.name}"
            )
            JournalEntry.objects.create(
                transaction=txn,
                account=sales_acc,
                debit=Decimal('0.00'),
                credit=taxable_subtotal,
                line_description="Net sales income post-discount"
            )
            if tax_amount > Decimal('0.00') and tax_acc:
                JournalEntry.objects.create(
                    transaction=txn,
                    account=tax_acc,
                    debit=Decimal('0.00'),
                    credit=tax_amount,
                    line_description=f"Output VAT ({max_applied_tax_rate}%)"
                )

            inv = Invoice.objects.create(
                company=comp,
                invoice_number=invoice_number,
                customer=customer,
                date=date,
                due_date=due_date,
                gross_subtotal=gross_subtotal,
                percent_discount_rate=percent_rate,
                percent_discount_amount=pct_discount_amt,
                value_discount_amount=value_discount,
                free_discount_amount=free_discount_total,
                total_discount=total_discount_calculated,
                taxable_subtotal=taxable_subtotal,
                tax_rate=max_applied_tax_rate,
                tax_amount=tax_amount,
                grand_total=grand_total,
                notes=notes,
                transaction=txn,
                created_by=request.user
            )

            for itm in line_items:
                InvoiceItem.objects.create(
                    invoice=inv,
                    product_id=itm['product_id'],
                    description=itm['description'],
                    hs_code=itm['hs_code'],
                    quantity=itm['quantity'],
                    unit_price=itm['unit_price'],
                    amount=itm['amount'],
                    is_free=itm['is_free'],
                    promo_badge=itm['promo_badge']
                )

        messages.success(request, f"Invoice {invoice_number} created.")
        return redirect('invoice-list')

    return render(request, 'accounting/invoice_form.html')