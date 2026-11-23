from django.contrib.auth.models import Group
from django.db import models


class AccesRole(models.Model):
    """Pages du back-office autorisées pour un rôle (un rôle = un groupe Django)."""

    role = models.OneToOneField(Group, on_delete=models.CASCADE, related_name="acces")
    sections = models.CharField("sections autorisées", max_length=255, blank=True)

    class Meta:
        verbose_name = "accès d'un rôle"
        verbose_name_plural = "accès des rôles"

    def __str__(self):
        return self.role.name

    @property
    def liste(self):
        return [s for s in self.sections.split(",") if s]
