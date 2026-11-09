from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Payment, UserProfile
from ..serializers import PaymentSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('bill__tenant', 'recorded_by')
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        try:
            role = request.user.profile.role
        except UserProfile.DoesNotExist:
            role = 'staff'

        if role != 'admin':
            return Response({'error': 'Only admin can delete payment records'}, status=403)

        bill = self.get_object().bill
        response = super().destroy(request, *args, **kwargs)
        bill.update_status()
        return response
