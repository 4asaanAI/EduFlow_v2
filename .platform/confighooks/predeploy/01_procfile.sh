#!/bin/bash
cat > /var/app/staging/Procfile << 'EOF'
web: gunicorn server:app --bind 0.0.0.0:8000 --workers 4 --worker-class uvicorn.workers.UvicornWorker --pythonpath /var/app/current/backend --timeout 120 --access-logfile - --error-logfile -
EOF
