from django.db import migrations, models
import estate_app.email_drafts.validation


def seed_templates(apps,schema_editor):
    Template=apps.get_model('estate_app','EmailTemplate')
    closing='\n\nAmounts reflect payments recorded in BillTrack when this draft was prepared. If already paid, please share the payment reference so the records can be checked.\n\n{signing_authority}\n{organisation_name}'
    for name,subject,intro in [
        ('Invoice covering letter','Invoice details for {allottee_name}','Please find the following invoice details. Attach the relevant invoices before sending.'),
        ('Payment reminder','Payment reminder for {allottee_name}','Please review the following outstanding bill details and arrange payment where due.'),
        ('Overdue notice','Outstanding payment follow-up for {allottee_name}','Please review the bill details below. Payment is requested for amounts that have passed their confirmed due date.')]:
        Template.objects.create(name=name,subject=subject,body='Dear {allottee_name},\n\n'+intro+'\n\nPrepared: {preparation_date}\n\n{bill_details}\n\nTotal outstanding for selected bills: {outstanding_total}'+closing)

class Migration(migrations.Migration):
    dependencies = [('estate_app', '0001_initial')]
    operations = [
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('subject', models.CharField(help_text=estate_app.email_drafts.validation.HELP, max_length=240, validators=[estate_app.email_drafts.validation.validate_header, estate_app.email_drafts.validation.validate_template])),
                ('body', models.TextField(help_text=estate_app.email_drafts.validation.HELP, max_length=30000, validators=[estate_app.email_drafts.validation.validate_template])),
                ('active', models.BooleanField(default=True)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.AddField(
            model_name='systemsettings', name='email_draft_cc',
            field=models.CharField(blank=True, default='', help_text='Default email draft CC addresses, separated by commas or semicolons.', max_length=2000, validators=[estate_app.email_drafts.validation.validate_recipients]),
        ),
        migrations.RunPython(seed_templates, migrations.RunPython.noop),
    ]
