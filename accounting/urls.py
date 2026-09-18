from django.urls import path
from . import views

urlpatterns = [
    path('', views.daybook_view, name='daybook'),
    path('vouchers/new/', views.voucher_create_view, name='voucher-create'),
    path('chart-of-accounts/', views.coa_view, name='coa'),
    path('ledger/<int:account_id>/', views.ledger_statement_view, name='ledger-statement'),
]