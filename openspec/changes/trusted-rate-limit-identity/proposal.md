## Why

The rate limiter reads JWT subjects without signature verification. A caller can rotate
forged subjects to obtain fresh login quotas without authenticating.

## What Changes

- Always charge login requests to the connection's client IP, ignoring bearer identity.
- On other routes, use a user bucket only for a bounded, signed, unexpired application
  token with valid subject and expiry. Otherwise use the connection IP bucket.
- Add failing-before/passing-after attack tests and valid-token positive controls.

## Scope

Local patch against PR4 `3cf4954`; no Redis behavior, authentication authorization,
threshold, product feature, deployment, remote branch or production changes.
