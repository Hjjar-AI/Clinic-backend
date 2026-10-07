import re

_DIACRITICS_PATTERN = re.compile(r'[\u064B-\u065F\u0670]')

_NORMALISATION_MAP = {
    '\u0629': '\u0647',   # Ta marbuta -> Ha
    '\u0649': '\u064A',   # Alef maksura -> Alef y
    '\u0623': '\u0627',   # Alef hamza above -> Alef
    '\u0625': '\u0627',   # Alef hamza below -> Alef
    '\u0622': '\u0627',   # Alef madda -> Alef
    '\u0624': '\u0648',   # Waw hamza -> Waw
    '\u0626': '\u064A',   # Yeh hamza -> Yeh
    '\u0671': '\u0627',   # Alef wasla -> Alef
}

def normalise_arabic(text: str) -> str:
    """
    Strip diacritics and normalise common Arabic characters.
    Returns a plain-Arabic string suitable for full-text search.
    """
    if not text:
        return text
    text = _DIACRITICS_PATTERN.sub('', text)
    for src, dest in _NORMALISATION_MAP.items():
        text = text.replace(src, dest)
    return text