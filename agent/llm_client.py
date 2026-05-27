import anthropic
from core.config import get_settings
import asyncio
from anthropic import APIStatusError
class LLMClient:
    SONNET = "claude-sonnet-4-6"
    OPUS = "claude-opus-4-7"

    def __init__(self):
        settings = get_settings()
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    
    async def simple(
            self,
            prompt: str | None = None,
            system: str | None = None,
            messages: list[dict] | None= None,
            max_tokens: int = 1024,
            **kwargs,
    ) -> str:
        return await self._call(self.SONNET,prompt,system,messages,max_tokens,**kwargs)
    
    async def complex(
            self,
            prompt:str | None = None,
            system:str | None = None,
            messages: list[dict] | None= None,
            max_tokens: int = 2048,
            **kwargs,
    ) -> str:
        return await self._call(self.OPUS,prompt,system,messages,max_tokens,**kwargs)
    
    async def _call(
            self,
            model:str,
            prompt:str | None,
            system:str | None,
            messages: list[dict] | None,
            max_tokens: int,
            **kwargs,
    ) -> str:
        if messages is None:
            if prompt is None:
                raise ValueError("Must provide either `prompt` or `messages`")
            messages = [{"role": "user", "content": prompt}]

        params: dict = {"model": model, "max_tokens": max_tokens, "messages": messages, **kwargs}

        if system:
            params["system"] = [{"type": "text", "text": system}]

      
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = await self._client.messages.create(**params)
                return response.content[0].text
            except APIStatusError as e:
                if e.status_code not in (429, 529) or attempt == max_attempts - 1:
                    raise
                await asyncio.sleep(2 ** attempt)


llm = LLMClient()