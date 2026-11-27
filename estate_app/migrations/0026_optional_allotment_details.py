from django.db import migrations, models

from estate_app.activity.database import install, uninstall


class Migration(migrations.Migration):
    dependencies = [('estate_app', '0025_demand_of_dues_template')]

    operations = [
        migrations.RunPython(uninstall, install),
        migrations.AddField(
            model_name='systemsettings', name='allotment_details_enabled',
            field=models.BooleanField(default=False, verbose_name='Show additional allotment details',
                help_text='Show notice, measurement, charge approval and possession or handover fields on allotment forms.'),
        ),
        migrations.AlterField(
            model_name='rentrevision', name='approval_reference',
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.RunPython(install, uninstall),
    ]
