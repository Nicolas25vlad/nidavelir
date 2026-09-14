# Nidavelir operator runbook

This is the shortest supported path from a fresh self-hosted install to a reviewed task. It is intentionally operational: when something fails, use the checks in the same order before entering containers manually.

## 1. Install

```bash
curl -fsSL https://raw.githubusercontent.com/Nicolas25vlad/nidavelir/main/deploy/install.sh | sudo bash
```

Open a new login session after install so membership in the `nidavelir` operator group is refreshed. Configure rootless Docker or explicit Docker access for the operator account; routine Nidavelir commands should not require `sudo`.

## 2. Configure repository access and one worker harness

Edit the retained appliance environment:

```bash
nano /opt/nidavelir/.env
```

At minimum, configure GitHub branch access and one worker harness while browser-login persistence is still being completed:

```dotenv
NIDAVELIR_GITHUB_TOKEN=...
NIDAVELIR_OPENAI_API_KEY=...   # Codex worker, optional if another harness is configured
NIDAVELIR_CURSOR_API_KEY=...   # Cursor worker, optional if another harness is configured
```

Never put these values in tasks, prompts, repository files, screenshots, or worker logs.

## 3. Start and prove readiness

```bash
nidavelir update
nidavelir status
nidavelir health
nidavelir ready
nidavelir doctor
```

Interpret them separately:

- `health` proves the Core process is alive.
- `ready` proves Core can reach PostgreSQL, Docker, and the configured worker image.
- `doctor` checks the appliance configuration, auth material, Docker access, Compose validity, and live readiness together.

Do not start dogfood work while `ready` or `doctor` is failing.

## 4. Open the Web control plane

Production is loopback-first. On the server itself open the configured Web port, or tunnel it from another machine:

```bash
ssh -L 8080:127.0.0.1:8080 user@server
```

Then open `http://127.0.0.1:8080` locally. Retrieve the browser/operator token intentionally:

```bash
nidavelir operator-token
```

The browser keeps the operator token in session storage; it is not compiled into the Web image.

## 5. Connect a supervisor through MCP

Retrieve the MCP bearer token:

```bash
nidavelir mcp-token
```

The default endpoint is:

```text
http://127.0.0.1:8001/mcp
```

For a remote supervisor, tunnel the port or publish it only behind HTTPS/firewall controls. A Codex/Cursor/Claude/ChatGPT client is a **supervisor**. The Codex/Cursor CLI inside a Nidavelir worker is a **worker harness**; these choices are independent.

## 6. Create a task

For Nidavelir itself, use repository `Nicolas25vlad/nidavelir`. The repository now carries `.nidavelir.json`, so deterministic Core/MCP/Web checks are selected before heuristic validation.

A good first task is intentionally small and reversible. Include:

- one clear outcome;
- concrete acceptance criteria;
- no unrelated refactor request;
- an explicit profile when the auto-router could reasonably be ambiguous.

Until GitHub issue import (#132) lands, create the durable task from Web/MCP and copy only the useful issue context rather than an entire discussion thread.

## 7. Start and observe

Choose a configured worker harness and start the task. Normal state progression is:

```text
BACKLOG -> QUEUED -> PREPARING/RUNNING -> AGENT_DONE -> VALIDATING
```

The HTTP Core only enqueues. The dedicated executor owns long-running attempts, leases, heartbeats, and concurrency slots. Restarting the Core API should not kill active work.

Useful commands while a task runs:

```bash
nidavelir status
nidavelir logs executor
nidavelir logs core
nidavelir ready
```

Avoid entering or modifying the worker container manually. If manual container surgery is required for a task to complete, count that as a dogfood failure and preserve the evidence.

## 8. Review from Web

Task Detail should be sufficient to decide without opening the API/MCP manually. Before approval, inspect:

1. validation mode and reason;
2. persisted checks and failures;
3. the **UNVALIDATED** warning when validation was skipped;
4. complete diff;
5. worker harness/profile and profile fingerprint/Skills;
6. token usage and cache hit ratio;
7. retry context from a previous rejection, when present.

`UNVALIDATED` is reviewable, not equivalent to validated. Approve it only when you consciously accept the missing deterministic evidence.

## 9. Reject/retry or merge

If the result is wrong, reject it with concise actionable feedback. Nidavelir stores that feedback as bounded structured retry context rather than growing the task description forever. Start a fresh attempt after rejection.

If the result is correct, approve it first, then merge the reviewed commit. Merge verifies that the reviewed branch SHA has not moved.

## 10. Restart test

Before trusting the appliance for unattended work, deliberately exercise the recovery boundary with a non-critical task:

```bash
nidavelir restart core
nidavelir ready
```

The executor is a separate service, so restarting only Core should not turn an active attempt into a zombie. For executor/service troubleshooting:

```bash
nidavelir logs executor
nidavelir logs core
nidavelir doctor
```

## 11. Weekend dogfood gate

The current milestone is not “one task worked once”. Record three real Nidavelir issues that complete this loop without manual intervention inside workers:

```text
create/import -> queue -> execute -> validate -> review -> merge or deliberate retry
```

For every failure, keep the task/attempt ID and exact stage. Fix the orchestration failure before increasing autonomy or parallelism.

## Fast failure checklist

If a task does not start:

```bash
nidavelir doctor
nidavelir ready
nidavelir logs executor
```

If the Web cannot act:

```bash
nidavelir operator-token
nidavelir health
nidavelir logs web
nidavelir logs core
```

If MCP cannot connect:

```bash
nidavelir mcp-token
nidavelir logs mcp
nidavelir health
```

If an attempt appears stuck, capture the task ID and attempt ID first, then inspect `executor` and `core` logs. Do not run global Docker prune commands; Nidavelir cleanup is intentionally installation-scoped.