import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from dotenv import load_dotenv  # Add this import
from agent import call_openrouter, search_membrain, save_memory, manage_local_file, SYSTEM_PROMPT, whatsapp_tool, facebook_tool

# Load environment variables
load_dotenv()

# Global state
chat_history = []

def init_chat_history():
    global chat_history
    print("Initializing chat history...")
    
    # Check if API keys are loaded
    if not os.getenv("OPENROUTER_API_KEY"):
        print("⚠️  WARNING: OPENROUTER_API_KEY not set!")
    if not os.getenv("MEMBRAIN_API_KEY"):
        print("⚠️  WARNING: MEMBRAIN_API_KEY not set!")
    
    current_files = manage_local_file("list", ".")
    db_context = search_membrain("user profile, hackathon, clawmind, ishan, preferences")

    chat_history = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"LOCAL FILES: {current_files}"},
        {"role": "system", "content": f"LONG-TERM MEMORY: {db_context}"}
    ]

# Initialize on startup
init_chat_history()

class ChatHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        # Add a simple health check endpoint
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            health_status = {
                "status": "healthy",
                "service": "ClawMind Agent API",
                "openrouter_configured": bool(os.getenv("OPENROUTER_API_KEY")),
                "membrain_configured": bool(os.getenv("MEMBRAIN_API_KEY")),
                "endpoints": ["POST /api/chat", "GET /health", "GET /"]
            }
            self.wfile.write(json.dumps(health_status).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global chat_history
        if self.path == '/api/chat':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            req_data = json.loads(post_data.decode('utf-8'))
            
            user_msg = req_data.get('message', '')
            if user_msg:
                chat_history.append({"role": "user", "content": user_msg})
                
            reply_text = "I didn't understand that."
            # Max 5 React steps
            for _ in range(5):
                response = call_openrouter(chat_history)
                if not response:
                    reply_text = "Sorry, I couldn't reach the OpenRouter API."
                    break
                    
                ai_msg = response["choices"][0]["message"]["content"]
                chat_history.append({"role": "assistant", "content": ai_msg})
                
                try:
                    data = json.loads(ai_msg)
                    decision = data[0] if isinstance(data, list) else data
                    action = decision.get("action")
                    
                    if action == "reply":
                        reply_text = decision.get("message")
                        break
                    elif action == "search":
                        res = search_membrain(decision.get("query", user_msg))
                        chat_history.append({"role": "system", "content": f"MEMORY RESULT:\n{res}"})
                    elif action == "remember":
                        res = save_memory(decision.get("fact"), decision.get("tags", []))
                        chat_history.append({"role": "system", "content": f"SAVE STATUS: {res}"})
                    elif action == "file_system":
                        res = manage_local_file(decision.get("action_type"), decision.get("path"), decision.get("content"))
                        chat_history.append({"role": "system", "content": f"FILE RESULT: {res}"})
                    elif action == "whatsapp":
                        res = whatsapp_tool(decision.get("action_type"), decision.get("contact"), decision.get("message"))
                        chat_history.append({"role": "system", "content": f"WHATSAPP RESULT: {res}"})
                    elif action == "facebook":
                        res = facebook_tool(decision.get("action_type"), decision.get("image_path"), decision.get("caption"), decision.get("message"))
                        chat_history.append({"role": "system", "content": f"FACEBOOK RESULT: {res}"})
                    elif action == "open_terminal":
                        import subprocess
                        subprocess.Popen(["open", "-a", "Terminal", "."])
                        chat_history.append({"role": "system", "content": "SUCCESS: Terminal opened for the user."})
                    else:
                        break
                except Exception as e:
                    print(f"Error parsing AI JSON output: {e}")
                    reply_text = "I encountered an internal error parsing my own thought process."
                    break

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"reply": reply_text}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def run(server_class=HTTPServer, handler_class=ChatHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"🚀 Starting ClawMind API server on port {port}...")
    print(f"📍 Health check: http://localhost:{port}/health")
    print(f"📍 Chat endpoint: POST http://localhost:{port}/api/chat")
    httpd.serve_forever()

if __name__ == '__main__':
    # Use PORT environment variable for Render compatibility
    port = int(os.getenv('PORT', 8000))
    run(port=port)