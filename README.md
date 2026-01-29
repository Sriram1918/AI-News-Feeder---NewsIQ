# AI-Powered News Intelligence System

An AI-powered news aggregation and intelligence system that monitors real-time news, detects breaking events, verifies information across sources, generates evolving story timelines, and delivers personalized yet ethically diverse news feeds.

## Features

- **Personalized Research Assistant**: Deep context analysis for any news article
- **Deep Research Mode**: RAG-based analysis with multiple perspectives
- **Story Timelines**: Track how stories evolve over time
- **Ethical Diversity**: Combat filter bubbles with "Blind Spot Articles"
- **Real-time Ingestion**: RSS feed monitoring with automatic content extraction

## Tech Stack

- **Backend**: Python 3.11, FastAPI, Celery
- **Database**: PostgreSQL 15 + pgvector
- **Cache/Queue**: Redis
- **Embeddings**: Google Gemini text-embedding-004
- **LLM**: Google Gemini 1.5 Flash
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+
- Python 3.11+
- Google AI API Key

### Setup

1. Clone and setup environment:
```bash
cp .env.example .env
# Edit .env with your API keys
```

2. Start all services:
```bash
docker-compose up -d
```

3. Run database migrations:
```bash
cd backend
alembic upgrade head
```

4. Start the development servers:
```bash
# Backend (in one terminal)
cd backend
uvicorn app.main:app --reload --port 8000

# Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

5. Open http://localhost:5173

## Project Structure

```
news-intelligence-system/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # API endpoints
│   │   ├── services/            # Business logic
│   │   ├── models/              # SQLAlchemy models
│   │   └── tasks/               # Celery tasks
│   ├── db/                      # Migrations & schema
│   └── tests/                   # Test suites
├── frontend/
│   └── src/
│       ├── components/          # React components
│       ├── hooks/               # Custom hooks
│       └── pages/               # Page components
└── docker-compose.yml
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## License

MIT
