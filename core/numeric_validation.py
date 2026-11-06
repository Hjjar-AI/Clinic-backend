"""Numeric primitives shared by catalog definitions and saved clinical answers."""
import math


def finite_number(value, *, coerce=False):
    if isinstance(value, bool) or (not coerce and type(value) not in (int, float)):
        raise ValueError('A finite number is required')
    try:
        number = float(value) if coerce else value
        if not math.isfinite(number):
            raise ValueError('A finite number is required')
    except (TypeError, OverflowError) as exc:
        raise ValueError('A finite number is required') from exc
    return number


def valid_scale_range(minimum, maximum, step, *, bound_step=True):
    try:
        for value in (minimum, maximum, step):
            finite_number(value)
        span = maximum - minimum
        return math.isfinite(span) and span > 0 and step > 0 and (not bound_step or step <= span)
    except (ValueError, OverflowError):
        return False


def step_aligned(value, minimum, step):
    try:
        increments = (value - minimum) / step
        return math.isfinite(increments) and math.isclose(increments, round(increments), rel_tol=0, abs_tol=1e-7)
    except (TypeError, ValueError, OverflowError, ZeroDivisionError):
        return False
