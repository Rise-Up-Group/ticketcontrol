# Generated by Django 4.0.4 on 2022-04-29 10:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ticketcontrol', '0010_user_new_email'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Permission',
        ),
    ]
