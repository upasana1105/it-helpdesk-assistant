"""Unit tests for IT Helpdesk function tools."""
import unittest
from app.tools import get_ticket_status, get_system_status, request_access


class TestTools(unittest.TestCase):

    def test_get_ticket_status_success(self):
        res = get_ticket_status("INC-101")
        self.assertTrue(res["success"])
        self.assertEqual(res["ticket"]["ticket_id"], "INC-101")
        self.assertEqual(res["ticket"]["status"], "In Progress")

    def test_get_ticket_status_not_found(self):
        res = get_ticket_status("INC-999")
        self.assertFalse(res["success"])
        self.assertIn("error", res)
        self.assertIn("available_sample_tickets", res)

    def test_get_system_status_success(self):
        res = get_system_status("vpn")
        self.assertTrue(res["success"])
        self.assertEqual(res["system"]["name"], "Corporate VPN")

    def test_get_system_status_invalid(self):
        res = get_system_status("unknown_system")
        self.assertFalse(res["success"])
        self.assertIn("supported_services", res)

    def test_request_access_success(self):
        res = request_access(user_name="Alice", resource_name="GCP Cloud Console", reason="Dev Project")
        self.assertTrue(res["success"])
        self.assertTrue(res["request_id"].startswith("REQ-"))
        self.assertEqual(res["status"], "Submitted")

    def test_request_access_missing_args(self):
        res = request_access(user_name="", resource_name="GCP", reason="")
        self.assertFalse(res["success"])


if __name__ == "__main__":
    unittest.main()

