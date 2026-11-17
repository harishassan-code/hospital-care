from django.apps import AppConfig


class MatchingConfig(AppConfig):
    name = "apps.matching"

    def ready(self):
        from . import checks  # noqa: F401  (registers the blood compatibility system check)
