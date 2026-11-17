from rest_framework.authentication import SessionAuthentication


class ClinicSessionAuthentication(SessionAuthentication):
    def authenticate_header(self, request):
        return 'Session'
