"""Gunicorn configuration for Rock Paper Scissors app."""
import multiprocessing
import os

# Server socket
bind = 'unix:/var/www/scissors/scissors.sock'
backlog = 2048

# Worker processes
# workers = multiprocessing.cpu_count() * 2 + 1
workers = 1 
worker_class = 'gevent'  # For async support
worker_connections = 1000
timeout = 120
keepalive = 5

# Restart workers after this many requests (helps prevent memory leaks)
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = '/var/www/scissors/logs/access.log'
errorlog = '/var/www/scissors/logs/error.log'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'scissors'

# Server mechanics
daemon = False
pidfile = '/var/www/scissors/gunicorn.pid'
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed in the future)
# keyfile = None
# certfile = None
