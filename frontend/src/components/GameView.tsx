import { useEffect, useMemo, useRef, useState } from "react";
import { connectSocket, fetchState, fetchTraces, submitAction } from "../api";
import type { HumanActionPayload, PublicState, Trace } from "../types";
import TracePanel from "./TracePanel";

const PHASE_LABELS: Record<string, string> = {
  setup: "Setup",
  night: "Night",
  day_discussion: "Day · Discussion",
  day_vote: "Day · Vote",
  game_over: "Game Over",
};

const ROLE_CLASSES: Record<string, string> = {
  werewolf: "role-wolf",
  seer: "role-seer",
  villager: "role-villager",
};

export default function GameView({ gameId }: { gameId: string }) {
  const [state, setState] = useState<PublicState | null>(null);
  const [traces, setTraces] = useState<Trace[]>([]);
  const [statement, setStatement] = useState("");
  const [suspicion, setSuspicion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let mounted = true;
    const load = () => {
      fetchState(gameId)
        .then((s) => mounted && setState(s))
        .catch(() => undefined);
      fetchTraces(gameId)
        .then((t) => mounted && setTraces(t.traces))
        .catch(() => undefined);
    };
    load();
    const ws = connectSocket(gameId, (msg) => setState(msg.state));
    const timer = window.setInterval(load, 3000); // fallback if the socket drops
    return () => {
      mounted = false;
      ws.close();
      window.clearInterval(timer);
    };
  }, [gameId]);

  const eventCount = state?.events.length ?? 0;
  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight });
  }, [eventCount]);

  const me = useMemo(() => state?.players.find((p) => p.is_human) ?? null, [state]);

  if (!state) return <p className="muted loading">Loading game…</p>;

  const nameOf = (id: string | null | undefined): string =>
    state.players.find((p) => p.id === id)?.name ?? "—";

  const send = async (payload: HumanActionPayload) => {
    setError(null);
    try {
      await submitAction(gameId, payload);
      setStatement("");
      setSuspicion("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "action rejected");
    }
  };

  const aliveOthers = state.players.filter((p) => p.alive && p.id !== me?.id);
  const pending = state.pending_human;

  return (
    <main className="game">
      <div className="game-header">
        <div>
          <span className="round-label">Round {state.round}</span>
          <span className={`phase-badge phase-${state.phase}`}>
            {PHASE_LABELS[state.phase] ?? state.phase}
          </span>
        </div>
        {state.winner && (
          <div className={`winner-banner ${state.winner}`}>
            The {state.winner} win the game
          </div>
        )}
      </div>

      <div className="game-layout">
        <section className="players">
          <h2>Players</h2>
          {state.players.map((p) => (
            <div key={p.id} className={`player ${p.alive ? "" : "dead"}`}>
              <div className="player-top">
                <span className="player-name">{p.name}</span>
                {p.is_human && <span className="badge you">you</span>}
                {p.role ? (
                  <span className={`role ${ROLE_CLASSES[p.role] ?? ""}`}>{p.role}</span>
                ) : (
                  <span className="role role-hidden">hidden</span>
                )}
              </div>
              <div className="player-persona">{p.persona}</div>
            </div>
          ))}
        </section>

        <section className="board">
          <h2>Village feed</h2>
          <div className="transcript" ref={transcriptRef}>
            {state.events.map((e) => (
              <div key={e.id} className={`event event-${e.type}`}>
                <span className="event-round">r{e.round}</span>
                {e.actor && <span className="event-actor">{nameOf(e.actor)}</span>}
                <span className="event-content">{e.content}</span>
              </div>
            ))}
          </div>

          {pending && me?.alive && (
            <div className="action-bar">
              {pending === "speech" && (
                <>
                  <textarea
                    value={statement}
                    onChange={(e) => setStatement(e.target.value)}
                    placeholder="Address the village…"
                    rows={2}
                  />
                  <div className="action-row">
                    <select value={suspicion} onChange={(e) => setSuspicion(e.target.value)}>
                      <option value="">accuse nobody</option>
                      {aliveOthers.map((p) => (
                        <option key={p.id} value={p.id}>
                          suspect {p.name}
                        </option>
                      ))}
                    </select>
                    <button
                      className="primary"
                      disabled={!statement.trim()}
                      onClick={() =>
                        send({ kind: "speech", statement, suspicion: suspicion || null })
                      }
                    >
                      Speak
                    </button>
                  </div>
                </>
              )}
              {pending === "vote" && (
                <div className="action-row wrap">
                  <span className="muted">Vote to eliminate:</span>
                  {aliveOthers.map((p) => (
                    <button key={p.id} className="secondary" onClick={() => send({ kind: "vote", target: p.id })}>
                      {p.name}
                    </button>
                  ))}
                  <button className="ghost" onClick={() => send({ kind: "vote", target: "abstain" })}>
                    abstain
                  </button>
                </div>
              )}
              {(pending === "night_kill" || pending === "night_inspect") && (
                <div className="action-row wrap">
                  <span className="muted">
                    {pending === "night_kill" ? "Choose your victim:" : "Choose who to inspect:"}
                  </span>
                  {aliveOthers.map((p) => (
                    <button
                      key={p.id}
                      className="secondary"
                      onClick={() =>
                        send({ kind: pending === "night_kill" ? "kill" : "inspect", target: p.id })
                      }
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              )}
              {error && <p className="error">{error}</p>}
            </div>
          )}
        </section>

        <aside className="inspector">
          <h2>Decision inspector</h2>
          <p className="muted small">
            Every agent decision, traced: prompt hash, retrieved memories, raw model output,
            guardrail attempts and latency.
          </p>
          <TracePanel traces={traces} nameOf={nameOf} />
        </aside>
      </div>
    </main>
  );
}
