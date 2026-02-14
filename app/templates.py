import time

import markdown
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

# Configure Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Cache-busting version: set once at startup so all static asset URLs
# get a ?v= query param that changes on each deploy/restart.
templates.env.globals["static_version"] = str(int(time.time()))


# Add markdown filter
def markdown_filter(text):
    """Convert markdown text to HTML."""
    if not text:
        return ""
    # Configure markdown with useful extensions
    md = markdown.Markdown(
        extensions=[
            "extra",  # Tables, footnotes, abbreviations, etc.
            "codehilite",  # Code syntax highlighting
            "toc",  # Table of contents
            "nl2br",  # New line to <br>
            "smarty",  # Smart quotes and dashes
        ]
    )
    html = md.convert(str(text))
    return Markup(html)


# Register the filter
templates.env.filters["markdown"] = markdown_filter
