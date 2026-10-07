# backend/apps/referrals/views.py
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from core.permissions import CanAccessVisit, HasViewReferrals
from core.exceptions import error_response
from .services import ReferralService

class ReferralLetterView(APIView):
    permission_classes = [IsAuthenticated, HasViewReferrals, CanAccessVisit]
    service = ReferralService()

    def post(self, request, visit_id):
        visit = self.service.get_visit(visit_id)
        if not visit:
            return error_response(404, 'الزيارة غير موجودة', {})
        self.check_object_permissions(request, visit)
        pdf = self.service.generate_pdf(
            visit,
            request.data.get('version'),
            request.data.get('reason'),
            request.user.id,
        )
        if pdf:
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="referral_{visit_id}.pdf"'
            return response
        return error_response(503, 'تعذر إنشاء ملف PDF؛ تحقق من إعدادات مولد المستندات وحاول مجدداً', {})
