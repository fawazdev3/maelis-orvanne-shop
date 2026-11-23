import uuid

from django.db import migrations, models


def remplir_jetons(apps, schema_editor):
    Commande = apps.get_model("boutique", "Commande")
    for commande in Commande.objects.all():
        commande.jeton = uuid.uuid4()
        commande.save(update_fields=["jeton"])


class Migration(migrations.Migration):
    dependencies = [
        ("boutique", "0002_paiement_a_la_livraison"),
    ]

    operations = [
        migrations.AddField(
            model_name="commande",
            name="jeton",
            field=models.UUIDField(editable=False, null=True, verbose_name="jeton"),
        ),
        migrations.RunPython(remplir_jetons, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="commande",
            name="jeton",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="jeton"),
        ),
    ]
