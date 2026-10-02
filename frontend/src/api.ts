import type {
  ConfigInfo,
  GameSummary,
  HumanActionPayload,
  PublicState,
  TracesResponse,
} from "./types";

export interface CreateGameOptions {
  num_players: number;
  human_name?: string;
  autoplay: boolean;
  seed?: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${init?.method ?? "GET"} ${path} failed (${res.status}): ${detail}`);
  }
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const fetchConfig = () => request<ConfigInfo>("/api/config");
export const listGames = () => request<{ games: GameSummary[] }>("/api/games");
export const fetchState = (id: string) => request<PublicState>(`/api/games/${id}`);
export const fetchTraces = (id: string) => request<TracesResponse>(`/api/games/${id}/traces`);
export const createGame = (opts: CreateGameOptions) =>
  request<{ id: string }>("/api/games", json(opts));
export const submitAction = (id: string, action: HumanActionPayload) =>
  request<{ accepted: boolean }>(`/api/games/${id}/actions`, json(action));

export interface WsMessage {
  type: "state" | "event";
  state: PublicState;
}

export function connectSocket(gameId: string, onMessage: (msg: WsMessage) => void): WebSocket {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/games/${gameId}`);
  ws.onmessage = (e) => onMessage(JSON.parse(e.data) as WsMessage);
  return ws;
}
