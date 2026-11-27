from django.db import migrations, models

from estate_app.activity.database import install, uninstall


class Migration(migrations.Migration):
    dependencies = [('estate_app', '0027_renewal_deposit_carry_forward')]

    operations = [
        migrations.RunPython(uninstall, install),
        migrations.AddField(model_name='allotment', name='security_timing', field=models.CharField(
            blank=True, default='', max_length=6, choices=[('before', 'Before allotment order'), ('after', 'After allotment order')])),
        migrations.AddField(model_name='allotment', name='security_offer_date', field=models.DateField(blank=True, null=True)),
        migrations.RunPython(install, uninstall),
    ]
