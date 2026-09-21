import json
import re
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# Local / same warm container only. Replace with DynamoDB later.
GAMES = {}

LICHESS_EXPORT = "https://lichess.org/game/export/{game_id}"
USER_AGENT = "chess-master/0.1 (lichess pgn import)"
GAME_ID_RE = re.compile(r"^[A-Za-z0-9]{8}$")
HEADER_RE = re.compile(r'^\[(\w+)\s+"(.*)"\]\s*$', re.MULTILINE)


class ClientError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def lambda_handler(event, context):
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    resource = event.get("resource") or event.get("path") or ""

    try:
        if method == "POST" and resource.rstrip("/").endswith("/games"):
            return _create_game(event)
        if method == "GET" and "/games/" in resource:
            return _get_game(event)
        return _response(404, {"error": "not found"})
    except ClientError as exc:
        return _response(exc.status, {"error": exc.message})


def _create_game(event):
    payload = _json_body(event)
    lichess_url = (payload.get("lichessUrl") or payload.get("lichess_url") or "").strip()
    pgn = (payload.get("pgn") or "").strip()

    if lichess_url:
        game_id = parse_lichess_game_id(lichess_url)
        pgn = fetch_lichess_pgn(game_id)
        source = "lichess"
    elif pgn:
        game_id = None
        source = "pgn"
    else:
        raise ClientError(400, "provide lichessUrl or pgn")

    headers = parse_pgn_headers(pgn)
    stored = {
        "id": uuid.uuid4().hex[:8],
        "status": "imported",
        "source": source,
        "lichessUrl": lichess_url or None,
        "lichessGameId": game_id,
        "white": headers.get("White"),
        "black": headers.get("Black"),
        "result": headers.get("Result"),
        "pgn": pgn,
    }
    GAMES[stored["id"]] = stored
    return _response(201, stored)


def _get_game(event):
    params = event.get("pathParameters") or {}
    game_id = params.get("id")
    if not game_id:
        raise ClientError(400, "missing game id")
    game = GAMES.get(game_id)
    if not game:
        raise ClientError(404, "game not found")
    return _response(200, game)


def parse_lichess_game_id(url):
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower().removeprefix("www.")
    if host != "lichess.org":
        raise ClientError(400, "url must be on lichess.org")

    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        raise ClientError(400, "lichess url is missing a game id")

    if len(parts) >= 3 and parts[0] == "game" and parts[1] == "export":
        candidate = parts[2]
    else:
        candidate = parts[0]

    candidate = candidate.removesuffix(".pgn")[:8]
    if not GAME_ID_RE.match(candidate):
        raise ClientError(400, "could not parse lichess game id")
    return candidate


def fetch_lichess_pgn(game_id):
    request = Request(
        LICHESS_EXPORT.format(game_id=game_id),
        headers={
            "Accept": "application/x-chess-pgn",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            pgn = response.read().decode("utf-8").strip()
    except HTTPError as exc:
        if exc.code == 404:
            raise ClientError(404, "lichess game not found") from exc
        raise ClientError(502, "lichess export failed") from exc
    except URLError as exc:
        raise ClientError(502, "could not reach lichess") from exc

    if not pgn or not (pgn.startswith("[") or pgn[:1].isdigit()):
        raise ClientError(502, "lichess did not return pgn")
    return pgn


def parse_pgn_headers(pgn):
    return {match.group(1): match.group(2) for match in HEADER_RE.finditer(pgn)}


def _json_body(event):
    raw = event.get("body")
    if not raw:
        return {}
    if event.get("isBase64Encoded"):
        raise ClientError(400, "base64 bodies are not supported")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClientError(400, "body must be json") from exc
    if not isinstance(data, dict):
        raise ClientError(400, "body must be a json object")
    return data


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
