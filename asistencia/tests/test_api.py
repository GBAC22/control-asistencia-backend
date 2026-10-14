from datetime import date, time, timedelta
from io import BytesIO, StringIO
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from openpyxl import Workbook

from asistencia.models import (
    Asistencia,
    AuditoriaActividad,
    Estudiante,
    FechaClase,
    ModuloAcademico,
    UsuarioAdmin,
)


class AttendanceApiTests(TestCase):
    def setUp(self):
        today = timezone.localdate()
        self.module = ModuloAcademico.objects.create(
            nombre="Módulo de pruebas",
            fecha_inicio=today - timedelta(days=2),
            fecha_fin=today + timedelta(days=30),
            es_activo=True,
        )
        self.student = Estudiante.objects.create(
            modulo=self.module,
            numero_registro="REG-001",
            nombre_completo="Estudiante de Prueba",
            correo_electronico="student@example.test",
        )
        self.class_session = FechaClase.objects.create(
            modulo=self.module,
            fecha=today,
            hora_inicio=time(8, 0),
            hora_fin=time(10, 0),
        )
        self.admin = UsuarioAdmin.objects.create(
            nombre="Admin de Prueba",
            correo="admin@example.test",
            password_hash=make_password("a-secure-test-password"),
        )

    @patch(
        "asistencia.management.commands.seed_admin.getpass",
        side_effect=["another-secure-password", "another-secure-password"],
    )
    def test_seed_admin_creates_account_with_hashed_password(self, _getpass):
        call_command(
            "seed_admin",
            nombre="Inicial",
            correo="initial-admin@example.test",
            stdout=StringIO(),
        )
        admin = UsuarioAdmin.objects.get(correo="initial-admin@example.test")
        self.assertNotEqual(admin.password_hash, "another-secure-password")
        self.assertTrue(check_password("another-secure-password", admin.password_hash))

    @patch(
        "asistencia.management.commands.seed_admin.getpass",
        side_effect=AssertionError("Existing admin password must not be prompted."),
    )
    def test_seed_admin_is_idempotent_and_preserves_existing_account(self, _getpass):
        original_hash = self.admin.password_hash
        call_command(
            "seed_admin",
            nombre="Replacement",
            correo=self.admin.correo.upper(),
            stdout=StringIO(),
        )
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.nombre, "Admin de Prueba")
        self.assertEqual(self.admin.password_hash, original_hash)

    @patch(
        "asistencia.management.commands.reset_admin_password.getpass",
        side_effect=["a-new-secure-password", "a-new-secure-password"],
    )
    def test_reset_admin_password_changes_only_password_hash(self, _getpass):
        original_name = self.admin.nombre
        original_email = self.admin.correo
        call_command(
            "reset_admin_password",
            correo=self.admin.correo.upper(),
            stdout=StringIO(),
        )
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.nombre, original_name)
        self.assertEqual(self.admin.correo, original_email)
        self.assertTrue(check_password("a-new-secure-password", self.admin.password_hash))
        self.assertFalse(check_password("a-secure-test-password", self.admin.password_hash))

    def _csrf_headers(self):
        self.client.get("/api/auth/csrf")
        return {"HTTP_X_CSRFTOKEN": self.client.cookies["csrftoken"].value}

    def _admin_login(self):
        response = self.client.post(
            "/api/auth/login/admin",
            data={
                "correo": self.admin.correo,
                "password": "a-secure-test-password",
            },
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 200, response.content)

    def _student_login(self):
        response = self.client.post(
            "/api/auth/login/student",
            data={
                "numero_registro": self.student.numero_registro,
                "password": self.student.numero_registro,
            },
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_student_login_marks_once_and_creates_audit(self):
        self._student_login()

        response = self.client.post(
            "/api/student/attendance/mark",
            data={},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Asistencia.objects.count(), 1)
        self.assertEqual(
            AuditoriaActividad.objects.filter(accion="MARCAR_ASISTENCIA").count(), 1
        )

        duplicate = self.client.post(
            "/api/student/attendance/mark",
            data={},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_admin_can_filter_and_update_attendance_with_audit(self):
        self._admin_login()
        report = self.client.get(
            f"/api/admin/attendance?fecha={timezone.localdate().isoformat()}"
        )
        self.assertEqual(report.status_code, 200, report.content)
        row = report.json()["results"][0]
        self.assertEqual(row["numero_registro"], self.student.numero_registro)
        self.assertEqual(row["estado"], "PENDIENTE")

        response = self.client.put(
            "/api/admin/attendance/update",
            data={
                "id_fecha_clase": str(self.class_session.id_fecha_clase),
                "id_estudiante": str(self.student.id_estudiante),
                "estado": "FALTA",
            },
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["estado"], "FALTA")
        audit = AuditoriaActividad.objects.get(accion="MODIFICAR_ASISTENCIA")
        self.assertEqual(audit.rol_actor, AuditoriaActividad.RolActor.ADMIN)
        self.assertEqual(audit.valor_nuevo["estado"], "FALTA")

    def test_admin_can_select_a_historical_module_in_attendance_report(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        historical_module = ModuloAcademico.objects.create(
            nombre="Módulo histórico",
            fecha_inicio=yesterday - timedelta(days=3),
            fecha_fin=yesterday,
            es_activo=False,
        )
        historical_student = Estudiante.objects.create(
            modulo=historical_module,
            numero_registro="REG-HIST",
            nombre_completo="Estudiante histórico",
        )
        FechaClase.objects.create(
            modulo=historical_module,
            fecha=yesterday,
            hora_inicio=time(8, 0),
            hora_fin=time(10, 0),
        )
        self._admin_login()

        response = self.client.get(
            "/api/admin/attendance",
            {
                "fecha": yesterday.isoformat(),
                "id_modulo": str(historical_module.id_modulo),
            },
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["results"][0]["id_estudiante"], str(historical_student.id_estudiante))
        self.assertEqual(response.json()["results"][0]["estado"], "FALTA")

    def test_module_activation_deactivates_previous_module(self):
        next_module = ModuloAcademico.objects.create(
            nombre="Siguiente",
            fecha_inicio=timezone.localdate(),
            fecha_fin=timezone.localdate() + timedelta(days=30),
            es_activo=False,
        )
        Estudiante.objects.create(
            modulo=next_module,
            numero_registro="REG-002",
            nombre_completo="Estudiante del siguiente módulo",
        )
        FechaClase.objects.create(
            modulo=next_module,
            fecha=timezone.localdate(),
            hora_inicio=time(11, 0),
            hora_fin=time(12, 0),
        )
        self._admin_login()
        response = self.client.post(
            f"/api/admin/modules/{next_module.id_modulo}/activate",
            data={"confirmar": True},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.module.refresh_from_db()
        next_module.refresh_from_db()
        self.assertFalse(self.module.es_activo)
        self.assertTrue(next_module.es_activo)

    def test_activation_requires_imported_students_and_class_dates(self):
        empty_module = ModuloAcademico.objects.create(
            nombre="Módulo vacío",
            fecha_inicio=timezone.localdate(),
            fecha_fin=timezone.localdate() + timedelta(days=30),
            es_activo=False,
        )
        self._admin_login()
        response = self.client.post(
            f"/api/admin/modules/{empty_module.id_modulo}/activate",
            data={"confirmar": True},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 409)
        self.module.refresh_from_db()
        self.assertTrue(self.module.es_activo)

    def test_attendance_is_limited_to_one_mark_per_calendar_day(self):
        FechaClase.objects.create(
            modulo=self.module,
            fecha=timezone.localdate(),
            hora_inicio=time(13, 0),
            hora_fin=time(14, 0),
        )
        self._student_login()
        response = self.client.post(
            "/api/student/attendance/mark",
            data={},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Asistencia.objects.filter(estudiante=self.student).count(), 1)

    def test_admin_can_cancel_class_with_reason_and_restore_it(self):
        self._admin_login()
        response = self.client.post(
            f"/api/admin/classes/{self.class_session.id_fecha_clase}/cancel",
            data={"motivo": "Lluvia intensa"},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.class_session.refresh_from_db()
        self.assertTrue(self.class_session.es_cancelada)
        self.assertEqual(self.class_session.motivo_cancelacion, "Lluvia intensa")
        audit = AuditoriaActividad.objects.get(accion="CANCELAR_CLASE")
        self.assertEqual(audit.valor_nuevo["motivo_cancelacion"], "Lluvia intensa")

        report = self.client.get(
            "/api/admin/attendance",
            {
                "fecha": timezone.localdate().isoformat(),
                "id_modulo": str(self.module.id_modulo),
            },
        )
        self.assertEqual(report.status_code, 200, report.content)
        self.assertEqual(report.json()["results"][0]["estado"], "CANCELADA")

        response = self.client.post(
            f"/api/admin/classes/{self.class_session.id_fecha_clase}/restore",
            data={},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.class_session.refresh_from_db()
        self.assertFalse(self.class_session.es_cancelada)
        self.assertIsNone(self.class_session.motivo_cancelacion)
        self.assertTrue(
            AuditoriaActividad.objects.filter(accion="RESTAURAR_CLASE").exists()
        )

    def test_student_cannot_mark_a_cancelled_class(self):
        self.class_session.es_cancelada = True
        self.class_session.motivo_cancelacion = "Lluvia"
        self.class_session.save(update_fields=["es_cancelada", "motivo_cancelacion"])
        self._student_login()

        today = self.client.get("/api/student/attendance")
        self.assertEqual(today.status_code, 200, today.content)
        self.assertFalse(today.json()["programada"])
        self.assertTrue(today.json()["cancelada"])
        self.assertEqual(today.json()["motivo_cancelacion"], "Lluvia")

        response = self.client.post(
            "/api/student/attendance/mark",
            data={},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Asistencia.objects.count(), 0)

    def test_student_can_see_upcoming_classes_but_cannot_mark_them_early(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.class_session.delete()
        future_class = FechaClase.objects.create(
            modulo=self.module,
            fecha=tomorrow,
            hora_inicio=time(19, 0),
            hora_fin=time(22, 0),
        )
        self._student_login()

        schedule = self.client.get("/api/student/schedule")
        self.assertEqual(schedule.status_code, 200, schedule.content)
        self.assertEqual(len(schedule.json()["results"]), 1)
        future_entry = next(
            item
            for item in schedule.json()["results"]
            if item["id_fecha_clase"] == str(future_class.id_fecha_clase)
        )
        self.assertFalse(future_entry["es_hoy"])
        self.assertFalse(future_entry["es_cancelada"])
        self.assertIsNone(future_entry["asistencia"])

        response = self.client.post(
            "/api/student/attendance/mark",
            data={},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Asistencia.objects.count(), 0)

    def test_student_schedule_includes_cancelled_upcoming_class_and_reason(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        cancelled_class = FechaClase.objects.create(
            modulo=self.module,
            fecha=tomorrow,
            hora_inicio=time(19, 0),
            hora_fin=time(22, 0),
            es_cancelada=True,
            motivo_cancelacion="Lluvia",
        )
        self._student_login()

        response = self.client.get("/api/student/schedule")

        self.assertEqual(response.status_code, 200, response.content)
        entry = next(
            item
            for item in response.json()["results"]
            if item["id_fecha_clase"] == str(cancelled_class.id_fecha_clase)
        )
        self.assertTrue(entry["es_cancelada"])
        self.assertEqual(entry["motivo_cancelacion"], "Lluvia")

    def test_cannot_cancel_class_after_attendance_has_been_recorded(self):
        Asistencia.objects.create(
            estudiante=self.student,
            fecha_clase=self.class_session,
            estado=Asistencia.Estado.PRESENTE,
            fecha_hora_marcado=timezone.now(),
        )
        self._admin_login()
        response = self.client.post(
            f"/api/admin/classes/{self.class_session.id_fecha_clase}/cancel",
            data={"motivo": "Lluvia"},
            content_type="application/json",
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 409)
        self.class_session.refresh_from_db()
        self.assertFalse(self.class_session.es_cancelada)

    def test_workbook_import_creates_students_classes_and_audit(self):
        module = ModuloAcademico.objects.create(
            nombre="Importación",
            fecha_inicio=timezone.localdate(),
            fecha_fin=timezone.localdate() + timedelta(days=7),
            es_activo=False,
        )
        workbook = Workbook()
        students = workbook.active
        students.title = "estudiantes"
        students.append(["numero_registro", "nombre_completo", "correo_electronico"])
        students.append(["REG-002", "Nueva Persona", "new@example.test"])
        classes = workbook.create_sheet("fechas_clase")
        classes.append(["fecha", "hora_inicio", "hora_fin"])
        classes.append([timezone.localdate(), time(9, 0), time(11, 0)])
        content = BytesIO()
        workbook.save(content)
        content.seek(0)

        self._admin_login()
        response = self.client.post(
            f"/api/admin/modules/{module.id_modulo}/import",
            data={
                "archivo": SimpleUploadedFile(
                    "modulo.xlsx",
                    content.read(),
                    content_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            },
            **self._csrf_headers(),
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["importados"], {"estudiantes": 1, "fechas_clase": 1})
        self.assertTrue(
            Estudiante.objects.filter(
                modulo=module, numero_registro="REG-002"
            ).exists()
        )
        self.assertTrue(
            AuditoriaActividad.objects.filter(
                modulo=module, accion="IMPORTAR_EXCEL"
            ).exists()
        )

    def test_health_endpoint_checks_database(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})
