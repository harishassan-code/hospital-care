"""System check (story #37): a broken blood compatibility rules file fails `manage.py check` and runserver."""

from django.core.checks import Error, register
from django.core.exceptions import ImproperlyConfigured

from .compatibility import load_rules


@register
def blood_compatibility_rules(app_configs, **kwargs):
    try:
        load_rules()
    except ImproperlyConfigured as exc:
        return [Error(str(exc), id="matching.E001", hint="Fix apps/matching/blood_compatibility.json.")]
    return []
