from django.db import migrations, models


def remplir_numeros(apps, schema_editor):
    """Les anciennes commandes étaient toutes au Togo : on calcule leur numéro international."""
    Commande = apps.get_model("boutique", "Commande")
    for c in Commande.objects.all():
        chiffres = "".join(ch for ch in c.telephone if ch.isdigit())
        if chiffres.startswith("00"):
            chiffres = chiffres[2:]
        if len(chiffres) == 8:
            chiffres = "228" + chiffres
        c.telephone_international = chiffres
        c.save(update_fields=["telephone_international"])


class Migration(migrations.Migration):
    dependencies = [("boutique", "0003_commande_jeton")]

    operations = [
        migrations.AddField(
            model_name="commande",
            name="telephone_international",
            field=models.CharField(blank=True, max_length=20, verbose_name="téléphone international"),
        ),
        migrations.AddField(
            model_name="commande",
            name="pays",
            field=models.CharField(default="TG", max_length=2, verbose_name="pays de livraison"),
        ),
        migrations.RunPython(remplir_numeros, migrations.RunPython.noop),
    ]
