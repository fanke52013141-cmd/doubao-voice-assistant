"""Network helpers for showing the phone-accessible LAN address."""
import ipaddress
import re
import socket
import subprocess


VIRTUAL_OR_UNUSABLE_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
)
PRIVATE_LAN_NETWORKS = (
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
)


def _parse_ipv4(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    return address if address.version == 4 else None


def _is_usable_lan_ip(value):
    address = _parse_ipv4(value)
    if address is None:
        return False
    if any(address in network for network in VIRTUAL_OR_UNUSABLE_NETWORKS):
        return False
    return any(address in network for network in PRIVATE_LAN_NETWORKS)


def _priority(value):
    address = _parse_ipv4(value)
    if address is None:
        return (99, value)
    if address in PRIVATE_LAN_NETWORKS[0]:
        group = 0
    elif address in PRIVATE_LAN_NETWORKS[1]:
        group = 1
    elif address in PRIVATE_LAN_NETWORKS[2]:
        group = 2
    else:
        group = 3
    return (group, tuple(int(part) for part in value.split(".")))


def _add_candidate(candidates, value):
    address = _parse_ipv4(value)
    if address is None:
        return
    text = str(address)
    if text not in candidates:
        candidates.append(text)


def _hostname_candidates():
    candidates = []
    try:
        hostname = socket.gethostname()
        for item in socket.getaddrinfo(hostname, None, socket.AF_INET):
            _add_candidate(candidates, item[4][0])
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            _add_candidate(candidates, ip)
    except OSError:
        pass
    return candidates


def _route_candidates():
    candidates = []
    for target in ("8.8.8.8", "1.1.1.1"):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect((target, 80))
            _add_candidate(candidates, sock.getsockname()[0])
        except OSError:
            pass
        finally:
            sock.close()
    return candidates


def _ipconfig_candidates():
    candidates = []
    try:
        output = subprocess.check_output(
            ["ipconfig"],
            text=True,
            encoding="utf-8",
            errors="ignore",
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return candidates

    for line in output.splitlines():
        if "IPv4" not in line:
            continue
        match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line)
        if match:
            _add_candidate(candidates, match.group(0))
    return candidates


def get_local_ip_candidates():
    """Return usable LAN IPv4 addresses, excluding loopback and proxy adapters."""
    candidates = []
    for source in (_hostname_candidates, _route_candidates, _ipconfig_candidates):
        for ip in source():
            _add_candidate(candidates, ip)
    usable = [ip for ip in candidates if _is_usable_lan_ip(ip)]
    return sorted(usable, key=_priority)


def get_local_ip():
    """Return the best phone-accessible LAN IP, or loopback when none is found."""
    candidates = get_local_ip_candidates()
    return candidates[0] if candidates else "127.0.0.1"
