from __future__ import annotations

import sqlite3
from pathlib import Path

from .bootstrap import ensure_search_indexes

FTS_TABLES = ("messages_fts", "knowledge_messages_fts", "watch_signals_fts", "watch_issue_stories_fts")
ROW_COUNT_SQL = {
    "messages_fts": "SELECT COUNT(*) FROM messages_fts",
    "knowledge_messages_fts": "SELECT COUNT(*) FROM knowledge_messages_fts",
    "watch_signals_fts": "SELECT COUNT(*) FROM watch_signals_fts",
    "watch_issue_stories_fts": "SELECT COUNT(*) FROM watch_issue_stories_fts",
}
DELETE_SQL = {
    "messages_fts": "DELETE FROM messages_fts",
    "knowledge_messages_fts": "DELETE FROM knowledge_messages_fts",
    "watch_signals_fts": "DELETE FROM watch_signals_fts",
    "watch_issue_stories_fts": "DELETE FROM watch_issue_stories_fts",
}


def _row_count(conn: sqlite3.Connection, table_name: str) -> int:
    return int(conn.execute(ROW_COUNT_SQL[table_name]).fetchone()[0])


def rebuild_operational_search_index(database_path: Path) -> dict[str, object]:
    database_path = Path(database_path)
    try:
        with sqlite3.connect(database_path) as conn:
            index_state = ensure_search_indexes(conn)
            if not index_state.get("fts5_available"):
                return {"ok": False, "reason": "fts5_unavailable", "database_path": str(database_path), **index_state}

            for table_name in FTS_TABLES:
                conn.execute(DELETE_SQL[table_name])

            conn.execute(
                """
                INSERT INTO messages_fts(message_id, subject, from_addr, snippet, sent_at, folder_kind)
                SELECT message_id, COALESCE(subject, ''), COALESCE(from_addr, ''), COALESCE(snippet, ''),
                       COALESCE(sent_at, ''), COALESCE(folder_kind, '')
                FROM messages
                """
            )
            conn.execute(
                """
                INSERT INTO knowledge_messages_fts(knowledge_id, subject, from_addr, summary_text, category, sent_at)
                SELECT knowledge_id, COALESCE(subject, ''), COALESCE(from_addr, ''), COALESCE(summary_text, ''),
                       COALESCE(category, ''), COALESCE(sent_at, '')
                FROM knowledge_messages
                """
            )
            conn.execute(
                """
                INSERT INTO watch_signals_fts(signal_id, title, summary_text, author, url, published_at)
                SELECT signal_id, COALESCE(title, ''), COALESCE(summary_text, ''), COALESCE(author, ''),
                       COALESCE(url, ''), COALESCE(published_at, '')
                FROM watch_signals
                """
            )
            conn.execute(
                """
                INSERT INTO watch_issue_stories_fts(issue_id, canonical_title, canonical_summary, primary_company_tag, last_seen_at)
                SELECT issue_id, COALESCE(canonical_title, ''), COALESCE(canonical_summary, ''),
                       COALESCE(primary_company_tag, ''), COALESCE(last_seen_at, '')
                FROM watch_issue_stories
                """
            )
            counts = {table_name: _row_count(conn, table_name) for table_name in FTS_TABLES}
            conn.commit()
    except sqlite3.Error as exc:
        return {"ok": False, "reason": "sqlite_error", "database_path": str(database_path), "error": str(exc)}
    return {"ok": True, "database_path": str(database_path), "indexed_rows": counts}


def _search_table(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    source_table: str,
    source_id_column: str,
    title_column: str,
    summary_column: str,
    timestamp_column: str,
    query: str,
    limit: int,
) -> list[dict[str, object]]:
    sql = f"""
        SELECT
            {source_id_column} AS source_id,
            {title_column} AS title,
            {summary_column} AS summary,
            {timestamp_column} AS timestamp,
            bm25({table_name}) AS rank
        FROM {table_name}
        WHERE {table_name} MATCH ?
        ORDER BY rank
        LIMIT ?
    """
    rows = conn.execute(sql, (query, limit)).fetchall()
    return [
        {
            "source_table": source_table,
            "source_id": row["source_id"],
            "title": row["title"] or "",
            "summary": row["summary"] or "",
            "timestamp": row["timestamp"] or "",
            "rank": float(row["rank"]),
        }
        for row in rows
    ]


def search_operational_index(database_path: Path, query: str, limit: int = 10) -> dict[str, object]:
    database_path = Path(database_path)
    normalized_query = query.strip()
    bounded_limit = max(1, min(int(limit), 100))
    if not normalized_query:
        return {"ok": False, "reason": "empty_query", "database_path": str(database_path), "rows": []}
    try:
        with sqlite3.connect(database_path) as conn:
            conn.row_factory = sqlite3.Row
            index_state = ensure_search_indexes(conn)
            if not index_state.get("fts5_available"):
                return {"ok": False, "reason": "fts5_unavailable", "database_path": str(database_path), **index_state}
            rows: list[dict[str, object]] = []
            rows.extend(_search_table(conn, table_name="messages_fts", source_table="messages", source_id_column="message_id", title_column="subject", summary_column="snippet", timestamp_column="sent_at", query=normalized_query, limit=bounded_limit))
            rows.extend(_search_table(conn, table_name="knowledge_messages_fts", source_table="knowledge_messages", source_id_column="knowledge_id", title_column="subject", summary_column="summary_text", timestamp_column="sent_at", query=normalized_query, limit=bounded_limit))
            rows.extend(_search_table(conn, table_name="watch_signals_fts", source_table="watch_signals", source_id_column="signal_id", title_column="title", summary_column="summary_text", timestamp_column="published_at", query=normalized_query, limit=bounded_limit))
            rows.extend(_search_table(conn, table_name="watch_issue_stories_fts", source_table="watch_issue_stories", source_id_column="issue_id", title_column="canonical_title", summary_column="canonical_summary", timestamp_column="last_seen_at", query=normalized_query, limit=bounded_limit))
    except sqlite3.OperationalError as exc:
        return {"ok": False, "reason": "invalid_query", "database_path": str(database_path), "query": query, "error": str(exc), "rows": []}
    except sqlite3.Error as exc:
        return {"ok": False, "reason": "sqlite_error", "database_path": str(database_path), "error": str(exc), "rows": []}

    rows.sort(key=lambda row: (float(row["rank"]), str(row["source_table"]), str(row["source_id"])))
    return {"ok": True, "database_path": str(database_path), "query": normalized_query, "limit": bounded_limit, "rows": rows[:bounded_limit]}
