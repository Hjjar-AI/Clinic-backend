from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal('0.01')
MAX_AMOUNT = Decimal('99999999.99')
MAX_QUANTITY = Decimal('999999.99')


def bounded_decimal(value, *, minimum=Decimal('0'), maximum=MAX_AMOUNT):
    try:
        amount = Decimal(str(value))
        if (isinstance(value, bool) or not amount.is_finite() or not minimum <= amount <= maximum
                or amount != amount.quantize(CENT)):
            raise ValueError('Invalid two-place decimal')
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('Invalid two-place decimal') from exc
    return amount


def round_money(amount):
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
