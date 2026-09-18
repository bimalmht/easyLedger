from django.shortcuts import render
from .models import Account

def voucher_create_view(request):
    accounts = Account.objects.filter(is_active=True)
    return render(request, 'accounting/voucher_form.html', {'accounts': accounts})