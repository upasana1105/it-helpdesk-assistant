"""API Endpoint tests for FastAPI and A2A Protocol."""
import unittest
try:
    from app.fast_api_app import app
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False



@unittest.skipUnless(HAS_FASTAPI, "fastapi package not installed in environment")
class TestFastAPIApp(unittest.TestCase):


    def test_root_endpoint(self):
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["service"], "IT Helpdesk AI Assistant")

    def test_health_endpoint(self):
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_chat_endpoint(self):
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.post("/chat", json={"prompt": "Check status of INC-102", "user_id": "api_user"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("INC-102", data["response"])

    def test_a2a_rpc_endpoint(self):
        from fastapi.testclient import TestClient
        client = TestClient(app)
        rpc_payload = {
            "jsonrpc": "2.0",
            "method": "a2a.execute",
            "params": {
                "prompt": "Is Single Sign-On SSO active?",
                "user_id": "a2a_peer_agent"
            },
            "id": 42
        }
        response = client.post("/a2a/app", json=rpc_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], 42)
        self.assertIn("result", data)
        self.assertIn("Single Sign-On", data["result"]["response"])


if __name__ == "__main__":
    unittest.main()

