"""AI3 private AI Lab: persistent knowledge, projects and local coding assistant."""
import json
import re
import sqlite3
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.main import OLLAMA_URL, LLM_TIMEOUT, db, now, require_admin

router = APIRouter(prefix="/v1/admin/ai-lab", tags=["AI Lab"])


def init_lab_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS ai_lab_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ai_lab_knowledge_title ON ai_lab_knowledge(title);
        CREATE TABLE IF NOT EXISTS ai_lab_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            language TEXT NOT NULL DEFAULT 'text',
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ai_lab_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            path TEXT NOT NULL,
            content TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(project_id, path),
            FOREIGN KEY(project_id) REFERENCES ai_lab_projects(id) ON DELETE CASCADE
        );
        """)


class KnowledgeIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=1_000_000)
    tags: str = Field(default="", max_length=2000)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._ -]+$")
    language: str = Field(default="text", max_length=80)
    description: str = Field(default="", max_length=10000)


class FileIn(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    content: str = Field(default="", max_length=2_000_000)


class LabChat(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=100_000)
    use_knowledge: bool = True


class CodeTask(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    project_id: Optional[int] = None
    language: str = Field(default="text", max_length=80)
    task: str = Field(min_length=1, max_length=100_000)
    use_knowledge: bool = True


def knowledge_context(query: str, limit: int = 12) -> str:
    terms = [x.lower() for x in re.findall(r"[\w.-]{3,}", query)[:24]]
    with db() as con:
        rows = con.execute("SELECT id,title,content,tags FROM ai_lab_knowledge ORDER BY updated_at DESC LIMIT 200").fetchall()
    scored = []
    for row in rows:
        hay = f"{row['title']} {row['tags']} {row['content']}".lower()
        score = sum(1 for term in terms if term in hay)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda x: (-x[0], x[1]['id']))
    selected = [r for _, r in scored[:limit]] or rows[:min(limit, len(rows))]
    return "\n\n".join(f"### {r['title']}\n{r['content']}\nTags: {r['tags']}" for r in selected)


async def ollama_chat(model: str, system: str, prompt: str):
    payload = {"model": model, "stream": False, "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]}
    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            response = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"Ollama unavailable: {type(exc).__name__}")
    if response.status_code >= 400:
        raise HTTPException(response.status_code, response.text[:2000])
    data = response.json()
    return data.get("message", {}).get("content", ""), data


@router.get("/status", dependencies=[Depends(require_admin)])
def status():
    init_lab_db()
    with db() as con:
        knowledge = con.execute("SELECT COUNT(*) FROM ai_lab_knowledge").fetchone()[0]
        projects = con.execute("SELECT COUNT(*) FROM ai_lab_projects").fetchone()[0]
        files = con.execute("SELECT COUNT(*) FROM ai_lab_files").fetchone()[0]
    return {"knowledge_entries": knowledge, "projects": projects, "files": files, "learning_mode": "persistent-local"}


@router.get("/knowledge", dependencies=[Depends(require_admin)])
def list_knowledge():
    init_lab_db()
    with db() as con:
        rows = con.execute("SELECT id,title,tags,source,created_at,updated_at,length(content) AS characters FROM ai_lab_knowledge ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


@router.post("/knowledge", dependencies=[Depends(require_admin)])
def add_knowledge(body: KnowledgeIn):
    init_lab_db()
    with db() as con:
        cur = con.execute("INSERT INTO ai_lab_knowledge(title,content,tags,created_at,updated_at) VALUES(?,?,?,?,?)", (body.title, body.content, body.tags, now(), now()))
    return {"ok": True, "id": cur.lastrowid, "title": body.title, "characters": len(body.content)}


@router.delete("/knowledge/{knowledge_id}", dependencies=[Depends(require_admin)])
def delete_knowledge(knowledge_id: int):
    init_lab_db()
    with db() as con:
        cur = con.execute("DELETE FROM ai_lab_knowledge WHERE id=?", (knowledge_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "knowledge entry not found")
    return {"ok": True}


@router.get("/projects", dependencies=[Depends(require_admin)])
def list_projects():
    init_lab_db()
    with db() as con:
        rows = con.execute("SELECT p.*,COUNT(f.id) AS files FROM ai_lab_projects p LEFT JOIN ai_lab_files f ON f.project_id=p.id GROUP BY p.id ORDER BY p.updated_at DESC").fetchall()
    return [dict(r) for r in rows]


@router.post("/projects", dependencies=[Depends(require_admin)])
def create_project(body: ProjectIn):
    init_lab_db()
    with db() as con:
        try:
            cur = con.execute("INSERT INTO ai_lab_projects(name,language,description,created_at,updated_at) VALUES(?,?,?,?,?)", (body.name, body.language, body.description, now(), now()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "project already exists")
    return {"ok": True, "id": cur.lastrowid, **body.model_dump()}


@router.get("/projects/{project_id}/files", dependencies=[Depends(require_admin)])
def list_files(project_id: int):
    init_lab_db()
    with db() as con:
        if not con.execute("SELECT 1 FROM ai_lab_projects WHERE id=?", (project_id,)).fetchone():
            raise HTTPException(404, "project not found")
        rows = con.execute("SELECT id,path,length(content) AS characters,updated_at FROM ai_lab_files WHERE project_id=? ORDER BY path", (project_id,)).fetchall()
    return [dict(r) for r in rows]


@router.put("/projects/{project_id}/files", dependencies=[Depends(require_admin)])
def save_file(project_id: int, body: FileIn):
    init_lab_db()
    with db() as con:
        if not con.execute("SELECT 1 FROM ai_lab_projects WHERE id=?", (project_id,)).fetchone():
            raise HTTPException(404, "project not found")
        con.execute("INSERT INTO ai_lab_files(project_id,path,content,updated_at) VALUES(?,?,?,?) ON CONFLICT(project_id,path) DO UPDATE SET content=excluded.content,updated_at=excluded.updated_at", (project_id, body.path, body.content, now()))
        con.execute("UPDATE ai_lab_projects SET updated_at=? WHERE id=?", (now(), project_id))
    return {"ok": True, "project_id": project_id, "path": body.path, "characters": len(body.content)}


@router.get("/projects/{project_id}/files/{path:path}", dependencies=[Depends(require_admin)])
def read_file(project_id: int, path: str):
    init_lab_db()
    with db() as con:
        row = con.execute("SELECT path,content,updated_at FROM ai_lab_files WHERE project_id=? AND path=?", (project_id, path)).fetchone()
    if not row:
        raise HTTPException(404, "file not found")
    return dict(row)


@router.post("/teach", dependencies=[Depends(require_admin)])
def teach(body: KnowledgeIn):
    return add_knowledge(body)


@router.post("/chat", dependencies=[Depends(require_admin)])
async def lab_chat(body: LabChat):
    init_lab_db()
    context = knowledge_context(body.prompt) if body.use_knowledge else ""
    system = "You are the private AI3 assistant. You are allowed to work with the owner's supplied knowledge and technical projects. Do not claim that stored knowledge is true without evidence. Never expose secrets."
    if context:
        system += "\n\nOWNER KNOWLEDGE:\n" + context
    answer, raw = await ollama_chat(body.model, system, body.prompt)
    return {"answer": answer, "model": body.model, "knowledge_used": bool(context), "raw": raw}


@router.post("/code", dependencies=[Depends(require_admin)])
async def code_task(body: CodeTask):
    init_lab_db()
    context = knowledge_context(body.task) if body.use_knowledge else ""
    project_context = ""
    if body.project_id:
        with db() as con:
            rows = con.execute("SELECT path,content FROM ai_lab_files WHERE project_id=? ORDER BY path", (body.project_id,)).fetchall()
        project_context = "\n\n".join(f"FILE: {r['path']}\n```\n{r['content']}\n```" for r in rows)
    system = f"You are AI3 Coding Lab. Program in {body.language}. Produce correct, maintainable code, explain important choices, and identify tests. You may use the owner's private project files and knowledge. Do not invent files or APIs."
    prompt = body.task
    if context:
        prompt += "\n\nPRIVATE KNOWLEDGE:\n" + context
    if project_context:
        prompt += "\n\nCURRENT PROJECT FILES:\n" + project_context
    answer, raw = await ollama_chat(body.model, system, prompt)
    return {"answer": answer, "model": body.model, "language": body.language, "knowledge_used": bool(context), "project_files_used": bool(project_context), "raw": raw}


# Included by app.main after its application object is initialized.
def install(app):
    init_lab_db()
    app.include_router(router)
