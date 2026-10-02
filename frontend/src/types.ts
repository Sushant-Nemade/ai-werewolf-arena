export interface PlayerInfo {
  id: string;
  name: string;
  persona: string;
  alive: boolean;
  is_human: boolean;
  role: string | null;
}

export interface GameEventData {
  id: number;
  round: number;
  phase: string;
  type: string;
  actor: string | null;
  content: string;
  public: boolean;
  metadata: Record<string, unknown>;
}

export interface PublicState {
  id: string;
  round: number;
  phase: string;
  winner: string | null;
  pending_human: string | null;
  players: PlayerInfo[];
  events: GameEventData[];
}

export interface Trace {
  id: string;
  game_id: string;
  round: number;
  phase: string;
  agent: string;
  task: string;
  model: string;
  prompt_hash: string;
  prompt_chars: number;
  retrieved_memory_ids: string[];
  raw_output: string;
  parsed_output: Record<string, unknown> | null;
  guardrail_attempts: number;
  fail_closed: boolean;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  created_at: string;
}

export interface TracesResponse {
  summary: Record<string, number>;
  traces: Trace[];
}

export interface ConfigInfo {
  provider: string;
  ollama_model: string;
  openai_model: string;
  features: string[];
}

export interface GameSummary {
  id: string;
  provider: string;
  phase: string;
  round: number;
  winner: string | null;
  players: number;
}

export interface HumanActionPayload {
  kind: string;
  statement?: string;
  suspicion?: string | null;
  target?: string;
  reason?: string;
}
