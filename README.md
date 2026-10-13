# Attendance Control API

Django and PostgreSQL backend for the attendance-control application.

## Local setup

From this directory, create and activate a virtual environment if needed, then
install the declared dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with local database settings and a secret `DJANGO_SECRET_KEY`. Never
commit `.env` or real student data. Apply migrations and start the development
server:

```powershell
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Create the first administrator interactively:

```powershell
python manage.py seed_admin --nombre "Administrator" --correo "admin@example.test"
```

The command prompts for a password without displaying it. For API requests from
the Angular development server, configure its proxy to this backend.

## Tests

```powershell
python manage.py test asistencia.tests
```

## Sample import workbook

`plantilla_carga_asistencia_prueba_2026-10-13_a_2026-11-13.xlsx` contains
fictional example records only. Replace them with authorized data before use.
