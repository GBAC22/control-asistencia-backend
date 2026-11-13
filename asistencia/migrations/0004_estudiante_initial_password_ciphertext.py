from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("asistencia", "0003_estudiante_password_hash"),
    ]

    operations = [
        migrations.AddField(
            model_name="estudiante",
            name="initial_password_ciphertext",
            field=models.TextField(blank=True, null=True),
        ),
    ]
