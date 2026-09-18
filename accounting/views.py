from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from .models import Account, Transaction, JournalEntry, AccountType
import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

# --- Account Code Generation Helpers ---

CATEGORY_PREFIX_MAP = {
    AccountType.ASSET: 1000,
    AccountType.LIABILITY: 2000,
    AccountType.EQUITY: 3000,
    AccountType.INCOME: 4000,
    AccountType.EXPENSE: 5000,
}

def get_next_account_code(account_type):
    """
    Finds the highest existing numeric code for the given account category
    and increments it by 10 (or 1). Defaults to base prefix + 10 if none exist.
    """
    base_prefix = CATEGORY_PREFIX_MAP.get(account_type, 1000)
    existing_accounts = Account.objects.filter(account_type=account_type)
    
    numeric_codes = []
    for acc in existing_accounts:
        try:
            numeric_codes.append(int(acc.code))
        except ValueError:
            continue

    if numeric_codes:
        next_code = max(numeric_codes) + 10
    else:
        next_code = base_prefix + 10

    return str(next_code)


# --- Views ---

def voucher_create_view(request):
    def get_voucher_context():
        accounts = Account.objects.filter(is_active=True).order_by('code')
        accounts_data = [
            {'id': acc.id, 'name': f"{acc.code} - {acc.name}"}
            for acc in accounts
        ]
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

        # Validate line items
        for acc_id, desc, deb, cred in zip(account_ids, descriptions, debits, credits):
            d_val = Decimal(deb or '0.00')
            c_val = Decimal(cred or '0.00')

            # Ignore empty lines
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
            messages.error(request, 'A voucher must have at least two non-zero entries.')
            return render(request, 'accounting/voucher_form.html', get_voucher_context())

        if total_debit != total_credit or total_debit == Decimal('0.00'):
            messages.error(request, f'Debit ({total_debit}) and Credit ({total_credit}) must be equal and greater than 0.')
            return render(request, 'accounting/voucher_form.html', get_voucher_context())

        # Atomic commit to ensure complete consistency
        with transaction.atomic():
            # Sequential Voucher Number: JV-YYYYMM-XXXX
            year_month = timezone.now().strftime('%Y%m')
            count = Transaction.objects.filter(voucher_number__startswith=f"JV-{year_month}").count() + 1
            voucher_number = f"JV-{year_month}-{count:04d}"

            txn = Transaction.objects.create(
                date=date,
                voucher_number=voucher_number,
                reference=reference,
                narration=narration
            )

            for item in valid_entries:
                account = Account.objects.get(id=item['account_id'])
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


def daybook_view(request):
    transactions = Transaction.objects.prefetch_related('entries__account').order_by('-date', '-id')
    return render(request, 'accounting/daybook.html', {'transactions': transactions})


def coa_view(request):
    """
    Displays the Chart of Accounts categorized by Account Type
    along with each account's current net balance.
    """
    accounts = Account.objects.filter(is_active=True).annotate(
        total_debit=Sum('journal_entries__debit'),
        total_credit=Sum('journal_entries__credit')
    ).order_by('code')

    grouped_accounts = {}
    for choice in AccountType.choices:
        grouped_accounts[choice[0]] = {
            'label': choice[1],
            'accounts': []
        }

    for acc in accounts:
        d = acc.total_debit or Decimal('0.00')
        c = acc.total_credit or Decimal('0.00')

        # Normal balances:
        # Assets & Expenses have normal debit balances (Debit - Credit)
        # Liabilities, Equity & Income have normal credit balances (Credit - Debit)
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
    """
    Shows the ledger statement / running balance for a specific account.
    """
    account = get_object_or_404(Account, id=account_id)
    entries = JournalEntry.objects.filter(account=account).select_related('transaction').order_by('transaction__date', 'transaction__id')

    # Compute running balance
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

    context = {
        'account': account,
        'ledger_lines': ledger_lines,
        'final_balance': abs(running_balance),
        'final_nature': 'Dr' if (running_balance >= 0 and account.account_type in [AccountType.ASSET, AccountType.EXPENSE]) or (running_balance < 0 and account.account_type not in [AccountType.ASSET, AccountType.EXPENSE]) else 'Cr'
    }
    return render(request, 'accounting/ledger_statement.html', context)


@require_POST
def account_quick_create_api(request):
    try:
        data = json.loads(request.body)
        account_type = data.get('account_type', '').strip()
        code = data.get('code', '').strip()
        name = data.get('name', '').strip()

        if not name or not account_type:
            return JsonResponse({'status': 'error', 'message': 'Account name and category are required.'}, status=400)

        # Auto-generate if code wasn't provided
        if not code:
            code = get_next_account_code(account_type)

        if Account.objects.filter(code=code).exists():
            return JsonResponse({'status': 'error', 'message': f'Account code {code} already exists.'}, status=400)

        new_acc = Account.objects.create(
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
    
    next_code = get_next_account_code(account_type)
    return JsonResponse({'status': 'success', 'next_code': next_code})

def trial_balance_view(request):
    """
    Computes real-time closing debit or credit balances for all active accounts.
    Verifies that total debits equal total credits across the business.
    """
    accounts = Account.objects.filter(is_active=True).annotate(
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

        # Calculate net position
        net = d - c
        debit_balance = Decimal('0.00')
        credit_balance = Decimal('0.00')

        if net > 0:
            debit_balance = net
        elif net < 0:
            credit_balance = abs(net)

        grand_debit += debit_balance
        grand_credit += credit_balance

        tb_rows.append({
            'account': acc,
            'debit_balance': debit_balance,
            'credit_balance': credit_balance,
        })

    is_balanced = (grand_debit == grand_credit)

    return render(request, 'accounting/trial_balance.html', {
        'tb_rows': tb_rows,
        'grand_debit': grand_debit,
        'grand_credit': grand_credit,
        'is_balanced': is_balanced,
    })


def profit_loss_view(request):
    """
    Calculates operational performance: Total Revenue minus Total Expenses.
    """
    accounts = Account.objects.filter(
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

    net_profit = total_income - total_expense

    return render(request, 'accounting/profit_loss.html', {
        'income_rows': income_rows,
        'expense_rows': expense_rows,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
    })

def dashboard_view(request):
    """
    Executive dashboard with key liquidity metrics, receivables/payables,
    net profit/loss indicator, and recent transactions.
    """
    accounts = Account.objects.filter(is_active=True).annotate(
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

        # Identify Cash/Bank assets (1010, 1020, or assets containing 'Cash'/'Bank')
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
    recent_transactions = Transaction.objects.prefetch_related('entries__account').order_by('-date', '-id')[:5]

    context = {
        'cash_bank_balance': cash_bank_balance,
        'receivables_balance': receivables_balance,
        'payables_balance': payables_balance,
        'net_profit': net_profit,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'accounting/dashboard.html', context)


def balance_sheet_view(request):
    """
    Generates point-in-time balance sheet:
    Assets = Liabilities + Equity (including current period Net Profit)
    """
    accounts = Account.objects.filter(is_active=True).annotate(
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
            balance = d - c
            if balance != Decimal('0.00'):
                assets.append({'account': acc, 'amount': balance})
                total_assets += balance
        elif acc.account_type == AccountType.LIABILITY:
            balance = c - d
            if balance != Decimal('0.00'):
                liabilities.append({'account': acc, 'amount': balance})
                total_liabilities += balance
        elif acc.account_type == AccountType.EQUITY:
            balance = c - d
            if balance != Decimal('0.00'):
                equity.append({'account': acc, 'amount': balance})
                total_equity_base += balance
        elif acc.account_type == AccountType.INCOME:
            total_income += (c - d)
        elif acc.account_type == AccountType.EXPENSE:
            total_expense += (d - c)

    current_period_earnings = total_income - total_expense
    total_equity_and_reserves = total_equity_base + current_period_earnings
    total_liabilities_and_equity = total_liabilities + total_equity_and_reserves

    is_balanced = abs(total_assets - total_liabilities_and_equity) < Decimal('0.01')

    context = {
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_equity_base': total_equity_base,
        'current_period_earnings': current_period_earnings,
        'total_equity_and_reserves': total_equity_and_reserves,
        'total_liabilities_and_equity': total_liabilities_and_equity,
        'is_balanced': is_balanced,
    }
    return render(request, 'accounting/balance_sheet.html', context)