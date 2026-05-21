import json
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.sse import sse_client
from core.config import get_settings

class MCPClient:
    def __init__(self):
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None

    async def connect(self) -> None:
        settings = get_settings()
        self._stack = AsyncExitStack()
        read,write = await self._stack.enter_async_context(
            sse_client(url=settings.mcp_server_url)
        )
        self._session = await self._stack.enter_async_context(
            ClientSession(read,write)
        )
        await self._session.initialize()
    
    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._session = None
        self._stack = None
    
    async def call_tool(self,name:str,arguments: dict | None=None):
        if self._session is None:
            raise RuntimeError("MCP client is not connected- call connect() first")
        result = await self._session.call_tool(name,arguments or {})
        

        if result.isError:
            detail = result.content[0].text if result.content else "unknown error"
            raise RuntimeError(f"mcp tool '{name}' failed: {detail}")
        
        
        return [json.loads(block.text) for block in result.content]
    
    async def list_tools(self)-> list[str]:
        if self._session is None:
            raise RuntimeError("MCP client is not connected - call connect() first")
        result = await self._session.list_tools()
        return [tool.name for tool in result.tools]
    
mcp_client = MCPClient()
        