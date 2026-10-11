import logging
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)


def document_font_css():
    """Resolve bundled fonts locally, without a running frontend or a CDN."""
    frontend = settings.BASE_DIR.parent / 'frontend'
    configured = getattr(settings, 'PDF_FONT_DIR', None)
    candidates = [Path(configured)] if configured else [
        frontend / 'public' / 'static' / 'fonts',
        frontend / 'dist' / 'static' / 'fonts', frontend / 'dist' / 'fonts',
    ]
    names = {'Clinic Arabic': 'Cairo-VariableFont_slnt,wght.ttf',
             'Clinic Latin': 'Inter-VariableFont_opsz,wght.ttf'}
    directory = next((path for path in candidates if all((path / name).is_file() for name in names.values())), None)
    if directory is None:
        raise FileNotFoundError('Bundled PDF fonts are missing; configure PDF_FONT_DIR.')
    rules = []
    for family, filename in names.items():
        for weight in (400, 700):
            rules.append(f'@font-face {{font-family:"{family}"; src:url("{(directory / filename).resolve().as_uri()}"); font-weight:{weight};}}')
    rules.append('@page {font-family:"Clinic Arabic","Clinic Latin",sans-serif;}')
    return '\n'.join(rules)

def render_pdf_from_html(html: str, base_url: str = None) -> bytes:
    """
    Render PDF from HTML using WeasyPrint.
    Returns PDF bytes, or None on failure.
    """
    try:
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
        # Set a default base_url to resolve static files (fonts, CSS).
        # The frontend is a sibling of the backend project root.
        if base_url is None:
            base_url = settings.BASE_DIR.parent / 'frontend' / 'dist'
        fonts = FontConfiguration()
        stylesheet = CSS(string=document_font_css(), font_config=fonts)
        pdf = HTML(string=html, base_url=str(base_url)).write_pdf(stylesheets=[stylesheet], font_config=fonts)
        return pdf
    except Exception as e:
        logger.error(f"WeasyPrint PDF generation error: {e}")
        return None
