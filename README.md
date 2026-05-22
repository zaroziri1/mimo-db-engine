# MiMo Database Design Engine

Natural language → Production-ready database schema, powered by **MiMo v2.5 Pro**.

## Features

- **Natural Language Input** — Describe your project in plain English
- **6 Quick Templates** — E-Commerce, Social Media, SaaS, Blog, Hospital, Project Management
- **Schema Visualization** — Tables with columns, types, constraints
- **ERD Diagram** — Visual entity-relationship diagram
- **SQL Migrations** — Ready-to-use CREATE TABLE SQL
- **Optimization Engine** — MiMo-powered index and performance suggestions
- **Export** — Download SQL migration file

## How It Works

1. Describe your project (or pick a template)
2. MiMo analyzes and generates complete database schema
3. View tables, ERD, relationships, recommendations
4. Export SQL migration
5. Run optimization analysis

## API Endpoints

- `POST /api/generate` — Generate schema from description
- `POST /api/optimize` — Get optimization suggestions
- `POST /api/indexes` — Get index suggestions
- `GET /api/templates` — Example project templates
- `POST /api/export/sql` — Export as SQL file

## Tech Stack

- **Backend:** Python FastAPI
- **AI:** MiMo v2.5 Pro (Xiaomi)
- **Frontend:** Vanilla HTML/CSS/JS
- **Database:** PostgreSQL schema output

## Deployment

```bash
pip install -r requirements.txt
python src/main.py
```

## Powered By

- [MiMo](https://github.com/XiaomiMiMo/MiMo) — Xiaomi's AI Reasoning Model
