from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from ..account_security.service import permitted
from ..models import EmailTemplate
from .service import generate


class ApprovedUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and permitted(request.user))


class GenerationInput(serializers.Serializer):
    allottee_id = serializers.IntegerField(required=False, min_value=1)
    bill_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=500)
    template_id = serializers.PrimaryKeyRelatedField(queryset=EmailTemplate.objects.filter(active=True))

    def validate_bill_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Select each bill once.')
        return value


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = ('id', 'name', 'subject', 'body')


@method_decorator(never_cache, name='dispatch')
class EmailTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [ApprovedUser]
    queryset = EmailTemplate.objects.filter(active=True)
    serializer_class = TemplateSerializer
    pagination_class = None


@method_decorator(never_cache, name='dispatch')
class EmailDraftViewSet(viewsets.GenericViewSet):
    """Merge a named template into a temporary email; no persistence or sending."""
    permission_classes = [ApprovedUser]
    serializer_class = GenerationInput

    @action(detail=False, methods=['post'])
    def generate(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response(generate(data.get('allottee_id'), data['bill_ids'], data['template_id']))
