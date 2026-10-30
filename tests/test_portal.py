import unittest

from screen_capture.portal import request_path


class PortalTest(unittest.TestCase):
    def test_request_path_from_unique_name_and_token(self):
        self.assertEqual(
            request_path(":1.42", "tok123"),
            "/org/freedesktop/portal/desktop/request/1_42/tok123",
        )
