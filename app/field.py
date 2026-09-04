"""Laptop field-application entry point for RF-Finder."""

from __future__ import annotations

import argparse
import os
import time

from .field_service import RFService
from .tactical_server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description="RF-Finder laptop field monitor")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()

    service = RFService(scan_interval_s=args.interval)
    service.start()
    server = create_server(service, host=args.host, port=args.port)

    print("RF-Finder Field Monitor")
    print(f"Source: {service.source_name}")
    print(f"Tactical UI: http://{args.host}:{args.port}")
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
