"""Local-network discovery advertisement for the RF Finder phone client."""

from __future__ import annotations

import socket

from zeroconf import ServiceInfo, Zeroconf

SERVICE_TYPE = "_rf-finder._tcp.local."
SERVICE_NAME = "RF Finder._rf-finder._tcp.local."


def _lan_ipv4_addresses() -> list[str]:
    """Return non-loopback IPv4 addresses usable by a LAN client."""
    addresses: set[str] = set()
    try:
        host = socket.gethostname()
        for family, _, _, _, sockaddr in socket.getaddrinfo(host, None, socket.AF_INET):
            if family == socket.AF_INET:
                address = sockaddr[0]
                if not address.startswith("127."):
                    addresses.add(address)
    except OSError:
        pass

    # The UDP probe only discovers the preferred local address; it sends no
    # application data.
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("192.0.2.1", 80))
        address = probe.getsockname()[0]
        probe.close()
        if address and not address.startswith("127."):
            addresses.add(address)
    except OSError:
        pass

    return sorted(addresses)


class RFServiceAdvertiser:
    """Advertise the RF Finder HTTP service using DNS-SD/mDNS."""

    def __init__(self, port: int) -> None:
        self.port = port
        self._zeroconf: Zeroconf | None = None
        self._service: ServiceInfo | None = None

    @property
    def addresses(self) -> list[str]:
        return _lan_ipv4_addresses()

    def start(self) -> bool:
        addresses = self.addresses
        if not addresses:
            return False

        service = ServiceInfo(
            SERVICE_TYPE,
            SERVICE_NAME,
            addresses=[socket.inet_aton(address) for address in addresses],
            port=self.port,
            properties={
                b"path": b"/camera",
                b"protocol": b"http",
                b"version": b"1",
            },
            server=f"rf-finder-{socket.gethostname()}.local.",
        )
        zc = Zeroconf()
        try:
            zc.register_service(service)
        except Exception:
            zc.close()
            return False
        self._zeroconf = zc
        self._service = service
        return True

    def stop(self) -> None:
        if self._zeroconf is None:
            return
        try:
            if self._service is not None:
                self._zeroconf.unregister_service(self._service)
        finally:
            self._zeroconf.close()
            self._zeroconf = None
            self._service = None
