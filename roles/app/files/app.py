#!/usr/bin/env python3
import json, os, socket, time, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import format_trace_id
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

APP_NAME = os.environ.get('APP_NAME', 'infra-demo')
provider = TracerProvider(resource=Resource.create({'service.name': os.environ.get('OTEL_SERVICE_NAME', APP_NAME)}))
provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer('demo-app')

START = time.time()
COUNT = 0
HTTP_REQUESTS = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        global COUNT
        COUNT += 1
        clean_path = urllib.parse.urlparse(self.path).path
        with tracer.start_as_current_span('GET ' + clean_path) as span:
            span.set_attribute('http.method', 'GET')
            span.set_attribute('http.target', clean_path)
            if clean_path == '/boom':
                HTTP_REQUESTS.labels(method='GET', endpoint='/boom', status='500').inc()
                self.send_response(500)
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if clean_path == '/metrics':
                HTTP_REQUESTS.labels(method='GET', endpoint='/metrics', status='200').inc()
                self.send_response(200)
                self.send_header('Content-Type', CONTENT_TYPE_LATEST)
                self.end_headers()
                self.wfile.write(generate_latest())
                return
            body = json.dumps({'app': APP_NAME, 'host': socket.gethostname(), 'pid': os.getpid(), 'uptime_sec': int(time.time() - START), 'requests': COUNT}, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            HTTP_REQUESTS.labels(method='GET', endpoint='/', status='200').inc()

if __name__ == '__main__':
    HTTPServer(('0.0.0.0', 8080), H).serve_forever()