"""Cross-platform RF field-application entry point for RF-Finder."""

from __future__ import annotations

import argparse
import socket

from .field_service import RFService
from .tactical_server import create_server


def _local_ip() -> str:
    """Best-effort LAN address for opening the dashboard from a phone."""
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("192.0.2.1", 80))
        address = probe.getsockname()[0]
        probe.close()
        return address
    except OSError:
        return "<computer-LAN-IP>"


def main() -> None:
    parser = argparse.ArgumentParser(description="RF-Finder cross-platform field monitor")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address; 0.0.0.0 allows LAN clients")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()

    service = RFService(scan_interval_s=args.interval)
    service.start()
    server = create_server(service, host=args.host, port=args.port)

    print("RF-Finder Field Monitor")
    print(f"Platform: {service.status()['platform']}")
    print(f"Source: {service.source_name}")
    print(f"Local dashboard: http://127.0.0.1:{args.port}/tactical")
    if args.host == "0.0.0.0":
        print(f"Phone/LAN dashboard: http://{_local_ip()}:{args.port}/tactical")
    else:
        print(f"Dashboard: http://{args.host}:{args.port}/tactical")
    print("Phone sensors remain telemetry-only; RF measurements come from the configured capture source.")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
        server.server_close()


if __name__ == "__main__":
    main()
