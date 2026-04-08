# ACE — Assistant for Connector Engineering

RAG-powered Q&A system for technical connector engineering knowledge.

## Quick Start
docker-compose up --build

## Architecture
- Backend: FastAPI + SQLite + Chroma
- Frontend: React + Vite + TailwindCSS
- Embeddings: sentence-transformers (self-hosted)
- LLM: OpenRouter
- OCR: Tesseract
