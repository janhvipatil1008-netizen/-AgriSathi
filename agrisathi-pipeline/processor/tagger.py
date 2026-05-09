"""
Metadata tagging for each chunk.

Tags enrich the vector payload so Qdrant filters can narrow retrieval
(e.g. only fetch chunks about wheat, or only pest-related content).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from processor.chunker import Chunk

# ── Agriculture keyword taxonomy ──────────────────────────────────────────────

_CROP_KEYWORDS: set[str] = {
    "wheat", "rice", "paddy", "maize", "corn", "soybean", "cotton",
    "sugarcane", "potato", "tomato", "onion", "mustard", "groundnut",
    "chickpea", "lentil", "jowar", "bajra", "ragi",
}

_PEST_KEYWORDS: set[str] = {
    "pest", "insect", "aphid", "whitefly", "thrips", "borer", "locust",
    "nematode", "mite", "weevil", "caterpillar",
}

_DISEASE_KEYWORDS: set[str] = {
    "disease", "blight", "rust", "wilt", "rot", "mildew", "mosaic",
    "smut", "scab", "canker", "anthracnose",
}

_ADVISORY_KEYWORDS: set[str] = {
    "sowing", "irrigation", "fertiliser", "fertilizer", "harvest",
    "spray", "dose", "treatment", "recommendation", "advisory",
}

_WEATHER_KEYWORDS: set[str] = {
    "rainfall", "temperature", "humidity", "drought", "flood",
    "monsoon", "forecast", "weather",
}


@dataclass
class ChunkMetadata:
    source_name: str
    source_type: str          # pdf | csv | html | txt
    source_url: str
    source_page: int
    crops: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)


def tag(chunk: Chunk, source_name: str, source_type: str, source_url: str) -> ChunkMetadata:
    """Derive metadata tags from chunk text using keyword matching."""
    text_lower = chunk.text.lower()
    words = set(re.findall(r"\b\w+\b", text_lower))

    crops = sorted(words & _CROP_KEYWORDS)

    topics: list[str] = []
    if words & _PEST_KEYWORDS:
        topics.append("pest")
    if words & _DISEASE_KEYWORDS:
        topics.append("disease")
    if words & _ADVISORY_KEYWORDS:
        topics.append("advisory")
    if words & _WEATHER_KEYWORDS:
        topics.append("weather")

    return ChunkMetadata(
        source_name=source_name,
        source_type=source_type,
        source_url=source_url,
        source_page=chunk.source_page,
        crops=crops,
        topics=topics,
    )
