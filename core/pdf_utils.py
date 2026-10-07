import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def render_pdf_from_html(html: str, base_url: str = None) -> bytes:
    """
    Render PDF from HTML using WeasyPrint.
    Returns PDF bytes, or None on failure.
    """
    try:
        from weasyprint import HTML
        # Set a default base_url to resolve static files (fonts, CSS).
        # The frontend is a sibling of the backend project root.
        if base_url is None:
            base_url = settings.BASE_DIR.parent / 'frontend' / 'dist'
        pdf = HTML(string=html, base_url=str(base_url)).write_pdf()
        return pdf
    except Exception as e:
        logger.error(f"WeasyPrint PDF generation error: {e}")
        return None
