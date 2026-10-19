from typing import Any
from cleaner import prepare_text_for_dedup
from simhash import SimHashIndex, simhash


class DisjointSetUnion:
    """Disjoint Set Union (Union-Find) with path compression and union by rank."""

    def __init__(self):
        self.parent: dict[Any, Any] = {}
        self.rank: dict[Any, int] = {}

    def find(self, item: Any) -> Any:
        if item not in self.parent:
            self.parent[item] = item
            self.rank[item] = 0
            return item

        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, a: Any, b: Any) -> None:
        root_a = self.find(a)
        root_b = self.find(b)

        if root_a == root_b:
            return

        if self.rank[root_a] < self.rank[root_b]:
            self.parent[root_a] = root_b
        elif self.rank[root_a] > self.rank[root_b]:
            self.parent[root_b] = root_a
        else:
            self.parent[root_b] = root_a
            self.rank[root_a] += 1


def _extract_article_id(article: dict) -> Any:
    """Extract article ID from an article dictionary."""
    if "articles_id" in article:
        return article["articles_id"]
    if "article_id" in article:
        return article["article_id"]
    if "id" in article:
        return article["id"]
    raise KeyError("Article must contain 'articles_id' or 'article_id' key")


def find_candidate_sets(
    articles: list[dict],
    threshold: int = 3,
) -> list[set[Any]]:
    """Find sets of near-duplicate articles using SimHash.

    Articles with Hamming distance <= threshold are grouped into candidate sets.

    Args:
        articles: List of article dicts, each containing 'articles_id' and 'content'.
        threshold: Maximum Hamming distance to consider two articles duplicates (default: 3).

    Returns:
        A list of sets, where each set contains the 'articles_id' values of duplicate candidates.
    """
    if not articles:
        return []

    index = SimHashIndex(k=threshold)
    dsu = DisjointSetUnion()

    for article in articles:
        art_id = _extract_article_id(article)
        content = article.get("content", "")
        clean_text = prepare_text_for_dedup(content)

        if not clean_text:
            continue

        fingerprint = simhash(clean_text)

        # Query existing fingerprints for near duplicates
        near_dups = index.get_near_duplicates(fingerprint)
        for dup_id in near_dups:
            dsu.union(art_id, dup_id)

        index.add(art_id, fingerprint)

    # Group IDs by their connected component root
    clusters: dict[Any, set[Any]] = {}
    for article in articles:
        art_id = _extract_article_id(article)
        if art_id in dsu.parent:
            root = dsu.find(art_id)
            clusters.setdefault(root, set()).add(art_id)

    # Return only duplicate candidate sets (groups with 2 or more articles)
    return [c_set for c_set in clusters.values() if len(c_set) > 1]


def find_candidate_article_sets(
    articles: list[dict],
    threshold: int = 3,
) -> list[list[dict]]:
    """Find sets of near-duplicate articles, returning original article dicts.

    Args:
        articles: List of article dicts, each containing 'articles_id' and 'content'.
        threshold: Maximum Hamming distance to consider duplicates (default: 3).

    Returns:
        A list of lists, where each sublist contains the duplicate article dicts.
    """
    candidate_id_sets = find_candidate_sets(articles, threshold=threshold)
    id_to_article = {_extract_article_id(a): a for a in articles}

    result = []
    for id_set in candidate_id_sets:
        result.append([id_to_article[art_id] for art_id in id_set if art_id in id_to_article])
    return result


def remove_duplicates(
    articles: list[dict],
    threshold: int = 3,
) -> list[dict]:
    """Deduplicate articles, keeping only one representative article per duplicate candidate set.

    Unique articles and the first seen article from each duplicate set are preserved.

    Args:
        articles: List of article dicts, each containing 'articles_id' and 'content'.
        threshold: Maximum Hamming distance to consider duplicates (default: 3).

    Returns:
        List of deduplicated article dicts.
    """
    if not articles:
        return []

    candidate_sets = find_candidate_sets(articles, threshold=threshold)

    ids_to_drop: set[Any] = set()

    for c_set in candidate_sets:
        # Keep the first occurring article in the list for this cluster
        seen_first = False
        for article in articles:
            art_id = _extract_article_id(article)
            if art_id in c_set:
                if not seen_first:
                    seen_first = True
                else:
                    ids_to_drop.add(art_id)

    return [
        article for article in articles
        if _extract_article_id(article) not in ids_to_drop
    ]
