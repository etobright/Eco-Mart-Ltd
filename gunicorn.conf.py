import os
# SQLite lives on a single local persistent disk; sessions are in this worker.
bind = '0.0.0.0:' + os.environ.get('PORT', '10000')
workers = 1
worker_class = 'gthread'
threads = 8
timeout = 60
keepalive = 5
# Avoid automatic worker recycling: sessions are intentionally in memory.
max_requests = 0
accesslog = '-'
errorlog = '-'
capture_output = True
limit_request_line = 4094
limit_request_fields = 50
limit_request_field_size = 8190
