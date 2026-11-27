from django.db import migrations, models

from estate_app.activity.database import install, uninstall
from estate_app.email_drafts.validation import validate_recipients


class Migration(migrations.Migration):
    dependencies = [('estate_app', '0024_email_draft_bcc')]

    operations = [
        migrations.RunPython(uninstall, install),
        migrations.AddField(
            model_name='emailtemplate', name='cc',
            field=models.CharField(blank=True, default='', max_length=2000, validators=[validate_recipients],
                                   help_text='Template CC addresses. Leave blank to use the System Settings defaults.'),
        ),
        migrations.AddField(
            model_name='emailtemplate', name='manual_only',
            field=models.BooleanField(default=False, help_text='Offer this template only in manual email drafts.'),
        ),
        migrations.RunPython(install, uninstall),
    ]
