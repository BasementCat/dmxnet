import socket
import os


def has_dualstack_ipv6():
    """Ported from python3.8 source

    Return True if the platform supports creating a SOCK_STREAM socket
    which can handle both AF_INET and AF_INET6 (IPv4 / IPv6) connections.
    """
    if not socket.has_ipv6 \
            or not hasattr(socket._socket, 'IPPROTO_IPV6') \
            or not hasattr(socket._socket, 'IPV6_V6ONLY'):
        return False
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            return True
    except error:
        return False


def create_server(address, *, family=socket.AF_INET, type=socket.SOCK_STREAM, backlog=None, reuse_port=False,
                  dualstack_ipv6=False):
    """Ported from python3.8 source

    Convenience function which creates a SOCK_STREAM type socket
    bound to *address* (a 2-tuple (host, port)) and return the socket
    object.
    *family* should be either AF_INET or AF_INET6.
    *backlog* is the queue size passed to socket.listen().
    *reuse_port* dictates whether to use the SO_REUSEPORT socket option.
    *dualstack_ipv6*: if true and the platform supports it, it will
    create an AF_INET6 socket able to accept both IPv4 or IPv6
    connections. When false it will explicitly disable this option on
    platforms that enable it by default (e.g. Linux).
    >>> with create_server((None, 8000)) as server:
    ...     while True:
    ...         conn, addr = server.accept()
    ...         # handle new connection
    """
    if reuse_port and not hasattr(socket._socket, "SO_REUSEPORT"):
        raise ValueError("SO_REUSEPORT not supported on this platform")
    if dualstack_ipv6:
        if not has_dualstack_ipv6():
            raise ValueError("dualstack_ipv6 not supported on this platform")
        if family != socket.AF_INET6:
            raise ValueError("dualstack_ipv6 requires AF_INET6 family")
    sock = socket.socket(family, type)
    try:
        # Note about Windows. We don't set SO_REUSEADDR because:
        # 1) It's unnecessary: bind() will succeed even in case of a
        # previous closed socket on the same address and still in
        # TIME_WAIT state.
        # 2) If set, another socket is free to bind() on the same
        # address, effectively preventing this one from accepting
        # connections. Also, it may set the process in a state where
        # it'll no longer respond to any signals or graceful kills.
        # See: msdn2.microsoft.com/en-us/library/ms740621(VS.85).aspx
        if os.name not in ('nt', 'cygwin') and \
                hasattr(socket._socket, 'SO_REUSEADDR'):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except error:
                # Fail later on bind(), for platforms which may not
                # support this option.
                pass
        if reuse_port:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        if socket.has_ipv6 and family == socket.AF_INET6:
            if dualstack_ipv6:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            elif hasattr(socket._socket, "IPV6_V6ONLY") and \
                    hasattr(socket._socket, "IPPROTO_IPV6"):
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        try:
            sock.bind(address)
        except socket.error as err:
            msg = '%s (while attempting to bind on address %r)' % \
                (err.strerror, address)
            raise socket.error(err.errno, msg) from None
        if backlog is None:
            sock.listen()
        else:
            sock.listen(backlog)
        return sock
    except socket.error:
        sock.close()
        raise