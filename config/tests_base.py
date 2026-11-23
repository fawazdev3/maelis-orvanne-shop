from django.core.cache import cache
from django.test import TestCase as TestCaseDjango


class TestCase(TestCaseDjango):
    """Chaque test repart avec des compteurs anti-abus vides."""

    def run(self, result=None):
        cache.clear()
        return super().run(result)
