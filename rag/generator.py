import asyncio
from collections.abc import AsyncIterator

from app.settings import settings


async def stream_gemini(prompt: str, system: str) -> AsyncIterator[str]:
    """
    Stream Gemini 2.0 Flash response token by token.
    Wraps the sync Vertex SDK using a thread + asyncio.Queue for true streaming.
    """
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=256)

    def _generate() -> None:
        import vertexai
        from vertexai.generative_models import (
            Content,
            GenerationConfig,
            GenerativeModel,
            Part,
        )

        vertexai.init(project=settings.google_cloud_project, location=settings.vertex_location)
        model = GenerativeModel(
            settings.vertex_generation_model,
            system_instruction=system,
        )
        try:
            response = model.generate_content(
                [Content(role="user", parts=[Part.from_text(prompt)])],
                generation_config=GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=1024,
                ),
                stream=True,
            )
            for chunk in response:
                if chunk.text:
                    loop.call_soon_threadsafe(queue.put_nowait, chunk.text)
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(queue.put_nowait, f"\n[Generation error: {exc}]")
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    loop.run_in_executor(None, _generate)

    while True:
        token = await queue.get()
        if token is None:
            break
        yield token
