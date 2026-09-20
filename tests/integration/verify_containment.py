"""Run in a disposable Linux container as root; intentionally drops privilege."""
import errno
import os
import socket
import tempfile
from chronos.gateway.containment import contain_worker


root = tempfile.mkdtemp(prefix='containment-')
os.chmod(root, 0o755)
contain_worker(root)
assert os.getuid() == os.getgid() == 1000
assert not os.path.exists('/app/requirements.txt')
for operation in (lambda: socket.socket(), os.fork,
                  lambda: os.execve('/does-not-exist', ['test'], {}),
                  lambda: os.setuid(0)):
    try:
        operation()
    except OSError as exc:
        assert exc.errno == errno.EPERM, exc
    else:
        raise AssertionError('Forbidden runtime operation succeeded')
print('PASS: chroot hides runtime files; privilege regain, new sockets, process creation and exec denied')
