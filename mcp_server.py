import asyncio
import mysql.connector
from mysql.connector import Error
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from pydantic import BaseModel
from typing import Any, Optional
import json
import os

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',  # Change as per your MySQL setup
    'password': '12345678',  # Add your password
    'database': 'chatbot_db',
    'port': 3306
}

class GetProfileArguments(BaseModel):
    user_id: str

class MCPServer:
    def __init__(self):
        self.server = Server("mysql-profile-server")
        
        # Register tools
        self.server.list_tools()(self.handle_list_tools)
        self.server.call_tool()(self.handle_call_tool)
        
        # Initialize database connection
        self.db_connection = None
        
    async def connect_to_database(self):
        """Establish MySQL database connection"""
        try:
            self.db_connection = mysql.connector.connect(
                host=DB_CONFIG['host'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                port=DB_CONFIG['port']
            )
            print("✅ Connected to MySQL database")
            return True
        except Error as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    async def handle_list_tools(self) -> list[types.Tool]:
        """List available tools"""
        return [
            types.Tool(
                name="get_profile",
                description="Get user profile details from the database by user ID",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "The unique user ID"
                        }
                    },
                    "required": ["user_id"]
                }
            )
        ]
    
    async def handle_call_tool(
        self, name: str, arguments: dict[str, Any] | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """Handle tool calls"""
        if name == "get_profile":
            return await self.handle_get_profile(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    async def handle_get_profile(self, arguments: Optional[dict]) -> list[types.TextContent]:
        """Execute get_profile tool"""
        try:
            if not arguments or 'user_id' not in arguments:
                return [
                    types.TextContent(
                        type="text",
                        text="Error: user_id is required"
                    )
                ]
            
            user_id = arguments['user_id']
            
            # Connect to database if not connected
            if not self.db_connection or not self.db_connection.is_connected():
                await self.connect_to_database()
            
            cursor = self.db_connection.cursor(dictionary=True)
            
            # Query the database
            query = "SELECT * FROM profiles WHERE user_id = %s"
            cursor.execute(query, (user_id,))
            result = cursor.fetchone()
            
            cursor.close()
            
            if result:
                # Format the response
                profile_text = f"""
                User Profile Details:
                - User ID: {result['user_id']}
                - Name: {result['user_name']}
                - Created Date: {result['created_date']}
                - Phone: {result['phone_number']}
                - Business: {result['business_name']}
                - Email: {result['email_id']}
                """
                
                return [
                    types.TextContent(
                        type="text",
                        text=profile_text
                    )
                ]
            else:
                return [
                    types.TextContent(
                        type="text",
                        text=f"No profile found for user ID: {user_id}"
                    )
                ]
                
        except Error as e:
            error_msg = f"Database error: {str(e)}"
            print(f"❌ {error_msg}")
            return [
                types.TextContent(
                    type="text",
                    text=f"Error accessing database: {str(e)}"
                )
            ]
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"❌ {error_msg}")
            return [
                types.TextContent(
                    type="text",
                    text=f"Error: {str(e)}"
                )
            ]
    
    async def run(self):
        """Run the MCP server"""
        print("🚀 Starting MCP Server with MySQL Profile Tool...")
        
        # Connect to database
        if not await self.connect_to_database():
            print("⚠️  Starting server without database connection")
        
        # Run with stdio transport
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="mysql-profile-server",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

async def main():
    server = MCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())