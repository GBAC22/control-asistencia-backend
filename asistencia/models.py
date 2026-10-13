import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


class ModuloAcademico(models.Model):
    id_modulo = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        db_default=models.Func(
            function="uuid_generate_v4", output_field=models.UUIDField()
        ),
        editable=False,
    )
    nombre = models.CharField(max_length=255)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    es_activo = models.BooleanField(
        default=False, db_default=False, null=True, blank=True
    )
    creado_en = models.DateTimeField(
        default=timezone.now,
        db_default=models.functions.Now(),
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "modulos_academicos"
        constraints = [
            models.UniqueConstraint(
                fields=["es_activo"],
                condition=Q(es_activo=True),
                name="unq_modulo_activo",
            ),
        ]


class UsuarioAdmin(models.Model):
    id_admin = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        db_default=models.Func(
            function="uuid_generate_v4", output_field=models.UUIDField()
        ),
        editable=False,
    )
    nombre = models.CharField(max_length=255)
    correo = models.CharField(max_length=255, unique=True)
    password_hash = models.CharField(max_length=255)
    creado_en = models.DateTimeField(
        default=timezone.now,
        db_default=models.functions.Now(),
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "usuarios_admin"


class Estudiante(models.Model):
    id_estudiante = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        db_default=models.Func(
            function="uuid_generate_v4", output_field=models.UUIDField()
        ),
        editable=False,
    )
    modulo = models.ForeignKey(
        ModuloAcademico,
        on_delete=models.DO_NOTHING,
        db_column="id_modulo",
        related_name="estudiantes",
    )
    numero_registro = models.CharField(max_length=50)
    nombre_completo = models.CharField(max_length=255)
    correo_electronico = models.CharField(max_length=255, null=True, blank=True)
    creado_en = models.DateTimeField(
        default=timezone.now,
        db_default=models.functions.Now(),
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "estudiantes"
        constraints = [
            models.UniqueConstraint(
                fields=["numero_registro", "modulo"],
                name="estudiantes_numero_registro_id_modulo_key",
            ),
        ]


class FechaClase(models.Model):
    id_fecha_clase = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        db_default=models.Func(
            function="uuid_generate_v4", output_field=models.UUIDField()
        ),
        editable=False,
    )
    modulo = models.ForeignKey(
        ModuloAcademico,
        on_delete=models.DO_NOTHING,
        db_column="id_modulo",
        related_name="fechas_clase",
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    es_cancelada = models.BooleanField(default=False)
    motivo_cancelacion = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "fechas_clase"


class Asistencia(models.Model):
    class Estado(models.TextChoices):
        PRESENTE = "PRESENTE", "Presente"
        FALTA = "FALTA", "Falta"

    id_asistencia = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        db_default=models.Func(
            function="uuid_generate_v4", output_field=models.UUIDField()
        ),
        editable=False,
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.DO_NOTHING,
        db_column="id_estudiante",
        related_name="asistencias",
    )
    fecha_clase = models.ForeignKey(
        FechaClase,
        on_delete=models.DO_NOTHING,
        db_column="id_fecha_clase",
        related_name="asistencias",
    )
    estado = models.CharField(
        max_length=20, choices=Estado.choices, null=True, blank=True
    )
    fecha_hora_marcado = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "asistencias"
        constraints = [
            models.CheckConstraint(
                condition=Q(estado__in=["PRESENTE", "FALTA"]),
                name="asistencias_estado_check",
            ),
            models.UniqueConstraint(
                fields=["estudiante", "fecha_clase"],
                name="asistencias_id_estudiante_id_fecha_clase_key",
            ),
        ]


class AuditoriaActividad(models.Model):
    class RolActor(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        ESTUDIANTE = "ESTUDIANTE", "Estudiante"

    id_auditoria = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        db_default=models.Func(
            function="uuid_generate_v4", output_field=models.UUIDField()
        ),
        editable=False,
    )
    modulo = models.ForeignKey(
        ModuloAcademico,
        on_delete=models.DO_NOTHING,
        db_column="id_modulo",
        related_name="auditorias",
    )
    usuario_actor = models.CharField(max_length=255)
    rol_actor = models.CharField(
        max_length=50, choices=RolActor.choices, null=True, blank=True
    )
    accion = models.CharField(max_length=255)
    entidad_afectada = models.CharField(max_length=255)
    valor_anterior = models.JSONField(null=True, blank=True)
    valor_nuevo = models.JSONField(null=True, blank=True)
    fecha_hora = models.DateTimeField(
        default=timezone.now,
        db_default=models.functions.Now(),
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "auditoria_actividades"
        constraints = [
            models.CheckConstraint(
                condition=Q(rol_actor__in=["ADMIN", "ESTUDIANTE"]),
                name="auditoria_actividades_rol_actor_check",
            ),
        ]
