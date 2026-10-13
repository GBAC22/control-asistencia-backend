from getpass import getpass

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from asistencia.models import UsuarioAdmin


class Command(BaseCommand):
    help = "Create the initial administrator, or leave an existing account unchanged."

    def add_arguments(self, parser):
        parser.add_argument("--nombre", required=True)
        parser.add_argument("--correo", required=True)

    def handle(self, *args, **options):
        name = options["nombre"].strip()
        email = options["correo"].strip()
        if not name or not email:
            raise CommandError("Nombre y correo son obligatorios.")

        existing = UsuarioAdmin.objects.filter(correo__iexact=email).first()
        if existing:
            self.stdout.write(
                self.style.WARNING(
                    f"El administrador {existing.correo} ya existe; no se realizaron cambios."
                )
            )
            return

        password = getpass("Contraseña del administrador: ")
        confirmation = getpass("Confirme la contraseña: ")
        if len(password) < 12:
            raise CommandError("La contraseña debe tener al menos 12 caracteres.")
        if password != confirmation:
            raise CommandError("Las contraseñas no coinciden.")

        admin = UsuarioAdmin.objects.create(
            nombre=name,
            correo=email,
            password_hash=make_password(password),
        )
        self.stdout.write(
            self.style.SUCCESS(f"Administrador creado (ID: {admin.id_admin}).")
        )
