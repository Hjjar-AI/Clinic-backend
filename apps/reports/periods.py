from datetime import date
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.core.exceptions import ValidationError

MONTH_NAMES = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']

def monthly_period(months, start=None, end=None):
    if type(months) is not int or not 1 <= months <= 120:
        raise ValidationError({'months': ['المدة بين 1 و120 شهراً']})
    end = end or timezone.localdate()
    start = start or end.replace(day=1) - relativedelta(months=months-1)
    if start > end or end.year - start.year > 100:
        raise ValidationError({'date_from': ['الفترة غير صالحة']})
    return start, end

def fill_months(rows, start, end):
    counts = {(r['month'].year, r['month'].month): r['count'] for r in rows}
    labels, values = [], []
    month = start.replace(day=1)
    while month <= end:
        labels.append(f'{MONTH_NAMES[month.month-1]} {month.year}')
        values.append(counts.get((month.year, month.month), 0))
        if month.year == 9999 and month.month == 12:
            break
        month += relativedelta(months=1)
    return labels, values
