from django.urls import path
from . import views

urlpatterns = [
    path('', views.daybook_view, name='daybook'),
    path('vouchers/new/', views.voucher_create_view, name='voucher-create'),
]