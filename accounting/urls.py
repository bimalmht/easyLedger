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
    path('purchases/', views.purchase_invoice_list, name='purchase_invoice_list'),
    path('purchases/create/', views.purchase_invoice_create, name='purchase_invoice_create'),
    path('purchases/<uuid:pk>/', views.purchase_invoice_detail, name='purchase_invoice_detail'),
    
    # Credit Notes
    path('credit-notes/', views.credit_note_list_view, name='credit-note-list'),
    path('credit-notes/new/', views.credit_note_create_view, name='credit-note-create'),
    path('credit-notes/<int:credit_note_id>/', views.credit_note_detail_view, name='credit-note-detail'),
    path('api/invoices/<int:invoice_id>/items/', views.invoice_items_api, name='invoice-items-api'),
    path('templates/credit-notes/', views.credit_note_template_list_view, name='credit-note-template-list'),
    path('templates/credit-notes/new/', views.credit_note_template_edit_view, name='credit-note-template-create'),
    path('templates/credit-notes/<int:template_id>/edit/', views.credit_note_template_edit_view, name='credit-note-template-edit'),
    
    # Masters (Tax, Product, Customer)
    path('masters/taxes/', views.tax_list_view, name='tax-list'),
    path('masters/taxes/new/', views.tax_create_edit_view, name='tax-create'),
    path('masters/taxes/<int:tax_id>/edit/', views.tax_create_edit_view, name='tax-edit'),

    path('masters/products/', views.product_list_view, name='product-list'),
    path('masters/products/new/', views.product_create_edit_view, name='product-create'),
    path('masters/products/<int:product_id>/edit/', views.product_create_edit_view, name='product-edit'),
    path('masters/products/<int:product_id>/delete/', views.product_delete_view, name='product-delete'),

    path('masters/customers/', views.customer_list_view, name='customer-list'),
    path('masters/customers/new/', views.customer_create_edit_view, name='customer-create'),
    path('masters/customers/<int:customer_id>/edit/', views.customer_create_edit_view, name='customer-edit'),
    path('masters/customers/<int:customer_id>/delete/', views.customer_delete_view, name='customer-delete'),
    
    
    # Supplier Master CRUD & Quick Create API
    path('suppliers/', views.supplier_list_view, name='supplier-list'),
    path('suppliers/create/', views.supplier_create_edit_view, name='supplier-create'),
    path('suppliers/<uuid:supplier_id>/edit/', views.supplier_create_edit_view, name='supplier-edit'),
    path('suppliers/<uuid:supplier_id>/delete/', views.supplier_delete_view, name='supplier-delete'),
    
    # Other Charges Master CRUD & Quick-Create API
    path('other-charges/', views.other_charges_list_view, name='other-charges-list'),
    path('other-charges/create/', views.other_charges_create_edit_view, name='other-charges-create'),
    path('other-charges/<uuid:charge_id>/edit/', views.other_charges_create_edit_view, name='other-charges-edit'),
    path('other-charges/<uuid:charge_id>/delete/', views.other_charges_delete_view, name='other-charges-delete'),
                    
    # System Configuration Route
    path('settings/configuration/', views.company_settings_view, name='company-settings'),

    # APIs
    path('api/accounts/next-code/', views.get_next_account_code_api, name='next-account-code'),
    path('api/accounts/quick-create/', views.quick_create_account_api, name='quick-create-account'),
    path('audit-trail/', views.audit_trail_view, name='audit-trail'),
    path('api/products/search/', views.product_search_api, name='product-search-api'),
    path('api/customers/search/', views.customer_search_api, name='customer-search-api'),
    path('api/customers/quick-create/', views.quick_create_customer_api, name='quick-create-customer'),
    path('api/products/quick-create/', views.quick_create_product_api, name='quick-create-product'),
    path('api/accounts/search/', views.account_search_api, name='account-search-api'),
    path('api/suppliers/search/', views.supplier_search_api, name='supplier_search_api'),
    path('api/products/search/', views.product_search_api, name='product_search_api'),
    path('api/other-charges/list/', views.other_charges_list_api, name='other_charges_list_api'),
    path('api/suppliers/quick-create/', views.quick_create_supplier_api, name='quick-create-supplier-api'),
    path('api/other-charges/quick-create/', views.quick_create_other_charge_api, name='quick-create-other-charge-api'),
]