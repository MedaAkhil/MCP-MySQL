import subprocess
import sys
import time
import webbrowser
from threading import Thread
import os

def run_server(script_name, port=8000):
    """Run a server in a subprocess"""
    print(f"🚀 Starting {script_name} on port {port}...")
    subprocess.run([sys.executable, script_name])

def main():
    """Main entry point - start all services"""
    print("=" * 60)
    print("🤖 END-TO-END CHATBOT WITH MCP SERVER & GROQ LLM")
    print("=" * 60)
    
    # Check for .env file
    if not os.path.exists(".env"):
        print("\n❌ ERROR: .env file not found!")
        print("Please create a .env file with your Groq API key:")
        print('GROQ_API_KEY="your-api-key-here"')
        print("\nGet your API key from: https://console.groq.com/keys")
        return
    
    print("\n📋 Starting services:")
    print("1. MCP Server (Port 8000)")
    print("2. Chatbot Orchestrator (Port 8001)")
    print("3. Opening Chatbot UI in browser")
    
    # Note: In production, you'd run these in separate terminals
    # For simplicity, we'll start them sequentially
    print("\n⚠️  IMPORTANT: Please run these in separate terminals:")
    print("\nTerminal 1:")
    print("python mcp_server_sse.py")
    print("\nTerminal 2:")
    print("python orchestrator.py")
    print("\nThen open: http://localhost:8001 in your browser")
    
    # Alternative: Open browser with instructions
    time.sleep(2)
    
    # Create a simple instructions page
    with open("instructions.html", "w") as f:
        f.write("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Chatbot Setup Instructions</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
                .container { max-width: 800px; margin: 0 auto; }
                .step { background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 10px; }
                code { background: #333; color: #fff; padding: 2px 6px; border-radius: 4px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 Chatbot Setup Instructions</h1>
                
                <div class="step">
                    <h2>📋 Step 1: Open Terminal 1</h2>
                    <p>Run the MCP Server:</p>
                    <code>python mcp_server_sse.py</code>
                    <p>You should see: "Starting MCP Server with SSE transport on http://localhost:8000"</p>
                </div>
                
                <div class="step">
                    <h2>📋 Step 2: Open Terminal 2</h2>
                    <p>Run the Chatbot Orchestrator:</p>
                    <code>python orchestrator.py</code>
                    <p>You should see: "Starting Chatbot Orchestrator on http://localhost:8001"</p>
                </div>
                
                <div class="step">
                    <h2>📋 Step 3: Open Chatbot</h2>
                    <p>Open your browser and go to:</p>
                    <code><a href="http://localhost:8001">http://localhost:8001</a></code>
                    <p>Or open the HTML file:</p>
                    <code><a href="templates/index.html">templates/index.html</a></code>
                </div>
                
                <div class="step">
                    <h2>🔧 Test Everything is Working</h2>
                    <p>Try asking: "What are the details for user U001?"</p>
                    <p>The chatbot should:</p>
                    <ol>
                        <li>Detect it needs to call get_profile tool</li>
                        <li>Call MCP server to get data from MySQL</li>
                        <li>Return the profile information</li>
                    </ol>
                </div>
            </div>
        </body>
        </html>
        """)
    
    webbrowser.open("instructions.html")
    print("\n✅ Instructions page opened in browser!")

if __name__ == "__main__":
    main()