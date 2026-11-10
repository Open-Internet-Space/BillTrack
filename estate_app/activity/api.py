from django.db import transaction
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .context import operation, current_operation
from .deletion import deletion_plan, confirmed


class AuditedViewSetMixin:
    def dispatch(self, request, *args, **kwargs):
        with operation(source='api', reason='API create/read workflow'), transaction.atomic():
            response = super().dispatch(request, *args, **kwargs)
            if response.status_code >= 400:
                transaction.set_rollback(True)
            return response

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        context = current_operation.get()
        context.update(actor_id=request.user.pk, actor_name=request.user.get_username())
        if request.method in ('PUT', 'PATCH', 'DELETE'):
            reason = request.headers.get('X-Change-Reason') or request.data.get('change_reason', '')
            if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
                raise ValidationError({'change_reason': 'Enter a written reason (maximum 2000 characters).'})
            context['reason'] = reason.strip()
        if request.method == 'DELETE':
            plan = self.get_deletion_plan()
            token = request.headers.get('X-Deletion-Confirmation') or request.data.get('confirmation')
            if not confirmed(token, plan):
                raise ValidationError({'confirmation': 'Review deletion-preview and confirm the current affected records first.'})

    def get_deletion_plan(self):
        obj = self.get_object()
        soft = obj._meta.label_lower == 'estate_app.tenant' and obj.bills.exists()
        return deletion_plan([obj], soft=soft)

    @action(detail=True, methods=['get'], url_path='deletion-preview')
    def deletion_preview(self, request, *args, **kwargs):
        plan = self.get_deletion_plan()
        return Response({'affected': plan['affected'], 'confirmation': plan['confirmation']})
