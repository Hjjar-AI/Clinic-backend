from django.urls import path
from .views import ReferralLetterView

urlpatterns = [
    path('visit/<int:visit_id>/', ReferralLetterView.as_view(), name='referral-letter'),
]