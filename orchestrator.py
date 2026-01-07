from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import re
from groq import Groq
import os
from dotenv import load_dotenv
import aiohttp
import asyncio

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Chatbot Orchestrator")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is required")

client = Groq(api_key=GROQ_API_KEY)

# MCP Server URL
MCP_SERVER_URL = "http://localhost:8000"

# Conversation history storage (in-memory for now)
conversation_history = {}

# Define request/response models
class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    user_id: str  # User asking the question
    message: str
    conversation_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    response: str
    tool_used: bool = False
    tool_result: Optional[str] = None
    conversation_id: str

class ToolCall(BaseModel):
    tool_call: bool
    name: str
    arguments: Dict[str, Any]

# Helper functions
def detect_tool_call(llm_response: str) -> Optional[ToolCall]:
    """Detect if LLM response contains a tool call"""
    try:
        # Look for JSON pattern in the response
        json_pattern = r'\{[^{}]*"tool_call"[^{}]*\{[^{}]*\}?[^{}]*\}'
        match = re.search(json_pattern, llm_response, re.DOTALL)
        
        if match:
            json_str = match.group(0)
            data = json.loads(json_str)
            
            # Validate required fields
            if (data.get("tool_call") is True and 
                "name" in data and 
                "arguments" in data):
                return ToolCall(**data)
        
        # Alternative: Check if response contains tool call indicator
        if '"tool_call": true' in llm_response or "'tool_call': true" in llm_response:
            # Try to parse the entire response as JSON
            try:
                data = json.loads(llm_response)
                if data.get("tool_call") is True:
                    return ToolCall(**data)
            except:
                pass
        
        return None
        
    except json.JSONDecodeError:
        return None
    except Exception as e:
        print(f"Error detecting tool call: {e}")
        return None

async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Call a tool on the MCP server"""
    try:
        async with aiohttp.ClientSession() as session:
            endpoint = f"{MCP_SERVER_URL}/call_tool"
            payload = {
                "tool_name": tool_name,
                "arguments": arguments
            }
            
            async with session.post(endpoint, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("result", "No result returned")
                else:
                    error_text = await response.text()
                    return f"Error calling tool: {response.status} - {error_text}"
                    
    except Exception as e:
        return f"Failed to call tool: {str(e)}"

def build_prompt(user_message: str, history: List[Message], tools_available: List[Dict]) -> str:
    """Build the prompt for the LLM"""
    
    tools_description = ""
    for tool in tools_available:
        tools_description += f"- {tool['name']}: {tool['description']}\n"
        if 'inputSchema' in tool:
            params = json.dumps(tool['inputSchema'], indent=2)
            tools_description += f"  Parameters schema: {params}\n"
    
    system_prompt = f"""You are a helpful assistant with access to tools. 
You can either respond directly to the user or call a tool if needed.

AVAILABLE TOOLS:
{tools_description}

TOOL CALL FORMAT:
If you need to call a tool, respond ONLY with this JSON format:
{{
  "tool_call": true,
  "name": "tool_name",
  "arguments": {{"param1": "value1", "param2": "value2"}}
}}

Otherwise, respond normally with your answer.

CONVERSATION HISTORY:"""
    
    # Add conversation history
    history_text = ""
    for msg in history[-6:]:  # Last 3 exchanges
        history_text += f"\n{msg.role}: {msg.content}"
    
    # Current user message
    current_message = f"\n\nUser: {user_message}\nAssistant:"
    
    return system_prompt + history_text + current_message

# Available tools (for now, hardcoded)
AVAILABLE_TOOLS = [
    {
        "name": "get_profile",
        "description": "Get user profile details from the database by user ID. Use this when user asks about profile information, user details, or needs to lookup someone's information.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The unique user ID (e.g., 'U001', 'U002')"
                }
            },
            "required": ["user_id"]
        }
    }
]

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Main chat endpoint"""
    
    # Initialize conversation history if not exists
    if request.conversation_id not in conversation_history:
        conversation_history[request.conversation_id] = []
    
    history = conversation_history[request.conversation_id]
    
    print(f"\n{'='*60}")
    print(f"Chat Request: User {request.user_id}")
    print(f"Message: {request.message}")
    print(f"History length: {len(history)}")
    print(f"{'='*60}")
    
    # Build the prompt
    prompt = build_prompt(request.message, history, AVAILABLE_TOOLS)
    
    # Call Groq LLM
    try:
        print("\n🤖 Calling Groq LLM...")
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3,  # Lower temperature for more consistent tool calls
            max_tokens=500
        )
        
        llm_response = chat_completion.choices[0].message.content
        print(f"📝 LLM Response: {llm_response[:200]}...")
        
        # Check for tool call
        tool_call = detect_tool_call(llm_response)
        
        if tool_call and tool_call.tool_call:
            print(f"🛠️  Tool call detected: {tool_call.name}")
            print(f"📤 Arguments: {tool_call.arguments}")
            
            # Call the tool
            tool_result = await call_mcp_tool(tool_call.name, tool_call.arguments)
            print(f"📥 Tool result received ({len(tool_result)} chars)")
            
            # Add user message and tool call to history
            history.append(Message(role="user", content=request.message))
            history.append(Message(role="assistant", content=f"[Tool call: {tool_call.name}]"))
            
            # Now get final response from LLM with tool result
            final_prompt = f"""Tool call result for {tool_call.name}:
{tool_result}

Original user question: {request.message}

Based on the tool result above, provide a helpful answer to the user:"""
            
            print("\n🤖 Getting final response from LLM...")
            final_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": final_prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=500
            )
            
            final_response = final_completion.choices[0].message.content
            
            # Add final response to history
            history.append(Message(role="assistant", content=final_response))
            
            # Keep history manageable (last 10 messages)
            if len(history) > 10:
                conversation_history[request.conversation_id] = history[-10:]
            
            return ChatResponse(
                response=final_response,
                tool_used=True,
                tool_result=tool_result,
                conversation_id=request.conversation_id
            )
            
        else:
            # No tool call needed, use LLM response directly
            print("💬 Direct response (no tool call)")
            
            # Update history
            history.append(Message(role="user", content=request.message))
            history.append(Message(role="assistant", content=llm_response))
            
            # Keep history manageable
            if len(history) > 10:
                conversation_history[request.conversation_id] = history[-10:]
            
            return ChatResponse(
                response=llm_response,
                tool_used=False,
                conversation_id=request.conversation_id
            )
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history"""
    if conversation_id in conversation_history:
        return {
            "conversation_id": conversation_id,
            "history": conversation_history[conversation_id]
        }
    else:
        return {
            "conversation_id": conversation_id,
            "history": []
        }

@app.delete("/conversations/{conversation_id}")
async def clear_conversation(conversation_id: str):
    """Clear conversation history"""
    if conversation_id in conversation_history:
        del conversation_history[conversation_id]
    return {"message": "Conversation cleared"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "chatbot-orchestrator",
        "mcp_server": MCP_SERVER_URL
    }

@app.get("/tools")
async def list_tools():
    """List available tools"""
    return AVAILABLE_TOOLS

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Chatbot Orchestrator on http://localhost:8001")
    print("💬 Chat endpoint: POST http://localhost:8001/chat")
    print("📝 Get conversation: GET http://localhost:8001/conversations/{id}")
    print("🛠️  Available tools: GET http://localhost:8001/tools")
    print("🌐 Health check: GET http://localhost:8001/health")
    
    # Create .env file if it doesn't exist
    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write('GROQ_API_KEY="your-groq-api-key-here"\n')
        print("\n⚠️  Please add your Groq API key to the .env file!")
        print("   Get your API key from: https://console.groq.com/keys")
    
    uvicorn.run(app, host="0.0.0.0", port=8001)