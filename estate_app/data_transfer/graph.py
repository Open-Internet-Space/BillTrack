"""Collection invariants for staged records, without querying colliding live IDs."""
import calendar
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from ..models import (Allotment,AllotmentRequirement,Bill,EstateCharge,EstateChargePayment,
                      Payment,RentRevision,SecurityMovement,Shop,SystemSettings)
from ..models.estate import yearly_end
from ..estate.billing import annual_revisions
from ..estate.security import required_security,validate_security_pair,validate_security_timing


def require(condition,message):
    if not condition:
        raise ValidationError(message)


def validate_graph(objects):
    grouped=defaultdict(list)
    for item in objects:
        obj=item.object
        grouped[type(obj)].append(obj)
    require(len(grouped[SystemSettings]) <= 1, 'The export must contain at most one system settings record.')
    today=timezone.localdate()
    # UUIDs are checked by the parser; these are additional natural/operation keys.
    for model,rows in grouped.items():
        for field in model._meta.fields:
            if not field.unique or field.primary_key:continue
            seen=set()
            for row in rows:
                value=getattr(row,field.attname)
                if value is not None:
                    require(value not in seen,f'Duplicate {model._meta.label_lower}.{field.name}.')
                    seen.add(value)
    codes=set()
    for shop in grouped[Shop]:
        require(shop.code==shop.code.strip().upper() and shop.code.casefold() not in codes,'Shop codes must be canonical and unique.')
        codes.add(shop.code.casefold())
        require(bool(shop.availability_confirmed_on)==bool(shop.availability_reference.strip()),'Shop availability needs its date and reference.')
        require(not shop.availability_confirmed_on or shop.availability_confirmed_on<=today,'Shop availability cannot be future-dated.')
        require(bool(shop.opens_at)==bool(shop.closes_at),'Record both operating-hour limits.')

    successors=set();awards=set();terms=grouped[Allotment]
    for term in terms:
        chain=term._lineage()
        require(len(chain)<=3,'An award permits only two extensions.')
        term.validate_rent_basis()
        require(term.end_date>=term.start_date,'Invalid allotment dates.')
        require(term.start_date>=term.letter_issued_on or term.exception_reference.strip(),'An earlier term start requires approved authority.')
        require(not term.exception_reason.strip() or term.exception_reference.strip(),'A date exception reason requires an approval reference.')
        require(not term.termination_date or term.start_date<=term.termination_date<=term.end_date,'Invalid effective termination date.')
        for date,ref in [('termination_date','termination_reference'),('possession_date','possession_reference'),
                         ('handover_date','handover_reference'),('vacation_deadline','vacation_reference')]:
            require(bool(getattr(term,date))==bool(getattr(term,ref).strip()),'Term dates and evidence references must be recorded together.')
        if term.possession_date:
            require(term.start_date<=term.possession_date<=min(today,term.effective_end),'Invalid actual possession date.')
        if term.shop_id and term.possession_date:
            require((term.shop.availability_confirmed_on and term.shop.availability_confirmed_on<=term.possession_date)
                or any(peer.shop_id==term.shop_id and peer.pk!=term.pk and peer.handover_date and peer.handover_date<term.possession_date for peer in terms),
                'Possession requires earlier availability or handover evidence.')
        if term.handover_date:
            origin = term.possession_origin
            require(origin is not None and max(term.start_date, origin.possession_date) <= term.handover_date <= today,
                    'Handover requires recorded or continued possession in the term.')
        if term.renewal_of_id:
            previous=term.renewal_of
            require(term.renewal_of_id not in successors,'A preceding term cannot have two renewals.')
            successors.add(term.renewal_of_id)
            require((term.shop_id,term.tenant_id)==(previous.shop_id,previous.tenant_id),'Renewal ownership differs from the preceding term.')
            require(term.rent_basis==previous.rent_basis,'A renewal retains the original charge basis.')
            require(term.start_date>previous.effective_end and term.approval_reference.strip() and term.performance_reference.strip(),
                    'Renewal needs nonoverlapping dates, approval and performance evidence.')
            maximum=yearly_end(term.start_date)
        else:
            require(not term.carry_forward_deposit, 'Only a renewal can record deposit carry-forward.')
            key=(term.record_scope,term.award_reference)
            require(key not in awards,'Duplicate original award reference in the allotment history.')
            awards.add(key)
            maximum=yearly_end(term.letter_issued_on)
        require(term.end_date<=maximum or term.exception_reference.strip(),'A longer term needs its approved exception.')
        if term.security_required_amount is not None:
            require(not term.renewal_of_id and term.security_initial_rent is not None and
                term.security_required_amount>=required_security(term.security_initial_rent),'Invalid original-award security requirement.')
            require(term.security_due_date and term.security_requirement_reference.strip() and term.security_requirement_reason.strip(),
                    'Security requirements need their original deadline, approval and basis.')
            validate_security_timing(term)
        else:
            require(term.security_initial_rent is None and not any((term.security_due_date,term.security_timing,term.security_offer_date,term.security_requirement_reference,
                term.security_requirement_reason,term.security_extended_due_date,term.security_extension_reference,term.security_last_operation_id)),
                'Partial security requirement evidence is not sufficient.')
        require(bool(term.security_extended_due_date)==bool(term.security_extension_reference.strip()),'Security extension date and authority must match.')
        if term.security_extended_due_date:
            require(term.security_due_date and term.security_extended_due_date>=term.security_due_date,'Invalid security deadline extension.')
        if term.refund_review_status!='pending':
            require(term.security_required_amount is not None and term.refund_review_reference.strip() and term.refund_review_reason.strip(),
                    'Refund clearance needs a reviewed requirement, authority and reason.')
    for index,term in enumerate(terms):
        for peer in terms[index+1:]:
            if term.record_scope!=peer.record_scope:continue
            require(term.start_date>peer.effective_end or peer.start_date>term.effective_end,'Shop allotment terms overlap.')
    terms_by_scope = defaultdict(list)
    for term in terms:
        terms_by_scope[term.record_scope].append(term)
    for history in terms_by_scope.values():
        periods = sorted(Allotment.possession_periods(history).values(), key=lambda period: period[0])
        for (_, end), (start, _) in zip(periods, periods[1:]):
            require(end is not None and start > end, 'Physical possession overlaps.')
    for requirement in grouped[AllotmentRequirement]:
        requirement.clean()
    rates=defaultdict(list)
    for rate in grouped[RentRevision]:
        require(not rate.original_award.renewal_of_id and rate.rate>0 and rate.reason.strip(),
                'Invalid reviewed original-award rate.')
        if rate.original_award.rent_basis == 'flat':
            require(rate.rate==rate.rate.quantize(Decimal('0.01')),'Flat charges use at most two decimal places.')
        rates[rate.original_award_id].append(rate)
    for rows in rates.values():
        rows.sort(key=lambda row:row.effective_date)
        notice = rows[0].original_award.notice_governed
        if notice:
            require(all(rate.approval_reference.strip() for rate in rows), 'Rate approval reference is required.')
        for previous,current in zip(rows,rows[1:]):
            require(current.effective_date>previous.effective_date,'Duplicate rate effective date.')
            if not notice:
                continue
            revisions=annual_revisions(previous.rate,previous.effective_date,current.effective_date, flat=current.original_award.rent_basis=='flat')
            require(current.exception_reference.strip() or len(revisions)==1 and
                revisions[0]['effective_date']==current.effective_date and revisions[0]['rate']==current.rate,'Invalid annual rate progression.')

    bill_keys=set()
    for bill in grouped[Bill]:
        bill.clean(allotment=bill.allotment if bill.allotment_id else None, check_retained_payments=False)
        require(2000<=bill.year<=2100 and 1<=bill.month<=12 and min(bill.rent,bill.electric,bill.water)>=0,'Invalid bill period or principal.')
        require(min(bill.gst_on_rent,bill.cgst_on_rent,bill.sgst_on_rent,bill.igst_on_rent)>=0 and
                bill.gst_on_rent==bill.cgst_on_rent+bill.sgst_on_rent+bill.igst_on_rent,'GST snapshots do not reconcile.')
        require((bill.billing_category=='allotment')==bool(bill.allotment_id),'Billing category and term differ.')
        key=('term',bill.allotment_id,bill.year,bill.month) if bill.allotment_id else ('person',bill.tenant_id,bill.year,bill.month)
        require(key not in bill_keys,'Duplicate billing period.');bill_keys.add(key)
        if bill.allotment_id:
            term=bill.allotment
            require(term.tenant_id==bill.tenant_id,'Bill belongs to a different allottee from its term.')
            first=dt.date(bill.year,bill.month,1);last=first.replace(day=calendar.monthrange(bill.year,bill.month)[1])
            require(term.start_date<=last and term.effective_end>=first,'Bill period is outside its term.')
        if bill.billing_policy=='notices_368_369':
            require(bill.allotment_id and bill.allotment.notice_governed and not bill.issue_date,'Invalid notice-policy linkage or legacy receipt date.')
            require(not bill.raised_date or bill.raised_date<=today,'Invoice raising cannot be future-dated.')
            require(bill.due_date==(bill.raised_date+dt.timedelta(days=7) if bill.raised_date else None),'Notice invoice deadline differs from raising plus seven days.')
            if bill.email_dispatched_at:
                require(not timezone.is_naive(bill.email_dispatched_at) and bill.email_dispatched_at<=timezone.now()
                    and bill.raised_date and bill.dispatch_day>=bill.raised_date and bill.dispatch_sender_id
                    and bill.dispatch_recipient.strip() and bill.dispatch_message_reference.strip(),'Incomplete confirmed dispatch evidence.')
            if bill.rate_snapshot is not None or bill.area_snapshot is not None:
                require(bill.rate_snapshot is not None and bill.rate_snapshot>0 and (
                    bill.area_snapshot is None if bill.allotment.rent_basis=='flat'
                    else bill.area_snapshot is not None and bill.area_snapshot>0),'Invalid saved charge evidence.')
                require(bill.rent_revision_id and bill.full_month_rent is not None,'Saved rate snapshots require their reviewed revision and original rent.')
            if bill.rent_revision_id:
                require(bill.rent_revision.original_award_id==bill.allotment.original_award.pk,'Rate belongs to another award.')
                require(bill.rate_snapshot==bill.rent_revision.rate,'Saved rate evidence differs from its revision.')
                bill.prepare_notice_rent()
            else:
                require(bill.full_month_rent is not None and bill.rent_override_reason.strip() and
                    (not bill.raised_date or bill.rate_exception_reference.strip()),'Missing rate evidence requires an explicit reviewed override and issue authority.')
        else:
            require(not any((bill.raised_date,bill.email_dispatched_at,bill.dispatch_sender_id,bill.dispatch_recipient,bill.dispatch_message_reference)),
                    'Legacy bills cannot claim notice dispatch evidence.')
    charges={row.pk:row for row in grouped[EstateCharge]};fees=set()
    charge_paid=defaultdict(lambda:Decimal('0'))
    for receipt in grouped[EstateChargePayment]:
        require(receipt.amount>0 and receipt.charge.assessed_on<=receipt.payment_date<=today and receipt.receipt_reference.strip(),'Invalid charge receipt amount/date/reference.')
        charge_paid[receipt.charge_id]+=receipt.amount
    for charge in charges.values():
        require(charge.net_amount>=0 and charge.tax_amount>=0 and charge.gross_amount>0 and charge.description.strip() and charge.authority_reference.strip(),
                'Invalid approved charge assessment.')
        require(charge.assessed_on<=today and charge.due_date>=charge.assessed_on,'Invalid charge assessment/deadline dates.')
        require(charge.waiver_amount>=0 and charge_paid[charge.pk]+charge.waiver_amount<=charge.gross_amount,'Charge receipts and waiver exceed its assessment.')
        if charge.waiver_amount or any((charge.waiver_reference,charge.waiver_reason,charge.waived_by_id,charge.waived_at)):
            require(charge.waiver_reference.strip() and charge.waiver_reason.strip() and charge.waived_by_id and charge.waived_at,'Incomplete waiver authority.')
        if charge.kind=='extension_fee':
            require(charge.allotment_id not in fees and charge.allotment.extension_number<2,'Duplicate or excess extension fee.')
            fees.add(charge.allotment_id)
            require(not charge.allotment.notice_governed or charge.net_amount==1000,'Notified extension fee differs from 1000 net.')
        if charge.renewal_term_id:
            require(charge.kind=='extension_fee' and charge.renewal_term.renewal_of_id==charge.allotment_id,'Fee links to the wrong renewal.')
    for term in terms:
        if term.renewal_of_id and term.renewal_of.notice_governed:
            fee = next((charge for charge in charges.values() if charge.renewal_term_id == term.pk), None)
            require(fee is not None and fee.allotment_id == term.renewal_of_id and fee.kind == 'extension_fee'
                    and fee.net_amount == 1000, 'A notice-governed renewal requires its linked 1000 extension fee.')
    movements={row.operation_id:row for row in grouped[SecurityMovement] if row.operation_id}
    histories=defaultdict(list);applications={}
    for movement in grouped[SecurityMovement]:
        root=movement.original_award
        require(not root.renewal_of_id and movement.amount>0 and movement.effective_date<=today
            and (movement.kind=='received' or movement.effective_date>=root.letter_issued_on)
            and movement.reference.strip() and movement.reason.strip() and movement.recorded_by_id,'Invalid security movement identity, amount or evidence.')
        histories[root.pk].append(movement)
        if movement.kind=='applied':
            require(movement.operation_id and bool(movement.applied_bill_id)!=bool(movement.applied_charge_id),'Security application needs exactly one target and operation.')
            target=movement.applied_bill or movement.applied_charge
            require(target.allotment_id and target.allotment.original_award.pk==root.pk and target.allotment.tenant_id==root.tenant_id,
                    'Security application crosses an original award or allottee.')
            applications[movement.operation_id]=movement
        else:
            require(not movement.applied_bill_id and not movement.applied_charge_id,'A non-application movement cannot settle an obligation.')
    for history in histories.values():
        held=Decimal('0')
        for movement in sorted(history,key=lambda row:(row.effective_date,row.pk)):
            held+=movement.amount if movement.kind=='received' else -movement.amount
            require(held>=0,'Security history becomes negative.')
    paired=set()
    for receipt in [*grouped[Payment],*grouped[EstateChargePayment]]:
        if isinstance(receipt,Payment):
            require(receipt.amount>=0 and receipt.penalty_paid>=0 and receipt.amount+receipt.penalty_paid>0,'Invalid bill receipt components.')
            if receipt.bill.billing_policy=='notices_368_369':
                require(receipt.bill.raised_date and receipt.bill.raised_date<=receipt.payment_date<=today,'Notice receipt is outside its issued dates.')
        if receipt.source=='security_application':
            require(receipt.operation_id in applications and receipt.operation_id not in paired,'Missing or repeated paired security application.')
            paired.add(receipt.operation_id)
            receipt._security_authorized=True
            receipt._security_movement=movements[receipt.operation_id]
        validate_security_pair(receipt,receipt,'bill' if isinstance(receipt,Payment) else 'charge')
    require(paired==set(applications),'A security application has no matching obligation settlement.')
