"""Validated physical layouts; the reference scan is never part of an issued PDF."""
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from core.pdf_utils import document_font_css


def normalize_print_options(value):
    if not isinstance(value, dict):
        raise ValidationError({'print_options': ['إعدادات الورق غير صالحة']})
    allowed = {'mode', 'width_mm', 'height_mm', 'offset_x_mm', 'offset_y_mm'}
    mode = value.get('mode', 'blank')
    if set(value) - allowed or not isinstance(mode, str) or mode not in {'blank', 'preprinted'}:
        raise ValidationError({'print_options': ['نوع الورق أو إعداداته غير صالحة']})
    result = {'mode': value.get('mode', 'blank')}
    for key, default, minimum, maximum in (
        ('width_mm', 105, 80, 216), ('height_mm', 148, 120, 350),
        ('offset_x_mm', 0, -5, 5), ('offset_y_mm', 0, -5, 5),
    ):
        try:
            number = Decimal(str(value.get(key, default)))
            if not number.is_finite() or not minimum <= number <= maximum or number != number.quantize(Decimal('.01')):
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError({'print_options': [f'{key}: أدخل قيمة بين {minimum} و{maximum} بدقة منزلتين كحد أقصى']})
        result[key] = float(number) if result['mode'] == 'preprinted' or not key.startswith('offset_') else 0.0
    return result


def preprinted_geometry(options):
    width, height = options['width_mm'], options['height_mm']
    x, y = options['offset_x_mm'], options['offset_y_mm']
    return {
        'width': width, 'height': height, 'left': width * .07 + x,
        'content_width': width * .84, 'body_top': height * .385 + y,
        'body_height': height * .36, 'name_left': width * .475 + x,
        'value_width': width * .28, 'row_one': height * .202 + y,
        'row_two': height * .226 + y, 'field_height': height * .024,
        'summary_top': height * .269 + y, 'summary_width': width * .52,
        'summary_height': height * .058, 'duration_top': height * .341 + y,
        'signature_top': height * .76 + y, 'signature_width': width * .30,
        'signature_height': height * .045, 'date_top': height * .808 + y,
        'date_left': width * .50 + x, 'date_width': width * .17,
    }


def render_preprinted(prescription, options):
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    fonts = FontConfiguration()
    stylesheet = CSS(string=document_font_css(), font_config=fonts)
    geometry = preprinted_geometry(options)
    medications = prescription.get('medications') or []
    indexed = [{**medication, 'index': index} for index, medication in enumerate(medications)]
    def render(sheets, measurement=False, field_font=6.5):
        html = render_to_string('prescriptions/prescription_preprinted.html', {
            'prescription': prescription, 'paper': geometry, 'sheets': sheets,
            'measurement': measurement, 'field_font': field_font,
        })
        return HTML(string=html).render(stylesheets=[stylesheet], font_config=fonts)

    # One measuring sheet per medicine avoids table-row clipping and estimates
    # both the upper drug-name box and the free instruction area with real fonts.
    measured = render([[med] for med in indexed] or [[]], measurement=True)
    def sizes(document):
        fields, summaries, bodies = {}, {}, {}
        for page in document.pages:
            pending = [page._page_box]
            while pending:
                box = pending.pop()
                box = getattr(box, '_box', box)
                pending.extend(getattr(box, 'children', ()))
                element = getattr(box, 'element', None)
                if element is None or type(box).__name__ != 'BlockBox':
                    continue
                field = element.get('data-field')
                if field:
                    fields[field] = max(fields.get(field, 0), box.height)
                index = element.get('data-index')
                kind = element.get('data-kind')
                if index is not None and kind in {'summary', 'body'}:
                    target = summaries if kind == 'summary' else bodies
                    target[int(index)] = box.height + box.margin_top + box.margin_bottom
        return fields, summaries, bodies
    fields, summaries, bodies = sizes(measured)
    px_per_mm = 96 / 25.4
    field_font = 6.5
    if any(height > geometry['field_height'] * px_per_mm + .5 for height in fields.values()):
        field_font = 5
        measured = render([[med] for med in indexed] or [[]], measurement=True, field_font=field_font)
        fields, summaries, bodies = sizes(measured)
    if any(height > geometry['field_height'] * px_per_mm + .5 for height in fields.values()):
        raise ValidationError({'print_options': ['بيانات المريض لا تتسع في خانات النموذج؛ اختر أبعاداً أكبر أو ورقاً فارغاً']})
    if len(summaries) != len(indexed) or len(bodies) != len(indexed):
        raise ValidationError({'print_options': ['تعذر قياس المحتوى بأمان؛ اختر الورق الفارغ']})
    sheets, current, body_height, summary_height = [], [], 0, 0
    body_limit = geometry['body_height'] * px_per_mm - 24
    summary_limit = geometry['summary_height'] * px_per_mm
    for med in indexed:
        index = med['index']; body, summary = bodies[index], summaries[index]
        if body > body_limit or summary > summary_limit:
            raise ValidationError({'print_options': ['تعليمات أحد الأدوية لا تتسع في النموذج؛ اختر أبعاداً أكبر أو ورقاً فارغاً']})
        if current and (body_height + body > body_limit or summary_height + summary > summary_limit):
            sheets.append(current); current = []; body_height = summary_height = 0
        current.append(med); body_height += body; summary_height += summary
    if current or not sheets:
        sheets.append(current)
    document = render(sheets, field_font=field_font)
    if len(document.pages) != len(sheets):
        raise ValidationError({'print_options': ['تعذر توزيع المحتوى بأمان على الورق']})
    return document.write_pdf()
