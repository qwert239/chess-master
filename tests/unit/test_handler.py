import json
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from src import app


SAMPLE_PGN = """[Event "Casual game"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 1-0
"""


@pytest.fixture(autouse=True)
def clear_games():
    app.GAMES.clear()
    yield
    app.GAMES.clear()


def test_parse_lichess_game_id():
    assert app.parse_lichess_game_id("https://lichess.org/abcdefgh") == "abcdefgh"
    assert app.parse_lichess_game_id("https://www.lichess.org/abcdefgh/white") == "abcdefgh"
    assert app.parse_lichess_game_id("https://lichess.org/game/export/abcdefgh") == "abcdefgh"


def test_parse_lichess_game_id_rejects_other_hosts():
    with pytest.raises(app.ClientError) as exc:
        app.parse_lichess_game_id("https://chess.com/abcdefgh")
    assert exc.value.status == 400


def test_create_game_from_pgn():
    event = {
        "httpMethod": "POST",
        "resource": "/games",
        "body": json.dumps({"pgn": SAMPLE_PGN}),
    }
    ret = app.lambda_handler(event, None)
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 201
    assert data["status"] == "imported"
    assert data["source"] == "pgn"
    assert data["white"] == "Alice"
    assert data["black"] == "Bob"
    assert data["pgn"].startswith("[Event")
    assert data["id"] in app.GAMES


def test_get_game_after_create():
    created = json.loads(
        app.lambda_handler(
            {
                "httpMethod": "POST",
                "resource": "/games",
                "body": json.dumps({"pgn": SAMPLE_PGN}),
            },
            None,
        )["body"]
    )
    ret = app.lambda_handler(
        {
            "httpMethod": "GET",
            "resource": "/games/{id}",
            "pathParameters": {"id": created["id"]},
        },
        None,
    )
    data = json.loads(ret["body"])
    assert ret["statusCode"] == 200
    assert data["id"] == created["id"]
    assert data["pgn"] == created["pgn"]


def test_get_game_missing():
    ret = app.lambda_handler(
        {
            "httpMethod": "GET",
            "resource": "/games/{id}",
            "pathParameters": {"id": "missing1"},
        },
        None,
    )
    assert ret["statusCode"] == 404


@patch("src.app.urlopen")
def test_create_game_from_lichess_url(mock_urlopen):
    mock_urlopen.return_value.__enter__.return_value.read.return_value = SAMPLE_PGN.encode("utf-8")
    ret = app.lambda_handler(
        {
            "httpMethod": "POST",
            "resource": "/games",
            "body": json.dumps({"lichessUrl": "https://lichess.org/abcdefgh"}),
        },
        None,
    )
    data = json.loads(ret["body"])
    assert ret["statusCode"] == 201
    assert data["source"] == "lichess"
    assert data["lichessGameId"] == "abcdefgh"
    assert data["white"] == "Alice"


@patch("src.app.urlopen")
def test_lichess_not_found(mock_urlopen):
    mock_urlopen.side_effect = HTTPError(
        url="https://lichess.org/game/export/abcdefgh",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=None,
    )
    ret = app.lambda_handler(
        {
            "httpMethod": "POST",
            "resource": "/games",
            "body": json.dumps({"lichessUrl": "https://lichess.org/abcdefgh"}),
        },
        None,
    )
    assert ret["statusCode"] == 404
