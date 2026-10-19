# Database Engineering: Indexing, MVCC & Schema Design

Source: Handbook Chapter 18 (`VirtualOffice_Complete_Guide.md`).

## 1. Indexing Principles
1. **Every query in the API must have an index plan**: In `schema.md`, document for every table and index which `API-###` endpoint it serves.
2. **Composite index column order**: Equality columns first, then range or sort columns (`user_id, created_at`).
3. **Index types**:
   - **B-tree (default)**: Equality, ranges, sorting, prefix LIKE.
   - **GIN**: Arrays, JSONB tags, full-text search vectors.
   - **Partial indexes**: Filtered subsets (`WHERE status = 'active'`).
4. **Foreign keys**: Always index foreign key columns explicitly.

## 2. Multi-Version Concurrency Control (MVCC)
1. **Prevent lost updates**: Use optimistic concurrency (`version` column) or `SELECT ... FOR UPDATE` inside short transactions.
2. **Keep transactions short**: Never perform network I/O or wait for user input inside a transaction.
3. **Avoid hot rows**: Do not update a single global counter per request; use append-only event logs or distributed counters.

## 3. Schema Standards (Appendix A.6)
- Primary keys: UUIDv7 or autoincrement integers.
- Timestamps: Store UTC (`timestamptz`), include `created_at` and `updated_at`.
- Enums: Use `CHECK` constraints rather than free text.
- Access rules: Document row-level security or service-layer access control policies for Read, Insert, Update, Delete per table.
