from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vector_store as vs  # noqa: E402


def make_record(
    article_id: str = "a1",
    chunk_index: int = 0,
    section: str | None = "intro",
    vector: tuple[float, ...] = (0.1, 0.2, 0.3),
    content: str = "hello world",
    token_count: int = 3,
) -> dict:
    return {
        "article_id": article_id,
        "chunk_index": chunk_index,
        "content": content,
        "embedding": list(vector),
        "metadata": {
            "article_id": article_id,
            "chunk_index": chunk_index,
            "section": section,
            "title": "Title",
            "source": "finnhub",
            "symbol": "AAPL",
            "url": "https://example.com/a",
            "published_at": "2026-10-14T00:00:00+00:00",
            "token_count": token_count,
        },
    }


class FakeQdrantClient:
    """Minimal Qdrant client double recording every call."""

    def __init__(self, existing: tuple[str, ...] = ()) -> None:
        self.existing = set(existing)
        self.created: list[tuple[str, object]] = []
        self.dropped: list[str] = []
        self.upserts: list[tuple[str, list, bool]] = []
        self.deletes: list[tuple[str, object, bool]] = []
        self.queries: list[dict] = []
        self.closed = False
        self.query_result: list = []

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.existing

    def create_collection(self, collection_name: str, vectors_config: object) -> None:
        self.created.append((collection_name, vectors_config))
        self.existing.add(collection_name)

    def delete_collection(self, collection_name: str) -> None:
        self.dropped.append(collection_name)
        self.existing.discard(collection_name)

    def upsert(self, collection_name: str, points: list, wait: bool = True) -> None:
        self.upserts.append((collection_name, list(points), wait))

    def delete(self, collection_name: str, points_selector: object, wait: bool = True) -> None:
        self.deletes.append((collection_name, points_selector, wait))

    def query_points(self, **kwargs) -> SimpleNamespace:
        self.queries.append(kwargs)
        return SimpleNamespace(points=list(self.query_result))

    def close(self) -> None:
        self.closed = True

    @property
    def upserted_points(self) -> list:
        return [point for _, points, _ in self.upserts for point in points]


class TestBuildPointId(unittest.TestCase):
    def test_uses_database_chunk_id_when_available(self) -> None:
        self.assertEqual(vs.build_point_id("a1", 3, 42), 42)
        self.assertIsInstance(vs.build_point_id("a1", 3, 42), int)

    def test_uuid_fallback_is_deterministic(self) -> None:
        first = vs.build_point_id("a1", 0)
        second = vs.build_point_id("a1", 0)
        self.assertEqual(first, second)
        self.assertNotEqual(first, vs.build_point_id("a1", 1))
        self.assertNotEqual(first, vs.build_point_id("a2", 0))

    def test_uuid_fallback_is_parseable_uuid(self) -> None:
        import uuid

        self.assertIsInstance(uuid.UUID(vs.build_point_id("a1", 0)), uuid.UUID)


class TestResolveVectorSize(unittest.TestCase):
    def test_known_models(self) -> None:
        self.assertEqual(vs.resolve_vector_size("text-embedding-3-small"), 1536)
        self.assertEqual(vs.resolve_vector_size("text-embedding-3-large"), 3072)

    def test_dimensions_override_model_default(self) -> None:
        self.assertEqual(vs.resolve_vector_size("text-embedding-3-large", 256), 256)

    def test_unknown_model_raises(self) -> None:
        with self.assertRaises(ValueError):
            vs.resolve_vector_size("some-future-model")


class TestGetQdrantClient(unittest.TestCase):
    def test_requires_url(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                vs.get_qdrant_client()

    def test_builds_client_from_environment(self) -> None:
        env = {"QDRANT_URL": "http://localhost:6333", "QDRANT_API_KEY": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(vs, "QdrantClient") as client_cls:
                vs.get_qdrant_client()
                client_cls.assert_called_once_with(
                    url="http://localhost:6333",
                    api_key="secret",
                    timeout=vs.DEFAULT_TIMEOUT,
                    prefer_grpc=False,
                )

    def test_returns_provided_client_untouched(self) -> None:
        fake = FakeQdrantClient()
        self.assertIs(vs.get_qdrant_client(client=fake), fake)

    def test_explicit_arguments_win_over_environment(self) -> None:
        env = {"QDRANT_URL": "http://env:6333", "QDRANT_API_KEY": "env-key"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(vs, "QdrantClient") as client_cls:
                vs.get_qdrant_client(url="http://arg:6333", api_key="arg-key")
class TestResolveCollectionName(unittest.TestCase):
    def test_default(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(vs.resolve_collection_name(), vs.DEFAULT_COLLECTION)

    def test_environment_override(self) -> None:
        with mock.patch.dict(os.environ, {"QDRANT_COLLECTION": "news_test"}, clear=True):
            self.assertEqual(vs.resolve_collection_name(), "news_test")

    def test_argument_wins(self) -> None:
        with mock.patch.dict(os.environ, {"QDRANT_COLLECTION": "news_test"}, clear=True):
            self.assertEqual(vs.resolve_collection_name("explicit"), "explicit")


class TestBuildPoints(unittest.TestCase):
    def test_payload_and_point_id_from_chunk_ids(self) -> None:
        points = vs.build_points(
            [make_record(article_id="a1", chunk_index=1)],
            chunk_ids={("a1", 1): 77},
        )
        self.assertEqual(len(points), 1)
        point = points[0]
        self.assertEqual(point.id, 77)
        self.assertEqual(point.vector, [0.1, 0.2, 0.3])
        self.assertEqual(point.payload["article_id"], "a1")
        self.assertEqual(point.payload["chunk_id"], 77)
        self.assertEqual(point.payload["chunk_index"], 1)
        self.assertEqual(point.payload["section"], "intro")
        self.assertEqual(point.payload["symbol"], "AAPL")
        self.assertEqual(point.payload["token_count"], 3)
        self.assertEqual(point.payload["content"], "hello world")

    def test_uuid_fallback_when_chunk_id_unknown(self) -> None:
        point = vs.build_points([make_record()])[0]
        self.assertEqual(point.id, vs.build_point_id("a1", 0))
        self.assertNotIn("chunk_id", point.payload)

    def test_content_can_be_excluded(self) -> None:
        point = vs.build_points([make_record()], include_content=False)[0]
        self.assertNotIn("content", point.payload)

    def test_empty_values_are_removed_from_payload(self) -> None:
        point = vs.build_points([make_record(section=None)])[0]
        self.assertNotIn("section", point.payload)

    def test_missing_embedding_raises(self) -> None:
        record = make_record()
        record["embedding"] = []
        with self.assertRaises(ValueError):
            vs.build_points([record])

    def test_missing_article_id_raises(self) -> None:
        record = make_record()
        record["article_id"] = None
        with self.assertRaises(ValueError):
            vs.build_points([record])


class TestEnsureCollection(unittest.TestCase):
    def test_creates_collection_when_missing(self) -> None:
        fake = FakeQdrantClient()
        created = vs.ensure_collection(fake, collection_name="c", vector_size=8)
        self.assertTrue(created)
        self.assertEqual(fake.created[0][0], "c")
        self.assertEqual(fake.created[0][1].size, 8)
        self.assertEqual(fake.created[0][1].distance, vs.models.Distance.COSINE)

    def test_returns_false_when_collection_exists(self) -> None:
        fake = FakeQdrantClient(existing=("c",))
        self.assertFalse(vs.ensure_collection(fake, collection_name="c"))
        self.assertEqual(fake.created, [])

    def test_recreate_drops_then_creates(self) -> None:
        fake = FakeQdrantClient(existing=("c",))
        created = vs.ensure_collection(fake, collection_name="c", vector_size=4, recreate=True)
        self.assertTrue(created)
        self.assertEqual(fake.dropped, ["c"])
        self.assertEqual(len(fake.created), 1)

    def test_vector_size_from_model_default(self) -> None:
        fake = FakeQdrantClient()
        vs.ensure_collection(fake, collection_name="c", model="text-embedding-3-large")
        self.assertEqual(fake.created[0][1].size, 3072)

    def test_unknown_distance_raises(self) -> None:
        fake = FakeQdrantClient()
        with self.assertRaises(ValueError):
            vs.ensure_collection(fake, collection_name="c", distance="hamming")


class TestUpsertVectors(unittest.TestCase):
    def test_upserts_points_keyed_by_chunk_id(self) -> None:
        fake = FakeQdrantClient()
        records = [make_record(chunk_index=index) for index in range(3)]
        chunk_ids = {("a1", index): 100 + index for index in range(3)}

        stored = vs.upsert_vectors(
            records,
            chunk_ids=chunk_ids,
            collection_name="c",
            client=fake,
        )

        self.assertEqual(stored, 3)
        self.assertEqual(fake.created[0][0], "c")
        self.assertEqual(fake.created[0][1].size, 3)
        self.assertEqual([point.id for point in fake.upserted_points], [100, 101, 102])

    def test_deletes_previous_article_vectors_before_upsert(self) -> None:
        fake = FakeQdrantClient(existing=("c",))
        records = [make_record(article_id="a1"), make_record(article_id="a2", chunk_index=1)]

        vs.upsert_vectors(records, collection_name="c", client=fake)

        self.assertEqual(len(fake.deletes), 1)
        self.assertEqual(fake.deletes[0][0], "c")
        self.assertEqual(fake.deletes[0][1].filter.must[0].match.any, ["a1", "a2"])

    def test_replace_existing_can_be_disabled(self) -> None:
        fake = FakeQdrantClient(existing=("c",))
        vs.upsert_vectors([make_record()], collection_name="c", client=fake, replace_existing=False)
        self.assertEqual(fake.deletes, [])

    def test_batches_are_flushed_in_chunks(self) -> None:
        fake = FakeQdrantClient()
        records = [make_record(chunk_index=index) for index in range(5)]

        stored = vs.upsert_vectors(records, collection_name="c", client=fake, batch_size=2)

        self.assertEqual(stored, 5)
        self.assertEqual([len(batch) for _, batch, _ in fake.upserts], [2, 2, 1])

    def test_does_not_close_provided_client(self) -> None:
        fake = FakeQdrantClient()
        vs.upsert_vectors([make_record()], collection_name="c", client=fake)
        self.assertFalse(fake.closed)

    def test_closes_client_it_created(self) -> None:
        fake = FakeQdrantClient()
        with mock.patch.object(vs, "get_qdrant_client", return_value=fake):
            vs.upsert_vectors([make_record()], collection_name="c")
        self.assertTrue(fake.closed)

    def test_empty_records_do_nothing(self) -> None:
        fake = FakeQdrantClient()
        self.assertEqual(vs.upsert_vectors([], collection_name="c", client=fake), 0)
        self.assertEqual(fake.upserts, [])


class TestDeleteVectors(unittest.TestCase):
    def test_deletes_all_points_of_articles(self) -> None:
        fake = FakeQdrantClient(existing=("c",))
        deleted = vs.delete_vectors_by_article_ids(
            ["a2", "a1", "a1"], collection_name="c", client=fake
        )
        self.assertEqual(deleted, 2)
        self.assertEqual(fake.deletes[0][1].filter.must[0].match.any, ["a1", "a2"])

    def test_missing_collection_is_noop(self) -> None:
        fake = FakeQdrantClient()
        self.assertEqual(vs.delete_vectors_by_article_ids(["a1"], collection_name="c", client=fake), 0)
        self.assertEqual(fake.deletes, [])

    def test_empty_ids_is_noop(self) -> None:
        fake = FakeQdrantClient(existing=("c",))
        self.assertEqual(vs.delete_vectors_by_article_ids([], collection_name="c", client=fake), 0)
        self.assertEqual(fake.deletes, [])


class TestSearchSimilar(unittest.TestCase):
    def test_returns_id_score_and_payload(self) -> None:
        fake = FakeQdrantClient(existing=("c",))
        fake.query_result = [
            SimpleNamespace(id=10, score=0.9, payload={"article_id": "a1"}),
            SimpleNamespace(id=11, score=0.8, payload={"article_id": "a2"}),
        ]

        hits = vs.search_similar([0.1, 0.2, 0.3], top_k=2, collection_name="c", client=fake)

        self.assertEqual([hit["id"] for hit in hits], [10, 11])
        self.assertEqual(hits[0]["score"], 0.9)
        self.assertEqual(hits[0]["payload"]["article_id"], "a1")
        self.assertEqual(fake.queries[0]["limit"], 2)

    def test_missing_collection_returns_no_hits(self) -> None:
        fake = FakeQdrantClient()
        self.assertEqual(vs.search_similar([0.1], collection_name="c", client=fake), [])
        self.assertEqual(fake.queries, [])

    def test_empty_vector_raises(self) -> None:
        with self.assertRaises(ValueError):
            vs.search_similar([], collection_name="c", client=FakeQdrantClient())


class TestBuildArticleFilter(unittest.TestCase):
    def test_filter_matches_sorted_ids(self) -> None:
        built = vs.build_article_filter(["b", "a", "a"])
        self.assertEqual(built.must[0].key, "article_id")
        self.assertEqual(built.must[0].match.any, ["a", "b"])

    def test_empty_ids_raise(self) -> None:
        with self.assertRaises(ValueError):
            vs.build_article_filter([])


if __name__ == "__main__":
    unittest.main()
