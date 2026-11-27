from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..models import Tenant
from ..activity.api import AuditedViewSetMixin
from ..serializers import TenantSerializer
from ..estate.api import AllotmentSerializer


class TenantViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    queryset = Tenant.with_last_billed_month()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'active']
    search_fields = ['name', 'allotment_description', 'contact']
    ordering_fields = ['name', 'type', 'created_at']
    ordering = ['name']
    contract_essentials = frozenset({
        'award_reference', 'letter_issued_on', 'start_date', 'end_date', 'rent_basis',
        'actual_area', 'measurement_reference', 'accepted_rate_amount', 'approved_rate_reference',
    })

    def save_contract(self, tenant):
        if 'contract' not in self.request.data:
            return
        supplied = self.request.data['contract']
        if not isinstance(supplied, dict):
            raise ValidationError({'contract': 'Supply contract fields as an object.'})
        data = {**supplied, 'tenant': tenant.pk}
        term_id = data.pop('id', None)
        unavailable = data.pop('unavailable', [])
        if not isinstance(unavailable, list) or any(
                not isinstance(field, str) or field not in self.contract_essentials for field in unavailable):
            raise ValidationError({'contract': 'Choose valid fields to mark Not Available.'})
        if unavailable:
            if term_id is not None:
                raise ValidationError({'contract': 'Keep the recorded evidence on an existing term.'})
            draft = AllotmentSerializer(data={}, partial=True, context=self.get_serializer_context())
            # Incomplete dates and charge details are kept outside the term and billing tables.
            values = {key: value for key, value in data.items() if key in draft.fields
                      and not draft.fields[key].read_only and key not in unavailable
                      and key not in ('tenant', 'shop', 'renewal_of') and value not in ('', None)}
            draft.to_internal_value(values)
            tenant.contract_draft = {'fields': values, 'unavailable': sorted(set(unavailable))}
            tenant.save(update_fields=['contract_draft', 'updated_at'])
            return
        term = None
        if term_id is not None:
            if not isinstance(term_id, int) or isinstance(term_id, bool):
                raise ValidationError({'contract': 'Choose a valid term for this allotment.'})
            term = tenant.allotments.filter(pk=term_id).first()
            if term is None:
                raise ValidationError({'contract': 'Choose a valid term for this allotment.'})
        contract = AllotmentSerializer(term, data=data, partial=term is not None,
                                      context=self.get_serializer_context())
        if not contract.is_valid():
            raise ValidationError({'contract': contract.errors})
        contract.save()
        if term is None and tenant.contract_draft:
            tenant.contract_draft = {}
            tenant.save(update_fields=['contract_draft', 'updated_at'])

    def perform_create(self, serializer):
        self.save_contract(serializer.save())

    def perform_update(self, serializer):
        self.save_contract(serializer.save())

    def destroy(self, request, *args, **kwargs):
        tenant = self.get_object()
        if tenant.bills.exists() or tenant.allotments.exists():
            tenant.active = False
            tenant.save()
            return Response({
                'message': 'Allottee deactivated (has billing or allotment history)',
                'soft_delete': True
            })
        return super().destroy(request, *args, **kwargs)
