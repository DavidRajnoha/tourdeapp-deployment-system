#!/bin/sh

if [ "$DEBUG" = "True" ]; then
  echo "Running Flask application with the native server."
  exec python src/app.py
else
  echo "Running Flask application with Gunicorn."
  exec gunicorn -b :5000 src.app:app
fi