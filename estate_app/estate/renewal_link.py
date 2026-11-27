"""Reviewed correction for a term entered as a separate original award."""
from django.core.exceptions import ValidationError
from django.db.models import F
from django.utils import timezone

from ..models import Allotment, EstateCharge, RentRevision
from .security import SECURITY_FIELDS


def link_existing_extension(term_id, previous_id, *, approval, performance, move_fee):
    # Reserve the SQLite writer before checking the existing lineage and financial records.
    Allotment.objects.filter(pk=term_id).update(actual_area=F('actual_area'))
    term = Allotment.objects.get(pk=term_id)
    previous = Allotment.objects.filter(pk=previous_id, tenant_id=term.tenant_id, shop_id=term.shop_id).first()
    if previous is None or previous.pk == term.pk or previous.effective_end >= term.start_date:
        raise ValidationError('Choose an earlier, non-overlapping term for the same allotment.')
    if term.renewal_of_id or Allotment.objects.filter(renewal_of_id__in=[term.pk, previous.pk]).exists():
        raise ValidationError('The selected terms already have a renewal link. Refresh the list and review term history.')
    if previous.extension_number >= 2 or term.rent_basis != previous.rent_basis:
        raise ValidationError('The preceding term must have an extension available and use the same rent basis.')
    if term.notice_governed != previous.notice_governed:
        raise ValidationError('The terms use different notice rules. Review their contract and billing records before linking.')
    if term.security_movements.exists() or any(getattr(term, field) not in (None, '', 'pending') for field in SECURITY_FIELDS):
        raise ValidationError('Review the second term’s independent security deposit records before linking it.')

    original = previous.original_award
    term_rates = RentRevision.objects.filter(original_award=term)
    if term_rates.filter(effective_date__lt=term.start_date).exists() or (
            term_rates.exists() and original.rent_revisions.filter(effective_date__gte=term.start_date).exists()):
        raise ValidationError('The rent schedules overlap. Review their effective dates before linking these terms.')

    previous_fee = previous.charges.filter(kind='extension_fee').first()
    term_fee = term.charges.filter(kind='extension_fee').first()
    if move_fee and (previous_fee or not term_fee):
        raise ValidationError('Move the existing fee only when it is on the second term and the preceding term has no fee.')
    if term_fee and not move_fee and previous.extension_number == 1:
        raise ValidationError('The second extension cannot retain a fee for a further renewal.')
    if move_fee:
        # Change ownership only. The charge ID, assessment, receipts and waiver history are retained.
        EstateCharge.objects.filter(pk=term_fee.pk).update(allotment=previous, updated_at=timezone.now())

    term.renewal_of = previous
    term.approval_reference = approval
    term.performance_reference = performance
    term._link_existing_extension = True
    term.save(update_fields=['renewal_of', 'approval_reference', 'performance_reference', 'updated_at'])
    # Keep the original revision IDs so issued invoices retain their exact rate evidence.
    if term_rates.update(original_award=original, updated_at=timezone.now()) and original.notice_governed:
        original.rent_revisions.order_by('-effective_date').first().full_clean()
    return term
