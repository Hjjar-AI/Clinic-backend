import hashlib
from django.db import transaction
from core.exceptions import ConflictError
from django.core.exceptions import ValidationError, PermissionDenied
from .models import IssuedDocument


def finalized_revision(visit):
    if visit.status not in {'final', 'locked'}:
        raise ValidationError({'visit': ['يجب اعتماد الزيارة قبل إصدار المستند']})
    revision = visit.revisions.order_by('-number').first()
    if not revision:
        raise ValidationError({'visit': ['لا توجد نسخة معتمدة وموقعة لهذه الزيارة']})
    return revision


@transaction.atomic
def record_document(visit, actor, kind, snapshot, pdf, signature='', stamp=''):
    if actor.role not in {'admin', 'doctor'} or not actor.has_perm('edit_visit'):
        raise PermissionDenied('إصدار المستندات مخصص للطبيب المخول')
    from apps.visits.models import Visit
    visit = Visit.all_objects.select_for_update().get(pk=visit.pk)
    if not visit.is_active or visit.deleted_at or visit.version != snapshot.get('visit_version'):
        raise ConflictError('تغيرت الزيارة؛ أعد المعاينة قبل إصدار المستند')
    revision = finalized_revision(visit)
    if snapshot.get('revision_id') != revision.pk:
        raise ValidationError({'visit': ['المستند لا يطابق النسخة المعتمدة']})
    return IssuedDocument.objects.create(document_type=kind, revision=revision, issued_by=actor,
        snapshot=snapshot, checksum=hashlib.sha256(pdf).hexdigest(), pdf_data=pdf,
        signature_data=signature or '', stamp_data=stamp or '')
