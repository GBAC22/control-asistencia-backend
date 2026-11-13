# Credenciales iniciales de estudiantes

## Flujo

1. El operador configura `STUDENT_INITIAL_PASSWORDS_KEY`, distinta de
   `DJANGO_SECRET_KEY`, y ejecuta `python manage.py migrate`.
2. El administrador importa un Excel sin columnas `contrasena` ni `password`.
   Se genera una contraseña aleatoria diferente por estudiante.
3. En el panel, el administrador descarga el Excel de credenciales del módulo
   y entrega cada contraseña mediante un canal privado. Puede descargarlo de
   nuevo mientras las contraseñas iniciales no se hayan cambiado.
4. El estudiante inicia sesión y cambia su contraseña. La credencial inicial
   cifrada se elimina y deja de aparecer en futuras descargas.

La autenticación conserva únicamente el hash de la contraseña. Las contraseñas
iniciales se conservan cifradas con Fernet, sin caducidad, hasta su cambio;
solo un administrador autenticado puede descargarlas. Las descargas quedan
registradas sin incluir contraseñas. Los archivos ya descargados y las copias
de seguridad anteriores no se eliminan automáticamente: protégelos y bórralos
cuando dejen de ser necesarios.

Genera la clave de forma privada con
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
y guárdala en un gestor de secretos o archivo local protegido, nunca en Git.
Conserva una copia segura: cambiarla o perderla impide descifrar credenciales
pendientes. La migración no cambia contraseñas de estudiantes existentes; los
registros anteriores sin hash aún usan el número de registro y deben migrarse
antes de una exposición pública.

## Verificación

`python manage.py test asistencia.tests` verifica importación, autorización,
descargas repetidas, eliminación al cambiar contraseña y errores de clave.
Este cambio requiere desplegar también el frontend compatible y configurar el
secreto en cada tenant; no habilita por sí solo el despliegue en AWS.
