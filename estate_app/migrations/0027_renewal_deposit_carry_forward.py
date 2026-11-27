from django.db import migrations, models

from estate_app.activity.database import install, uninstall


class Migration(migrations.Migration):
    dependencies = [('estate_app', '0026_optional_allotment_details')]

    operations = [
        migrations.RunPython(uninstall, install),
        migrations.AddField(
            model_name='allotment', name='carry_forward_deposit',
            field=models.BooleanField(default=False, verbose_name='Carry forward existing security deposit'),
        ),
        migrations.RunPython(install, uninstall),
    ]
