"""WSGI entry point. Gunicorn runs one process with bounded request threads.

The existing local HTTP handler handles API and static routes. This adapter
provides its request streams and response headers from the WSGI interface.
"""
import io
from email.message import Message
from http import HTTPStatus
from urllib.parse import quote
from server import Handler, init

init()

class WSGIHandler(Handler):
    def __init__(self, environ):
        self.directory = str(__import__('server').ROOT / 'static')
        self.command = environ['REQUEST_METHOD']
        self.path = quote(environ.get('PATH_INFO', '/'), safe='/')
        if environ.get('QUERY_STRING'): self.path += '?' + environ['QUERY_STRING']
        self.request_version = 'HTTP/1.1'
        self.requestline = f'{self.command} {self.path} HTTP/1.1'
        self.headers = Message()
        for key, value in environ.items():
            if key.startswith('HTTP_'): self.headers[key[5:].replace('_','-')] = value
        for key in ['CONTENT_TYPE','CONTENT_LENGTH']:
            if environ.get(key): self.headers[key.replace('_','-')] = environ[key]
        self.rfile = environ['wsgi.input']
        self.wfile = io.BytesIO()
        self.status = 200
        self.response_headers = []
        self._headers_buffer = []
        self.close_connection = True
    def send_response(self, code, message=None):
        self.status = code
    def send_header(self, keyword, value):
        self.response_headers.append((keyword,str(value)))
    def flush_headers(self):
        self._headers_buffer = []

def application(environ, start_response):
    handler = WSGIHandler(environ)
    if handler.command == 'GET': handler.do_GET()
    elif handler.command == 'POST': handler.do_POST()
    elif handler.command == 'HEAD' and not handler.path.startswith('/api/'): handler.do_HEAD()
    else: handler.send_json({'error':'Méthode non autorisée.'},405)
    payload = handler.wfile.getvalue()
    # Replace any supplied length with the actual size except for HEAD,
    # which retains the resource length returned by SimpleHTTPRequestHandler.
    if handler.command != 'HEAD':
        handler.response_headers = [(k,v) for k,v in handler.response_headers if k.lower()!='content-length']
        handler.response_headers.append(('Content-Length',str(len(payload))))
    start_response(f'{handler.status} {HTTPStatus(handler.status).phrase}',handler.response_headers)
    return [payload]
