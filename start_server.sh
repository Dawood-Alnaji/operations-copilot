#!/bin/bash

echo "🚀 Starting Operations Copilot Development Server..."
echo ""

# Activate venv
source ../venv/bin/activate

# Run server
python manage.py runserver
