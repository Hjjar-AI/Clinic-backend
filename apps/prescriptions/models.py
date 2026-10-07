from django.db import models
from django.conf import settings
from core.models import TimeStampedModel, ImmutableModel

class PrescriptionSignature(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='prescription_signatures',
    )
    visit = models.ForeignKey(
        'visits.Visit',
        on_delete=models.PROTECT,
        related_name='prescription_signatures',
    )
    signature_data = models.TextField()
    stamp_data = models.TextField(blank=True, null=True)




class IssuedDocument(ImmutableModel):
    document_type = models.CharField(max_length=20, choices=[('prescription', 'Prescription'), ('referral', 'Referral')])
    revision = models.ForeignKey('visits.VisitRevision', on_delete=models.PROTECT, related_name='documents')
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='issued_documents')
    issued_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()
    checksum = models.CharField(max_length=64)
    pdf_data = models.BinaryField()
    signature_data = models.TextField(blank=True)
    stamp_data = models.TextField(blank=True)

