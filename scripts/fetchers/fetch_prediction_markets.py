"""Holt WM-Wahrscheinlichkeiten von Prediction Markets (Polymarket, Manifold).

Prediction-Market-Preise sind eine Crowd-Prognose AUSSERHALB der
Buchmacher-Maerkte -- als Benchmark und Divergenz-Signal (Markt vs.
Crowd). Jeder Lauf haengt einen zeitgestempelten Snapshot an ein
append-only CSV-Log an (analog zum Odds-Logging). Frei, ohne API-Key.
Reine Standardbibliothek.
"""
from __future__ import annotations

import csv
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


class PredictionMarketConfig:
    """Endpunkte, Suchbegriffe und Logpfad."""

    POLYMARKET_SEARCH: str = "https://gamma-api.polymarket.com/public-search?q="
    MANIFOLD_SEARCH: str = "https://api.manifold.markets/v0/search-markets?term="
    SEARCH_TERMS: tuple[str, ...] = ("World Cup 2026", "2026 FIFA World Cup")
    TITLE_FILTER: str = "world cup"
    TIMEOUT_SECONDS: int = 30
    POLITE_DELAY_SECONDS: float = 0.5
    LOG_FILE: str = "Alternative Data (Prediction Markets)/prediction_markets_log.csv"


def api_json(url: str, config: PredictionMarketConfig) -> object | None:
    """GET mit JSON-Antwort; None bei Fehler."""
    request = urllib.request.Request(url, headers={"User-Agent": "wm-quant-guru"})
    try:
        with urllib.request.urlopen(request, timeout=config.TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except Exception:
        return None


def polymarket_rows(fetched_at: str, config: PredictionMarketConfig) -> list[list[str]]:
    """Sammle Outcome-Preise aller WM-Events von Polymarket."""
    rows: list[list[str]] = []
    seen: set[str] = set()
    for term in config.SEARCH_TERMS:
        data = api_json(
            config.POLYMARKET_SEARCH + urllib.parse.quote(term), config
        )
        time.sleep(config.POLITE_DELAY_SECONDS)
        for event in (data or {}).get("events", []):
            title = event.get("title", "")
            if config.TITLE_FILTER not in title.lower() or event["id"] in seen:
                continue
            seen.add(event["id"])
            for market in event.get("markets", []):
                outcomes = json.loads(market.get("outcomes") or "[]")
                prices = json.loads(market.get("outcomePrices") or "[]")
                for outcome, price in zip(outcomes, prices):
                    rows.append(
                        [fetched_at, "polymarket", title,
                         market.get("question", ""), outcome, price,
                         str(market.get("volumeNum", ""))]
                    )
    return rows


def manifold_rows(fetched_at: str, config: PredictionMarketConfig) -> list[list[str]]:
    """Sammle Wahrscheinlichkeiten passender Manifold-Maerkte."""
    rows: list[list[str]] = []
    seen: set[str] = set()
    for term in config.SEARCH_TERMS:
        data = api_json(
            config.MANIFOLD_SEARCH + urllib.parse.quote(term) + "&limit=50", config
        )
        time.sleep(config.POLITE_DELAY_SECONDS)
        for market in data or []:
            question = market.get("question", "")
            if config.TITLE_FILTER not in question.lower() or market["id"] in seen:
                continue
            seen.add(market["id"])
            probability = market.get("probability")
            if probability is None:
                continue  # Mehrfachauswahl-Maerkte brauchen Detail-Calls
            rows.append(
                [fetched_at, "manifold", question, question, "YES",
                 f"{probability:.4f}", str(market.get("volume", ""))]
            )
    return rows


def main() -> None:
    """Ziehe einen Snapshot beider Quellen und haenge ihn ans Log an."""
    config = PredictionMarketConfig()
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = polymarket_rows(fetched_at, config) + manifold_rows(fetched_at, config)
    target = Path(config.LOG_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    is_new = not target.exists()
    with target.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(["fetched_at_utc", "source", "event", "question",
                             "outcome", "price_or_prob", "volume"])
        writer.writerows(rows)
    print(f"{len(rows)} Markt-Zeilen angehaengt -> {target}")


if __name__ == "__main__":
    main()
