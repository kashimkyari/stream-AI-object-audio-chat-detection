import multiprocessing

bind = "0.0.0.0:5000"
workers = multiprocessing.cpu_count() * 2 + 1  # Best practice
threads = 2
timeout = 60
loglevel = "info"
# accesslog = "/var/log/gunicorn/access.log"
# errorlog = "/var/log/gunicorn/error.log"
