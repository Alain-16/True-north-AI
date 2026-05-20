from mcp_server.app import mcp
import mcp_server.tools.patient
import mcp_server.tools.appointment

if __name__ == "__main__":
    mcp.run(transport="sse")