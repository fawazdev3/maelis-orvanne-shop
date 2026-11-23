from django.db import migrations


def creer_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nom in ["Administrateur", "Comptabilité"]:
        Group.objects.get_or_create(name=nom)


class Migration(migrations.Migration):
    dependencies = [("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(creer_roles, migrations.RunPython.noop)]
