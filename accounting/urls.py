from django.urls import path
from . import views

urlpatterns = [
    path('vouchers/new/', views.voucher_create_view, name='voucher-create'),
]