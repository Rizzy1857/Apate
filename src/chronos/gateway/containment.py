"""Linux worker defense in depth. The privileged FUSE daemon stays outside."""
import ctypes
import os
import sys
import errno


def is_honeypot_mount(root):
    """A directory/tmpfs at the target is not sufficient: require a FUSE mount."""
    with open('/proc/self/mountinfo', encoding='utf-8') as mounts:
        for line in mounts:
            before, after = line.split(' - ', 1)
            if before.split()[4] == root and after.split()[0].split('.')[0] == 'fuse':
                return True
    return False


def contain_worker(root):
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise RuntimeError('Session containment requires the Linux container runtime')
    libc = ctypes.CDLL(None, use_errno=True)
    seccomp = ctypes.CDLL('libseccomp.so.2', use_errno=True)
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    context = seccomp.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError('Unable to allocate session syscall filter')
    try:
        for name in ('execve', 'execveat', 'fork', 'vfork', 'clone', 'clone3',
                     'socket', 'socketpair', 'connect', 'bind', 'listen', 'accept', 'accept4',
                     'ptrace', 'mount', 'umount2', 'pivot_root', 'setns', 'unshare',
                     'fsopen', 'fsmount', 'move_mount', 'open_by_handle_at', 'io_uring_setup'):
            number = seccomp.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and seccomp.seccomp_rule_add(context, 0x50000 | errno.EPERM, number, 0) != 0:
                raise RuntimeError(f'Unable to restrict syscall {name}')
        _drop_privileges(root, libc)
        if seccomp.seccomp_load(context) != 0:
            raise RuntimeError('Unable to install session syscall filter')
    finally:
        seccomp.seccomp_release(context)


def _drop_privileges(root, libc):
    parent = os.getppid()
    # PR_SET_NO_NEW_PRIVS: exec can never recover privilege.
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'Unable to restrict session privileges')
    os.chdir(root)
    os.chroot('.')
    os.chdir('/')
    os.setgroups([])
    os.setgid(1000)
    os.setuid(1000)
    # Dropping credentials clears PDEATHSIG, so set it afterwards.
    if libc.prctl(1, 15, 0, 0, 0) != 0 or os.getppid() != parent:
        raise RuntimeError('Session supervisor disappeared')
    if os.geteuid() == 0:
        raise RuntimeError('Session privilege drop failed')
