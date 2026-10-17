"""Real local HTTP stalls must not retain inference transport processes."""
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from chronos.intelligence.inference import InferenceRuntime, ModelUnreachableError


@pytest.mark.parametrize('stage', ['headers', 'body'])
def test_real_stalled_http_is_killed(stage, monkeypatch):
    release = threading.Event()
    entered = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            entered.set()
            if stage == 'body':
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"response":"partial","done":false}\n')
                self.wfile.flush()
            release.wait(5)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv('OLLAMA_PORT', str(server.server_port))
    spawned = []
    original = subprocess.Popen

    def spawn(*args, **kwargs):
        process = original(*args, **kwargs)
        spawned.append(process)
        return process

    monkeypatch.setattr(subprocess, 'Popen', spawn)
    try:
        start = time.monotonic()
        with pytest.raises(ModelUnreachableError):
            InferenceRuntime(host='127.0.0.1').generate('test', timeout=1.5)
        assert time.monotonic() - start < 2.2
        assert entered.is_set(), 'Test must reach the real HTTP stall'
        assert len(spawned) == 1 and spawned[0].poll() is not None
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize('reason,body', [
    ('truncated', b'{"response":"synthetic partial","done":true,"done_reason":"length"}\n'),
    ('incomplete', b'{"response":"synthetic partial","done":false}\n'),
])
def test_real_http_failure_classification_survives_child(reason, body, monkeypatch):
    """Exercise the actual child protocol, not a mocked process response."""
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv('OLLAMA_PORT', str(server.server_port))
    runtime = InferenceRuntime(host='127.0.0.1')
    try:
        with pytest.raises(ModelUnreachableError) as error:
            runtime.generate('synthetic test', timeout=5)
        assert error.value.reason == reason
        assert runtime.circuit_breaker.models['llama3:8b'].failures == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
