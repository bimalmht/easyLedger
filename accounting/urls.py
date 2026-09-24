from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Core Operations
    path('', views.dashboard_view, name='dashboard'),
    path('daybook/', views.daybook_view, name='daybook'),
    path('vouchers/new/', views.voucher_create_view, name='voucher-create'),
    path('invoices/', views.invoice_list_view, name='invoice-list'),
    path('invoices/new/', views.invoice_create_view, name='invoice-create'),
    path('invoices/<int:invoice_id>/', views.invoice_detail_view, name='invoice-detail'),
    path('templates/', views.template_list_view, name='template-list'),
    path('templates/new/', views.template_edit_view, name='template-create'),
    path('templates/<int:template_id>/edit/', views.template_edit_view, name='template-edit'),
    path('chart-of-accounts/', views.coa_view, name='coa'),
    path('ledger/<int:account_id>/', views.ledger_statement_view, name='ledger-statement'),
    path('trial-balance/', views.trial_balance_view, name='trial-balance'),
    path('profit-and-loss/', views.profit_loss_view, name='profit-loss'),
    path('balance-sheet/', views.balance_sheet_view, name='balance-sheet'),

    # APIs
    path('api/accounts/create/', views.account_quick_create_api, name='account-quick-create'),
    path('api/accounts/next-code/', views.get_next_code_api, name='account-next-code'),
    path('api/customers/create/', views.customer_quick_create_api, name='customer-quick-create'),
    path('audit-trail/', views.audit_trail_view, name='audit-trail'),
]