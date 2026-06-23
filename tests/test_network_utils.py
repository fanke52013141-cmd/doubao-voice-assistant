import unittest
from unittest.mock import patch

from network_utils import _ipconfig_candidates, get_local_ip, get_local_ip_candidates


class NetworkUtilsTests(unittest.TestCase):
    def test_candidates_exclude_virtual_and_non_lan_addresses(self):
        with patch("network_utils._hostname_candidates", return_value=["198.18.0.1", "127.0.0.1", "192.168.30.70"]), \
             patch("network_utils._route_candidates", return_value=["198.18.0.1", "10.0.0.5"]), \
             patch("network_utils._ipconfig_candidates", return_value=["255.255.255.0", "169.254.1.2", "172.20.1.7"]):
            self.assertEqual(
                get_local_ip_candidates(),
                ["192.168.30.70", "10.0.0.5", "172.20.1.7"],
            )
            self.assertEqual(get_local_ip(), "192.168.30.70")

    def test_ipconfig_candidates_only_read_ipv4_address_lines(self):
        output = """
Windows IP Configuration

Wireless LAN adapter WLAN:
   IPv4 Address. . . . . . . . . . . : 192.168.30.70
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . : 192.168.30.1

Ethernet adapter LAN:
   IPv4 地址 . . . . . . . . . . . . : 10.0.0.9
"""
        with patch("subprocess.check_output", return_value=output):
            self.assertEqual(_ipconfig_candidates(), ["192.168.30.70", "10.0.0.9"])


if __name__ == "__main__":
    unittest.main()
