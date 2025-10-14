from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main_app", "0007_messagereply"),
    ]

    operations = [
        migrations.AddField(
            model_name="feedbackalumni",
            name="rating",
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")], null=True),
        ),
    ]
