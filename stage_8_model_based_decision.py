"""Stage 8: Model-Based Decision."""

import json
import importlib.util
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent


def load_module(filename, module_name):
    path = PROJECT_DIR / filename

    if not path.is_file():
        raise FileNotFoundError(
            f"Required project file not found: {filename}"
        )

    spec = importlib.util.spec_from_file_location(
        module_name, path
    )

    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {filename}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


model_module = load_module(
    "07_model_boundary_v2.py",
    "stage8_model_boundary"
)

behaviour = load_module(
    "stage_4_behaviour_specification_and_structured_decision.py",
    "stage8_behaviour"
)

policy = load_module(
    "stage_5_tool_validation_and_policy.py",
    "stage8_tool_policy"
)


SYSTEM_PROMPT = """
You are a decision component for a public-news curation agent.

Approved tools:
- newsdata
- gnews
- google_news_rss

Rules:
- Use public news only.
- Select an approved tool for news-search requests.
- Ask for clarification if the topic is missing.
- Do not perform purchases or financial actions.
- Return one valid JSON object without Markdown.
- Include a non-empty reason in every decision.

For a tool decision, use:
{
  "action": "tool",
  "tool": "google_news_rss",
  "args": {
    "query": "Artificial Intelligence",
    "max_results": 5
  },
  "reason": "Search for public news."
}

Allowed actions: tool, ask_user, escalate.
"""


def create_model_decision(user_query, model_client=None):
    if not isinstance(user_query, str) or not user_query.strip():
        return {
            "decision": {
                "action": "ask_user",
                "reason": "Please provide a news topic."
            },
            "valid": True,
            "message": "A news topic is required."
        }

    if model_client is None:
        model_client = model_module.GroqModelClient()

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": (
                "Choose an action for this request:\n"
                + user_query.strip()
            )
        }
    ]

    raw_response = model_client.generate(messages)

    try:
        decision = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError):
        return {
            "decision": None,
            "valid": False,
            "message": "The model response was not valid JSON."
        }

    valid, message = behaviour.validate_decision(decision)

    if not valid:
        return {
            "decision": decision,
            "valid": False,
            "message": "Decision validation failed: " + message
        }

    if decision["action"] == "tool":
        valid, message = policy.validate_tool_request(decision)

        if not valid:
            return {
                "decision": decision,
                "valid": False,
                "message": (
                    "Tool policy rejected the decision: " + message
                )
            }

    return {
        "decision": decision,
        "valid": True,
        "message": "Decision passed validation."
    }
