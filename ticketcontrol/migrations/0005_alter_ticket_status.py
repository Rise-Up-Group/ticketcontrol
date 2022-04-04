# Generated by Django 4.0.3 on 2022-03-16 09:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ticketcontrol', '0004_comment_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='status',
            field=models.CharField(choices=[('Unassigned', 'Unassigned'), ('Assigned', 'Assigned'), ('Closed', 'Closed'), ('Open', 'Open'), ('Waiting', 'Waiting')], default='Unassigned', max_length=15),
        ),
    ]
