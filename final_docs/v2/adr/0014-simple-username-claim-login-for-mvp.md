# ADR-0014 — Simple Username-Claim Login for MVP, Real OAuth Deferred

- **Status**: Accepted — supersedes the *timing* of ADR-0007, not its direction
- **Date**: 2026-07-26
- **Phase**: 2
- **Deciders**: Project owner

## Context

ADR-0007 locked "Log in with Lichess" as OAuth2 Authorization Code with PKCE, with
Chess.com linked as a profile source only (not a login provider), because Chess.com OAuth
is approval-gated. That ADR was left in `Proposed` status pending Phase 2 implementation.

Implementing Phase 2, the owner asked for a minimal setup: keep local Postgres (already
decided in ADR-0015), and "have simple login using lichess or chess login" — i.e. a
username-based login usable for both platforms, without the added moving parts a real
OAuth flow requires (registering a Lichess OAuth app identity, a PKCE code-verifier
exchange, a callback route, token storage and refresh).

Both platforms expose a public, unauthenticated "does this user exist" endpoint:
`GET /api/user/{username}` on Lichess, `GET /pub/player/{username}` on Chess.com. That is
enough to reject typos and to store each platform's canonical username casing, but it does
not prove the person logging in owns the account.

## Decision

**MVP login checks that a username exists on the chosen platform and logs the caller in as
that account.** No password, no OAuth token, no proof of ownership. The backend:

1. Looks the username up via the platform's public API (`app/integrations/platforms.py`).
2. Creates the account, an identity row, and a `self` profile on first sight; updates the
   display name on repeat login.
3. Issues its own signed session JWT (`app/domain/auth/session.py`), exactly as ADR-0007
   specified for the post-OAuth step — only the step that produces the "who is this"
   answer changes, not what happens after.

Every `user_identities` row this login path creates is marked `verified = false` with
`verification_method = "username_claim"`, so the trust level is visible in the data, not
just in a comment. Nothing before Phase 14 (Chess.com verification, ADR-0007) upgrades a
claim to verified.

**Both providers now use the same login path.** ADR-0007's asymmetry — Lichess as a login
provider, Chess.com as a source-only link — no longer applies during MVP, because neither
path proves ownership yet. That asymmetry returns once real Lichess OAuth lands, since
Lichess OAuth does prove ownership and username-claim does not.

Real Lichess OAuth2 PKCE, as ADR-0007 specified, is deferred rather than abandoned. It
becomes required before any private data or write-permission feature ships, because
"anyone can log in as anyone" is only acceptable while the product analyses public games.

## Rationale

The decisive point is the same shape as ADR-0015: the *interface* this decision produces —
`AuthService.login(provider, username) -> LoginResult`, a session-cookie-based
`CurrentUser` dependency, `user_identities.verified` as a boolean flag — is exactly what a
real OAuth exchange would also need to produce at the end of its flow. Adding PKCE later
means replacing the body of `PlatformClient.fetch_user`'s Lichess path with a token
exchange and setting `verified = true`, not redesigning the session, the schema, or the
routes.

That makes the deferral cheap in the same way ADR-0015's was: the expensive, hard-to-change
decisions (session token shape, identity table design, verified flag) are made correctly
now, and the part that changes later is contained to one integration module.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Implement Lichess PKCE now, Chess.com stays link-only (ADR-0007 as written) | More moving parts for Phase 2 — OAuth app registration, callback route, code-verifier storage — for a security property (proof of ownership) that does not yet protect anything, since MVP only analyses public games |
| Email/password | Contradicts the owner's original requirement that login is a chess platform account |
| Ship without any login, profile chosen by URL param | No account model at all; blocks Phase 3+ ingestion, which needs a durable profile to attach games to |

## Consequences

### Positive
- No OAuth app registration or client id/secret management for Phase 2
- One code path for both providers instead of two different trust models
- Session, schema, and route shape are the real ones Phase 14+ will keep
- Fully hermetic in tests — no network to an OAuth provider required to test login

### Negative
- **Anyone can log in as any username that exists on Lichess or Chess.com.** This is a
  real, accepted security gap, not a theoretical one. It must close before any private
  data, write access, or cross-profile permission grant (ADR-0012) ships.
- `verified = false` on every identity row until real OAuth lands, so no feature may treat
  a login as proof of anything beyond "a session exists for this display name"
- ADR-0007's Lichess/Chess.com asymmetry is paused, not resolved

### Follow-up required
- Before any private-data or write feature: implement Lichess OAuth2 PKCE per ADR-0007,
  flip that path's `verified` to `true`, and keep Chess.com on username-claim
- Phase 14: Chess.com claim verification via profile-field token, per ADR-0007

## References
- ADR-0007 — identity and OAuth strategy (direction retained, Lichess PKCE timing deferred)
- ADR-0015 — same deferral pattern applied to Supabase
- ADR-0012 — cross-profile permissions, which this ADR's gap must not be allowed to reach
- Decision D-003
