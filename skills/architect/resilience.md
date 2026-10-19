# Load Balancing, Caching, Queues and Resilience

Source: Handbook Chapter 19 (`VirtualOffice_Complete_Guide.md`).

## 1. Load Balancing & Statelessness
1. **Stateless instances**: No in-memory sessions or local disk state; store state in database or Redis.
2. **Health checks**: Configure `/health/live` (process alive) and `/health/ready` (dependencies reachable).
3. **Algorithms**: Least connections for variable request processing costs; round robin for uniform workloads.

## 2. Caching Patterns
1. **Cache-aside (default)**: Read cache $\to$ on miss, read DB $\to$ write cache with TTL. Delete cache on updates.
2. **Stampede protection**: Request coalescing / per-key lock with jittered TTLs.
3. **Degradation**: If cache fails, application must continue functioning directly against the database (graceful degradation).

## 3. Resilience Checklist
- **Timeouts**: Enforce timeouts at every hop: Load Balancer $>$ Application $>$ Database.
- **Retries**: Exponential backoff with jitter, only for idempotent operations.
- **Idempotency**: Require `Idempotency-Key` header on mutating POST operations.
- **Bulkheads & Circuit Breakers**: Isolate dependency failures to prevent cascading system collapse.
- **Rate Limiting**: Protect endpoints using token bucket algorithms per IP and authenticated user.
