# Generated by Django 4.0.5 on 2022-06-12 10:01

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ticketcontrol', '0017_alter_ticket_options_alter_ticket_moderators_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='category',
            name='color',
        ),
    ]