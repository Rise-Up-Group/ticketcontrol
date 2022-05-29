# Generated by Django 4.0.4 on 2022-05-16 12:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ticketcontrol', '0013_ticket_hidden'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='ticket',
            options={'permissions': (('hide_ticket', 'Hide the Ticket to everyone (shown as delete in the ui)'), ('unhide_ticket', 'Recover the Ticket (shown as recover ticket in the ui)'))},
        ),
        migrations.AddField(
            model_name='ticket',
            name='location',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]