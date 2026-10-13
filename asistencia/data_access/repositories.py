from datetime import date
from uuid import UUID

from django.db.models import Q

from asistencia.models import (
    Asistencia,
    AuditoriaActividad,
    Estudiante,
    FechaClase,
    ModuloAcademico,
    UsuarioAdmin,
)


def get_active_module() -> ModuloAcademico | None:
    return ModuloAcademico.objects.filter(es_activo=True).first()


def get_student_by_registration(
    registration_number: str, module_id: UUID
) -> Estudiante | None:
    return (
        Estudiante.objects.select_related("modulo")
        .filter(numero_registro=registration_number, modulo_id=module_id)
        .first()
    )


def get_student(student_id: UUID) -> Estudiante | None:
    return Estudiante.objects.select_related("modulo").filter(pk=student_id).first()


def get_admin(admin_id: UUID) -> UsuarioAdmin | None:
    return UsuarioAdmin.objects.filter(pk=admin_id).first()


def get_admin_by_email(email: str) -> UsuarioAdmin | None:
    return UsuarioAdmin.objects.filter(correo__iexact=email).first()


def get_class_by_id(class_id: UUID) -> FechaClase | None:
    return FechaClase.objects.select_related("modulo").filter(pk=class_id).first()


def get_class_on_date(
    module_id: UUID, class_date: date, *, lock: bool = False
) -> FechaClase | None:
    sessions = FechaClase.objects.filter(modulo_id=module_id, fecha=class_date)
    if lock:
        sessions = sessions.select_for_update()
    return sessions.order_by("hora_inicio").first()


def get_class_by_id_for_update(class_id: UUID) -> FechaClase | None:
    return (
        FechaClase.objects.select_for_update()
        .select_related("modulo")
        .filter(pk=class_id)
        .first()
    )


def get_classes_for_module(module_id: UUID):
    return FechaClase.objects.filter(modulo_id=module_id).order_by(
        "fecha", "hora_inicio"
    )


def get_upcoming_classes(module_id: UUID, from_date: date):
    return FechaClase.objects.filter(
        modulo_id=module_id, fecha__gte=from_date
    ).order_by("fecha", "hora_inicio")


def class_attendance_count(class_id: UUID) -> int:
    return Asistencia.objects.filter(fecha_clase_id=class_id).count()


def save_class_fields(class_session: FechaClase, *fields: str) -> None:
    class_session.save(update_fields=list(fields))


def get_attendance(student_id: UUID, class_id: UUID) -> Asistencia | None:
    return Asistencia.objects.filter(
        estudiante_id=student_id, fecha_clase_id=class_id
    ).first()


def get_attendance_for_day(student_id: UUID, class_date: date) -> Asistencia | None:
    return (
        Asistencia.objects.select_related("fecha_clase")
        .filter(estudiante_id=student_id, fecha_clase__fecha=class_date)
        .first()
    )


def create_attendance(**values) -> Asistencia:
    return Asistencia.objects.create(**values)


def new_attendance(**values) -> Asistencia:
    return Asistencia(**values)


def save_attendance(attendance: Asistencia) -> Asistencia:
    attendance.save()
    return attendance


def get_module(module_id: UUID) -> ModuloAcademico | None:
    return ModuloAcademico.objects.filter(pk=module_id).first()


def get_module_for_update(module_id: UUID) -> ModuloAcademico | None:
    return ModuloAcademico.objects.select_for_update().filter(pk=module_id).first()


def lock_modules_for_update() -> list[ModuloAcademico]:
    return list(ModuloAcademico.objects.select_for_update().order_by("id_modulo"))


def create_module(**values) -> ModuloAcademico:
    return ModuloAcademico.objects.create(**values)


def deactivate_other_modules(active_module_id: UUID) -> None:
    ModuloAcademico.objects.filter(es_activo=True).exclude(
        pk=active_module_id
    ).update(es_activo=False)


def save_module_fields(module: ModuloAcademico, *fields: str) -> None:
    module.save(update_fields=list(fields))


def module_import_counts(module_id: UUID) -> tuple[int, int]:
    return (
        Estudiante.objects.filter(modulo_id=module_id).count(),
        FechaClase.objects.filter(modulo_id=module_id).count(),
    )


def get_modules():
    return ModuloAcademico.objects.order_by("-fecha_inicio", "nombre")


def get_students_for_module(module_id: UUID):
    return Estudiante.objects.filter(modulo_id=module_id).order_by(
        "numero_registro", "nombre_completo"
    )


def get_students_for_report(module_id: UUID, search: str = ""):
    students = get_students_for_module(module_id)
    if search:
        students = students.filter(
            Q(numero_registro__icontains=search)
            | Q(nombre_completo__icontains=search)
            | Q(correo_electronico__icontains=search)
        )
    return students


def get_existing_registrations(module_id: UUID, registrations: list[str]) -> set[str]:
    return set(
        Estudiante.objects.filter(
            modulo_id=module_id, numero_registro__in=registrations
        ).values_list("numero_registro", flat=True)
    )


def bulk_create_students(module_id: UUID, rows: list[dict]) -> None:
    Estudiante.objects.bulk_create(
        [Estudiante(modulo_id=module_id, **row) for row in rows]
    )


def bulk_create_class_dates(module_id: UUID, rows: list[dict]) -> None:
    FechaClase.objects.bulk_create(
        [FechaClase(modulo_id=module_id, **row) for row in rows]
    )


def get_class_sessions(module_id: UUID, class_date: date):
    return FechaClase.objects.filter(
        modulo_id=module_id, fecha=class_date
    ).select_related("modulo").order_by("hora_inicio")


def get_attendance_for_class(class_id: UUID):
    return Asistencia.objects.filter(fecha_clase_id=class_id).select_related(
        "estudiante", "fecha_clase"
    )


def get_audit_logs(module_id: UUID | None = None, class_date: date | None = None):
    logs = AuditoriaActividad.objects.select_related("modulo").order_by(
        "-fecha_hora", "-id_auditoria"
    )
    if module_id:
        logs = logs.filter(modulo_id=module_id)
    if class_date:
        logs = logs.filter(fecha_hora__date=class_date)
    return logs


def create_audit(**values) -> AuditoriaActividad:
    return AuditoriaActividad.objects.create(**values)
