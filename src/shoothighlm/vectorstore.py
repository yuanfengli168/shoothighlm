"""Vector storage using sqlite-vec"""

import sqlite3
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass
import json


@dataclass
class SearchResult:
    """A search result with metadata"""
    chunk_id: str
    text: str
    source: str
    distance: float


class VectorStore:
    """SQLite + sqlite-vec for vector storage"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                source TEXT NOT NULL,
                embedding BLOB NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunk_index 
            USING vec0(chunk_id TEXT PRIMARY KEY, embedding float[1024])
        """)
        self.conn.commit()
    
    def add(self, chunk_id: str, text: str, source: str, embedding: List[float]) -> None:
        """Add a chunk with its embedding"""
        embedding_blob = json.dumps(embedding)
        self.conn.execute(
            "INSERT OR REPLACE INTO chunks VALUES (?, ?, ?, ?)",
            (chunk_id, text, source, embedding_blob),
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO chunk_index VALUES (?, ?)",
            (chunk_id, embedding_blob),
        )
        self.conn.commit()
    
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[SearchResult]:
        """Search for similar chunks"""
        cursor = self.conn.execute(
            """
            SELECT c.chunk_id, c.text, c.source, 
                   vec_distance_cosine(c.embedding, ?) as distance
            FROM chunks c
            JOIN chunk_index i ON c.chunk_id = i.chunk_id
            ORDER BY distance
            LIMIT ?
            """,
            (json.dumps(query_embedding), top_k),
        )
        return [
            SearchResult(
                chunk_id=row[0],
                text=row[1],
                source=row[2],
                distance=row[3],
            )
            for row in cursor.fetchall()
        ]
    
    def close(self) -> None:
        """Close database connection"""
        self.conn.close()
