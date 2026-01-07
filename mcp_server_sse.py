from mcp.server.sse import SseServerTransport
from mcp.server import Server
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import asyncio
import mysql.connector
from mysql.connector import Error
import mcp.types as types
from typing import Any, Optional
from fastapi.responses import JSONResponse

# Database configuration (same as before)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '12345678',
    'database': 'chatbot_db',
    'port': 3306
}

app = FastAPI()
server = Server("mysql-profile-server-sse")
db_connection = None

def connect_to_database():
    """Establish MySQL database connection"""
    global db_connection
    try:
        db_connection = mysql.connector.connect(**DB_CONFIG)
        print("✅ Connected to MySQL database")
        return True
    except Error as e:
        print(f"❌ Database connection failed: {e}")
        return False

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="get_profile",
            description="Get user profile details from database by user ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"}
                },
                "required": ["user_id"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Optional[dict]) -> list[types.TextContent]:
    """Handle tool calls"""
    if name != "get_profile":
        raise ValueError(f"Unknown tool: {name}")
    
    if not arguments or 'user_id' not in arguments:
        return [types.TextContent(type="text", text="Error: user_id is required")]
    
    user_id = arguments['user_id']
    
    try:
        # Connect to database if needed
        if not db_connection or not db_connection.is_connected():
            connect_to_database()
        
        cursor = db_connection.cursor(dictionary=True)
        query = "SELECT * FROM profiles WHERE user_id = %s"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            profile_text = f"""
            User Profile for {user_id}:
            - Name: {result['user_name']}
            - Created: {result['created_date']}
            - Phone: {result['phone_number']}
            - Business: {result['business_name']}
            - Email: {result['email_id']}
            """
            return [types.TextContent(type="text", text=profile_text)]
        else:
            return [types.TextContent(type="text", text=f"No profile for user ID: {user_id}")]
            
    except Error as e:
        return [types.TextContent(type="text", text=f"Database error: {str(e)}")]

@app.post("/sse")
async def handle_sse(request: Request):
    """SSE endpoint for MCP communication"""
    transport = SseServerTransport("/messages")
    
    async def event_generator():
        async with transport.connect_sse(request) as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                None  # initialization options
            )
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )

@app.post("/call_tool")
async def http_call_tool(request: dict):
    """Simplified HTTP endpoint for tool calls"""
    try:
        tool_name = request.get("tool_name")
        arguments = request.get("arguments", {})
        
        if not tool_name:
            return JSONResponse(
                status_code=400,
                content={"error": "tool_name is required"}
            )
        
        if tool_name != "get_profile":
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown tool: {tool_name}"}
            )
        
        if not arguments or 'user_id' not in arguments:
            return JSONResponse(
                status_code=400,
                content={"error": "user_id is required"}
            )
        
        # Connect to database if needed
        global db_connection
        if not db_connection or not db_connection.is_connected():
            connect_to_database()
        
        cursor = db_connection.cursor(dictionary=True)
        query = "SELECT * FROM profiles WHERE user_id = %s"
        cursor.execute(query, (arguments['user_id'],))
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            profile_data = {
                "user_id": result['user_id'],
                "user_name": result['user_name'],
                "created_date": str(result['created_date']),
                "phone_number": result['phone_number'],
                "business_name": result['business_name'],
                "email_id": result['email_id']
            }
            
            # Format the response
            formatted_response = f"""User Profile Details:
- User ID: {result['user_id']}
- Name: {result['user_name']}
- Created Date: {result['created_date']}
- Phone: {result['phone_number']}
- Business: {result['business_name']}
- Email: {result['email_id']}"""
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "result": formatted_response,
                    "data": profile_data
                }
            )
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "result": f"No profile found for user ID: {arguments['user_id']}"
                }
            )
            
    except Error as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "result": f"Database error: {str(e)}"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "result": f"Error: {str(e)}"
            }
        )
    

@app.post("/messages")
async def handle_messages(request: Request):
    """Handle MCP messages"""
    return {"status": "ok"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "mcp-server"}

if __name__ == "__main__":
    print("🚀 Starting MCP Server with SSE transport on http://localhost:8000")
    print("📡 SSE endpoint: POST http://localhost:8000/sse")
    print("🔧 HTTP tool endpoint: POST http://localhost:8000/call_tool")
    print("🌐 Health check: GET http://localhost:8000/health")
    
    # Initialize database connection
    connect_to_database()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)