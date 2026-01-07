from mcp.server.sse import SseServerTransport
from mcp.server import Server
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
import mysql.connector
from mysql.connector import Error
import mcp.types as types
from typing import Any, Optional
import json
from datetime import datetime

# Database configuration
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
        db_connection = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            port=DB_CONFIG['port'],
            autocommit=True
        )
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
        ),
        types.Tool(
            name="get_transactions",
            description="Get all transactions for a specific user",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user ID to get transactions for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of transactions to return (default: 10)",
                        "default": 10
                    }
                },
                "required": ["user_id"]
            }
        ),
        types.Tool(
            name="get_transaction_summary",
            description="Get summary statistics of transactions for a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user ID to get transaction summary for"
                    }
                },
                "required": ["user_id"]
            }
        ),
        types.Tool(
            name="search_transactions",
            description="Search transactions with various filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Filter by user ID (optional)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category (e.g., food, shopping)"
                    },
                    "min_amount": {
                        "type": "number",
                        "description": "Minimum transaction amount"
                    },
                    "max_amount": {
                        "type": "number",
                        "description": "Maximum transaction amount"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date (YYYY-MM-DD)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date (YYYY-MM-DD)"
                    },
                    "transaction_type": {
                        "type": "string",
                        "description": "Transaction type (credit/debit)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default: 20)",
                        "default": 20
                    }
                }
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Optional[dict]) -> list[types.TextContent]:
    """Handle tool calls for SSE protocol"""
    if name == "get_profile":
        return await handle_get_profile_mcp(arguments)
    elif name == "get_transactions":
        return await handle_get_transactions_mcp(arguments)
    elif name == "get_transaction_summary":
        return await handle_transaction_summary_mcp(arguments)
    elif name == "search_transactions":
        return await handle_search_transactions_mcp(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")

# MCP Protocol Handlers
async def handle_get_profile_mcp(arguments: Optional[dict]) -> list[types.TextContent]:
    """Handle get_profile tool for MCP protocol"""
    if not arguments or 'user_id' not in arguments:
        return [types.TextContent(type="text", text="Error: user_id is required")]
    
    user_id = arguments['user_id']
    result = await execute_get_profile(user_id)
    return [types.TextContent(type="text", text=result)]

async def handle_get_transactions_mcp(arguments: Optional[dict]) -> list[types.TextContent]:
    """Handle get_transactions tool for MCP protocol"""
    if not arguments or 'user_id' not in arguments:
        return [types.TextContent(type="text", text="Error: user_id is required")]
    
    user_id = arguments['user_id']
    limit = arguments.get('limit', 10)
    result = await execute_get_transactions(user_id, limit)
    return [types.TextContent(type="text", text=result)]

async def handle_transaction_summary_mcp(arguments: Optional[dict]) -> list[types.TextContent]:
    """Handle get_transaction_summary tool for MCP protocol"""
    if not arguments or 'user_id' not in arguments:
        return [types.TextContent(type="text", text="Error: user_id is required")]
    
    user_id = arguments['user_id']
    result = await execute_transaction_summary(user_id)
    return [types.TextContent(type="text", text=result)]

async def handle_search_transactions_mcp(arguments: Optional[dict]) -> list[types.TextContent]:
    """Handle search_transactions tool for MCP protocol"""
    result = await execute_search_transactions(arguments or {})
    return [types.TextContent(type="text", text=result)]

# HTTP Endpoint Handlers
async def handle_get_profile(arguments: dict) -> JSONResponse:
    """Handle get_profile tool for HTTP endpoint"""
    if not arguments or 'user_id' not in arguments:
        return JSONResponse(
            status_code=400,
            content={"error": "user_id is required"}
        )
    
    user_id = arguments['user_id']
    result = await execute_get_profile(user_id)
    
    # Try to extract data for JSON response
    try:
        # Parse the formatted text to extract data
        lines = result.split('\n')
        data = {}
        for line in lines:
            if ':' in line and line.strip():
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                data[key] = value
    except:
        data = {"raw_response": result}
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "result": result,
            "data": data
        }
    )

async def handle_get_transactions(arguments: dict) -> JSONResponse:
    """Handle get_transactions tool for HTTP endpoint"""
    if not arguments or 'user_id' not in arguments:
        return JSONResponse(
            status_code=400,
            content={"error": "user_id is required"}
        )
    
    user_id = arguments['user_id']
    limit = arguments.get('limit', 10)
    result = await execute_get_transactions(user_id, limit)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "result": result
        }
    )

async def handle_transaction_summary(arguments: dict) -> JSONResponse:
    """Handle get_transaction_summary tool for HTTP endpoint"""
    if not arguments or 'user_id' not in arguments:
        return JSONResponse(
            status_code=400,
            content={"error": "user_id is required"}
        )
    
    user_id = arguments['user_id']
    result = await execute_transaction_summary(user_id)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "result": result
        }
    )

async def handle_search_transactions(arguments: dict) -> JSONResponse:
    """Handle search_transactions tool for HTTP endpoint"""
    result = await execute_search_transactions(arguments)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "result": result
        }
    )

# Core Execution Functions
async def execute_get_profile(user_id: str) -> str:
    """Execute get_profile query"""
    try:
        # Connect to database if needed
        global db_connection
        if not db_connection or not db_connection.is_connected():
            connect_to_database()
        
        cursor = db_connection.cursor(dictionary=True)
        query = "SELECT * FROM profiles WHERE user_id = %s"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            profile_text = f"""User Profile Details:
- User ID: {result['user_id']}
- Name: {result['user_name']}
- Created Date: {result['created_date']}
- Phone: {result['phone_number']}
- Business: {result['business_name']}
- Email: {result['email_id']}"""
            print(profile_text)
            return profile_text
        else:
            return f"No profile found for user ID: {user_id}"
            
    except Error as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

async def execute_get_transactions(user_id: str, limit: int = 10) -> str:
    """Execute get_transactions query"""
    try:
        # Connect to database if needed
        global db_connection
        if not db_connection or not db_connection.is_connected():
            connect_to_database()
        
        cursor = db_connection.cursor(dictionary=True)
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM transactions WHERE user_id = %s"
        cursor.execute(count_query, (user_id,))
        count_result = cursor.fetchone()
        total_transactions = count_result['total']
        
        # Get transactions
        query = """
        SELECT * FROM transactions 
        WHERE user_id = %s 
        ORDER BY transaction_date DESC 
        LIMIT %s
        """
        cursor.execute(query, (user_id, limit))
        transactions = cursor.fetchall()
        cursor.close()
        
        if transactions:
            formatted_transactions = []
            for tx in transactions:
                formatted_tx = f"""
Transaction ID: {tx['transaction_id']}
Date: {tx['transaction_date']}
Amount: ${tx['amount']:.2f}
Type: {tx['transaction_type']}
Description: {tx['description']}
Status: {tx['status']}
Category: {tx['category']}
Merchant: {tx['merchant_name']}
                """.strip()
                formatted_transactions.append(formatted_tx)
            
            response_text = f"""Found {total_transactions} transactions for user {user_id}. Showing {len(transactions)} most recent:

{'='*50}
""" + "\n\n".join(formatted_transactions)
            return response_text
        else:
            return f"No transactions found for user ID: {user_id}"
            
    except Error as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

async def execute_transaction_summary(user_id: str) -> str:
    """Execute transaction summary query"""
    try:
        # Connect to database if needed
        global db_connection
        if not db_connection or not db_connection.is_connected():
            connect_to_database()
        
        cursor = db_connection.cursor(dictionary=True)
        
        # Get summary statistics
        summary_query = """
        SELECT 
            COUNT(*) as total_transactions,
            SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END) as total_credits,
            SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END) as total_debits,
            MIN(transaction_date) as first_transaction,
            MAX(transaction_date) as last_transaction,
            AVG(amount) as average_amount,
            COUNT(DISTINCT category) as unique_categories
        FROM transactions 
        WHERE user_id = %s
        """
        cursor.execute(summary_query, (user_id,))
        summary = cursor.fetchone()
        
        if summary and summary['total_transactions'] > 0:
            # Get transactions by category
            category_query = """
            SELECT category, COUNT(*) as count, SUM(amount) as total_amount
            FROM transactions 
            WHERE user_id = %s 
            GROUP BY category 
            ORDER BY total_amount DESC
            """
            cursor.execute(category_query, (user_id,))
            categories = cursor.fetchall()
            
            # Get recent transactions
            recent_query = """
            SELECT transaction_date, amount, description, status
            FROM transactions 
            WHERE user_id = %s 
            ORDER BY transaction_date DESC 
            LIMIT 5
            """
            cursor.execute(recent_query, (user_id,))
            recent = cursor.fetchall()
            
            cursor.close()
            
            # Format summary
            response_text = f"""Transaction Summary for User {user_id}:
            
📊 Overview:
- Total Transactions: {summary['total_transactions']}
- Total Credits: ${summary['total_credits'] or 0:.2f}
- Total Debits: ${summary['total_debits'] or 0:.2f}
- Net Balance: ${(summary['total_credits'] or 0) - (summary['total_debits'] or 0):.2f}
- Average Transaction: ${summary['average_amount'] or 0:.2f}
- First Transaction: {summary['first_transaction']}
- Last Transaction: {summary['last_transaction']}
- Unique Categories: {summary['unique_categories']}

📈 Spending by Category:"""
            
            for cat in categories:
                response_text += f"\n  - {cat['category']}: {cat['count']} transactions, Total: ${cat['total_amount']:.2f}"
            
            response_text += "\n\n🕐 Recent Transactions:"
            for tx in recent:
                response_text += f"\n  - {tx['transaction_date']}: ${tx['amount']:.2f} - {tx['description']} ({tx['status']})"
            
            return response_text
        else:
            cursor.close()
            return f"No transactions found for user ID: {user_id}"
            
    except Error as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

async def execute_search_transactions(arguments: dict) -> str:
    """Execute search transactions query"""
    try:
        user_id = arguments.get('user_id')
        category = arguments.get('category')
        min_amount = arguments.get('min_amount')
        max_amount = arguments.get('max_amount')
        start_date = arguments.get('start_date')
        end_date = arguments.get('end_date')
        transaction_type = arguments.get('transaction_type')
        limit = arguments.get('limit', 20)
        
        # Connect to database if needed
        global db_connection
        if not db_connection or not db_connection.is_connected():
            connect_to_database()
        
        cursor = db_connection.cursor(dictionary=True)
        
        # Build dynamic query
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = %s"
            params.append(user_id)
        
        if category:
            query += " AND category = %s"
            params.append(category)
        
        if min_amount:
            query += " AND amount >= %s"
            params.append(float(min_amount))
        
        if max_amount:
            query += " AND amount <= %s"
            params.append(float(max_amount))
        
        if start_date:
            query += " AND DATE(transaction_date) >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND DATE(transaction_date) <= %s"
            params.append(end_date)
        
        if transaction_type:
            query += " AND transaction_type = %s"
            params.append(transaction_type)
        
        query += " ORDER BY transaction_date DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, params)
        transactions = cursor.fetchall()
        
        # Get count
        count_query = query.replace("SELECT *", "SELECT COUNT(*) as count").replace("ORDER BY transaction_date DESC LIMIT %s", "")
        cursor.execute(count_query, params[:-1])  # Remove limit param for count
        count_result = cursor.fetchone()
        total_count = count_result['count']
        
        cursor.close()
        
        if transactions:
            # Format search results
            filters = []
            if user_id: filters.append(f"User: {user_id}")
            if category: filters.append(f"Category: {category}")
            if min_amount: filters.append(f"Min Amount: ${min_amount}")
            if max_amount: filters.append(f"Max Amount: ${max_amount}")
            if start_date: filters.append(f"From: {start_date}")
            if end_date: filters.append(f"To: {end_date}")
            if transaction_type: filters.append(f"Type: {transaction_type}")
            
            filter_text = " | ".join(filters) if filters else "No filters"
            
            response_text = f"""🔍 Transaction Search Results:
Filters: {filter_text}
Total Matching: {total_count}
Showing: {len(transactions)} transactions

{'='*50}
"""
            
            for tx in transactions:
                response_text += f"""
Transaction ID: {tx['transaction_id']}
User ID: {tx['user_id']}
Date: {tx['transaction_date']}
Amount: ${tx['amount']:.2f} ({tx['transaction_type']})
Category: {tx['category']}
Description: {tx['description']}
Status: {tx['status']}
Merchant: {tx['merchant_name']}
{'-'*30}
"""
            return response_text
        else:
            return "No transactions found matching the criteria"
            
    except Error as e:
        return f"Database error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

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

@app.post("/messages")
async def handle_messages(request: Request):
    """Handle MCP messages"""
    return {"status": "ok"}

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
        
        # Handle different tools
        if tool_name == "get_profile":
            return await handle_get_profile(arguments)
        elif tool_name == "get_transactions":
            return await handle_get_transactions(arguments)
        elif tool_name == "get_transaction_summary":
            return await handle_transaction_summary(arguments)
        elif tool_name == "search_transactions":
            return await handle_search_transactions(arguments)
        else:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown tool: {tool_name}"}
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

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "mcp-server"}

@app.get("/test_db")
async def test_database():
    """Test database connection and list tables"""
    try:
        global db_connection
        if not db_connection or not db_connection.is_connected():
            connect_to_database()
        
        cursor = db_connection.cursor(dictionary=True)
        
        # List tables
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        # Get table counts
        table_counts = {}
        for table in tables:
            table_name = list(table.values())[0]
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            count_result = cursor.fetchone()
            table_counts[table_name] = count_result['count']
        
        cursor.close()
        
        return {
            "status": "connected",
            "tables": tables,
            "counts": table_counts
        }
        
    except Error as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting MCP Server with SSE transport on http://localhost:8000")
    print("📡 SSE endpoint: POST http://localhost:8000/sse")
    print("🔧 HTTP tool endpoint: POST http://localhost:8000/call_tool")
    print("🌐 Health check: GET http://localhost:8000/health")
    print("🗄️  Database test: GET http://localhost:8000/test_db")
    
    # Initialize database connection
    if not connect_to_database():
        print("⚠️  Warning: Starting server without database connection")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)