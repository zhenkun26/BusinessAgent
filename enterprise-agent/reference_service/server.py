"""Opt-in isolated reference listeners. No external egress, automatic reset or raw access log."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import socket
import threading
import time
from typing import Any

from reference_service.contract import MAX_BODY, PROFILE, Response, canonical, identifier
from reference_service.service import Credential, Service
from reference_service.store import Store


class ReferenceServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], service: Service, *, control: bool) -> None:
        self.service = service
        self.control = control
        super().__init__(address, Handler)

    def handle_error(self, request: Any, client_address: Any) -> None:
        # Avoid traceback-local or request/header disclosure.
        print('REFERENCE_CONNECTION_FAILED', flush=True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    server_version = 'BusinessReference/1'
    sys_version = ''

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Retained sanitized attempt rows replace HTTP payload/access logs.

    def send_error(self, code: int, message: str | None = None,
                   explain: str | None = None) -> None:
        self.respond(Response(code, {'error': {'code': 'HTTP_REQUEST_REJECTED',
                                               'operation_id': None}}))

    def process(self) -> None:
        try:
            names = [name.lower() for name in self.headers.keys()]
            headers = {name.lower(): value for name, value in self.headers.items()}
            length = headers.get('content-length', '0')
            if (len(names) != len(set(names)) or 'transfer-encoding' in headers
                    or not length.isascii() or not length.isdigit() or len(length) > 6
                    or int(length) > MAX_BODY or len(self.path) > 2048):
                self.send_error(422)
                return
            raw = self.rfile.read(int(length))
            if len(raw) != int(length):
                self.send_error(422)
                return
            self.respond(self.server.service.handle(self.command, self.path, headers, raw,
                                                     control=self.server.control))
        except (OSError, TimeoutError):
            self.close_connection = True

    def respond(self, response: Response) -> None:
        if response.fault == 'drop':
            self.close_connection = True
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            return
        if response.fault == 'delay':
            time.sleep(6)  # Fixed operator fault, beyond the reference client's 5s attempt budget.
        payload = b'{invalid' if response.fault == 'malformed' else canonical(response.data).encode()
        # Control evidence is separately bounded and never consumed as a business receipt.
        maximum = 8 * 1024 * 1024 if self.server.control else MAX_BODY
        if len(payload) > maximum:
            response = Response(503, {'error': {'code': 'REFERENCE_EVIDENCE_LIMIT',
                                                'operation_id': None}})
            payload = canonical(response.data).encode()
        self.send_response(response.status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Connection', 'close')
        self.send_header('X-Reference-Profile', PROFILE)
        for name, value in response.headers.items():
            if name.lower() != 'x-reference-profile':
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    do_GET = do_POST = do_PATCH = do_DELETE = process


def configured_service(*, initialize: bool = False) -> Service:
    service = os.environ['REFERENCE_SERVICE']
    operator = os.environ['REFERENCE_OPERATOR_TOKEN']
    principal = identifier(os.environ['REFERENCE_PRINCIPAL'])
    credentials = {os.environ['REFERENCE_TOKEN']:
                   Credential(principal, frozenset({'read', 'write', 'compensate'}))}
    read_only = os.environ.get('REFERENCE_READ_TOKEN')
    if read_only:
        if read_only in credentials:
            raise ValueError('REFERENCE_CREDENTIALS_INVALID')
        credentials[read_only] = Credential(principal, frozenset({'read'}))
    # Validate credentials before any store initialization.
    if len(operator) < 32 or operator in credentials or any(len(key) < 32 for key in credentials):
        raise ValueError('REFERENCE_CREDENTIALS_INVALID')
    store = Store.open(Path(os.environ['REFERENCE_DB']), service, os.environ['REFERENCE_STORE_ID'],
                       initialize=initialize)
    return Service(store, credentials, operator)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initialize', action='store_true', help='Create a NEW ledger and exit')
    args = parser.parse_args()
    try:
        service = configured_service(initialize=args.initialize)
        if args.initialize:
            service.store.db.close()
            print('REFERENCE_STORE_INITIALIZED')
            return 0
        business = ReferenceServer(('0.0.0.0', 8080), service, control=False)
        control = ReferenceServer(('0.0.0.0', 8081), service, control=True)
        thread = threading.Thread(target=control.serve_forever, daemon=True)
        thread.start()
        try:
            business.serve_forever()
        finally:
            control.shutdown()
            control.server_close()
            business.server_close()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print('REFERENCE_STARTUP_FAILED')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
