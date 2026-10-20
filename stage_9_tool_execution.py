"""Stage 9: Validated News Tool Execution."""

import importlib.util
import os
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


def execute_tool_decision(decision, api_keys=None):
    """Validate a decision before executing an approved news tool."""

    behaviour = load_module(
        "stage_4_behaviour_specification_and_structured_decision.py",
        "stage9_behaviour"
    )

    valid, message = behaviour.validate_decision(decision)

    if not valid:
        return {
            "success": False,
            "articles": [],
            "message": "Decision rejected: " + str(message)
        }

    if decision.get("action") != "tool":
        return {
            "success": False,
            "articles": [],
            "message": "No tool execution requested."
        }

    policy = load_module(
        "stage_5_tool_validation_and_policy.py",
        "stage9_policy"
    )

    valid, message = policy.validate_tool_request(decision)

    if not valid:
        return {
            "success": False,
            "articles": [],
            "message": "Tool policy rejected request: " + str(message)
        }

    news_tools = load_module(
        "stage_2_news_tools.py",
        "stage9_news_tools"
    )

    tool_name = decision["tool"]
    args = decision["args"]
    query = args["query"]
    max_results = args.get("max_results", 5)
    api_keys = api_keys or {}

    if tool_name == "google_news_rss":
        articles = news_tools.get_google_news_rss(
            query=query,
            max_results=max_results
        )

    elif tool_name == "newsdata":
        api_key = (
            api_keys.get("newsdata")
            or os.environ.get("NEWSDATA_API_KEY")
        )

        if not api_key:
            return {
                "success": False,
                "articles": [],
                "message": "NewsData API key is not configured."
            }

        articles = news_tools.get_newsdata_news(
            query=query,
            api_key=api_key,
            max_results=max_results
        )

    elif tool_name == "gnews":
        api_key = (
            api_keys.get("gnews")
            or os.environ.get("GNEWS_API_KEY")
        )

        if not api_key:
            return {
                "success": False,
                "articles": [],
                "message": "GNews API key is not configured."
            }

        articles = news_tools.get_gnews_news(
            query=query,
            api_key=api_key,
            max_results=max_results
        )

    else:
        return {
            "success": False,
            "articles": [],
            "message": "Unsupported news tool."
        }

    if not isinstance(articles, list):
        return {
            "success": False,
            "articles": [],
            "message": "News tool returned an invalid result."
        }

    required_fields = ("title", "url")

    for article in articles:
        if not isinstance(article, dict):
            return {
                "success": False,
                "articles": [],
                "message": "News tool returned an invalid article."
            }

        if any(
            not isinstance(article.get(field), str)
            or not article[field].strip()
            for field in required_fields
        ):
            return {
                "success": False,
                "articles": [],
                "message": "An article is missing a valid title or URL."
            }

    return {
        "success": True,
        "tool": tool_name,
        "query": query,
        "count": len(articles),
        "articles": articles,
        "message": "News tool executed successfully."
    }
