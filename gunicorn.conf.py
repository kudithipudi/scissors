"""Gunicorn configuration for the Rock Paper Scissors FastAPI app."""

# Server socket
bind = 'unix:/var/www/scissors/scissors.sock'
backlog = 2048

# Worker processes (kept at 1: APScheduler runs in-process, and a second
# worker would double-run the cleanup job; fine for this app's traffic).
workers = 1
worker_class = 'uvicorn.workers.UvicornWorker'
timeout = 120
keepalive = 5

# Restart workers after this many requests (helps prevent memory leaks)
max_requests = 1000
max_requests_jitter = 50

# Trust the local nginx proxy's X-Forwarded-* headers (for https scheme in
# generated URLs, e.g. the QR-code join link).
forwarded_allow_ips = '*'

# Logging (stdout/stderr -> journald via systemd; see `journalctl -u scissors`)
accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'scissors'

# Server mechanics
daemon = False
umask = 0
