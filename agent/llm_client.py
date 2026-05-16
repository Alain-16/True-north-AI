import anthropic
from core.config import get_settings

class LLMClient:
    SONNET = "claude-sonnet-4-6"
    OPUS = "claude-opus-4-7"

    def __init__(self):
        settings = get_settings()
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    
    async def simple(
            self,
            prompt: str,
            system: str | None = None,
            max_tokens: int = 1024,
            **kwargs,
    ) -> str:
        return await self._call(self.SONNET,prompt,system,max_tokens,**kwargs)
    
    async def complex(
            self,
            prompt:str,
            system:str | None = None,
            max_tokens: int = 1024,
            **kwargs,
    ) -> str:
        return await self._call(self.OPUS,prompt,system,max_tokens,**kwargs)
    
    async def _call(
            self,
            model:str,
            prompt:str,
            system:str,
            max_tokens: int,
            **kwargs,
    ) -> str:
        params: dict = {
            "model" : model,
            "max_tokens":max_tokens,
            "messages":[{"role":"user","content":prompt}],
            **kwargs,
        }


        if system:
            params["system"] = [{
                "type": "text",
                "text": system,
            }]

        #  Execute the call by unpacking the dictionary
        response = await self._client.messages.create(**params)
        return response.content[0].text


llm = LLMClient()