# Scaling Playbook: Tiers, Formulas & Capacity Planning

Source: Handbook Chapter 17 (`VirtualOffice_Complete_Guide.md`).

## 1. Capacity Estimation Formulas
- **Average RPS**: $\text{DAU} \times \text{requests\_per\_user\_per\_day} \div 86,400$
- **Peak RPS**: $\text{Average RPS} \times \text{peak\_factor}$
- **Concurrent Users (Little's Law)**: $L = \lambda \times W$ (Requests in flight = arrival rate $\times$ average latency)
- **Peak Write RPS**: $\text{Peak RPS} \times \text{write\_share}$
- **Storage per Year**: $\text{DAU} \times \text{data\_per\_user\_per\_day} \times 365 \times (\text{replication factor} + \text{index overhead } \approx 30\text{--}50\%)$

## 2. Scale Tier Reference
| Tier | DAU | Avg RPS | Peak RPS | Peak Write RPS | Architecture Decisions |
|---|---|---|---|---|---|
| **T0** | $< 10,000$ | $< 6$ | $< 60$ | $< 6$ | Single app server / modular monolith, local SQLite or managed single PostgreSQL, indexed queries, local backups. No microservices, Kafka, or Kubernetes. |
| **T1** | $100,000$ (1 lakh) | $\approx 58$ | $\approx 580$ | $\approx 58$ | $\ge 2$ instances behind L7 load balancer, stateless apps, connection pooling (PgBouncer), Redis cache-aside, object storage for media. |
| **T2–T3** | $200,000\text{--}300,000$ | $116\text{--}174$ | $1,160\text{--}1,740$ | $116\text{--}174$ | Autoscaling (min 3), 1–2 read replicas, Redis stampede protection, monthly range partitioning for large tables, tuned autovacuum. |
| **T4** | $1,000,000$ (10 lakh) | $\approx 579$ | $\approx 5,800$ | $\approx 580$ | Container orchestration (K8s), functional domain DB splits, search engine (OpenSearch), durable event log (Kafka), circuit breakers. |
| **T5** | $10,000,000$ (1 crore) | $\approx 5,790$ | $\approx 58,000$ | $\approx 5,800$ | Sharding write path (Citus / distributed SQL), GeoDNS multi-region, cell-based architecture, queue load shedding. |

## 3. Core Operating Rules
1. **Design for the next tier, build for the current one**: Plan the migration path to $T(n+1)$, but do not build sharding or microservices for a T0/T1 system.
2. **Show the arithmetic**: All capacity numbers must show the explicit calculation from cited inputs.
3. **Partitioning before sharding**: Partitioning is a local single-server database optimization; sharding requires distributed application coordination.
