from django import template
from django.utils.safestring import mark_safe

register = template.Library()
PATHS = {
    'home': '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
    'car': '<path d="m5 7 2-4h10l2 4 2 3v8H3v-8zM3 10h18M7 14h1m8 0h1M5 18v3m14-3v3M5 7h14"/>',
    'plus': '<path d="M12 5v14M5 12h14"/>',
    'history': '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6m-6 4h6m-6 4h3"/>',
    'profile': '<circle cx="12" cy="7" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2z"/>',
    'fuel': '<path d="M4 21V4a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v17M3 21h12M5 6h7v5H5m9 2h2a1 1 0 0 1 1 1v4a2 2 0 0 0 4 0V9l-4-4m2 2v4h2"/>',
    'wrench': '<path d="M14 6a5 5 0 0 0-6 6l-5 5a3 3 0 0 0 4 4l5-5a5 5 0 0 0 6-6l-3 3-4-4z"/>',
    'chart': '<path d="M3 3v18h18M7 15l4-5 4 2 5-7"/>',
    'bell': '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
    'back': '<path d="m14 5-7 7 7 7M7 12h14"/>',
    'chevron': '<path d="m9 5 7 7-7 7"/>',
    'edit': '<path d="m15 4 5 5M4 16 16 4a3 3 0 0 1 4 4L8 20H4zM14 20h7"/>',
    'calendar': '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18m-12 4h1m4 0h1"/>',
    'camera': '<path d="M3 7h4l2-3h6l2 3h4v14H3z"/><circle cx="12" cy="13" r="4"/>',
    'image': '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="m3 16 6-6 6 6 3-3 3 3"/><circle cx="16" cy="8" r="1"/>',
    'logout': '<path d="M9 3H4v18h5m6-14 5 5-5 5m-7-5h12"/>',
    'settings': '<path d="m9 3-1 3-3 1-2 4 2 2v4l4 2 3-1 3 1 4-2v-4l2-2-2-4-3-1-1-3z"/><circle cx="12" cy="12" r="3"/>',
    'download': '<path d="M12 3v12m-5-5 5 5 5-5M3 16v5h18v-5"/>',
    'help': '<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 1 1 4 3c-1 0-1 2-1 2m0 3h.01"/>',
    'check': '<path d="m5 12 4 4L19 6"/>',
    'menu': '<path d="M4 6h16M4 12h16M4 18h16"/>',
    'close': '<path d="m6 6 12 12M6 18 18 6"/>',
    'shield': '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="m8 12 3 3 5-6"/>',
    'pin': '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0z"/><circle cx="12" cy="10" r="2"/>',
}


@register.simple_tag
def icon(name):
    return mark_safe('<svg class="icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + PATHS.get(name, PATHS['history']) + '</svg>')
