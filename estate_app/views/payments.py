from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from ..models import Payment, UserProfile
from ..activity.api import AuditedViewSetMixin
from ..serializers import PaymentSerializer


class PaymentViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('bill__tenant', 'bill__allotment__shop', 'recorded_by')
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['bill']

    def destroy(self, request, *args, **kwargs):
        if self.get_object().source != 'receipt':
            raise ValidationError('Paired security settlements cannot be deleted as ordinary receipts.')
        try:
            role = request.user.profile.role
        except UserProfile.DoesNotExist:
            role = 'staff'

        if role != 'admin' and not request.user.is_superuser:
            return Response({'error': 'Only admin can delete payment records'}, status=403)

        return super().destroy(request, *args, **kwargs)
