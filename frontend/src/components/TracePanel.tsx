import type { Trace } from "../types";

interface Props {
  traces: Trace[];
  nameOf: (id: string) => string;
}

export default function TracePanel({ traces, nameOf }: Props) {
  if (traces.length === 0) {
    return <p className="muted">No decisions recorded yet — they appear here as agents act.</p>;
  }
  return (
    <div className="traces">
      {[...traces].reverse().map((t) => (
        <details key={t.id} className={`trace ${t.fail_closed ? "trace-failed" : ""}`}>
          <summary>
            <span className="trace-agent">{nameOf(t.agent)}</span>
            <span className="trace-task">{t.task}</span>
            <span className="trace-meta">
              r{t.round} · {Math.round(t.latency_ms)}ms · {t.guardrail_attempts}{" "}
              attempt{t.guardrail_attempts > 1 ? "s" : ""}
            </span>
            {t.fail_closed && <span className="badge danger">fail-closed</span>}
          </summary>
          <div className="trace-body">
            <dl>
              <dt>Model</dt>
              <dd>{t.model}</dd>
              <dt>Prompt</dt>
              <dd>
                hash {t.prompt_hash} · {t.prompt_chars} chars · {t.prompt_tokens} +{" "}
                {t.completion_tokens} tokens
              </dd>
              <dt>Retrieved memories</dt>
              <dd>
                {t.retrieved_memory_ids.length > 0 ? t.retrieved_memory_ids.join(", ") : "none"}
              </dd>
              <dt>Parsed output</dt>
              <dd>
                <code>{JSON.stringify(t.parsed_output)}</code>
              </dd>
              <dt>Raw output</dt>
              <dd>
                <pre>{t.raw_output}</pre>
              </dd>
            </dl>
          </div>
        </details>
      ))}
    </div>
  );
}
