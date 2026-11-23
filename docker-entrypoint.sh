#!/bin/sh
# Roda toda vez que o container sobe, antes do servidor.
set -e

echo "Aplicando migrações do banco..."
python manage.py migrate --noinput
python manage.py sincronizar_feriados

echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

# Executa o comando definido no CMD do Dockerfile (o gunicorn)
exec "$@"
