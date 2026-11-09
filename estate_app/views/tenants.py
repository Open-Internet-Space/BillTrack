from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Tenant
from ..serializers import TenantSerializer


class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.with_last_billed_month()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'active']
    search_fields = ['name', 'contact']
    ordering_fields = ['name', 'type', 'created_at']
    ordering = ['name']

    def destroy(self, request, *args, **kwargs):
        tenant = self.get_object()
        if tenant.bills.exists():
            tenant.active = False
            tenant.save()
            return Response({
                'message': 'Allottee deactivated (has billing history)',
                'soft_delete': True
            })
        return super().destroy(request, *args, **kwargs)
