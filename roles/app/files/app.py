#!/usr/bin/env python3
"""Demo app: JSON + code (utf8 only), listens on :8080. With OpenTelemetry tracing."""
import json
import os
import socket
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import format_trace_id

APP_NAME = os.environ.get('APP_NAME', 'infra-demo')

provider = TracerProvider(resource=Resource.create(
    {'service.name': os.environ.get('OTEL_SERVICE_NAME', APP_NAME)}))
provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer('demo-app')

START = time.time()
COUNT = 0


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        global COUNT
        COUNT += 1
        with tracer.start_as_current_span('GET ' + self.path) as span:
            span.set_attribute('http.method', 'GET')
            span.set_attribute('http.target', self.path)
            if self.path == '/boom':
                print('ERROR: boom requested, returning 500', flush=True)
                self.send_response(500)
                self.send_header('Content-Length', '0')
                self.end_headers()
                span.set_attribute('http.status_code', 500)
                return
            body = json.dumps({
                'app': APP_NAME,
                'host': socket.gethostname(),
                'pid': os.getpid(),
                'uptime_sec': int(time.time() - START),
                'requests': COUNT,
            }, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            span.set_attribute('http.status_code', 200)

    def log_message(self, fmt, *args):
        ctx = trace.get_current_span().get_span_context()
        tid = format_trace_id(ctx.trace_id) if ctx.is_valid else '-'
        print(f'{self.address_string()} tid={tid} {fmt % args}', flush=True)


if __name__ == '__main__':
    HTTPServer(('0.0.0.0', 8080), H).serve_forever()
