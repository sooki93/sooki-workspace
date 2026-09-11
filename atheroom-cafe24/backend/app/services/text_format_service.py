"""Shared product-copy typography for detail and brief descriptions."""
import html
import re

FONT_SIZE='11px'

def format_text(text):
    escaped=html.escape(str(text))
    escaped=re.sub(r'^(\s*)(comment|detail[ \t]+info)(?=[ \t:]|$)',
                   r'\1<strong style="font-size:11px;font-weight:700">\2</strong>',escaped,flags=re.I|re.M)
    return escaped.replace('\n','<br>')
