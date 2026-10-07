# backend/apps/prescriptions/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .services import PrescriptionService
from apps.visits.models import Visit
from core.permissions import CanAccessVisit, HasExportPdf
from core.exceptions import error_response
from core.signals import log_action


class PrescriptionPreviewView(APIView):
    permission_classes = [IsAuthenticated, HasExportPdf, CanAccessVisit]
    service = PrescriptionService()

    def get(self, request, visit_id):
        visit = get_object_or_404(
            Visit.objects.select_related('patient', 'author'),
            id=visit_id,
        )
        self.check_object_permissions(request, visit)
        data = self.service.create_preview(visit, request.user.id)
        return Response({'data': data})


class PrescriptionGenerateView(APIView):
    permission_classes = [IsAuthenticated, HasExportPdf, CanAccessVisit]
    service = PrescriptionService()

    def post(self, request):
        visit_id = request.data.get('visit_id')
        signature_data = request.data.get('signature')
        stamp_data = request.data.get('stamp')
        if not visit_id:
            return error_response(400, 'visit_id is required', {})
        visit = get_object_or_404(
            Visit.objects.select_related('patient', 'author'),
            id=visit_id,
        )
        self.check_object_permissions(request, visit)
        preview_token = request.data.get('preview_token')
        snapshot = self.service.get_preview(preview_token, request.user.id, visit)
        result = self.service.generate_prescription_pdf(snapshot, signature_data, stamp_data)

        if isinstance(result, bytes):
            self.service.save_signature(request.user, visit_id, signature_data, stamp_data)
            self.service.discard_preview(preview_token)
            log_action(request.user.id, 'generate_prescription', 'Visit', visit.id, {
                'summary': f'Generated prescription from visit version {visit.version}',
                'visit_version': visit.version,
                'template_version': snapshot['template_version'],
            })
            response = HttpResponse(result, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="prescription_{visit_id}.pdf"'
            return response
        return error_response(503, 'تعذر إنشاء ملف PDF؛ تحقق من إعدادات مولد المستندات وحاول مجدداً', {})
