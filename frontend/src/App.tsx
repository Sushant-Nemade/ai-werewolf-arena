import { useState } from "react";
import Lobby from "./components/Lobby";
import GameView from "./components/GameView";

export default function App() {
  const [gameId, setGameId] = useState<string | null>(null);

  return (
    <div className="app">
      <header className="topbar">
        <button className="brand" onClick={() => setGameId(null)}>
          <span className="brand-dot" />
          AI Werewolf Arena
        </button>
        {gameId && (
          <button className="ghost" onClick={() => setGameId(null)}>
            ← Back to lobby
          </button>
        )}
      </header>
      {gameId ? <GameView gameId={gameId} /> : <Lobby onOpen={setGameId} />}
    </div>
  );
}
