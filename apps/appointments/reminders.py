def appointment_reminder_prefix(appointment, window):
    if window not in {'day', 'hour'}:
        raise ValueError('Unknown appointment reminder window')
    return f'appointment-{window}:{appointment.pk}:'


def appointment_reminder_key(appointment, window):
    return (f'{appointment_reminder_prefix(appointment, window)}{appointment.reminder_generation}:'
            f'{appointment.appointment_date.isoformat()}:{appointment.appointment_time}')
