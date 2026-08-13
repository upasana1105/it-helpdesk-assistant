"""Unit and integration tests for ITHelpdeskAgent."""
import unittest
from app.agent import ITHelpdeskAgent
from app.app_utils.memory_utils import MemoryBankService


class TestAgent(unittest.TestCase):

    def test_agent_ticket_flow(self):
        agent = ITHelpdeskAgent()
        result = agent.run(prompt="What is the status of ticket INC-101?", user_id="test_user")
        
        self.assertEqual(result["status"], "success")
        self.assertIn("INC-101", result["response"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(result["tool_calls"][0]["tool"], "get_ticket_status")

    def test_agent_system_status_flow(self):
        agent = ITHelpdeskAgent()
        result = agent.run(prompt="Is the VPN working fine?", user_id="test_user")
        
        self.assertEqual(result["status"], "success")
        self.assertIn("Corporate VPN", result["response"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(result["tool_calls"][0]["tool"], "get_system_status")

    def test_agent_access_request_flow(self):
        agent = ITHelpdeskAgent()
        result = agent.run(prompt="I need to request access to VPN Password Reset", user_id="test_user")
        
        self.assertEqual(result["status"], "success")
        self.assertIn("REQ-", result["response"])
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(result["tool_calls"][0]["tool"], "request_access")

    def test_agent_memory_extraction(self):
        agent = ITHelpdeskAgent()
        user_id = "mem_user_01"
        
        # Introduce name
        agent.run(prompt="Hello, my name is Charles.", user_id=user_id)
        
        memories = MemoryBankService.get_memories(user_id)
        self.assertTrue(any("Charles" in m for m in memories))


if __name__ == "__main__":
    unittest.main()

