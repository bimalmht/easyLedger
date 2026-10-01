import datetime
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounting.models import (
    FiscalYear,
    DocumentSequence,
    Account,
    JournalEntry,
    Transaction,
    AccountType,
)
from accounting.utils.nepali_date import ad_to_bs, bs_to_ad, BS_CALENDAR_DATA


def _to_date(val):
    """
    Safely converts string, datetime, or date into a datetime.date object.
    Prevents TypeError if bs_to_ad returns a datetime.date object instead of str.
    """
    if val is None:
        return timezone.now().date()
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, datetime.date):
        return val
    if isinstance(val, str):
        return datetime.datetime.strptime(val.strip(), "%Y-%m-%d").date()
    return val


def get_or_create_active_fiscal_year(company, target_ad_date=None):
    """
    Resolves or initializes the applicable Nepalese Fiscal Year based on the transaction date.
    Nepali FY starts Shrawan 1 and ends Ashadh end.
    """
    target_ad_date = _to_date(target_ad_date)

    # 1. Check if an active open FiscalYear already covers this date
    fy = FiscalYear.objects.filter(
        company=company,
        start_date_ad__lte=target_ad_date,
        end_date_ad__gte=target_ad_date,
    ).first()

    if fy:
        return fy

    # 2. Derive fiscal year programmatically from the BS date
    bs_date_str = ad_to_bs(target_ad_date.strftime("%Y-%m-%d"))
    bs_year, bs_month, _ = map(int, bs_date_str.split("-"))

    if bs_month >= 4:  # Shrawan (Month 4) to Chaitra (Month 12)
        start_bs_year = bs_year
        end_bs_year = bs_year + 1
    else:              # Baishakh (Month 1) to Ashadh (Month 3)
        start_bs_year = bs_year - 1
        end_bs_year = bs_year

    name = f"{start_bs_year}/{str(end_bs_year)[-3:]}"  # e.g., 2083/084
    code = f"{str(start_bs_year)[-2:]}{str(end_bs_year)[-2:]}"  # e.g., 8384

    start_date_bs = f"{start_bs_year}-04-01"

    # Look up last day of Ashadh for end_bs_year
    ashadh_days = BS_CALENDAR_DATA.get(end_bs_year, [31] * 12)[2]
    end_date_bs = f"{end_bs_year}-03-{ashadh_days:02d}"

    # Safely convert to date objects
    start_date_ad = _to_date(bs_to_ad(start_date_bs))
    end_date_ad = _to_date(bs_to_ad(end_date_bs))

    fy, _ = FiscalYear.objects.get_or_create(
        company=company,
        name=name,
        defaults={
            "code": code,
            "start_date_bs": start_date_bs,
            "end_date_bs": end_date_bs,
            "start_date_ad": start_date_ad,
            "end_date_ad": end_date_ad,
            "is_closed": False,
        },
    )

    # Pre-populate all standard sequential counters for this fiscal year
    default_seqs = [
        (DocumentSequence.DocumentType.SALES_INVOICE, "INV"),
        (DocumentSequence.DocumentType.PURCHASE_INVOICE, "PINV"),
        (DocumentSequence.DocumentType.CREDIT_NOTE, "CN"),
        (DocumentSequence.DocumentType.DEBIT_NOTE, "DN"),
        (DocumentSequence.DocumentType.JOURNAL_VOUCHER, "JV"),
    ]
    for doc_type, pfx in default_seqs:
        DocumentSequence.objects.get_or_create(
            company=company,
            fiscal_year=fy,
            document_type=doc_type,
            defaults={
                "prefix": pfx,
                "next_number": 1,
                "padding_digits": 6,
            },
        )

    return fy


def generate_next_voucher_number(company, doc_type, ad_date=None, default_prefix=None):
    """
    Atomically generates the next sequence number (e.g. INV-8384-000001).
    Automatically resets to 1 upon rollover into a new fiscal year.
    """
    fy = get_or_create_active_fiscal_year(company, ad_date)

    if default_prefix is None:
        default_prefix = doc_type

    seq, _ = DocumentSequence.objects.select_for_update().get_or_create(
        company=company,
        fiscal_year=fy,
        document_type=doc_type,
        defaults={
            "prefix": default_prefix,
            "next_number": 1,
            "padding_digits": 6,
        },
    )

    current_num = seq.next_number
    seq.next_number = current_num + 1
    seq.save(update_fields=["next_number"])

    formatted_number = f"{seq.prefix}-{fy.code}-{str(current_num).zfill(seq.padding_digits)}"
    return formatted_number


def close_fiscal_year(company, fiscal_year, user=None):
    """
    Executes the statutory Year-End Closing Journal Entry:
    1. Zeroes out all temporary Income ledgers (Debit Income).
    2. Zeroes out all temporary Expense ledgers (Credit Expense).
    3. Transfers the net profit/loss into Retained Earnings / Reserves (Account 3010/3020).
    4. Marks the fiscal year as closed.
    """
    with transaction.atomic():
        if fiscal_year.is_closed:
            raise ValueError(f"Fiscal Year {fiscal_year.name} is already closed.")

        # Determine net earnings for the period
        income_accs = Account.objects.filter(company=company, account_type=AccountType.INCOME)
        expense_accs = Account.objects.filter(company=company, account_type=AccountType.EXPENSE)

        total_income = Decimal("0.00")
        total_expense = Decimal("0.00")

        jv_entries = []

        for acc in income_accs:
            d = JournalEntry.objects.filter(
                account=acc,
                transaction__date__range=[fiscal_year.start_date_ad, fiscal_year.end_date_ad],
            ).aggregate(Sum('debit'))['debit__sum'] or Decimal("0.00")
            c = JournalEntry.objects.filter(
                account=acc,
                transaction__date__range=[fiscal_year.start_date_ad, fiscal_year.end_date_ad],
            ).aggregate(Sum('credit'))['credit__sum'] or Decimal("0.00")
            bal = c - d
            if bal != Decimal("0.00"):
                total_income += bal
                jv_entries.append({
                    "account": acc,
                    "debit": bal,
                    "credit": Decimal("0.00"),
                    "desc": f"Close {acc.name} to Retained Earnings",
                })

        for acc in expense_accs:
            d = JournalEntry.objects.filter(
                account=acc,
                transaction__date__range=[fiscal_year.start_date_ad, fiscal_year.end_date_ad],
            ).aggregate(Sum('debit'))['debit__sum'] or Decimal("0.00")
            c = JournalEntry.objects.filter(
                account=acc,
                transaction__date__range=[fiscal_year.start_date_ad, fiscal_year.end_date_ad],
            ).aggregate(Sum('credit'))['credit__sum'] or Decimal("0.00")
            bal = d - c
            if bal != Decimal("0.00"):
                total_expense += bal
                jv_entries.append({
                    "account": acc,
                    "debit": Decimal("0.00"),
                    "credit": bal,
                    "desc": f"Close {acc.name} to Retained Earnings",
                })

        net_profit = total_income - total_expense

        retained_account, _ = Account.objects.get_or_create(
            company=company,
            code="3010",
            defaults={"name": "Retained Earnings / Owner Equity", "account_type": AccountType.EQUITY},
        )

        if net_profit > Decimal("0.00"):
            jv_entries.append({
                "account": retained_account,
                "debit": Decimal("0.00"),
                "credit": net_profit,
                "desc": "Transfer Net Profit to Retained Earnings",
            })
        elif net_profit < Decimal("0.00"):
            jv_entries.append({
                "account": retained_account,
                "debit": abs(net_profit),
                "credit": Decimal("0.00"),
                "desc": "Transfer Net Loss to Retained Earnings",
            })

        # Record Closing Transaction
        closing_jv_no = f"YEC-{fiscal_year.code}"
        txn = Transaction.objects.create(
            company=company,
            date=fiscal_year.end_date_ad,
            voucher_number=closing_jv_no,
            reference=f"YEAR-END-{fiscal_year.name}",
            narration=f"Fiscal Year {fiscal_year.name} Automated Closing Voucher",
        )

        for entry in jv_entries:
            JournalEntry.objects.create(
                transaction=txn,
                account=entry["account"],
                debit=entry["debit"],
                credit=entry["credit"],
                line_description=entry["desc"],
            )

        fiscal_year.is_closed = True
        fiscal_year.save(update_fields=["is_closed"])