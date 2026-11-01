## Decision

Login has no trusted authenticated principal, so its quota always uses request.client.host.
Do not parse bearer tokens there or consult caller-supplied forwarded headers. The server's
existing trusted-proxy configuration determines the connection client address.

For other routes verify the configured application JWT signature/algorithm and require
sub and exp. Bound the encoded token to 8192 characters and subject to the database's
64-character user-ID limit; reject empty subjects and non-numeric/non-finite expiry.
Invalid tokens fall back to the IP quota. This establishes quota identity only; route
authentication still controls authorization, revocation and current roles.
Bearer scheme matching is case-insensitive, consistent with the authentication layer,
so changing scheme capitalization does not switch a valid user to an IP bucket.

Keep existing Redis selection/fallback, shared key namespaces, limits and response format.
Per-account abuse controls and distributed Redis failure policy remain separate work.
Do not transplant the newer dirty local branch's broader changes.

## Validation

Record tests failing against the old implementation before modifying it. Verify rotating
forged/valid subjects cannot evade login limits, valid authenticated users retain separate
quotas, bad/expired/malformed tokens share the IP quota, and forwarded headers do not
change the connection IP. Run focused and full offline suites, then independent review.
