from django.test import SimpleTestCase

from asistencia.models import (
    Asistencia,
    AuditoriaActividad,
    Estudiante,
    FechaClase,
    ModuloAcademico,
    UsuarioAdmin,
)


class ModelSchemaTests(SimpleTestCase):
    def test_table_names_match_database_schema(self):
        expected_tables = {
            ModuloAcademico: "modulos_academicos",
            UsuarioAdmin: "usuarios_admin",
            Estudiante: "estudiantes",
            FechaClase: "fechas_clase",
            Asistencia: "asistencias",
            AuditoriaActividad: "auditoria_actividades",
        }

        for model, table_name in expected_tables.items():
            with self.subTest(model=model.__name__):
                self.assertEqual(model._meta.db_table, table_name)

    def test_foreign_keys_use_database_column_names(self):
        expected_columns = {
            Estudiante: {"modulo": "id_modulo"},
            FechaClase: {"modulo": "id_modulo"},
            Asistencia: {
                "estudiante": "id_estudiante",
                "fecha_clase": "id_fecha_clase",
            },
            AuditoriaActividad: {"modulo": "id_modulo"},
        }

        for model, columns in expected_columns.items():
            for field_name, column_name in columns.items():
                with self.subTest(model=model.__name__, field=field_name):
                    self.assertEqual(
                        model._meta.get_field(field_name).column, column_name
                    )

    def test_database_constraints_are_declared(self):
        expected_constraints = {
            ModuloAcademico: {"unq_modulo_activo"},
            Estudiante: {"estudiantes_numero_registro_id_modulo_key"},
            Asistencia: {
                "asistencias_estado_check",
                "asistencias_id_estudiante_id_fecha_clase_key",
            },
            AuditoriaActividad: {"auditoria_actividades_rol_actor_check"},
        }

        for model, expected_names in expected_constraints.items():
            with self.subTest(model=model.__name__):
                actual_names = {
                    constraint.name for constraint in model._meta.constraints
                }
                self.assertTrue(expected_names.issubset(actual_names))

    def test_nullable_columns_match_database_schema(self):
        nullable_fields = {
            ModuloAcademico: {"es_activo", "creado_en"},
            UsuarioAdmin: {"creado_en"},
            Estudiante: {"correo_electronico", "creado_en"},
            Asistencia: {"estado", "fecha_hora_marcado"},
            AuditoriaActividad: {
                "rol_actor",
                "valor_anterior",
                "valor_nuevo",
                "fecha_hora",
            },
        }

        for model, fields in nullable_fields.items():
            for field_name in fields:
                with self.subTest(model=model.__name__, field=field_name):
                    self.assertTrue(model._meta.get_field(field_name).null)

    def test_uuid_primary_keys_have_application_and_database_defaults(self):
        models_with_uuid_primary_keys = (
            ModuloAcademico,
            UsuarioAdmin,
            Estudiante,
            FechaClase,
            Asistencia,
            AuditoriaActividad,
        )

        for model in models_with_uuid_primary_keys:
            primary_key = model._meta.pk
            with self.subTest(model=model.__name__):
                self.assertIsNotNone(primary_key.default)
                self.assertIsNotNone(primary_key.db_default)
