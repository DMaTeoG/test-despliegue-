#!/usr/bin/env bash
# Terminar inmediatamente si ocurre un error
set -o errexit

# Instalar dependencias
pip install -r requirements.txt

# Recopilar archivos estáticos
python manage.py collectstatic --no-input

# Ejecutar las migraciones en la base de datos PostgreSQL de Render
python manage.py migrate
