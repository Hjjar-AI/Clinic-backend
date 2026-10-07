# backend/apps/appointments/serializers.py
from rest_framework import serializers
from .models import Appointment
from apps.patients.models import Patient
from apps.accounts.models import User

class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.full_name', read_only=True)
    patient_id = serializers.PrimaryKeyRelatedField(
        source='patient',
        queryset=Patient.objects.filter(deleted_at__isnull=True),
        write_only=True,
        required=True,
    )
    doctor_id = serializers.PrimaryKeyRelatedField(
        source='doctor',
        queryset=User.objects.filter(role__in=['doctor', 'admin'], is_active=True),
        write_only=True,
        required=True,
    )

    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'patient_name', 'doctor', 'doctor_name',
            'appointment_date', 'appointment_time', 'duration_minutes',
            'status', 'status_reason', 'notes', 'reminder_sent', 'reminder_sent_hour',
            'version', 'created_at', 'updated_at',
            'patient_id', 'doctor_id',
        ]
        read_only_fields = [
            'id', 'patient', 'patient_name', 'doctor', 'doctor_name',
            'created_at', 'updated_at', 'reminder_sent', 'reminder_sent_hour',
        ]
