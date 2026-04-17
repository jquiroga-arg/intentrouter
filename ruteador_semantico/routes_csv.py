"""Construcción de Route de semantic-router a partir del CSV de intenciones."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import List

from semantic_router import Route


def routes_from_intents_csv(csv_path: Path) -> List[Route]:
    """CSV sin cabecera: id,utterance,category (utterance puede ir entre comillas)."""
    by_category: dict[str, list[str]] = defaultdict(list)
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            utterance = (row[1] or "").strip()
            category = (row[2] or "").strip()
            if not utterance or not category:
                continue
            by_category[category].append(utterance)

    return [
        Route(name=name, utterances=utterances)
        for name, utterances in sorted(by_category.items(), key=lambda x: x[0])
    ]
