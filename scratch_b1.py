import asyncio

from agent.mcp_client import mcp_client


async def main():
      await mcp_client.connect()
      try:
          tools = await mcp_client.list_tools()
          print(f"\nConnected — {len(tools)} tools:\n{tools}")

          specialities = await mcp_client.call_tool("list_specialities", {})
          print(f"\nlist_specialities round-trip:\n{specialities}")
      finally:
          await mcp_client.close()


asyncio.run(main())
