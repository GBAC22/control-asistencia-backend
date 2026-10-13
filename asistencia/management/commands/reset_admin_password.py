from getpass import getpass

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from asistencia.models import UsuarioAdmin


class Command(BaseCommand):
    help = "Reset the password for an existing administrator account."

    def add_arguments(self, parser):
        parser.add_argument("--correo", required=True)

    def handle(self, *args, **options):
        email = options["correo"].strip()
        if not email:
            raise CommandError("El correo es obligatorio.")

        admin = UsuarioAdmin.objects.filter(correo__iexact=email).first()
        if admin is None:
            raise CommandError(
                "No existe un administrador con ese correo. Use el mismo correo "
                "registrado al crear la cuenta."
            )

        password = getpass("Nueva contraseña del administrador: ")
        confirmation = getpass("Confirme la nueva contraseña: ")
        if len(password) < 12:
            raise CommandError("La contraseña debe tener al menos 12 caracteres.")
        if password != confirmation:
            raise CommandError("Las contraseñas no coinciden.")

        admin.password_hash = make_password(password)
        admin.save(update_fields=["password_hash"])
        self.stdout.write(
            self.style.SUCCESS(f"Contraseña actualizada para {admin.correo}.")
        )
