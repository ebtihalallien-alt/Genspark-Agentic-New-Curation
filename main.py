import os
import importlib.util
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

# Load API keys securely from Google Colab Secrets.
# No API key values are printed or stored in this file.
try:
    from google.colab import userdata

    for key_name in (
        "GROQ_API_KEY",
        "NEWSDATA_API_KEY",
        "GNEWS_API_KEY"
    ):
        try:
            value = userdata.get(key_name)
            if value:
                os.environ[key_name] = value
        except Exception:
            pass
except ImportError:
    # Outside Google Colab, configure the environment variables
    # before running this script.
    pass

api_keys = {
    "newsdata": os.environ.get("NEWSDATA_API_KEY"),
    "gnews": os.environ.get("GNEWS_API_KEY")
}


def load_module(filename, module_name):
    path = PROJECT_DIR / filename

    if not path.is_file():
        raise FileNotFoundError(f"Missing project file: {filename}")

    spec = importlib.util.spec_from_file_location(module_name, path)

    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module: {filename}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_project(user_query="Artificial Intelligence"):
    print("=" * 55)
    print("GENSPARK AGENTIC NEWS CURATION SYSTEM")
    print("=" * 55)

    if not os.environ.get("GROQ_API_KEY"):
        raise ValueError(
            "GROQ_API_KEY is not configured. "
            "Add it to Colab Secrets or environment variables."
        )

    stage2 = load_module(
        "stage_2_news_tools.py",
        "main_stage2"
    )
    stage10 = load_module(
        "stage_10_integration_and_tracing.py",
        "main_stage10"
    )
    stage11 = load_module(
        "stage_11_news_curation.py",
        "main_stage11"
    )

    # Step 1: Run the integrated AI agent.
    print("\nSTEP 1: AI AGENT DECISION AND TOOL EXECUTION")

    agent_result = stage10.run_integrated_agent(
        user_query,
        api_keys=api_keys
    )

    print("Agent status:", agent_result["status"])

    for item in agent_result["trace"]:
        print(item)

    if agent_result["status"] != "COMPLETED":
        print("\nAgent did not complete successfully.")
        return agent_result

    decision = agent_result.get("decision") or {}
    selected_tool = decision.get("tool")

    if decision.get("action") != "tool":
        print("The agent did not select a news retrieval tool.")
        return agent_result

    # Step 2: Collect news from the three sources.
    print("\nSTEP 2: COLLECT NEWS FROM THREE SOURCES")

    collected = {
        "newsdata": [],
        "gnews": [],
        "google_news_rss": []
    }

    if selected_tool not in collected:
        raise ValueError(
            f"Unsupported selected news tool: {selected_tool}"
        )

    collected[selected_tool] = agent_result.get("articles", [])

    collectors = {
        "newsdata": lambda: stage2.get_newsdata_news(
            query=user_query,
            api_key=api_keys["newsdata"],
            max_results=3
        ),
        "gnews": lambda: stage2.get_gnews_news(
            query=user_query,
            api_key=api_keys["gnews"],
            max_results=3
        ),
        "google_news_rss": lambda: stage2.get_google_news_rss(
            query=user_query,
            max_results=3
        )
    }

    for source, collect_function in collectors.items():
        if source == selected_tool:
            continue

        try:
            if source in ("newsdata", "gnews") and not api_keys[source]:
                print(source, ": API key unavailable")
                continue

            collected[source] = collect_function()
            print(source, ":", len(collected[source]), "articles")

        except Exception as error:
            print(source, "collection failed:", str(error))

    # Step 3: Merge articles.
    print("\nSTEP 3: MERGE ARTICLES")

    merged_articles = stage11.merge_articles(
        collected["newsdata"],
        collected["gnews"],
        collected["google_news_rss"]
    )

    print("Total collected:", len(merged_articles))

    # Step 4: Remove duplicates.
    print("\nSTEP 4: DUPLICATE REMOVAL")

    unique_articles = stage11.remove_duplicates(merged_articles)

    print("After duplicate removal:", len(unique_articles))
    print(
        "Duplicates removed:",
        len(merged_articles) - len(unique_articles)
    )

    # Step 5: Rank articles.
    print("\nSTEP 5: RELEVANCE RANKING")

    ranked_articles = stage11.rank_articles(
        unique_articles,
        user_query
    )
    print("Ranking completed.")

    # Step 6: Review article structure.
    print("\nSTEP 6: ARTICLE REVIEW")

    review_result = stage11.review_articles(ranked_articles)
    approved = review_result["approved"]
    rejected = review_result["rejected"]

    print("Approved:", len(approved))
    print("Rejected:", len(rejected))

    # Step 7: Save articles in SQLite.
    print("\nSTEP 7: SQLITE DATABASE")

    db_path = str(PROJECT_DIR / "news_database.db")

    database_result = stage11.save_articles_sqlite(
        approved,
        db_path
    )
    print("Database result:", database_result)

    # Step 8: Generate the final digest.
    print("\nSTEP 8: FINAL NEWS DIGEST")

    digest = stage11.generate_news_digest(
        approved,
        limit=5
    )

    for index, article in enumerate(digest, start=1):
        print(f"\n{index}. {article['title']}")
        print("Source:", article["source"])
        print("Relevance:", article["relevance_score"])
        print("URL:", article["url"])

    print("\n" + "=" * 55)
    print("PROJECT EXECUTION FINISHED")
    print("=" * 55)

    return {
        "agent": agent_result,
        "collected": collected,
        "merged_count": len(merged_articles),
        "unique_count": len(unique_articles),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "database": database_result,
        "digest": digest
    }


if __name__ == "__main__":
    run_project("Artificial Intelligence")
