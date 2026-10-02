import { useEffect, useState } from "react";
import { createGame, fetchConfig } from "../api";
import type { ConfigInfo } from "../types";

const FEATURES = [
  {
    title: "Multi-agent orchestration",
    body: "Seven agents with hidden roles, distinct personas and private knowledge play a full game of Werewolf — night kills, seer inspections, debate and votes.",
  },
  {
    title: "Episodic memory (RAG)",
    body: "Every event is written into each agent's memory. Before acting, agents retrieve the most relevant past events and reason over them.",
  },
  {
    title: "Guardrails, fail-closed",
    body: "Model output is extracted, schema-validated and domain-checked with bounded retries. Invalid behaviour falls back to a safe action and is recorded.",
  },
  {
    title: "Decision tracing",
    body: "Every decision is inspectable: prompt hash, retrieved memories, raw output, latency and guardrail attempts — live in the inspector panel.",
  },
];

export default function Lobby({ onOpen }: { onOpen: (id: string) => void }) {
  const [config, setConfig] = useState<ConfigInfo | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchConfig().then(setConfig).catch(() => undefined);
  }, []);

  const start = async (human: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const res = await createGame({
        num_players: 7,
        human_name: human ? name.trim() || "You" : undefined,
        autoplay: true,
        seed: Math.floor(Math.random() * 1_000_000),
      });
      onOpen(res.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to start game");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="lobby">
      <section className="hero">
        <p className="eyebrow">Multi-agent LLM social deduction</p>
        <h1>
          Seven agents enter the village.
          <br />
          Two of them are wolves.
        </h1>
        <p className="lede">
          Autonomous LLM agents deceive, deduce, debate and vote their way through a full game of
          Werewolf. Watch an all-AI match unfold live — or take a seat and try to out-reason them.
        </p>
        <div className="lobby-actions">
          <button className="primary" disabled={busy} onClick={() => start(false)}>
            Spectate an AI arena
          </button>
          <div className="join-row">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              maxLength={24}
            />
            <button className="secondary" disabled={busy} onClick={() => start(true)}>
              Join as a player
            </button>
          </div>
        </div>
        {error && <p className="error">{error}</p>}
        {config && (
          <p className="provider-badge">
            Active provider: <code>{config.provider}</code>
            {config.provider === "mock" && (
              <span className="muted"> — deterministic offline demo mode; set ARENA_LLM_PROVIDER=ollama for real models</span>
            )}
          </p>
        )}
      </section>

      <section className="features">
        {FEATURES.map((f) => (
          <article key={f.title} className="feature-card">
            <h3>{f.title}</h3>
            <p>{f.body}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
