import asyncio
import mcp.client.stdio
import mcp.client as mcp
import json

async def test_mcp_server():
    """Test the MCP server directly"""
    print("🧪 Testing MCP Server...")
    
    # Start the server process
    import subprocess
    server_process = subprocess.Popen(
        ["python", "mcp_server.py"],
        stdout=subprocess.PIPE,
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    try:
        # Connect to server via stdio
        async with mcp.client.stdio.stdio_client(
            server_process.stdout,
            server_process.stdin
        ) as client:
            # Initialize
            await client.initialize()
            
            # List tools
            tools = await client.list_tools()
            print(f"📋 Available tools: {[t.name for t in tools.tools]}")
            
            # Call get_profile tool
            print("\n🔧 Testing get_profile tool...")
            result = await client.call_tool(
                "get_profile",
                arguments={"user_id": "U001"}
            )
            
            print("✅ Tool call result:")
            for content in result.content:
                if content.type == "text":
                    print(content.text)
            
    finally:
        # Clean up
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    asyncio.run(test_mcp_server())