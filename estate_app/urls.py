"""
BillTrack - App URLs
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views.reports import reports

from .email_drafts.api import EmailDraftViewSet, EmailTemplateViewSet

router = DefaultRouter()
router.register('email-drafts', EmailDraftViewSet, basename='email-draft')
router.register('email-templates', EmailTemplateViewSet, basename='email-template')
router.register('tenants', views.TenantViewSet, basename='tenant')
router.register('bills', views.BillViewSet, basename='bill')
router.register('payments', views.PaymentViewSet, basename='payment')

urlpatterns = [
    # Auth
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/me/', views.me_view, name='me'),

    # Dashboard
    path('dashboard/', views.dashboard_stats, name='dashboard'),
    path('reports/', reports, name='reports'),

    # Invoice (HTML + PDF via WeasyPrint)
    path('invoice/bulk/', views.bulk_invoice_view, name='bulk-invoice'),
    path('invoice/<int:bill_id>/', views.invoice_view, name='invoice'),
    path('invoice/<int:bill_id>/format-2/', views.invoice_format2_view, name='invoice-format-2'),

    # ViewSets (DRF Router)
    path('', include(router.urls)),
]
