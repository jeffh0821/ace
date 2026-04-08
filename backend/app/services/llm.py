"""LLM service — call OpenRouter for answer generation with confidence scoring."""

import json
from dataclasses import dataclass
from typing import List, Optional

import httpx

from app.core.config import settings
from app.services.retrieval import RetrievedChunk

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You are ACE (Assistant for Connector Engineering), a technical Q&A assistant for PEI-Genesis. You answer questions about electrical connectors and related engineering topics based ONLY on the provided context documents.

RULES:
1. Answer ONLY based on the provided context. Do not use external knowledge.
2. If the context does not contain enough information to answer confidently, say so.
3. Cite your sources using the document title and page number.
4. Be clear, conversational, and technically accurate.

You MUST respond in the following JSON format:
{
  "answer": "Your answer text here with inline citations like [Document Title, p.X]",
  "confidence": 0.85,
  "citations": [
    {
      "document_title": "Document Title",
      "page_number": 1,
      "excerpt": "Relevant excerpt from the source"
    }
  ]
}

The "confidence" field must be a float between 0.0 and 1.0 representing how confident you are that your answer is correct and complete based on the provided context. Use these guidelines:
- 0.9-1.0: Context directly and clearly answers the question
- 0.7-0.9: Context mostly answers the question with minor gaps
- 0.5-0.7: Context partially addresses the question
- 0.0-0.5: Context is insufficient or irrelevant
"""


@dataclass
class LLMResponse:
    answer: str
    confidence: float
    citations: List[dict]
    raw_response: Optional[str] = None


def _build_context(chunks: List[RetrievedChunk]) -> str:
    if not chunks:
        return "No relevant documents found."
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"--- Source {i}: {chunk.document_title} (Page {chunk.page_number}) ---\n"
            f"{chunk.text}\n"
        )
    return "\n".join(parts)


async def generate_answer(question: str, chunks: List[RetrievedChunk]) -> LLMResponse:
    """Send question + context to OpenRouter, parse structured response."""
    context = _build_context(chunks)

    user_message = f"""Context documents:
{context}

Question: {question}

Respond in the required JSON format with answer, confidence, and citations."""

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://ace.pei-genesis.local",
                "X-Title": "ACE Q&A",
            },
            json={
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.1,
                "max_tokens": 2000,
            },
        )
        response.raise_for_status()

    data = response.json()
    raw_content = data["choices"][0]["message"]["content"]

    try:
        content = raw_content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]
        parsed = json.loads(content)

        return LLMResponse(
            answer=parsed.get("answer", "I could not generate an answer."),
            confidence=float(parsed.get("confidence", 0.0)),
            citations=parsed.get("citations", []),
            raw_response=raw_content,
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return LLMResponse(
            answer=raw_content,
            confidence=0.3,
            citations=[],
            raw_response=raw_content,
        )
