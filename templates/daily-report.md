# Daily Report: Day {{day}}
**Project**: {{project_id}}
**Date**: {{date}}
**Status**: {{status}}

## 1. Blockers
{{#if blockers}}
| Story | Owner | Blocker Description | Why / Root Cause | Action Required |
|---|---|---|---|---|
{{#each blockers}}
| {{id}} | {{owner}} | {{blocker}} | {{why}} | {{action}} |
{{/each}}
{{else}}
*No blockers today.*
{{/if}}

## 2. Progress & What Moved
| Story | Title | Owner | Points | Stage | Status |
|---|---|---|---|---|---|
{{#each stories}}
| {{id}} | {{title}} | {{owner}} | {{points}} | {{stage}} | {{status}} |
{{/each}}

## 3. Metrics & Burndown
- **Total Points Planned**: {{total_points}}
- **Points Completed**: {{points_completed}}
- **Points Remaining**: {{points_remaining}}
- **Bugs Found**: {{bug_count}}
- **Review Rounds**: {{review_rounds}}
- **Average Cycle Time (hours)**: {{avg_cycle_time_hours}}

## 4. Token Spend vs Budget (from Ledger)
| Role | Tokens Used | Token Budget | % Used | Status |
|---|---|---|---|---|
{{#each role_tokens}}
| {{role}} | {{used}} | {{budget}} | {{pct}}% | {{status}} |
{{/each}}
- **Total Tokens Used**: {{total_tokens_used}} / {{total_token_budget}} ({{total_tokens_pct}}%)
- **Total Cost (USD)**: ${{total_cost_usd}}

## 5. What Needs the Client
{{#if client_needs}}
{{#each client_needs}}
- **{{id}}**: {{question}} (Owner: {{owner}})
{{/each}}
{{else}}
*None. Team has all required client inputs for current sprint.*
{{/if}}
