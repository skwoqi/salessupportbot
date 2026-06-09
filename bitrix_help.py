from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HELP_ARTICLES_FILE = Path("bitrix_help_articles.json")


def load_articles() -> list[dict[str, Any]]:
    if not HELP_ARTICLES_FILE.exists():
        return []
    with HELP_ARTICLES_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zа-яё0-9]+", text.lower())
        if len(token) > 2
    }


def find_articles(query: str, limit: int = 3) -> list[dict[str, Any]]:
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    ranked = []
    for article in load_articles():
        title = str(article.get("title", ""))
        category = str(article.get("category", ""))
        summary = str(article.get("summary", ""))
        keywords = [str(item) for item in article.get("keywords", [])]

        title_tokens = tokenize(title)
        category_tokens = tokenize(category)
        keyword_tokens = tokenize(" ".join(keywords))
        summary_tokens = tokenize(summary)

        score = 0
        score += len(query_tokens & title_tokens) * 5
        score += len(query_tokens & keyword_tokens) * 4
        score += len(query_tokens & category_tokens) * 3
        score += len(query_tokens & summary_tokens)

        if score:
            ranked.append((score, article))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [article for _, article in ranked[:limit]]
