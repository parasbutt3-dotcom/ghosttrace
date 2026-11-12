# GHOSTTRACE — GitHub Research Report

## Evaluated repositories

| Repository | Stars | License | Language | Reuse decision |
|---|---|---|---|---|
| ActivityWatch/activitywatch | ~19.6k | MPL-2.0 | Python | Reuse API contract for activity ingestion |
| wazuh/wazuh | ~17.7k | Other (GPL-ish) | C++ | Integrate via REST API (no code vendoring) |
| keycloak/keycloak | ~37.8k | Apache-2.0 | Java | Reference for identity; not vendored (too heavy) |
| open-telemetry/opentelemetry-collector | ~7.8k | Apache-2.0 | Go | Event schema inspiration |
| SigNoz/signoz | ~32.6k | Other | TS | UI inspiration only |
| openobserve/openobserve | ~23.0k | AGPL-3.0 | TS/Rust | Not vendored (AGPL) |

## Selection rationale

- ActivityWatch: mature, free, local-first activity tracker with a documented HTTP API. We integrate via its REST API rather than vendoring, preserving MPL-2.0 attribution.
- Wazuh: industry SIEM; integrate via its REST API (auth token + alerts/agents). No code vendored.
- Google: use official google-auth-oauthlib / google-api-python-client only for verified endpoints. Consumer Google accounts do not expose login events or connected-app inventory; these are reported as `permission_status=unavailable` honestly.
- OpenTelemetry: event schema mirrors OTel resource/attribute style but no code vendored.

## License compliance

No upstream source code was copied. Integration is via network APIs only. Attribution retained in this document and README.
