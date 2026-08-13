"""Standalone interactive web server for IT Helpdesk Assistant."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from app.agent import root_agent

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>IT Helpdesk AI Assistant - Playground</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f7f6; margin: 0; padding: 20px; }
        .container { max-width: 800px; margin: auto; background: white; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden; display: flex; flex-direction: column; height: 90vh; }
        .header { background: #1a73e8; color: white; padding: 16px 20px; font-size: 20px; font-weight: bold; }
        .chat-box { flex: 1; padding: 20px; overflow-y: auto; background: #fafafa; }
        .msg { margin-bottom: 16px; display: flex; flex-direction: column; }
        .msg.user { align-items: flex-end; }
        .msg.bot { align-items: flex-start; }
        .bubble { max-width: 75%; padding: 12px 16px; border-radius: 18px; font-size: 15px; line-height: 1.4; white-space: pre-wrap; }
        .msg.user .bubble { background: #1a73e8; color: white; border-bottom-right-radius: 4px; }
        .msg.bot .bubble { background: #e8f0fe; color: #1f1f1f; border-bottom-left-radius: 4px; border: 1px solid #d2e3fc; }
        .tool-trace { margin-top: 6px; font-size: 12px; background: #f1f3f4; border: 1px solid #dadce0; border-radius: 4px; padding: 6px 10px; font-family: monospace; color: #3c4043; }
        .controls { display: flex; padding: 16px; background: white; border-top: 1px solid #e0e0e0; gap: 10px; }
        input[type="text"] { flex: 1; padding: 12px 16px; font-size: 15px; border: 1px solid #ccc; border-radius: 24px; outline: none; }
        button { background: #1a73e8; color: white; border: none; padding: 12px 24px; border-radius: 24px; font-size: 15px; font-weight: bold; cursor: pointer; }
        button:hover { background: #1557b0; }
        .presets { padding: 10px 20px; background: #fff; border-top: 1px solid #eee; display: flex; gap: 8px; flex-wrap: wrap; }
        .chip { background: #f1f3f4; border: 1px solid #dadce0; padding: 6px 12px; border-radius: 16px; font-size: 13px; cursor: pointer; }
        .chip:hover { background: #e8eaed; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">🛠️ IT & Enterprise Helpdesk Assistant</div>
        <div class="chat-box" id="chat">
            <div class="msg bot">
                <div class="bubble">Hello! I am your IT Helpdesk Assistant. How can I help you today? Try typing a question or click one of the preset tests below!</div>
            </div>
        </div>
        <div class="presets">
            <div class="chip" onclick="sendPreset('What is the status of ticket INC-101?')">🎫 Check INC-101</div>
            <div class="chip" onclick="sendPreset('Is the Corporate VPN operational?')">🌐 Check VPN Status</div>
            <div class="chip" onclick="sendPreset('I need to request a password reset for user Dave')">🔑 Request Password Reset</div>
            <div class="chip" onclick="sendPreset('Hello, my name is Alex and I use a Mac M3')">🧠 Test Memory Extraction</div>
        </div>
        <div class="controls">
            <input type="text" id="prompt" placeholder="Ask about tickets, system health, or access requests..." onkeypress="if(event.key==='Enter') sendMsg()">
            <button onclick="sendMsg()">Send</button>
        </div>
    </div>

    <script>
        async function sendMsg() {
            const input = document.getElementById('prompt');
            const txt = input.value.trim();
            if (!txt) return;
            input.value = '';
            appendMsg(txt, 'user');

            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({prompt: txt, user_id: 'browser_user'})
                });
                const data = await res.json();
                appendMsg(data.response, 'bot', data.tool_calls);
            } catch (err) {
                appendMsg('Error communicating with assistant server: ' + err, 'bot');
            }
        }

        function sendPreset(txt) {
            document.getElementById('prompt').value = txt;
            sendMsg();
        }

        function appendMsg(text, sender, tools = []) {
            const chat = document.getElementById('chat');
            const msgDiv = document.createElement('div');
            msgDiv.className = 'msg ' + sender;

            const bubble = document.createElement('div');
            bubble.className = 'bubble';
            bubble.innerText = text;
            msgDiv.appendChild(bubble);

            if (tools && tools.length > 0) {
                tools.forEach(t => {
                    const trace = document.createElement('div');
                    trace.className = 'tool-trace';
                    trace.innerText = `⚙️ Tool Executed: ${t.tool}(${JSON.stringify(t.args)})`;
                    msgDiv.appendChild(trace);
                });
            }

            chat.appendChild(msgDiv);
            chat.scrollTop = chat.scrollHeight;
        }
    </script>
</body>
</html>
"""


class SimpleRequestHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):

        if self.path == "/" or self.path.startswith("/dev-ui"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
                prompt = data.get("prompt", "")
                user_id = data.get("user_id", "browser_user")
                
                result = root_agent.run(prompt=prompt, user_id=user_id)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_error(404)


def run_server(port=8080):
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, SimpleRequestHandler)
    print(f"IT Helpdesk Assistant Web Playground running at http://127.0.0.1:{port}/")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
