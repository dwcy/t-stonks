"""Quantum-computing RSS news feeds, injected into the shared NewsService."""

from __future__ import annotations

from marketcore.services.news_service import FeedEntry

QUANTUM_NEWS_FEEDS: tuple[FeedEntry, ...] = (
    (
        "QuantumIns",
        "https://news.google.com/rss/search?q=when:24h+site:thequantuminsider.com&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "QC-General",
        "https://news.google.com/rss/search?q=when:24h+%22quantum+computing%22&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "QC-Stocks",
        "https://news.google.com/rss/search?q=when:48h+(IonQ+OR+Rigetti+OR+%22D-Wave%22+OR+%22Quantum+Computing+Inc%22+OR+Arqit+OR+SEALSQ+OR+%22Quantum+Si%22+OR+QTUM+OR+%22quantum+stock%22)&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "QC-Research",
        "https://news.google.com/rss/search?q=when:24h+(%22quantum+computing%22+breakthrough)&hl=en-US&gl=US&ceid=US:en",
    ),
)
