import asyncio
import json
from typing import Optional, Dict, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import subprocess
import sys

class MCPClient:
    def __init__(self, server_script: str = "mcp_server.py"):
        """
        Initialize MCP Client
        
        Args:
            server_script: Path to the MCP server script
        """
        self.server_script = server_script
        self.session: Optional[ClientSession] = None
        self.server_process: Optional[subprocess.Popen] = None
        
    async def connect(self):
        """Connect to the MCP server"""
        print("🔌 Connecting to MCP Server...")
        
        # Start the server process
        self.server_process = subprocess.Popen(
            [sys.executable, self.server_script],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Create stdio transport
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script],
            env=None
        )
        
        # Connect using stdio
        try:
            async with stdio_client(server_params) as (read_stream, write_stream):
                self.session = ClientSession(read_stream, write_stream)
                await self.session.initialize()
                print("✅ Connected to MCP Server")
                
                # List available tools
                tools = await self.session.list_tools()
                print(f"📋 Available tools: {[tool.name for tool in tools.tools]}")
                
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            raise
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on the MCP server"""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        
        print(f"🔧 Calling tool: {tool_name} with arguments: {arguments}")
        
        try:
            result = await self.session.call_tool(tool_name, arguments)
            
            # Extract text from result
            response_text = ""
            for content in result.content:
                if content.type == "text":
                    response_text += content.text + "\n"
            
            print(f"✅ Tool response received")
            return response_text.strip()
            
        except Exception as e:
            error_msg = f"Tool call failed: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg
    
    async def disconnect(self):
        """Disconnect from MCP server"""
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait()
            print("🔌 Disconnected from MCP Server")
    
    async def get_profile(self, user_id: str) -> str:
        """Convenience method to get profile data"""
        return await self.call_tool("get_profile", {"user_id": user_id})

# Simple test function
async def test_mcp_client():
    """Test the MCP client"""
    client = MCPClient()
    
    try:
        # Connect to server
        await client.connect()
        
        # Test get_profile tool
        print("\n" + "="*50)
        print("Testing get_profile tool...")
        print("="*50)
        
        # Test case 1: Valid user ID
        print("\n1. Testing with user_id='U001':")
        result1 = await client.get_profile("U001")
        print("Result:")
        print(result1)
        
        # Test case 2: Valid user ID
        print("\n2. Testing with user_id='U002':")
        result2 = await client.get_profile("U002")
        print("Result:")
        print(result2)
        
        # Test case 3: Non-existent user ID
        print("\n3. Testing with non-existent user_id='U999':")
        result3 = await client.get_profile("U999")
        print("Result:")
        print(result3)
        
        print("\n" + "="*50)
        print("✅ All tests completed!")
        print("="*50)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_mcp_client())