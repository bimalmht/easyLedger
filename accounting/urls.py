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
    
    # Credit Notes
    path('credit-notes/', views.credit_note_list_view, name='credit-note-list'),
    path('credit-notes/new/', views.credit_note_create_view, name='credit-note-create'),
    path('credit-notes/<int:credit_note_id>/', views.credit_note_detail_view, name='credit-note-detail'),
    path('api/invoices/<int:invoice_id>/items/', views.invoice_items_api, name='invoice-items-api'),
    path('templates/credit-notes/', views.credit_note_template_list_view, name='credit-note-template-list'),
    path('templates/credit-notes/new/', views.credit_note_template_edit_view, name='credit-note-template-create'),
    path('templates/credit-notes/<int:template_id>/edit/', views.credit_note_template_edit_view, name='credit-note-template-edit'),
    
    # Masters (Tax & Products)
    path('masters/taxes/', views.tax_list_view, name='tax-list'),
    path('masters/taxes/new/', views.tax_create_edit_view, name='tax-create'),
    path('masters/taxes/<int:tax_id>/edit/', views.tax_create_edit_view, name='tax-edit'),
    path('masters/products/', views.product_list_view, name='product-list'),
    path('masters/products/new/', views.product_create_edit_view, name='product-create'),
    path('masters/products/<int:product_id>/edit/', views.product_create_edit_view, name='product-edit'),

    # APIs
    path('api/accounts/create/', views.account_quick_create_api, name='account-quick-create'),
    path('api/accounts/next-code/', views.get_next_code_api, name='account-next-code'),
    path('api/customers/create/', views.customer_quick_create_api, name='customer-quick-create'),
    path('audit-trail/', views.audit_trail_view, name='audit-trail'),
    path('api/products/search/', views.product_search_api, name='product-search-api'),
    path('api/customers/search/', views.customer_search_api, name='customer-search-api'),
]