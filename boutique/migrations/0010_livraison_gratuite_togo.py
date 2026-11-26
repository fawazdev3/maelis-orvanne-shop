from django.db import migrations


def horaires_par_defaut(apps, schema_editor):
    HoraireJour = apps.get_model("boutique", "HoraireJour")
    for jour in range(7):
        HoraireJour.objects.get_or_create(
            jour=jour, defaults={"ouvert": jour != 6, "ouverture": "08:00", "fermeture": "19:00"}
        )


def livraison_gratuite_togo(apps, schema_editor):
    TarifLivraison = apps.get_model("boutique", "TarifLivraison")
    TarifLivraison.objects.filter(pays="TG").update(frais=0)
    if not TarifLivraison.objects.filter(pays="TG", ville_normalisee="").exists():
        TarifLivraison.objects.create(pays="TG", ville="", ville_normalisee="", frais=0)


class Migration(migrations.Migration):
    dependencies = [("boutique", "0009_horaires_ouverture")]

    operations = [
        migrations.RunPython(horaires_par_defaut, migrations.RunPython.noop),
        migrations.RunPython(livraison_gratuite_togo, migrations.RunPython.noop),
    ]
