from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib import messages
from django.utils import timezone
from .models import Account, Transaction, JournalEntry

def voucher_create_view(request):
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
            accounts = Account.objects.filter(is_active=True)
            return render(request, 'accounting/voucher_form.html', {'accounts': accounts})

        if total_debit != total_credit or total_debit == Decimal('0.00'):
            messages.error(request, f'Debit ({total_debit}) and Credit ({total_credit}) must be equal and greater than 0.')
            accounts = Account.objects.filter(is_active=True)
            return render(request, 'accounting/voucher_form.html', {'accounts': accounts})

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

    accounts = Account.objects.filter(is_active=True)
    return render(request, 'accounting/voucher_form.html', {'accounts': accounts})


def daybook_view(request):
    transactions = Transaction.objects.prefetch_related('entries__account').order_by('-date', '-id')
    return render(request, 'accounting/daybook.html', {'transactions': transactions})