import { Chess } from "https://cdn.jsdelivr.net/npm/chess.js@1.4.0/+esm";
import { Chessboard, FEN } from "https://cdn.jsdelivr.net/npm/cm-chessboard@8.7.11/+esm";

const API_BASE = window.API_BASE ?? "";
const ASSETS_URL = "https://cdn.jsdelivr.net/npm/cm-chessboard@8.7.11/assets/";

const form = document.querySelector("#load-form");
const urlInput = document.querySelector("#lichess-url");
const pgnInput = document.querySelector("#pgn-input");
const statusEl = document.querySelector("#status");
const stage = document.querySelector("#stage");
const playersEl = document.querySelector("#players");
const infoEl = document.querySelector("#game-info");
const movesEl = document.querySelector("#moves");
const plyLabel = document.querySelector("#ply-label");
const boardEl = document.querySelector("#board");

let board;
let fens = [];
let sans = [];
let ply = 0;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function positionsFromPgn(pgn) {
  const chess = new Chess();
  try {
    chess.loadPgn(pgn, { strict: false });
  } catch (err) {
    throw new Error(err.message || "could not parse pgn");
  }
  const history = chess.history();
  if (history.length === 0) {
    throw new Error("pgn has no moves");
  }
  chess.reset();
  const nextFens = [chess.fen()];
  for (const san of history) {
    chess.move(san);
    nextFens.push(chess.fen());
  }
  return { fens: nextFens, sans: history };
}

function renderMoves() {
  movesEl.innerHTML = "";
  for (let i = 0; i < sans.length; i += 2) {
    const row = document.createElement("li");
    const num = document.createElement("span");
    num.textContent = `${i / 2 + 1}.`;
    row.append(num, moveButton(i), moveButton(i + 1));
    movesEl.append(row);
  }
}

function moveButton(index) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "move";
  if (!sans[index]) {
    btn.disabled = true;
    btn.textContent = "";
    return btn;
  }
  btn.textContent = sans[index];
  btn.classList.toggle("active", ply === index + 1);
  btn.addEventListener("click", () => showPly(index + 1));
  return btn;
}

function showPly(next) {
  ply = Math.max(0, Math.min(next, fens.length - 1));
  board.setPosition(fens[ply]);
  plyLabel.textContent = `${ply} / ${fens.length - 1}`;
  renderMoves();
}

function ensureBoard() {
  if (board) {
    return;
  }
  board = new Chessboard(boardEl, {
    position: FEN.start,
    assetsUrl: ASSETS_URL,
    style: {
      animationDuration: 180,
    },
  });
}

function showGame(game) {
  const parsed = positionsFromPgn(game.pgn);
  fens = parsed.fens;
  sans = parsed.sans;
  ply = 0;
  playersEl.textContent = `${game.white || "White"} vs ${game.black || "Black"}`;
  const bits = [game.result, game.id && `id ${game.id}`, game.source].filter(Boolean);
  infoEl.textContent = bits.join(" · ");
  stage.hidden = false;
  ensureBoard();
  showPly(0);
}

async function loadGame(event) {
  event.preventDefault();
  const lichessUrl = urlInput.value.trim();
  const pgn = pgnInput.value.trim();
  if (!lichessUrl && !pgn) {
    setStatus("Enter a Lichess URL or paste a PGN.", true);
    return;
  }

  setStatus("Loading…");
  const body = lichessUrl ? { lichessUrl } : { pgn };
  try {
    const response = await fetch(`${API_BASE}/games`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    showGame(data);
    setStatus("Loaded.");
  } catch (err) {
    setStatus(err.message, true);
  }
}

form.addEventListener("submit", loadGame);
document.querySelector("#btn-start").addEventListener("click", () => showPly(0));
document.querySelector("#btn-prev").addEventListener("click", () => showPly(ply - 1));
document.querySelector("#btn-next").addEventListener("click", () => showPly(ply + 1));
document.querySelector("#btn-end").addEventListener("click", () => showPly(fens.length - 1));

document.addEventListener("keydown", (event) => {
  if (stage.hidden) {
    return;
  }
  if (event.key === "ArrowLeft") {
    showPly(ply - 1);
  }
  if (event.key === "ArrowRight") {
    showPly(ply + 1);
  }
});
