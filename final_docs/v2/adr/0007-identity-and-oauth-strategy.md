# ADR-0007 — Lichess OAuth Login, Chess.com by Username

- **Status**: Accepted — direction retained; Lichess PKCE *implementation timing* deferred
  by ADR-0014, which Phase 2 implements instead
- **Date**: 2026-07-25
- **Phase**: 0, direction implemented in Phase 2 via ADR-0014's simplified login
- **Deciders**: Project owner

## Context

The owner's requirement: *"I need every user profile they can login using lichess or
chess. After login based on lichess or chess, they have their dashboard or view."*

The original `project-plan.md` Phase 2 specified Supabase Auth with backend JWT
validation. That is incompatible with the requirement, for two reasons discovered during
Phase 0 research.

**Lichess.** Supports OAuth2 Authorization Code with PKCE. Client secrets are not
supported at all — it is a public-client flow, `client_id` is self-chosen, the
authorization endpoint is `https://lichess.org/oauth` and the token endpoint is
`https://lichess.org/api/token`. Fully usable today. But Supabase Auth has no Lichess
provider, and no generic OIDC provider that could stand in for one.

**Chess.com.** The Published-Data API is unauthenticated and read-only. Chess.com does
operate an OAuth login programme, but access is granted by application and approval. It
cannot be treated as available.

## Decision

**Login**: "Log in with Lichess" using OAuth2 Authorization Code + PKCE. The backend owns
the code exchange, creates or updates the `users` row in Supabase Postgres, and issues its
own session JWT signed with `SESSION_JWT_SECRET`. Supabase Auth is not used as the
authenticator.

**Chess.com**: linked as a username on a profile rather than a login provider.
`profile_sources.verified` is `false` for claimed usernames, and unverified sources are
never presented as authoritatively belonging to the user. Public archives are readable
regardless.

**Optional verification** (Phase 14): the user places a short token in their Chess.com
profile field, the backend reads it back via the public API, and marks the source
verified.

**Forward path**: the connector interface is designed so that if Chess.com partner OAuth
is approved, Chess.com is promoted to a login provider without changing the profile model.

## Rationale

The requirement is that users authenticate with a chess platform account. Lichess makes
that possible immediately and at no cost, since PKCE public clients need no registration
secret. Chess.com does not, and no amount of design makes an approval-gated programme
available on demand.

Backend-owned OAuth is the honest consequence. Supabase Auth cannot broker a provider it
does not support, so the choice is between adopting an identity broker that does, or
owning roughly a hundred lines of well-understood OAuth code. Owning it keeps the
dependency surface small and keeps Supabase in the role ADR-0002 assigns it: a data
platform.

The `verified` flag is not bureaucracy. A user can claim any Chess.com username, including
someone else's. Displaying an unverified claim as an established identity would be
misleading, and it would undermine the permission model in ADR-0012, which assumes profile
ownership means something.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Supabase Auth with email/password | Contradicts the stated requirement |
| Supabase Auth with a supported provider (Google, GitHub) | Does not connect the user to their chess games, which is the entire point |
| Auth0 or Clerk as a broker for Lichess | An extra vendor and cost for a flow that is straightforward to own |
| Wait for Chess.com OAuth approval before building login | Blocks Phase 2 on an external process with no timeline |
| Treat a claimed Chess.com username as verified | Anyone could claim anyone; breaks the permission model |

## Consequences

### Positive
- Login connects directly to the user's real games
- Lichess import at Phase 14 reuses the token already held
- No client secret to protect for Lichess
- Chess.com remains fully usable as a game source

### Negative
- The backend owns session issuance, refresh, and revocation
- Users with only a Chess.com account cannot log in in MVP — see open question Q-3
- Two identity paths (OAuth and username link) with different trust levels to keep straight
- Deviates from the approved plan, so it requires explicit sign-off

### Follow-up required
- **Owner decision (Q-3)**: should email/password be offered as a fallback for users with neither platform account?
- Phase 2: implement the PKCE flow, session issuance, and profile bootstrap
- Phase 14: Chess.com username verification; revisit partner OAuth

## References
- Lichess API OAuth2 PKCE — [lichess-org/api-demo](https://github.com/lichess-org/api-demo), [PKCE deprecation issue](https://github.com/ornicar/lila/issues/9214)
- [Chess.com Published-Data API](https://www.chess.com/announcements/view/published-data-api)
- [Chess.com OAuth / Login application](https://www.chess.com/blog/CHESScom/chess-com-oauth-login-connected-board-application)
- Decision D-003
