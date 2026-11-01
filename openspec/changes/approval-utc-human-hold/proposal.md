# Approval UTC and human review hold

Current main ignores expiry in decision/resume/batch and can redispatch after an uncertain result. Legacy naive timestamps and statuses cannot prove elapsed TTL or absence of effects.

Implement a server-owned UTC contract for new approvals, preserve legacy records behind a human-review hold, and commit a one-way executing state before dispatch. AI may describe evidence only; it cannot approve, clear a hold or authorize replay. A standalone additive schema increment introduces a nullable, immutable server-owned contract column. It never backfills legacy rows. No automatic legacy conversion or human override endpoint is included; applying the increment to any database requires separate authorization.
