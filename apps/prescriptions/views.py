# backend/apps/prescriptions/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .services import PrescriptionService
from apps.visits.models import Visit
from core.permissions import CanAccessVisit, HasExportPdf, HasViewVisits
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
        if 'print_options' in request.data:
            from .printing import normalize_print_options
            from django.utils import timezone
            snapshot = {**snapshot, 'print_options': normalize_print_options(request.data['print_options']),
                        'issue_date': timezone.localdate().strftime('%d/%m/%Y')}
        result = self.service.generate_prescription_pdf(snapshot, signature_data, stamp_data)

        if isinstance(result, bytes):
            from .issuance import record_document
            record_document(visit, request.user, 'prescription', snapshot, result, signature_data, stamp_data)
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


class PrescriptionCalibrationView(APIView):
    permission_classes = [IsAuthenticated, HasExportPdf]

    def post(self, request):
        from .printing import normalize_print_options, render_calibration
        options = normalize_print_options(request.data.get('print_options', {}))
        result = render_calibration(options)
        if not isinstance(result, bytes):
            return error_response(503, 'تعذر إنشاء ورقة المعايرة؛ حاول مجدداً', {})
        response = HttpResponse(result, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="prescription-calibration.pdf"'
        response['Cache-Control'] = 'no-store'
        return response


class PrescriptionHistoryView(APIView):
    permission_classes = [IsAuthenticated, HasViewVisits, HasExportPdf]

    def get(self, request, patient_id):
        from .history import prescription_history
        response = Response({'data': prescription_history(request.user, patient_id, request.query_params)})
        response['Cache-Control'] = 'no-store'
        return response


class ClinicalHandoverView(APIView):
    permission_classes = [IsAuthenticated, HasViewVisits, HasExportPdf]

    def get(self, request, visit_id=None, pdf=False, patient_id=None):
        from .handover import approved_handover, handover_pdf, latest_approved_handover
        data = latest_approved_handover(request.user, patient_id, request.query_params.get('exclude_visit')) if patient_id else approved_handover(request.user, visit_id)
        if pdf:
            result = handover_pdf(data)
            if not isinstance(result, bytes):
                return error_response(503, 'تعذر إنشاء ملخص التسليم', {})
            response = HttpResponse(result, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="handover_{visit_id}_revision_{data["revision_number"]}.pdf"'
        else:
            response = Response({'data': data})
        response['Cache-Control'] = 'no-store'
        return response


class PrescriptionDocumentView(APIView):
    permission_classes = [IsAuthenticated, HasViewVisits, HasExportPdf]

    def get(self, request, document_id, instructions=False):
        from .history import prescription_document, render_patient_instructions
        document = prescription_document(request.user, document_id)
        pdf = render_patient_instructions(document) if instructions else bytes(document.pdf_data)
        if not isinstance(pdf, bytes):
            return error_response(503, 'تعذر إنشاء تعليمات المريض؛ حاول مجدداً', {})
        response = HttpResponse(pdf, content_type='application/pdf')
        suffix = 'instructions' if instructions else 'prescription'
        response['Content-Disposition'] = f'attachment; filename="{suffix}_{document.pk}.pdf"'
        response['Cache-Control'] = 'no-store'
        if not instructions:
            response['X-Document-Checksum'] = document.checksum
        return response
