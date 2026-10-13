from django.urls import path

from asistencia.presentation import views

urlpatterns = []
urlpatterns = [
    path("api/health", views.health, name="health"),
    path("api/auth/csrf", views.csrf_token, name="csrf-token"),
    path("api/auth/login/student", views.student_login, name="student-login"),
    path("api/auth/login/admin", views.admin_login, name="admin-login"),
    path("api/auth/logout", views.logout, name="logout"),
    path("api/auth/me", views.current_actor, name="current-actor"),
    path(
        "api/student/attendance",
        views.student_attendance,
        name="student-attendance",
    ),
    path(
        "api/student/schedule",
        views.student_schedule,
        name="student-schedule",
    ),
    path(
        "api/student/attendance/mark",
        views.mark_attendance,
        name="mark-attendance",
    ),
    path("api/admin/modules", views.admin_modules, name="admin-modules"),
    path(
        "api/admin/modules/<uuid:module_id>/classes",
        views.admin_module_classes,
        name="admin-module-classes",
    ),
    path(
        "api/admin/modules/create",
        views.create_admin_module,
        name="create-admin-module",
    ),
    path(
        "api/admin/modules/<uuid:module_id>/activate",
        views.activate_module,
        name="activate-module",
    ),
    path(
        "api/admin/modules/<uuid:module_id>/import",
        views.import_module,
        name="import-module",
    ),
    path(
        "api/admin/classes/<uuid:class_id>/cancel",
        views.cancel_admin_class,
        name="cancel-admin-class",
    ),
    path(
        "api/admin/classes/<uuid:class_id>/restore",
        views.restore_admin_class,
        name="restore-admin-class",
    ),
    path(
        "api/admin/attendance",
        views.admin_attendance_report,
        name="admin-attendance-report",
    ),
    path(
        "api/admin/attendance/update",
        views.update_admin_attendance,
        name="update-admin-attendance",
    ),
    path("api/admin/audit", views.admin_audit_log, name="admin-audit-log"),
]
