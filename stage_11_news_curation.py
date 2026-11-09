import re
import html
import sqlite3
from urllib.parse import urlsplit, urlunsplit
from sentence_transformers import SentenceTransformer, util


def merge_articles(newsdata, gnews, google_news):
    return list(newsdata) + list(gnews) + list(google_news)


def remove_duplicates(articles):
    unique_articles = []
    seen_urls = set()
    seen_titles = set()

    for article in articles:
        url = article.get("url", "").strip()
        title = article.get("title", "").strip()

        if not url or not title:
            continue

        clean_url = urlsplit(url)
        normalized_url = urlunsplit((
            clean_url.scheme,
            clean_url.netloc,
            clean_url.path,
            clean_url.query,
            ""
        )).lower()

        normalized_title = re.sub(r"\W+", " ", title.lower()).strip()

        if normalized_url in seen_urls or normalized_title in seen_titles:
            continue

        seen_urls.add(normalized_url)
        seen_titles.add(normalized_title)
        unique_articles.append(article)

    return unique_articles


def rank_articles(articles, user_query):
    model = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    query_embedding = model.encode(
        user_query,
        convert_to_tensor=True
    )

    for article in articles:
        title = article.get("title") or ""
        description = article.get("description") or ""

        title = html.unescape(
            re.sub(r"<[^>]+>", " ", title)
        )

        description = html.unescape(
            re.sub(r"<[^>]+>", " ", description)
        )

        title_embedding = model.encode(
            title,
            convert_to_tensor=True
        )

        title_score = util.cos_sim(
            query_embedding,
            title_embedding
        ).item()

        if description.strip():
            description_embedding = model.encode(
                description,
                convert_to_tensor=True
            )

            description_score = util.cos_sim(
                query_embedding,
                description_embedding
            ).item()
        else:
            description_score = title_score

        article["relevance_score"] = round(
            0.8 * title_score + 0.2 * description_score,
            4
        )

    return sorted(
        articles,
        key=lambda article: article["relevance_score"],
        reverse=True
    )


def review_articles(articles):
    approved = []
    rejected = []

    for article in articles:
        title = article.get("title")
        url = article.get("url")
        source = article.get("source")

        if (
            isinstance(title, str) and title.strip()
            and isinstance(url, str) and url.startswith("https://")
            and isinstance(source, str) and source.strip()
        ):
            approved.append(article)
        else:
            rejected.append({
                "article": article,
                "reason": "Missing or invalid article information."
            })

    return {
        "approved": approved,
        "rejected": rejected
    }


def save_articles_sqlite(articles, db_path):
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_news (
            url TEXT PRIMARY KEY,
            title TEXT,
            source TEXT,
            published_at TEXT,
            relevance_score INTEGER
        )
    """)

    saved_count = 0

    for article in articles:
        cursor.execute("""
            INSERT OR IGNORE INTO processed_news
            (url, title, source, published_at, relevance_score)
            VALUES (?, ?, ?, ?, ?)
        """, (
            article.get("url"),
            article.get("title"),
            article.get("source"),
            article.get("published_at"),
            article.get("relevance_score", 0)
        ))
        saved_count += cursor.rowcount

    connection.commit()

    total_count = cursor.execute(
        "SELECT COUNT(*) FROM processed_news"
    ).fetchone()[0]

    connection.close()

    return {
        "new_articles_saved": saved_count,
        "total_articles_in_database": total_count
    }


def generate_news_digest(articles, limit=5):
    digest = []

    for article in articles[:limit]:
        digest.append({
            "title": article.get("title"),
            "description": article.get("description"),
            "source": article.get("source"),
            "url": article.get("url"),
            "relevance_score": article.get("relevance_score", 0)
        })

    return digest
