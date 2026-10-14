from __future__ import annotations

import json
import logging
from datetime import date
from uuid import UUID

from django.core.paginator import EmptyPage, Paginator
from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from asistencia.business import services
from asistencia.data_access import repositories
from asistencia.models import Asistencia

logger = logging.getLogger(__name__)


def _json_body(request: HttpRequest) -> dict:
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise services.ServiceError("El cuerpo debe ser JSON válido.") from None
    if not isinstance(payload, dict):
        raise services.ServiceError("El cuerpo JSON debe ser un objeto.")
    return payload


def _uuid(value: str, label: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(value)
    except (TypeError, ValueError, AttributeError):
        raise services.ServiceError(f"El identificador de {label} no es válido.") from None


def _service_error(error: services.ServiceError) -> JsonResponse:
    return JsonResponse({"error": error.message}, status=error.status_code)


def _admin_from_session(request: HttpRequest):
    if request.session.get("actor_type") != "ADMIN":
        raise services.ServiceError("Se requiere una sesión de administrador.", 401)
    admin_id = _uuid(request.session.get("actor_id"), "administrador")
    admin = repositories.get_admin(admin_id)
    if admin is None:
        request.session.flush()
        raise services.ServiceError("La sesión ya no es válida.", 401)
    return admin


def _student_from_session(request: HttpRequest):
    if request.session.get("actor_type") != "ESTUDIANTE":
        raise services.ServiceError("Se requiere una sesión de estudiante.", 401)
    student_id = _uuid(request.session.get("actor_id"), "estudiante")
    student = repositories.get_student(student_id)
    if student is None or not student.modulo.es_activo:
        request.session.flush()
        raise services.ServiceError("La sesión ya no pertenece al módulo activo.", 401)
    return student


def _admin_required(view):
    def wrapped(request: HttpRequest, *args, **kwargs):
        try:
            request.admin_actor = _admin_from_session(request)
            return view(request, *args, **kwargs)
        except services.ServiceError as error:
            return _service_error(error)

    return wrapped


def _student_required(view):
    def wrapped(request: HttpRequest, *args, **kwargs):
        try:
            request.student_actor = _student_from_session(request)
            return view(request, *args, **kwargs)
        except services.ServiceError as error:
            return _service_error(error)

    return wrapped


def _module_payload(module) -> dict:
    return {
        "id_modulo": str(module.id_modulo),
        "nombre": module.nombre,
        "fecha_inicio": module.fecha_inicio.isoformat(),
        "fecha_fin": module.fecha_fin.isoformat(),
        "es_activo": module.es_activo,
        "creado_en": module.creado_en.isoformat() if module.creado_en else None,
    }


def _class_payload(class_session) -> dict:
    return {
        "id_fecha_clase": str(class_session.id_fecha_clase),
        "id_modulo": str(class_session.modulo_id),
        "fecha": class_session.fecha.isoformat(),
        "hora_inicio": class_session.hora_inicio.isoformat(),
        "hora_fin": class_session.hora_fin.isoformat(),
        "es_cancelada": class_session.es_cancelada,
        "motivo_cancelacion": class_session.motivo_cancelacion,
    }


@require_GET
@ensure_csrf_cookie
def csrf_token(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"detail": "CSRF cookie initialized."})


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        logger.exception("Database health check failed.")
        return JsonResponse({"status": "unavailable", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})


@require_POST
def student_login(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
        password = str(payload.get("password", "") or payload.get("contrasena", ""))
        student = services.authenticate_student(
            str(payload.get("numero_registro", "")),
            password,
        )
    except services.ServiceError as error:
        return _service_error(error)
    request.session.cycle_key()
    request.session["actor_type"] = "ESTUDIANTE"
    request.session["actor_id"] = str(student.id_estudiante)
    return JsonResponse(
        {
            "actor": "ESTUDIANTE",
            "id_estudiante": str(student.id_estudiante),
            "numero_registro": student.numero_registro,
            "nombre_completo": student.nombre_completo,
            "modulo": student.modulo.nombre,
        }
    )


@require_POST
def admin_login(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
        admin = services.authenticate_admin(
            str(payload.get("correo", "")), str(payload.get("password", ""))
        )
    except services.ServiceError as error:
        return _service_error(error)
    request.session.cycle_key()
    request.session["actor_type"] = "ADMIN"
    request.session["actor_id"] = str(admin.id_admin)
    return JsonResponse(
        {
            "actor": "ADMIN",
            "id_admin": str(admin.id_admin),
            "nombre": admin.nombre,
            "correo": admin.correo,
        }
    )


@require_POST
def logout(request: HttpRequest) -> JsonResponse:
    request.session.flush()
    return JsonResponse({"detail": "Sesión cerrada."})


@require_GET
def current_actor(request: HttpRequest) -> JsonResponse:
    actor_type = request.session.get("actor_type")
    try:
        if actor_type == "ADMIN":
            admin = _admin_from_session(request)
            return JsonResponse(
                {
                    "actor": "ADMIN",
                    "id_admin": str(admin.id_admin),
                    "nombre": admin.nombre,
                    "correo": admin.correo,
                }
            )
        if actor_type == "ESTUDIANTE":
            student = _student_from_session(request)
            return JsonResponse(
                {
                    "actor": "ESTUDIANTE",
                    "id_estudiante": str(student.id_estudiante),
                    "numero_registro": student.numero_registro,
                    "nombre_completo": student.nombre_completo,
                    "modulo": student.modulo.nombre,
                }
            )
    except services.ServiceError as error:
        return _service_error(error)
    return JsonResponse({"error": "No hay una sesión activa."}, status=401)


@require_GET
@_student_required
def student_attendance(request: HttpRequest) -> JsonResponse:
    try:
        return JsonResponse(
            services.get_today_attendance(request.student_actor.id_estudiante)
        )
    except services.ServiceError as error:
        return _service_error(error)


@require_GET
@_student_required
def student_schedule(request: HttpRequest) -> JsonResponse:
    try:
        return JsonResponse(
            {"results": services.get_student_schedule(request.student_actor.id_estudiante)}
        )
    except services.ServiceError as error:
        return _service_error(error)


@require_POST
@_student_required
def mark_attendance(request: HttpRequest) -> JsonResponse:
    try:
        attendance = services.record_student_attendance(
            request.student_actor.id_estudiante
        )
    except services.ServiceError as error:
        return _service_error(error)
    return JsonResponse(
        {
            "id_asistencia": str(attendance.id_asistencia),
            "estado": attendance.estado,
            "fecha_hora_marcado": (
                attendance.fecha_hora_marcado.isoformat()
                if attendance.fecha_hora_marcado
                else None
            ),
        },
        status=201,
    )


@require_POST
@_student_required
def student_change_password(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
        services.change_student_password(
            request.student_actor.id_estudiante,
            str(payload.get("current_password", "") or payload.get("password_actual", "")),
            str(payload.get("new_password", "") or payload.get("nueva_password", "")),
        )
    except services.ServiceError as error:
        return _service_error(error)
    return JsonResponse({"detail": "Contraseña actualizada correctamente."})


@require_GET
@_admin_required
def admin_modules(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"results": [_module_payload(m) for m in repositories.get_modules()]})


@require_GET
@_admin_required
def admin_module_classes(request: HttpRequest, module_id: str) -> JsonResponse:
    try:
        parsed_module_id = _uuid(module_id, "módulo")
    except services.ServiceError as error:
        return _service_error(error)
    if repositories.get_module(parsed_module_id) is None:
        return _service_error(services.ServiceError("No se encontró el módulo.", 404))
    return JsonResponse(
        {
            "results": [
                _class_payload(class_session)
                for class_session in repositories.get_classes_for_module(
                    parsed_module_id
                )
            ]
        }
    )


@require_POST
@_admin_required
def cancel_admin_class(request: HttpRequest, class_id: str) -> JsonResponse:
    try:
        payload = _json_body(request)
        class_session = services.set_class_cancellation(
            _uuid(class_id, "fecha de clase"),
            request.admin_actor,
            cancelled=True,
            reason=str(payload.get("motivo", "")),
        )
    except services.ServiceError as error:
        return _service_error(error)
    return JsonResponse(_class_payload(class_session))


@require_POST
@_admin_required
def restore_admin_class(request: HttpRequest, class_id: str) -> JsonResponse:
    try:
        class_session = services.set_class_cancellation(
            _uuid(class_id, "fecha de clase"),
            request.admin_actor,
            cancelled=False,
        )
    except services.ServiceError as error:
        return _service_error(error)
    return JsonResponse(_class_payload(class_session))


@require_POST
@_admin_required
def create_admin_module(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
        module = services.create_module(
            str(payload.get("nombre", "")),
            payload.get("fecha_inicio"),
            payload.get("fecha_fin"),
        )
    except services.ServiceError as error:
        return _service_error(error)
    return JsonResponse(_module_payload(module), status=201)


@require_POST
@_admin_required
def activate_module(request: HttpRequest, module_id: str) -> JsonResponse:
    try:
        payload = _json_body(request)
        if payload.get("confirmar") is not True:
            raise services.ServiceError("La activación requiere confirmación explícita.")
        module = services.activate_module(
            _uuid(module_id, "módulo"), request.admin_actor
        )
    except services.ServiceError as error:
        return _service_error(error)
    return JsonResponse(_module_payload(module))


@require_POST
@_admin_required
def import_module(request: HttpRequest, module_id: str) -> JsonResponse:
    uploaded_file = request.FILES.get("archivo")
    if uploaded_file is None:
        return JsonResponse({"error": "Debe adjuntar el archivo en el campo 'archivo'."}, status=400)
    if not uploaded_file.name.lower().endswith(".xlsx"):
        return JsonResponse({"error": "Solo se aceptan archivos .xlsx."}, status=400)
    try:
        counts = services.import_module_workbook(
            _uuid(module_id, "módulo"),
            uploaded_file.read(10 * 1024 * 1024 + 1),
            request.admin_actor,
        )
    except services.ServiceError as error:
        return _service_error(error)
    return JsonResponse({"importados": counts}, status=201)


@require_GET
@_admin_required
def admin_attendance_report(request: HttpRequest) -> JsonResponse:
    date_text = request.GET.get("fecha", "")
    module_text = request.GET.get("id_modulo", "")
    try:
        try:
            report_date = date.fromisoformat(date_text)
        except (TypeError, ValueError):
            raise services.ServiceError("El parámetro fecha debe usar YYYY-MM-DD.") from None
        module = (
            repositories.get_active_module()
            if not module_text
            else repositories.get_module(_uuid(module_text, "módulo"))
        )
        if module is None:
            raise services.ServiceError("No se encontró el módulo solicitado.", 404)
        rows = services.attendance_report(
            report_date, module.id_modulo, request.GET.get("estudiante", "").strip()
        )
    except services.ServiceError as error:
        return _service_error(error)

    paginator = Paginator(rows, 100)
    try:
        page = paginator.page(request.GET.get("pagina", "1"))
    except (EmptyPage, ValueError):
        page = paginator.page(paginator.num_pages or 1)
    return JsonResponse(
        {
            "fecha": report_date.isoformat(),
            "total": paginator.count,
            "pagina": page.number,
            "paginas": paginator.num_pages,
            "results": page.object_list,
        }
    )


@require_http_methods(["PUT", "PATCH"])
@_admin_required
def update_admin_attendance(request: HttpRequest) -> JsonResponse:
    try:
        payload = _json_body(request)
        attendance = services.update_admin_attendance(
            request.admin_actor,
            _uuid(payload.get("id_fecha_clase"), "fecha de clase"),
            _uuid(payload.get("id_estudiante"), "estudiante"),
            str(payload.get("estado", "")),
        )
    except services.ServiceError as error:
        return _service_error(error)
    return JsonResponse(
        {
            "id_asistencia": str(attendance.id_asistencia),
            "id_estudiante": str(attendance.estudiante_id),
            "id_fecha_clase": str(attendance.fecha_clase_id),
            "estado": attendance.estado,
            "fecha_hora_marcado": (
                attendance.fecha_hora_marcado.isoformat()
                if attendance.fecha_hora_marcado
                else None
            ),
        }
    )


@require_GET
@_admin_required
def admin_audit_log(request: HttpRequest) -> JsonResponse:
    module_id = request.GET.get("id_modulo")
    date_text = request.GET.get("fecha")
    role_filter = request.GET.get("rol")
    try:
        parsed_module_id = _uuid(module_id, "módulo") if module_id else None
        parsed_date = date.fromisoformat(date_text) if date_text else None
    except (TypeError, ValueError):
        return JsonResponse({"error": "El parámetro fecha debe usar YYYY-MM-DD."}, status=400)
    except services.ServiceError as error:
        return _service_error(error)

    logs = repositories.get_audit_logs(parsed_module_id, parsed_date)
    if role_filter and role_filter.upper() in ("ADMIN", "ESTUDIANTE"):
        logs = logs.filter(rol_actor=role_filter.upper())
    paginator = Paginator(logs, 50)
    try:
        page = paginator.page(request.GET.get("pagina", "1"))
    except (EmptyPage, ValueError):
        page = paginator.page(paginator.num_pages or 1)
    results = [
        {
            "id_auditoria": str(item.id_auditoria),
            "id_modulo": str(item.modulo_id),
            "nombre_modulo": item.modulo.nombre if item.modulo else "",
            "usuario_actor": item.usuario_actor,
            "rol_actor": item.rol_actor,
            "accion": item.accion,
            "entidad_afectada": item.entidad_afectada,
            "valor_anterior": item.valor_anterior,
            "valor_nuevo": item.valor_nuevo,
            "fecha_hora": item.fecha_hora.isoformat() if item.fecha_hora else None,
        }
        for item in page.object_list
    ]
    return JsonResponse(
        {
            "total": paginator.count,
            "pagina": page.number,
            "paginas": paginator.num_pages,
            "results": results,
        }
    )
