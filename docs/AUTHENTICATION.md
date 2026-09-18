# RF Finder Authentication Specification

**Status:** Authoritative current authentication specification  
**Scope:** Local prototype authentication, HTTP API authentication, RBAC, and the boundary to future Android/voice-bot clients  
**Implementation references:** `app/auth.py`, `app/api_auth.py`, `app/tactical_server.py`, `app/voice_bot.py`

> This document defines the authentication model that RF Finder implements today. It deliberately does **not** introduce JWT, OAuth 2.0, OpenID Connect, refresh tokens, or a cloud identity provider into the local prototype. Those are future architecture options, not current requirements.

## 1. Security model and scope

RF Finder currently uses a **local, process-oriented authentication model**:

1. Local user accounts are stored in `data/auth/users.json`.
2. Passwords are stored only as salted PBKDF2-HMAC-SHA256 password hashes.
3. Successful login creates a cryptographically random opaque session token.
4. Active sessions are held **in memory only** by `AuthManager`.
5. HTTP clients present the session token as a Bearer token.
6. `APIAuth` validates the session and applies role-based permissions.
7. Session state is lost when the process exits or restarts.

The model is intended for the current local/offline prototype and controlled development environments. It is not yet the final identity architecture for a remotely connected Android application or hosted voice service.

## 2. Authoritative implementation

### 2.1 `app/auth.py`

`AuthManager` owns account storage and process-local sessions.

Constants currently defined by the implementation:

- PBKDF2-HMAC-SHA256
- 600,000 PBKDF2 iterations
- 16-byte random salt
- 32-byte token entropy input
- 1-hour default session lifetime
- minimum password length: 10 characters
- username length: 1–64 characters

Account records contain:

- username as the JSON object key
- role
- base64-encoded salt
- base64-encoded password hash
- PBKDF2 iteration count

Plaintext passwords are not persisted.

### 2.2 Password verification

On authentication, RF Finder:

1. Looks up the username.
2. Decodes the stored salt and password hash.
3. Reads the stored PBKDF2 iteration count.
4. Derives a hash from the supplied password.
5. Compares the derived and stored hashes with `hmac.compare_digest`.
6. Creates a session only after successful verification.

Invalid usernames and invalid passwords use the same externally visible authentication error.

### 2.3 Session tokens

The current session token is:

- opaque
- randomly generated with `secrets.token_urlsafe(32)`
- associated with a `Session` object in the `AuthManager._sessions` in-memory dictionary
- not a JWT
- not persisted to disk
- not self-describing
- not intended to carry claims

The server is authoritative for token validity. A token is valid only while its corresponding in-memory session exists and has not expired.

### 2.4 Expiration and logout

The default session lifetime is one hour.

`get_session()` rejects and removes expired sessions. `logout()` removes the token from the in-memory session store.

Because sessions are process-local, restarting RF Finder invalidates all active sessions.

## 3. HTTP API authentication

### 3.1 Request flow

The current HTTP authentication flow is:

```
Client/browser
    |
    | POST /api/auth/login
    | username + password
    v
APIAuth
    |
    v
AuthManager.authenticate()
    |
    +--> users.json
    |      salted password hash
    |
    +--> successful verification
            |
            v
      in-memory Session
            |
            v
      opaque session token
            |
            v
Client/browser stores token for its current session
```

Subsequent protected requests use:

```
Authorization: Bearer <opaque-session-token>
```

`APIAuth.principal_from_header()` extracts the token and asks `AuthManager` whether the session is still valid.

### 3.2 Authorization flow

For a protected endpoint:

```
HTTP request
   |
   v
Authorization header
   |
   v
APIAuth.principal_from_header()
   |
   +--> no/invalid session --> 401 Authentication required
   |
   v
APIPrincipal
   |
   v
permission check
   |
   +--> authenticated but missing permission --> 403 Not authorized
   |
   v
operation executes
```

The distinction is intentional:

- **401** = the request is not authenticated with a valid current session.
- **403** = the request is authenticated but its role lacks the required permission.

### 3.3 Current tactical web client

The tactical browser UI currently:

- receives the session token from `/api/auth/login`
- stores it in browser `sessionStorage`
- sends it in the `Authorization` header
- validates the session through `/api/auth/me`
- calls `/api/auth/logout` when signing out
- removes its local token on sign-out
- signs out locally when a protected request receives HTTP 401

The server also sends `Cache-Control: no-store` on its responses.

This browser storage arrangement is part of the current prototype and should not be treated as the final mobile credential-storage design.

## 4. Current roles and permissions

The implementation currently defines two roles.

| Permission | user | admin |
|---|:---:|:---:|
| `rf.read` | ✓ | ✓ |
| `rf.scan` | ✓ | ✓ |
| `investigation.read` | ✓ | ✓ |
| `investigation.write` | ✓ | ✓ |
| `telemetry.read` | ✓ | ✓ |
| `telemetry.write` | ✓ | ✓ |
| `admin.users` | — | ✓ |

The permission names are the authorization contract used by `APIAuth` and the protected server endpoints.

The role itself is stored with the local account record. Authorization is based on the server-side role-to-permission mapping, not on permissions supplied by the client.

## 5. Shared authentication boundary

The field application creates one authentication manager and passes it to the authenticated service surfaces.

Conceptually:

```
                 AuthManager
                     |
                   APIAuth
                  /       \
       Tactical HTTP     Spectrum HTTP
                  \
                RF Service
```

This means the local authenticated HTTP surfaces can share the same account/session authority rather than maintaining independent token stores.

The voice assistant currently uses `AuthManager` directly and creates a tool permission set after local login.

## 6. Current voice-bot model

The current `app/voice_bot.py` is a **local console assistant**, not a remote Android/cloud voice client.

Its current flow is:

1. Create `AuthManager`.
2. Run first-run setup if no local account exists.
3. Prompt for local username/password.
4. Authenticate and obtain a local session.
5. Build a `ToolRegistry` with RF permissions.
6. Run the assistant/router locally.
7. Log out the session on exit.

The current voice assistant grants `rf.scan` and `rf.read` to the tool registry for authenticated `user` and `admin` roles.

The authentication primitive is therefore shared, but the current voice interface is not yet a network authentication protocol.

## 7. Credential lifecycle

### Account creation

```
plaintext password
      |
      v
random 16-byte salt
      |
      v
PBKDF2-HMAC-SHA256 / 600,000 iterations
      |
      v
password_hash + salt + metadata
      |
      v
users.json
```

The plaintext password is not written to the account file.

### Login

```
username + password
      |
      v
lookup stored salt/hash
      |
      v
derive candidate hash
      |
      v
constant-time comparison
      |
      v
opaque random session token
```

### Logout

```
Bearer token
    |
    v
locate in-memory session
    |
    v
remove session
    |
    v
token no longer authenticates
```

## 8. Threat model for the current prototype

The current model is designed primarily to protect the local application and its authenticated API boundaries.

Relevant threats include:

- plaintext password disclosure through persistent storage
- incorrect password verification
- unauthorized access to protected HTTP endpoints
- use of expired sessions
- use of logged-out sessions
- privilege escalation from `user` to `admin`
- bypassing endpoint permission checks
- accidentally exposing an anonymous path around an authorization boundary

Current mitigations include:

- salted password hashing
- PBKDF2 work factor
- constant-time hash comparison
- cryptographically random session tokens
- server-side session state
- explicit role/permission checks
- session expiration
- logout invalidation
- tests covering core authentication and RBAC behavior

### Current limitations

The prototype does **not** yet provide all controls expected of an internet-facing production identity system. In particular:

- sessions are process-local and disappear on restart
- there is no persistent session store
- there is no refresh-token mechanism
- there is no account recovery workflow
- there is no MFA
- there is no device-bound credential model
- there is no centralized identity provider
- there is no OAuth/OIDC authorization server
- the current HTTP service is not, by itself, a production-grade public internet deployment boundary

These are explicit limitations, not missing JWT/OAuth features that should be silently added to the local prototype.

## 9. Security requirements for changes

Any authentication-related change to the current prototype must preserve these requirements unless this specification is deliberately revised:

1. Never persist plaintext passwords.
2. Use a unique random salt per password.
3. Preserve a strong password KDF and explicit iteration metadata.
4. Compare password-derived values using a timing-resistant comparison.
5. Generate session tokens with a cryptographically secure random source.
6. Keep token validation authoritative on the server.
7. Do not trust client-supplied roles or permissions.
8. Enforce permissions at the protected operation/API boundary.
9. Expire sessions.
10. Invalidate sessions on logout.
11. Do not create anonymous alternate paths around protected RF operations.
12. Add or update authentication tests whenever authentication behavior changes.
13. Treat the current token as an opaque session identifier, not as a claim-bearing identity document.

## 10. Future Android / voice-bot authentication model

The eventual Android client and network-connected voice bot are a **separate architecture phase**.

The current local session model should not be stretched into a public distributed identity protocol merely because those clients are planned.

Future design work may evaluate:

- a dedicated identity/authentication service
- OAuth 2.0 / OpenID Connect where appropriate
- short-lived access tokens
- refresh-token rotation and revocation
- secure Android credential storage
- device registration and device identity
- scoped client permissions
- token audience and issuer validation
- TLS-only transport
- server-side session/revocation controls
- MFA or step-up authentication for sensitive administrative actions
- voice-specific authorization so speech input cannot bypass normal API permissions
- audit trails linking account, device, request, and RF operation

Any future protocol must preserve the same core authorization principle:

**authentication establishes who/what is acting; authorization determines which RF Finder operation that principal may perform.**

### Android client boundary

A future Android application should authenticate to a dedicated remote API boundary rather than directly reading the local `users.json` file.

The conceptual future flow is:

```
Android app
    |
    | secure authentication
    v
Identity / authentication service
    |
    | access credential
    v
RF Finder API
    |
    v
server-side authorization
    |
    v
RF operation
```

The exact protocol is intentionally **not fixed by this document**.

### Future voice-bot boundary

A network-connected voice bot should not receive a privileged RF capability merely because a voice command was recognized.

The future flow should remain:

```
Voice input
    |
    v
speech / intent layer
    |
    v
authenticated client identity
    |
    v
authorized RF Finder API/tool
    |
    v
RF operation
```

Speech recognition, intent recognition, or an AI assistant must never be treated as proof of authorization.

## 11. JWT/OAuth decision

**Do not add JWT or OAuth to the local prototype solely to make the architecture look production-ready.**

JWT/OAuth become relevant when RF Finder crosses a boundary such as:

- remote clients over an untrusted network
- multiple independently deployed services
- centralized identity
- delegated authorization
- third-party integrations
- production account/device management

When that transition occurs, the protocol should be selected from the actual deployment and threat model rather than retrofitted prematurely.

Until then, the current local opaque-session model remains the authoritative implementation.

## 12. Testing requirements

Authentication tests must cover at minimum:

- account creation
- password hashing
- plaintext password exclusion
- successful authentication
- incorrect-password rejection
- duplicate-account rejection
- session creation
- token validation
- session expiration
- logout invalidation
- missing-token rejection
- invalid-token rejection
- role permission boundaries
- administrative permission boundaries
- protected API behavior

Existing tests in the repository include:

- `tests/test_auth.py`
- `tests/test_api_auth.py`

Changes to authentication should update these tests or add focused tests as appropriate.

## 13. Implementation map

| Component | Responsibility |
|---|---|
| `app/auth.py` | Local account storage, password KDF, session creation/validation/invalidation |
| `app/api_auth.py` | Bearer-token extraction, principal construction, RBAC enforcement |
| `app/tactical_server.py` | HTTP login/logout/session endpoints and protected RF API routes |
| `app/field.py` | Shared authentication boundary for application HTTP surfaces |
| `app/voice_bot.py` | Current local voice/console authentication and tool permissions |
| `tests/test_auth.py` | Local authentication behavior |
| `tests/test_api_auth.py` | API authentication and RBAC behavior |

## 14. Change-control rule

This file is the **authoritative authentication specification for the current RF Finder implementation**.

If implementation and this document diverge, the discrepancy must be resolved explicitly:

1. determine whether the code or specification is intended to change;
2. update the authoritative specification when the architecture changes;
3. add/update tests;
4. review security implications;
5. document any migration required for existing accounts or sessions.

Future Android/voice-bot authentication may replace or extend the local model, but that transition must be documented as a deliberate architecture change rather than an implicit introduction of JWT/OAuth into the prototype.
