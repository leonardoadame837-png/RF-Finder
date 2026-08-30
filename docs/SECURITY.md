# RF Finder Security Model

## Authentication

RF Finder stores password hashes, never plaintext passwords. Access and refresh tokens are generated from the OS cryptographic random source. Only token hashes are stored in SQLite.

Access tokens are short-lived (15 minutes by default). Refresh sessions are persisted for 30 days and are represented by hashes in the database.

## Authorization

Roles are `viewer`, `analyst`, `operator`, `admin`, and `owner`. API routes check permissions before accessing measurements or controlling devices.

## Audit logging

Authentication and device-management events are recorded in `audit_events`. Sensitive credentials and raw tokens are never written to audit metadata.

## Secrets

Real secrets belong in environment/secret-management infrastructure, not Git. `.env.example` contains configuration names only. Local `.env`, key files, and credential directories are ignored.

## API deployment

The development server should bind to `127.0.0.1`. A production deployment must use HTTPS/TLS, a trusted reverse proxy, restrictive CORS, rate limiting, secret management, backups, and an appropriately secured database host.

## RF safety boundary

Device-control operations are intentionally separated from passive measurement reads. Hardware drivers should be added behind the `DeviceManager` boundary and should validate frequency/sample-rate ranges before applying settings to physical hardware.
