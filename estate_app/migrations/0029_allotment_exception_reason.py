from django.db import migrations, models

from estate_app.activity.database import install, uninstall


class Migration(migrations.Migration):
    dependencies = [('estate_app', '0028_security_deposit_timing')]

    operations = [
        migrations.RunPython(uninstall, install),
        migrations.AddField(model_name='allotment', name='exception_reason', field=models.TextField(blank=True, max_length=2000)),
        migrations.RunPython(install, uninstall),
    ]
