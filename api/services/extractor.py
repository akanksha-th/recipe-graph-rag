from api.core.config import get_settings
from api.schema.graph import KnowledgeGraph, Triple
from groq import AsyncGroq
import asyncio
import json

settings = get_settings()
SYSTEM_PROMPT = """You are a knowledge graph extraction engine.
When given text, extract all factual triples (subject, predicate, object).
Respond ONLY with valid JSON in this exact format, no explanation:
{{
  "triples": [
    {{
      "subject": "I",
      "predicate": "ate",
      "object": "one fried egg"
    }},
    {{
      "subject": "fried egg",
      "predicate": "has",
      "object": "runny yolk"
    }},
    {{
      "subject": "toast",
      "predicate": "is",
      "object": "too dark"
    }},
    {{
      "subject": "toast",
      "predicate": "is",
      "object": "crisp"
    }},
    {{
      "subject": "coffee",
      "predicate": "contains",
      "object": "cream"
    }},
    {{
      "subject": "coffee",
      "predicate": "contains",
      "object": "sugar"
    }}
  ]
}}
"""

USER_PROMPT_TEMPLATE = """Extract all triples from the following text:

TEXT: "{text}"

Rules:
- Do NOT skip any possible, true triple
- Do NOT force any triple — only extract complete, meaningful ones
- Return ONLY the JSON object, no markdown, no explanation"""

CHUNK_SIZE = 4000      # characters per chunk
CHUNK_OVERLAP = 200


def _chunk_text(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        if end < len(text):
            boundary = text.rfind('. ', start, end)
            if boundary != -1:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        start = end - CHUNK_OVERLAP
    return chunks


class TripleExtractionService:
    def __init__(self):
        self.client = AsyncGroq(api_key=settings.groq_api_key)

    async def build_kg(self, text: str) -> KnowledgeGraph:
        chunks = _chunk_text(text)
        
        if len(chunks) == 1:
            return await self._extract_from_chunk(chunks[0])
        
        sem = asyncio.Semaphore(3)
        async def bounded_extract(chunk):
            async with sem:
                return await self._extract_from_chunk(chunk)
        
        results = await asyncio.gather(
            *[bounded_extract(chunk) for chunk in chunks],
            return_exceptions=True
        )
        
        # Merge all triples, skip failed chunks
        all_triples: list[Triple] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Warning: chunk {i} failed: {result}")
                continue
            all_triples.extend(result.triples)

        return KnowledgeGraph(triples=all_triples)

    async def _extract_from_chunk(self, text: str) -> KnowledgeGraph:
        try:
            raw_response = await self.client.chat.completions.create(
                model=settings.model_name,
                max_completion_tokens=4000,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": USER_PROMPT_TEMPLATE.format(text=text),
                    }
                ]
            )
            return self._parse_json(raw_response.choices[0].message.content)
        except Exception as e:
            raise ValueError(f"Failed to extract triples: {e}")

    def _parse_json(self, text: str) -> KnowledgeGraph:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]).strip()
        try:
            data = json.loads(text)
            if not data or "triples" not in data:
                raise ValueError("No triples found in the response")
            return KnowledgeGraph(**data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON: {e}")
