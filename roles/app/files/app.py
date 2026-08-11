#!/usr/bin/env python3
"""Demo-app: JSON о себе (stdlib only), слушает :8080."""
import json
import os
import socket
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

START = time.time()
COUNT = 0


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        global COUNT
        COUNT += 1
        body = json.dumps({
            "app": "infra-demo",
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "uptime_sec": int(time.time() - START),
            "requests": COUNT,
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), H).serve_forever()
