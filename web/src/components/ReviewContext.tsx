import type { Attempt, Task, ValidationCheck } from "../lib/api";

function number(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : new Intl.NumberFormat().format(value);
}

function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`;
}

function resultString(result: Record<string, unknown> | null, key: string): string | null {
  const value = result?.[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function resultNumber(result: Record<string, unknown> | null, key: string): number | null {
  const value = result?.[key];
  return typeof value === "number" ? value : null;
}

function resultStrings(result: Record<string, unknown> | null, key: string): string[] {
  const value = result?.[key];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

export function ReviewContext({
  task,
  attempt,
  checks,
}: {
  task: Task;
  attempt: Attempt | undefined;
  checks: ValidationCheck[];
}) {
  if (!attempt) return null;

  const unvalidated = attempt.validation_mode === "skipped" || attempt.validation_mode === "unresolved";
  const profile = resultString(attempt.result, "profile");
  const promptFingerprint = resultString(attempt.result, "prompt_fingerprint");
  const profileSchemaVersion = resultNumber(attempt.result, "profile_schema_version");
  const skills = resultStrings(attempt.result, "skills");
  const skippedChecks = checks.filter((check) => check.status === "SKIPPED").length;

  return (
    <article className="review-context section-block" aria-label="Review context">
      <div className="section-heading">
        <h2>Review context</h2>
        <span>{unvalidated ? "decision needs caution" : "durable evidence"}</span>
      </div>

      {unvalidated && (
        <div className="review-warning" role="alert">
          <strong>UNVALIDATED</strong>
          <span>{attempt.validation_reason || "No deterministic validation checks were available for this attempt."}</span>
        </div>
      )}

      <div className="review-context__grid">
        <section>
          <h3>Validation</h3>
          <dl className="kv-list">
            <div><dt>Mode</dt><dd>{attempt.validation_mode}</dd></div>
            <div><dt>Checks</dt><dd>{checks.length}{skippedChecks ? ` · ${skippedChecks} skipped` : ""}</dd></div>
            <div><dt>Reason</dt><dd>{attempt.validation_reason || "—"}</dd></div>
          </dl>
        </section>

        <section>
          <h3>Tokens</h3>
          <dl className="kv-list">
            <div><dt>Input</dt><dd>{number(attempt.input_tokens)}</dd></div>
            <div><dt>Cached input</dt><dd>{number(attempt.cached_input_tokens)}</dd></div>
            <div><dt>Output</dt><dd>{number(attempt.output_tokens)}</dd></div>
            <div><dt>Reasoning</dt><dd>{number(attempt.reasoning_tokens)}</dd></div>
            <div><dt>Total</dt><dd>{number(attempt.total_tokens)}</dd></div>
            <div><dt>Cache hit</dt><dd>{percent(attempt.cache_hit_ratio)}</dd></div>
          </dl>
        </section>

        <section>
          <h3>Supervisor</h3>
          <dl className="kv-list">
            <div><dt>Client</dt><dd>{task.supervisor_client || "—"}</dd></div>
            <div><dt>Session</dt><dd className="mono-wrap">{task.supervisor_session_id || "—"}</dd></div>
            <div><dt>Project</dt><dd>{task.project_id || "—"}</dd></div>
          </dl>
        </section>

        <section>
          <h3>Worker profile</h3>
          <dl className="kv-list">
            <div><dt>Profile</dt><dd>{profile || "—"}</dd></div>
            <div><dt>Schema</dt><dd>{profileSchemaVersion ?? "—"}</dd></div>
            <div><dt>Prompt</dt><dd className="mono-wrap">{promptFingerprint ? promptFingerprint.slice(0, 16) : "—"}</dd></div>
            <div><dt>Skills</dt><dd>{skills.length ? skills.join(", ") : "—"}</dd></div>
          </dl>
        </section>
      </div>

      {(attempt.retry_context || attempt.retry_review_ids.length > 0) && (
        <section className="review-context__retry">
          <h3>Retry context</h3>
          <p>{attempt.retry_context || "Structured retry references only."}</p>
          {attempt.retry_review_ids.length > 0 && (
            <small>Review IDs: {attempt.retry_review_ids.join(", ")}</small>
          )}
        </section>
      )}
    </article>
  );
}
