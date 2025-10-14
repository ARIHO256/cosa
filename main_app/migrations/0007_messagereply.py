from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("main_app", "0006_alter_alumni_options_alter_degree_options"),
    ]

    operations = [
        migrations.CreateModel(
            name="MessageReply",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sender_type", models.CharField(choices=[("alumni", "Alumni"), ("admin", "Admin"), ("coordinator", "Coordinator")], max_length=20)),
                ("content", models.TextField()),
                ("attachment", models.FileField(blank=True, null=True, upload_to="message_attachments/replies/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="replies", to="main_app.message")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="children", to="main_app.messagereply")),
                ("sender_admin", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="message_replies", to="main_app.admin")),
                ("sender_alumni", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="message_replies", to="main_app.alumni")),
                ("sender_coordinator", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="message_replies", to="main_app.alumnicoordinator")),
            ],
            options={
                "ordering": ["created_at"],
                "verbose_name": "Message Reply",
                "verbose_name_plural": "Message Replies",
            },
        ),
    ]
