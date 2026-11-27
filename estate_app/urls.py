"""
BillTrack - App URLs
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views.reports import reports
from .views.invoices.http import extension_fee_demand
from .estate.api import ShopViewSet, AllotmentViewSet, RequirementViewSet, RentRevisionViewSet, EstateAttentionView
from .estate.charges import EstateChargeViewSet, ChargePaymentViewSet
from .estate.security_api import SecurityAccountViewSet, SecurityMovementViewSet

from .email_drafts.api import EmailDraftViewSet, EmailTemplateViewSet

router = DefaultRouter()
router.register('shops', ShopViewSet, basename='shop')
router.register('allotments', AllotmentViewSet, basename='allotment')
router.register('allotment-requirements', RequirementViewSet, basename='allotment-requirement')
router.register('rent-revisions', RentRevisionViewSet, basename='rent-revision')
router.register('estate-charges', EstateChargeViewSet, basename='estate-charge')
router.register('estate-charge-payments', ChargePaymentViewSet, basename='estate-charge-payment')
router.register('estate-security', SecurityAccountViewSet, basename='estate-security')
router.register('security-movements', SecurityMovementViewSet, basename='security-movement')
router.register('email-drafts', EmailDraftViewSet, basename='email-draft')
router.register('email-templates', EmailTemplateViewSet, basename='email-template')
router.register('tenants', views.TenantViewSet, basename='tenant')
router.register('bills', views.BillViewSet, basename='bill')
router.register('payments', views.PaymentViewSet, basename='payment')

urlpatterns = [
    path('estate/attention/', EstateAttentionView.as_view(), name='estate-attention'),
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
    path('estate-charges/<int:charge_id>/demand/', extension_fee_demand, name='extension-fee-demand'),

    # ViewSets (DRF Router)
    path('', include(router.urls)),
]
