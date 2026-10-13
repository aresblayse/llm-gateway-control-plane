# Local / Enterprise AI Gateway & Model Operations Console

## 1. Product overview
A deterministic miniature AI gateway control plane with provider abstraction, capability-aware routing, policy enforcement, token-bucket rate limiting, caching, circuit-breaker state, usage metering and request replay.

## 2. Problem
Organizations need a controlled layer between applications and multiple AI models so routing, spend, latency, capability, policy and observability are managed centrally.

## 3. Why the problem matters
Direct provider integration makes governance and operational comparison difficult. A gateway creates a stable policy and routing boundary.

## 4. Architecture
```mermaid
flowchart LR
 A[Client Request] --> B[Validation / Policy]
 B --> C[Quota / Rate Limit]
 C --> D[Capability Filter]
 D --> E[Routing Engine]
 E --> F[Provider Adapter]
 F --> G[Response + Usage Meter]
 G --> H[Cache / Audit / Replay]
```

## 5. Core workflow
Enter a request → apply policy → check quota → filter models by capability/context/cost/latency → rank candidates → execute provider → meter usage → cache deterministic response → emit audit event → optionally replay under current configuration.

## 6. Algorithms
Priority routing, capability filtering, cost/latency constraints, token-bucket rate limiting, deterministic response caching, provider fallback, failure counters and circuit-breaker eligibility.

## 7. Technical implementation
The gateway is built around a `Provider` protocol. `MockProvider`, `LocalProvider` and an offline-safe `OpenAICompatibleProvider` adapter demonstrate interchangeability without requiring credentials. Request records and audit events are separated from UI composition.

## 8. Data model
Requests contain ID, project, model, provider, latency, token counts, cost, status, retry count, fallback state and policy decision. Policies contain model allowlists, cost ceilings, context ceilings and RPM limits.

## 9. Screenshots
The console provides overview metrics, a route simulator, model/provider catalog, policy view, request table, replay workflow and audit/diagnostics panel.

## 10. Demo instructions
Run `streamlit run app.py` and use the Route Simulator. The default mock providers require zero API keys.

## 11. Local setup
Python 3.14.8 target. Install requirements and run Streamlit.

## 12. Streamlit deployment
Create GitHub repository → upload → choose `app.py` in Streamlit Community Cloud → Deploy. External credentials are optional and not needed for demo mode.

## 13. Testing
`pytest -q` checks capability filtering, policy rejection, deterministic mock responses and arbitrary request handling.

## 14. Performance considerations
Request-level responses are cached, metrics are calculated from actual request records and routing work is bounded by the configured model catalog.

## 15. Security considerations
The demo contains no real API keys. Production adapters should use environment/secret managers, hashed API keys, TLS, RBAC, redacted logs and provider-specific authentication.

## 16. Scalability path
Demo: Streamlit + local state. Small organization: PostgreSQL/Redis. Medium: stateless gateway API plus persistent control plane. Enterprise: horizontally scaled gateway workers, distributed rate limits, queueing, centralized telemetry and identity management.

## 17. Limitations
The demo provider is synthetic. Cost and latency values are illustrative configuration values, not vendor benchmarks. External provider adapters are intentionally credential-free in the default deployment.

## 18. Future architecture
Add OpenAI-compatible HTTP transport, streaming responses, distributed quotas, policy versioning, secret manager integration, provider health probes and OpenTelemetry exporters.

## 19. Example use cases
Internal model gateway, project budgets, multi-model routing, provider failover, AI usage governance and request-level cost/latency observability.

## 20. License
MIT.
