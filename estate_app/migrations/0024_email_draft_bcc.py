from django.db import migrations, models

from estate_app.activity.database import install, uninstall
from estate_app.email_drafts.validation import validate_recipients


class Migration(migrations.Migration):
    dependencies = [('estate_app', '0023_communication_feature_switches')]

    operations = [
        migrations.RunPython(uninstall, install),
        migrations.AddField(
            model_name='systemsettings',
            name='email_draft_bcc',
            field=models.CharField(blank=True, default='', max_length=2000, validators=[validate_recipients],
                                   verbose_name='Default email draft BCC',
                                   help_text='Separate addresses with commas or semicolons.'),
        ),
        migrations.RunPython(install, uninstall),
    ]
