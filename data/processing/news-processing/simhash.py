import hashlib
import re
from collections import Counter
from typing import Any


def tokenize(text: str) -> list[str]:
    """Normalize and tokenize text into words."""
    text = text.lower()
    return re.findall(r"\b\w+\b", text, re.UNICODE)


def get_features(text: str) -> Counter:
    """Extract unigrams and bigrams as features with their frequencies."""
    tokens = tokenize(text)

    features = Counter()

    # Unigrams: handles word insertion or deletion well
    features.update(tokens)

    # Bigrams: captures local word order information
    features.update(
        " ".join(tokens[i:i + 2])
        for i in range(len(tokens) - 1)
    )

    return features


def hash_feature(feature: str, bits: int = 64) -> int:
    """Create a deterministic hash for each feature."""
    digest = hashlib.blake2b(
        feature.encode("utf-8"),
        digest_size=bits // 8,
    ).digest()

    return int.from_bytes(digest, byteorder="big")


def simhash(text: str, bits: int = 64) -> int:
    """Calculate the SimHash fingerprint of a given text."""
    features = get_features(text)
    if not features:
        return 0

    weights = [0] * bits

    for feature, frequency in features.items():
        hashed = hash_feature(feature, bits)

        for i in range(bits):
            bit_is_set = (hashed >> i) & 1
            weights[i] += frequency if bit_is_set else -frequency

    fingerprint = 0

    for i, weight in enumerate(weights):
        if weight >= 0:
            fingerprint |= 1 << i

    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    """Calculate the Hamming distance between two fingerprints."""
    return (a ^ b).bit_count()


class SimHashIndex:
    """Index for fast nearest-neighbor candidate search of 64-bit SimHash values.

    Partitions a 64-bit hash into (k + 1) blocks. By the pigeonhole principle,
    two hashes within Hamming distance k must match exactly in at least one block.
    """

    def __init__(self, k: int = 3, bits: int = 64):
        self.k = k
        self.bits = bits
        self.num_blocks = k + 1
        self.block_size = bits // self.num_blocks
        self.buckets: list[dict[int, set[Any]]] = [{} for _ in range(self.num_blocks)]
        self.fingerprints: dict[Any, int] = {}

    def _get_block(self, fingerprint: int, block_idx: int) -> int:
        start_bit = block_idx * self.block_size
        if block_idx == self.num_blocks - 1:
            mask = (1 << (self.bits - start_bit)) - 1
        else:
            mask = (1 << self.block_size) - 1
        return (fingerprint >> start_bit) & mask

    def add(self, doc_id: Any, fingerprint: int) -> None:
        """Add a document ID and its fingerprint to the index."""
        self.fingerprints[doc_id] = fingerprint
        for i in range(self.num_blocks):
            block_val = self._get_block(fingerprint, i)
            self.buckets[i].setdefault(block_val, set()).add(doc_id)

    def get_near_duplicates(self, fingerprint: int, exclude_id: Any = None) -> set[Any]:
        """Find all document IDs whose fingerprint has Hamming distance <= k."""
        candidates: set[Any] = set()
        for i in range(self.num_blocks):
            block_val = self._get_block(fingerprint, i)
            if block_val in self.buckets[i]:
                candidates.update(self.buckets[i][block_val])

        if exclude_id is not None:
            candidates.discard(exclude_id)

        # Verify exact Hamming distance threshold
        return {
            doc_id
            for doc_id in candidates
            if hamming_distance(fingerprint, self.fingerprints[doc_id]) <= self.k
        }
