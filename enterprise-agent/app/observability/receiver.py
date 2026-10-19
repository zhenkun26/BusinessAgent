"""Independent internal acceptance receiver; retained authenticated receipts, no notifications."""
from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os

from app.observability.monitor import validate_alert
from app.observability.retained import RetainedStore


class Receiver(BaseHTTPRequestHandler):
    store: RetainedStore
    token: str

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format: str, *args: object) -> None:
        pass  # Never log request headers, paths or bodies.

    def reply(self, status: int, body: dict) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(encoded)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(encoded)

    def authorized(self) -> bool:
        return hmac.compare_digest(self.headers.get('Authorization', '').encode(),
                                   ('Bearer '+self.token).encode())

    def do_POST(self) -> None:
        if not self.authorized():
            self.reply(401, {'error': 'UNAUTHORIZED'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if self.path != '/alerts' or not 0 < length <= 1024 or self.headers.get('Transfer-Encoding'):
                raise ValueError
            body = validate_alert(json.loads(self.rfile.read(length)))
            self.store.append('receipt', body['event_id'], body)
            self.reply(200, {'event_id': body['event_id'], 'status': 'retained'})
        except (ValueError, TypeError, KeyError, AttributeError):
            self.reply(400, {'error': 'ALERT_REJECTED'})
        except Exception:
            self.reply(503, {'error': 'RECEIPT_STORE_UNAVAILABLE'})

    def do_GET(self) -> None:
        if not self.authorized():
            self.reply(401, {'error': 'UNAUTHORIZED'})
            return
        if self.path != '/receipts':
            self.reply(404, {'error': 'NOT_FOUND'})
            return
        try:
            with self.store.connect() as db:
                rows = db.execute("SELECT body FROM retained_events WHERE channel='receipt' "
                                  'ORDER BY seq DESC LIMIT 100').fetchall()
            self.reply(200, {'items': [json.loads(row[0]) for row in rows]})
        except Exception:
            self.reply(503, {'error': 'RECEIPT_STORE_UNAVAILABLE'})


def main() -> None:
    token = os.environ.get('CONTROLLED_ALERT_TOKEN', '')
    if len(token) < 32:
        raise RuntimeError('RECEIVER_CONFIGURATION_REJECTED')
    Receiver.token = token
    Receiver.store = RetainedStore(os.environ.get('OBSERVABILITY_STORE_PATH', '/data/receiver/state.sqlite3'))
    HTTPServer(('0.0.0.0', 8090), Receiver).serve_forever()


if __name__ == '__main__':
    main()
