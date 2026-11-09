
"""Stage 10: Integration and Tracing."""

import importlib.util
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

APPROVED_TOOLS = {
    "newsdata",
    "gnews",
    "google_news_rss"
}


def load_module(filename, module_name):
    file_path = PROJECT_DIR / filename

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Required file not found: {filename}"
        )

    spec = importlib.util.spec_from_file_location(
        module_name, file_path
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not load module: {filename}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def run_integrated_agent(
    user_query,
    model_client=None,
    api_keys=None
):
    trace = []

    def record(step, status, message):
        trace.append({
            "step": step,
            "status": status,
            "message": message
        })

    def finish(
        status,
        message,
        decision=None,
        selected_tool=None,
        articles=None
    ):
        record("FINAL_STATE", status, message)

        return {
            "status": status,
            "message": message,
            "decision": decision,
            "selected_tool": selected_tool,
            "articles": articles or [],
            "trace": trace
        }

    try:
        record("START", "RUNNING", "Integrated agent started.")

        if not isinstance(user_query, str) or not user_query.strip():
            return finish(
                "FAILED_SAFELY",
                "User query must not be empty."
            )

        record("QUERY_VALIDATION", "PASSED", "User query is valid.")

        stage8 = load_module(
            "stage_8_model_based_decision.py",
            "stage8"
        )

        decision_result = stage8.create_model_decision(
            user_query,
            model_client=model_client
        )

        if not isinstance(decision_result, dict):
            return finish(
                "FAILED_SAFELY",
                "Model returned an invalid decision."
            )

        if not decision_result.get("valid", False):
            return finish(
                "FAILED_SAFELY",
                "Model decision did not pass validation.",
                decision=decision_result
            )

        decision = decision_result.get("decision")

        if not isinstance(decision, dict):
            return finish(
                "FAILED_SAFELY",
                "Decision structure is invalid.",
                decision=decision_result
            )

        action = decision.get("action")

        if action == "ask_user":
            return finish(
                "NEEDS_USER_INPUT",
                "More information is required.",
                decision=decision
            )

        if action == "escalate":
            return finish(
                "ESCALATED",
                "The request requires human review.",
                decision=decision
            )

        if action != "tool":
            return finish(
                "FAILED_SAFELY",
                "Unsupported decision action.",
                decision=decision
            )

        selected_tool = decision.get("tool")

        if selected_tool not in APPROVED_TOOLS:
            return finish(
                "FAILED_SAFELY",
                "Selected tool is not approved.",
                decision=decision,
                selected_tool=selected_tool
            )

        record(
            "MODEL_DECISION",
            "PASSED",
            "Approved tool selected: " + selected_tool
        )

        stage9 = load_module(
            "stage_9_tool_execution.py",
            "stage9"
        )

        execution_result = stage9.execute_tool_decision(
            decision,
            api_keys=api_keys
        )

        if not isinstance(execution_result, dict):
            return finish(
                "FAILED_SAFELY",
                "Tool returned an invalid result.",
                decision=decision,
                selected_tool=selected_tool
            )

        if execution_result.get("success") is not True:
            return finish(
                "FAILED_SAFELY",
                execution_result.get(
                    "message",
                    "Tool execution failed."
                ),
                decision=decision,
                selected_tool=selected_tool
            )

        articles = execution_result.get("articles")

        if not isinstance(articles, list):
            return finish(
                "FAILED_SAFELY",
                "Tool result does not contain an article list.",
                decision=decision,
                selected_tool=selected_tool
            )

        valid_articles = []

        for article in articles:
            if not isinstance(article, dict):
                continue

            title = article.get("title")
            url = article.get("url", "")

            if (
                isinstance(title, str)
                and title.strip()
                and isinstance(url, str)
                and url.startswith(("https://", "http://"))
            ):
                item = article.copy()
                item.setdefault("source", selected_tool)
                valid_articles.append(item)

        record(
            "RESULT_VALIDATION",
            "PASSED",
            f"Validated {len(valid_articles)} articles."
        )

        return finish(
            "COMPLETED",
            "Integrated agent completed successfully.",
            decision=decision,
            selected_tool=selected_tool,
            articles=valid_articles
        )

    except Exception as error:
        record(
            "ERROR",
            "FAILED",
            type(error).__name__ + ": " + str(error)
        )

        return finish(
            "FAILED_SAFELY",
            "The agent stopped safely after an execution error."
        )
