"""MiMo Database Design Engine - Backend API
Natural language → Production-ready database schema.
"""
import os
import json
import re
import time
import requests
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MiMo Database Design Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MIMO_API = os.getenv("MIMO_API_URL")
MIMO_MODEL = "xmtp/mimo-v2.5-pro"

SCHEMA_SYSTEM = """You are a senior database architect. Given a business description, design a production-ready PostgreSQL schema.

Return ONLY valid JSON (no markdown fences, no extra text):
{
  "project_name": "string",
  "description": "string",
  "database": "postgresql",
  "tables": [
    {
      "name": "string",
      "description": "string",
      "columns": [
        {"name": "string", "type": "string", "nullable": false, "primary_key": false, "unique": false, "default": null, "references": null}
      ],
      "indexes": [
        {"name": "string", "columns": ["string"], "unique": false, "type": "btree"}
      ]
    }
  ],
  "relationships": [
    {"from_table": "string", "from_column": "string", "to_table": "string", "to_column": "string", "type": "one_to_many"}
  ],
  "migrations": {"up": "CREATE TABLE SQL", "down": "DROP TABLE SQL"},
  "recommendations": ["string"]
}

Rules: PostgreSQL types (serial, uuid, varchar, text, boolean, timestamptz, jsonb, decimal). Every table: id, created_at, updated_at. snake_case. Foreign keys. Indexes on FKs. Return ONLY the JSON."""

INDEX_SYSTEM = """You are a database performance expert. Given a schema (JSON), analyze it and suggest additional indexes.

Return ONLY a JSON array of index suggestions:
[
  {
    "table": "string",
    "columns": ["string"],
    "type": "btree|gin|gist|hash|brin",
    "reason": "string",
    "estimated_impact": "high|medium|low"
  }
]

Consider: query patterns, foreign keys, common WHERE clauses, ORDER BY, JOIN conditions, partial indexes."""

OPTIMIZE_SYSTEM = """You are a database optimization expert. Given a schema (JSON), suggest optimizations.

Return ONLY a JSON array:
[
  {
    "category": "performance|security|data_integrity|scalability",
    "issue": "string",
    "suggestion": "string",
    "priority": "high|medium|low",
    "example": "SQL or code example"
  }
]"""

def call_mimo(system_prompt, user_prompt, max_tokens=4000):
    """Call MiMo API with streaming response handling."""
    try:
        resp = requests.post(
            MIMO_API,
            json={
                "model": MIMO_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
            timeout=180,
            stream=True,
        )
        resp.raise_for_status
        
        full_text = ""
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                choice = chunk.get("choices", [{}])[0]
                # Handle both streaming (delta) and non-streaming (message) formats
                delta = choice.get("delta", {})
                message = choice.get("message", {})
                content = delta.get("content") or message.get("content") or ""
                full_text += content
            except json.JSONDecodeError:
                continue
        
        return full_text.strip()
    except Exception as e:
        return None

def parse_json_response(text):
    """Extract JSON from MiMo response (handles markdown wrappers)."""
    if not text:
        return None
    # Try direct parse
    try:
        return json.loads(text)
    except:
        pass
    # Try extracting from ```json ... ``` blocks
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    # Try finding first { or [
    for i, ch in enumerate(text):
        if ch in ('{', '['):
            depth = 0
            for j, ch2 in enumerate(text[i:], i):
                if ch2 in ('{', '['):
                    depth += 1
                elif ch2 in ('}', ']'):
                    depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[i:j+1])
                    except:
                        break
            break
    # Try repairing truncated JSON
    # Find the start of JSON
    start = None
    for i, ch in enumerate(text):
        if ch in ('{', '['):
            start = i
            break
    if start is not None:
        partial = text[start:]
        # Count open/close braces
        opens = partial.count('{') + partial.count('[')
        closes = partial.count('}') + partial.count(']')
        if opens > closes:
            # Add missing closing brackets
            repair = partial
            stack = []
            for ch in repair:
                if ch in ('{', '['):
                    stack.append('}' if ch == '{' else ']')
                elif ch in ('}', ']'):
                    if stack and stack[-1] == ch:
                        stack.pop()
            repair += ''.join(reversed(stack))
            try:
                return json.loads(repair)
            except:
                pass
    return None

# ── API Endpoints ────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse("/root/mimo-db-engine/src/index.html")

@app.post("/api/generate")
async def generate_schema(request: Request):
    """Generate database schema from natural language description."""
    body = await request.json()
    description = body.get("description", "").strip()
    db_type = body.get("database", "postgresql")
    
    if not description:
        return JSONResponse({"error": "Description is required"}, status_code=400)
    
    prompt = f"Business description:\n{description}\n\nDatabase: {db_type}\n\nDesign the complete database schema. Be thorough — include all tables, columns, types, constraints, indexes, relationships, migrations, and recommendations."
    
    raw = call_mimo(SCHEMA_SYSTEM, prompt, max_tokens=8000)
    if not raw:
        return JSONResponse({"error": "MiMo API unavailable. Try again."}, status_code=503)
    
    schema = parse_json_response(raw)
    if not schema:
        return JSONResponse({"error": "Failed to parse schema. Try again.", "raw": raw[:500]}, status_code=500)
    
    return {"success": True, "schema": schema, "tokens_used": len(raw)}

@app.post("/api/optimize")
async def optimize_schema(request: Request):
    """Get optimization suggestions for a schema."""
    body = await request.json()
    schema = body.get("schema")
    
    if not schema:
        return JSONResponse({"error": "Schema is required"}, status_code=400)
    
    raw = call_mimo(OPTIMIZE_SYSTEM, f"Schema:\n{json.dumps(schema, indent=2)}", max_tokens=2000)
    if not raw:
        return JSONResponse({"error": "MiMo API unavailable"}, status_code=503)
    
    suggestions = parse_json_response(raw)
    if not suggestions:
        return JSONResponse({"error": "Failed to parse suggestions"}, status_code=500)
    
    return {"success": True, "suggestions": suggestions}

@app.post("/api/indexes")
async def suggest_indexes(request: Request):
    """Get index suggestions for a schema."""
    body = await request.json()
    schema = body.get("schema")
    
    if not schema:
        return JSONResponse({"error": "Schema is required"}, status_code=400)
    
    raw = call_mimo(INDEX_SYSTEM, f"Schema:\n{json.dumps(schema, indent=2)}", max_tokens=2000)
    if not raw:
        return JSONResponse({"error": "MiMo API unavailable"}, status_code=503)
    
    indexes = parse_json_response(raw)
    if not indexes:
        return JSONResponse({"error": "Failed to parse indexes"}, status_code=500)
    
    return {"success": True, "indexes": indexes}

@app.get("/api/templates")
async def get_templates():
    """Get example project templates."""
    templates = [
        {
            "id": "ecommerce",
            "name": "E-Commerce Marketplace",
            "icon": "🛒",
            "description": "Multi-vendor marketplace with products, orders, payments, reviews",
            "prompt": "E-commerce marketplace with: users (buyers/sellers), products with variants, categories, shopping cart, orders with order items, payments, shipping addresses, reviews and ratings, coupons/discounts, seller profiles with shop settings. Support for multiple vendors per platform."
        },
        {
            "id": "social",
            "name": "Social Media Platform",
            "icon": "📱",
            "description": "Posts, comments, followers, likes, notifications",
            "prompt": "Social media platform with: user profiles, posts with images/media, comments (nested), likes, followers/following, direct messages, notifications, hashtags, bookmarks, user blocks/mutes, content reports/moderation."
        },
        {
            "id": "saas",
            "name": "SaaS Platform",
            "icon": "☁️",
            "description": "Multi-tenant SaaS with subscriptions, teams, permissions",
            "prompt": "SaaS platform with: organizations/teams, team members with roles (admin/member/viewer), subscription plans with features, billing/invoices, API keys, audit logs, user invitations, usage tracking, feature flags, webhooks."
        },
        {
            "id": "blog",
            "name": "Blog / CMS",
            "icon": "📝",
            "description": "Articles, categories, tags, comments, authors",
            "prompt": "Blog/CMS with: articles with rich content, categories, tags (many-to-many), comments with threading, authors/contributors with profiles, media library, SEO metadata, scheduled publishing, article versions/revisions."
        },
        {
            "id": "hospital",
            "name": "Hospital Management",
            "icon": "🏥",
            "description": "Patients, doctors, appointments, prescriptions, billing",
            "prompt": "Hospital management with: patients, doctors with specialties, appointments, medical records, prescriptions, lab results, billing/invoices, insurance claims, departments, room/bed management, staff schedules."
        },
        {
            "id": "project",
            "name": "Project Management",
            "icon": "📋",
            "description": "Projects, tasks, sprints, time tracking, team collaboration",
            "prompt": "Project management tool with: projects, tasks with subtasks, sprints/iterations, labels/tags, task assignments, comments/activity feed, time tracking, file attachments, project templates, team workspaces, custom fields."
        },
    ]
    return {"templates": templates}

@app.get("/api/export/sql")
async def export_sql():
    return JSONResponse({"info": "POST schema to /api/export/sql with body {schema}"}, status_code=200)

@app.post("/api/export/sql")
async def export_sql_post(request: Request):
    """Export schema as SQL migration file."""
    body = await request.json()
    schema = body.get("schema", {})
    
    sql_lines = ["-- Generated by MiMo Database Design Engine", 
                 f"-- Project: {schema.get('project_name', 'Untitled')}",
                 f"-- Database: {schema.get('database', 'postgresql')}",
                 ""]
    
    # Create tables
    for table in schema.get("tables", []):
        sql_lines.append(f"CREATE TABLE {table['name']} (")
        col_defs = []
        for col in table.get("columns", []):
            parts = [f"  {col['name']} {col['type']}"]
            if col.get("primary_key"):
                parts.append("PRIMARY KEY")
            if not col.get("nullable", True) and not col.get("primary_key"):
                parts.append("NOT NULL")
            if col.get("unique") and not col.get("primary_key"):
                parts.append("UNIQUE")
            if col.get("default"):
                parts.append(f"DEFAULT {col['default']}")
            col_defs.append(" ".join(parts))
        
        # Add foreign keys
        for col in table.get("columns", []):
            if col.get("references"):
                ref = col["references"]
                col_defs.append(f"  FOREIGN KEY ({col['name']}) REFERENCES {ref}")
        
        sql_lines.append(",\n".join(col_defs))
        sql_lines.append(");\n")
        
        # Indexes
        for idx in table.get("indexes", []):
            unique = "UNIQUE " if idx.get("unique") else ""
            cols = ", ".join(idx.get("columns", []))
            sql_lines.append(f"CREATE {unique}INDEX {idx['name']} ON {table['name']} ({cols});")
        
        sql_lines.append("")
    
    sql = "\n".join(sql_lines)
    return JSONResponse({"sql": sql}, media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)
