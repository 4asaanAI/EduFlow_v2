#!/bin/bash
cat > /var/app/staging/Procfile << 'EOF'
web: gunicorn application:application --bind 0.0.0.0:8000 --workers 4 --worker-class uvicorn.workers.UvicornWorker --access-logfile - --error-logfile -
EOF
