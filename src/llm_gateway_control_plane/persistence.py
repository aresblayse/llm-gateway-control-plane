from __future__ import annotations
import sqlite3, json, time
from pathlib import Path
class RequestStore:
    def __init__(self,path:Path):
        path.parent.mkdir(parents=True,exist_ok=True); self.path=path
        with sqlite3.connect(path) as c:c.execute('CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,created REAL,payload TEXT)')
    def save(self,record):
        with sqlite3.connect(self.path) as c:c.execute('INSERT OR REPLACE INTO requests VALUES(?,?,?)',(record['request_id'],time.time(),json.dumps(record)))
    def list(self):
        with sqlite3.connect(self.path) as c: rows=c.execute('SELECT payload FROM requests ORDER BY created DESC').fetchall()
        return [json.loads(r[0]) for r in rows]
