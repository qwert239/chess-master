import os

import boto3
import pytest
import requests

SAMPLE_PGN = """[White "Alice"]
[Black "Bob"]
[Result "*"]

1. e4 e5 *
"""


class TestApiGateway:
    @pytest.fixture()
    def api_gateway_url(self):
        stack_name = os.environ.get("AWS_SAM_STACK_NAME")
        if stack_name is None:
            raise ValueError("Set AWS_SAM_STACK_NAME to the deployed stack name")

        client = boto3.client("cloudformation")
        try:
            response = client.describe_stacks(StackName=stack_name)
        except Exception as exc:
            raise Exception(f"Cannot find stack {stack_name}") from exc

        outputs = response["Stacks"][0]["Outputs"]
        api_outputs = [output for output in outputs if output["OutputKey"] == "GamesApi"]
        if not api_outputs:
            raise KeyError(f"GamesApi not found in stack {stack_name}")
        return api_outputs[0]["OutputValue"]

    def test_create_and_get_game(self, api_gateway_url):
        create = requests.post(api_gateway_url, json={"pgn": SAMPLE_PGN}, timeout=10)
        assert create.status_code == 201
        game_id = create.json()["id"]

        fetched = requests.get(f"{api_gateway_url.rstrip('/')}/{game_id}", timeout=10)
        assert fetched.status_code == 200
        assert fetched.json()["white"] == "Alice"
