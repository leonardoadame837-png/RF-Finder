# RF Finder Authentication and Authorization

**Status:** Current implementation reference  
**Scope:** Local RF Finder application, HTTP API, and planned Android / voice-bot clients

This document defines the authentication, session, authorization, and security model currently implemented by RF Finder. It is intended to keep client and server implementations aligned as the project moves from a simulation-first local prototype toward authenticated mobile and voice-assisted clients.

## 1. Security model at a glance

RF Finder currently uses:

- Local user accounts stored in `data/auth/users.json`.
- Passwords stored as salted PBKDF2-HMAC-SHA256 password hashes, never as plaintext.
- A 16-byte cryptographically random salt per account.
- 600,000 PBKDF2 iterations for newly created accounts.
- Cryptographically random opaque bearer session tokens generated with Python `secrets`.
- Process-local, in-memory sessions with a default lifetime of 3,600 seconds (1 hour).
- Role-based access control (RBAC) with `user` and `admin` roles.
- HTTP authentication through `Authorization: Bearer <token>`.
- Explicit permission checks at protected API boundaries.

The current session token is **not a JWT**. It is an opaque random token whose meaning is held by the server-side in-memory session store.

## 2. Components

### `app/auth.py` — credential and session authority

`AuthManager` owns account creation, password verification, session creation, token validation, expiration, and logout.

Account records contain the role, Base64-encoded salt, Base64-encoded password hash, and PBKDF2 iteration count. Password verification derives a hash using the stored parameters and compares it with the stored hash using `hmac.compare_digest`.

Sessions contain:

- `User` — username and role.
- `token` — opaque bearer credential.
- `expires_at` — absolute expiration time.

Sessions are held in an in-memory dictionary and are not persisted to disk.

### `app/api_auth.py` — API authentication and RBAC

`APIAuth` adapts `AuthManager` to HTTP API requests. It parses Bearer authorization headers, resolves a live session, constructs an `APIPrincipal`, and enforces permissions through `require()`.

### HTTP servers

The tactical HTTP server and spectrum server construct or receive an `APIAuth` instance and use permission checks before protected operations. This establishes the authorization boundary between a client and RF Finder operations.

## 3. Credential lifecycle

### Account creation

1. A username is normalized with `strip()`.
2. Username length must be 1–64 characters.
3. Password length must be at least 10 characters.
4. Role must be `user` or `admin`.
5. A unique 16-byte random salt is generated.
6. PBKDF2-HMAC-SHA256 derives the password hash using 600,000 iterations.
7. The salt and hash are Base64-encoded and written to the authentication data file.
8. The plaintext password is not written to the account record.

The first-run setup creates the initial local administrator account.

### Password verification

At login, RF Finder loads the account record, decodes the stored salt and hash, derives a candidate hash from the supplied password, and compares the candidate to the stored hash using a constant-time comparison.

An invalid username and an incorrect password produce the same public error message (`Invalid username or password.`), reducing username-enumeration leakage at this layer.

## 4. Exact HTTP request flow

### Login

```text
Client
  |
  | POST /api/auth/login
  | {"username": "...", "password": "..."}
  v
HTTP server
  |
  v
APIAuth.login()
  |
  v
AuthManager.authenticate()
  |
  +--> load users.json
  +--> decode salt + stored hash
  +--> PBKDF2-HMAC-SHA256(password, salt, iterations)
  +--> constant-time hash comparison
  |
  +--> create random opaque session token
  +--> store Session in process memory
  |
  v
HTTP response
  {"token": "...", "expires_at": ..., "username": "...", "role": "...", "permissions": [...]}
```

The returned token is a bearer credential. Possession of a valid token is sufficient to authenticate API requests until expiration or logout, so it must be protected like a password while it remains valid.

### Authenticated request

```text
Client
  |
  | Authorization: Bearer <session-token>
  v
API endpoint
  |
  v
APIAuth.require(header, permission)
  |
  +--> parse Bearer token
  +--> AuthManager.get_session(token)
  +--> reject missing / expired token
  +--> construct APIPrincipal
  +--> check required permission
  |
  v
Protected RF Finder operation
```

A missing or invalid session produces an authentication failure. A valid session without the required permission produces an authorization failure.

### Logout

```text
Client
  |
  | POST /api/auth/logout
  | Authorization: Bearer <session-token>
  v
APIAuth.logout()
  |
  v
AuthManager.logout()
  |
  v
Session removed from memory
```

After logout, the same token no longer resolves to a live session.

## 5. Token lifecycle

1. **Issued:** after successful password verification.
2. **Stored:** only in the server process's in-memory session dictionary.
3. **Presented:** by the client in an HTTP `Authorization: Bearer` header.
4. **Validated:** by looking up the token in the active session store and checking `expires_at`.
5. **Expired:** after the configured session TTL; expired entries are removed when accessed.
6. **Revoked:** immediately when logout removes the session.
7. **Process restart:** all active sessions disappear because the current implementation does not persist them.

The default TTL is one hour. A deployment can configure the `AuthManager` session TTL, but clients must not assume that a token remains valid for a fixed period if the server configuration changes.

## 6. Authorization and permissions

RF Finder uses role-based permissions rather than treating authentication as sufficient authorization.

| Role | Permissions |
|---|---|
| `user` | `rf.read`, `rf.scan`, `investigation.read`, `investigation.write`, `telemetry.read`, `telemetry.write` |
| `admin` | All `user` permissions plus `admin.users` |

Permission checks should be performed at the server boundary. A UI control being hidden or disabled is not an authorization mechanism.

### Permission semantics

- `rf.read` — read RF/spectrum/observation information.
- `rf.scan` — start or stop RF scanning operations exposed by the API.
- `investigation.read` — read investigation data and reports.
- `investigation.write` — create or modify supported investigation data.
- `telemetry.read` — read telemetry exposed through protected API operations.
- `telemetry.write` — write telemetry through protected API operations.
- `admin.users` — administrator-level user-management capability.

Physical device controls must remain behind an authenticated and authorized server-side boundary. A future Android or voice-bot client must not receive authority merely because it can issue a command through a UI or conversational interface.

## 7. Android client requirements

The Android client should treat the RF Finder session token as a sensitive credential.

Required design constraints:

1. Use HTTPS/TLS for any network connection outside a trusted local development setup.
2. Do not hard-code passwords, bearer tokens, private keys, or API secrets in the application source.
3. Do not log passwords or bearer tokens.
4. Prefer OS-protected credential storage for a persistent mobile session rather than ordinary application preferences.
5. Handle HTTP `401` as an authentication/session problem and `403` as an authorization problem.
6. Refresh or re-authenticate when a session expires; do not attempt to manufacture or modify tokens client-side.
7. Keep privileged device operations behind explicit server-side permission checks.
8. Treat the server's permission response as informational; the server remains authoritative.

For a remote/mobile deployment, the current process-local session store is not sufficient for multiple independent server processes. A shared session store or another deliberately designed authentication architecture will be required before horizontal scaling.

## 8. Voice-bot client requirements

The RF Finder voice bot should be considered an authenticated client, not a privileged operator by default.

The voice layer should follow this boundary:

```text
Voice input
   |
   v
Intent / command interpretation
   |
   v
Authenticated RF Finder API client
   |
   v
Server-side authentication + permission check
   |
   v
Allowed RF Finder operation
```

The voice model must not be trusted as an authorization authority. Natural-language instructions such as “start scanning” or “change the device” must resolve to an API operation that independently enforces the caller's permissions.

For high-impact device operations, the eventual voice-bot design should support an explicit confirmation step and an auditable operation record. Confirmation is an additional safety control, not a replacement for server-side authorization.

## 9. Threat model

The authentication design should account for at least these threats:

| Threat | Current control | Remaining requirement / limitation |
|---|---|---|
| Password database disclosure | Salted PBKDF2 password hashes | Protect the filesystem and consider a modern password-hashing policy for future deployments |
| Password guessing | PBKDF2 raises per-guess cost | Add login rate limiting / abuse controls for exposed services |
| Token theft | Random 32-byte token; short-lived process-local session | Protect client storage and require TLS for remote use |
| Token replay | Token acts as a bearer credential | TLS, secure storage, expiration, logout/revocation controls |
| Unauthorized API operation | Server-side RBAC checks | Keep every privileged endpoint behind `require()` |
| Browser/client token leakage | Current web UI uses `sessionStorage` | Review browser security policy and consider stronger session-cookie architecture for browser deployments |
| Cross-origin abuse | Not represented by the auth layer itself | Define and enforce an explicit CORS policy for remote web clients |
| Brute-force login | No rate limiter in `AuthManager` | Required before exposing authentication to untrusted networks |
| Multi-worker inconsistency | Sessions are process-local | Use shared session state or a deliberately designed distributed token/session model |
| Credential/token logging | No credential logging should be introduced | Keep secrets out of application, proxy, CI, and analytics logs |
| Compromised client | API credentials may be exposed to a compromised endpoint | Minimize permissions and provide server-side revocation/expiration |
| Voice command abuse | Voice client must authenticate like other clients | Enforce permissions and confirmation for sensitive operations |

This threat model describes engineering risks; it is not a claim that the current prototype is production-ready for hostile networks.

## 10. Transport and deployment security requirements

Before RF Finder authentication is exposed beyond a controlled local development environment:

- Terminate HTTPS/TLS at the deployment boundary.
- Do not transmit passwords over plaintext HTTP on an untrusted network.
- Do not expose the development HTTP servers directly to the public Internet.
- Apply login rate limiting and monitoring.
- Define CORS behavior explicitly for browser-based clients.
- Review request-size, timeout, and connection limits on network-facing servers.
- Avoid returning sensitive diagnostic information in authentication errors.
- Keep authentication data and runtime state outside source control when deployment-specific data is used.
- Ensure backups of authentication data are protected to the same security standard as the live data.

## 11. Security boundaries

The following boundaries are intentional:

**Credential boundary**  
Passwords are accepted only for authentication and are transformed into password hashes. Application components should not persist plaintext credentials.

**Session boundary**  
The bearer token identifies an active server-side session. Code outside the authentication layer should not implement its own token validation.

**Authorization boundary**  
Protected API operations call `APIAuth.require()` with the permission they need. Clients cannot grant themselves permissions.

**Hardware boundary**  
Physical SDR/device controls should remain behind authenticated API operations and permission checks. A future client, including the voice bot, must not bypass this boundary by directly manipulating hardware from an untrusted UI path.

## 12. Current implementation limitations

The current authentication implementation is appropriate as a local prototype boundary, but several items remain before treating it as a general remote service:

1. Sessions are in-memory and disappear on process restart.
2. Sessions are not shared between independent worker processes.
3. There is no built-in login rate limiting in `AuthManager`.
4. TLS is a deployment concern rather than a property of the local authentication classes.
5. The browser UI currently keeps its bearer token in `sessionStorage`; this should receive a dedicated browser threat-model review before remote deployment.
6. There is no dedicated refresh-token mechanism.
7. There is no centralized security-event/audit subsystem in the authentication layer.

These limitations should be tracked as deployment/security work rather than silently worked around in clients.

## 13. Implementation references

The authoritative implementation is currently:

- `app/auth.py` — password hashing, accounts, sessions, expiration, logout.
- `app/api_auth.py` — Bearer-token parsing, principals, RBAC, and authorization checks.
- `app/tactical_server.py` — authenticated tactical HTTP endpoints and client integration.
- `app/spectrum_server.py` — authenticated spectrum API integration.
- `tests/test_api_auth.py` — API authentication and permission behavior tests.
- `tests/test_tactical_api.py` — authenticated tactical API behavior tests.

When this document and the implementation diverge, update this document as part of the same change that alters the security model.

## 14. Change checklist for authentication work

Before merging authentication-related changes, verify:

- [ ] No plaintext password is persisted.
- [ ] Password verification remains constant-time at the final comparison.
- [ ] Tokens remain cryptographically random and are not logged.
- [ ] Token expiration and logout behavior remain covered by tests.
- [ ] New protected endpoints call the authorization boundary.
- [ ] Required permissions are documented.
- [ ] Client-facing errors do not disclose unnecessary credential details.
- [ ] Android and voice-bot clients do not bypass server-side authorization.
- [ ] Security-sensitive changes include tests and documentation updates.

## 15. Reference implementation parameters

The current implementation defines these defaults in `app/auth.py`:

```text
PBKDF2 algorithm:       HMAC-SHA256
PBKDF2 iterations:      600,000
Salt size:              16 bytes
Session token entropy:  32 random bytes
Default session TTL:    3,600 seconds
Account password floor: 10 characters
Username maximum:       64 characters
```

These are implementation parameters, not permanent security guarantees. Re-evaluate them when the deployment threat model, supported platforms, or authentication architecture changes.
