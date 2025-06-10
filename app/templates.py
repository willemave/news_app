"""Template configuration with custom filters."""

from fastapi.templating import Jinja2Templates
import markdown
from markupsafe import Markup

# Initialize templates
templates = Jinja2Templates(directory="templates")

def markdown_filter(text):
    """Convert markdown text to HTML."""
    if not text:
        return ""
    md = markdown.Markdown(extensions=['fenced_code', 'tables', 'nl2br'])
    return Markup(md.convert(text))

# Register the markdown filter
templates.env.filters['markdown'] = markdown_filter