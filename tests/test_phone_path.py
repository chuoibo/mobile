"""Tests for the address and firewall logic behind `scripts/phone_path.py`.

Only the pure parts are exercised here, and that is the whole point: the two
defects this script exists to prevent are both *selection* mistakes, and both
look like success on the machine that makes them.

  * Choosing a docker bridge or Tailscale address for the QR. Every local probe
    against such an address answers, so nothing on this machine can tell it went
    wrong -- the phone just cannot route there.
  * Reading the Hyper-V firewall as open when it is not. `ports_allowed_by` is
    the only thing standing between "Block, with a rule listing other ports" and
    a confident green report.

The environment probes around them (`ip`, PowerShell, sockets) are not mocked
into fake passes. What they return on the machine running the check is reported
by the check itself.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "phone_path.py"
SPEC = importlib.util.spec_from_file_location("phone_path", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
phone_path = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = phone_path
SPEC.loader.exec_module(phone_path)


# repo-guard: allow=long-number reason=wsl-loopback-relay-address
RELAY = "10.255.255.254"
# repo-guard: allow=long-number reason=tailscale-cgnat-interface-address
TAILSCALE = "100.65.17.15"


def iface(name: str, address: str):
    return phone_path.Interface(name=name, address=address)


# Trimmed from this machine, which is the environment that motivated the script:
# eight docker bridges, a Tailscale interface, and one real LAN address. Kept as
# a list of source lines rather than one triple-quoted block so the two addresses
# the repo guard reads as long numbers can each carry their own annotation --
# they are interface addresses off `ip addr`, not anything belonging to a person.
REAL_IP_ADDR = "\n".join([
    r"1: lo    inet 127.0.0.1/8 scope host lo\       valid_lft forever preferred_lft forever",
    # repo-guard: allow=long-number reason=wsl-loopback-relay-address
    r"1: lo    inet 10.255.255.254/32 scope global lo\       valid_lft forever",
    r"3: eth1    inet 192.168.1.7/24 scope global noprefixroute eth1\       valid_lft forever",
    r"6: br-24ba099a7f39    inet 172.22.0.1/16 scope global br-24ba099a7f39\       valid_lft forever",
    r"8: docker0    inet 172.17.0.1/16 scope global docker0\       valid_lft forever",
    # repo-guard: allow=long-number reason=tailscale-cgnat-interface-address
    r"23: tailscale0    inet 100.65.17.15/32 scope global tailscale0\       valid_lft forever",
])


class PickLanAddress(unittest.TestCase):
    def test_picks_the_lan_address_past_docker_and_tailscale(self):
        chosen = phone_path.pick_lan_address(
            phone_path.parse_ip_addr(REAL_IP_ADDR), "eth1"
        ).chosen
        self.assertIsNotNone(chosen)
        self.assertEqual("192.168.1.7", chosen.address)
        self.assertEqual("eth1", chosen.name)

    def test_docker_bridge_is_never_chosen_even_when_it_comes_first(self):
        """Order must not decide it.

        A docker bridge is a private RFC1918 address on an interface that is up,
        which is every property the naive test looks for.
        """
        chosen = phone_path.pick_lan_address(
            [iface("docker0", "172.17.0.1"), iface("eth1", "192.168.1.7")], "eth1"
        ).chosen
        self.assertEqual("192.168.1.7", chosen.address)

    def test_docker_bridge_is_rejected_without_help_from_the_default_route(self):
        """The interface-name rule has to stand on its own.

        With a default route to compare against, a docker bridge is rejected for
        not being the default route's interface, and the name rule never gets a
        say -- so removing it changes nothing and every test still passes. It
        only carries weight when `ip route show default` gives us nothing, which
        is the case inside a container and whenever a VPN owns the route. There
        a bridge is private, up, and first in kernel order: chosen, and
        unreachable from the phone.
        """
        choice = phone_path.pick_lan_address(
            [iface("docker0", "172.17.0.1"),
             iface("br-24ba099a7f39", "172.22.0.1"),
             iface("eth1", "192.168.1.7")],
            None,
        )
        self.assertEqual("192.168.1.7", choice.chosen.address)

    def test_tailscale_is_rejected_for_being_tailscale(self):
        reason = phone_path.classify_interface(iface("tailscale0", "100.64.0.1"), "eth1")
        self.assertIsNotNone(reason)
        self.assertIn("ailscale", reason)

    def test_cgnat_address_is_rejected_on_any_interface_name(self):
        """The 100.64/10 rule must survive a renamed interface.

        Tailscale on this machine is `tailscale0`, but the name is configurable
        and the address range is not.
        """
        self.assertIsNotNone(phone_path.classify_interface(iface("eth9", "100.64.0.1"), "eth9"))

    def test_loopback_and_link_local_are_rejected(self):
        self.assertIsNotNone(phone_path.classify_interface(iface("lo", "127.0.0.1"), "eth1"))
        self.assertIsNotNone(phone_path.classify_interface(iface("eth1", "169.254.3.4"), "eth1"))

    def test_wsl_host_relay_address_is_rejected(self):
        """The /32 on `lo` answers locally and is not the LAN. Exact value kept:
        recognising this specific address is the behaviour under test."""
        # repo-guard: allow=long-number reason=wsl-loopback-relay-address
        relay = "10.255.255.254"
        self.assertIsNotNone(phone_path.classify_interface(iface("lo", relay), "eth1"))

    def test_no_lan_address_reports_every_rejection_with_a_reason(self):
        choice = phone_path.pick_lan_address(
            [iface("lo", "127.0.0.1"), iface("docker0", "172.17.0.1")], "eth1"
        )
        self.assertIsNone(choice.chosen)
        self.assertEqual(2, len(choice.rejected))
        self.assertTrue(all(reason for _, reason in choice.rejected))

    def test_second_valid_address_is_reported_not_silently_dropped(self):
        choice = phone_path.pick_lan_address(
            [iface("eth1", "192.168.1.7"), iface("eth1", "192.168.1.8")], "eth1"
        )
        self.assertEqual("192.168.1.7", choice.chosen.address)
        self.assertEqual(1, len(choice.rejected))


class ParseIpOutput(unittest.TestCase):
    def test_parses_name_and_address_in_kernel_order(self):
        parsed = phone_path.parse_ip_addr(REAL_IP_ADDR)
        self.assertEqual(
            [("lo", "127.0.0.1"), ("lo", RELAY), ("eth1", "192.168.1.7"),
             ("br-24ba099a7f39", "172.22.0.1"), ("docker0", "172.17.0.1"),
             ("tailscale0", TAILSCALE)],
            [(i.name, i.address) for i in parsed],
        )

    def test_default_route_interface(self):
        self.assertEqual(
            "eth1",
            phone_path.parse_default_iface(
                "default via 192.168.1.1 dev eth1 proto kernel metric 35"
            ),
        )

    def test_no_default_route_is_none_not_a_crash(self):
        self.assertIsNone(phone_path.parse_default_iface(""))


class FirewallPortCoverage(unittest.TestCase):
    """The check that decides whether the report says open or blocked."""

    def test_rule_listing_other_ports_covers_nothing(self):
        # The rule actually present on this machine: TCP 3100, 8010, 9100.
        rules = [{"name": "CMAROX LAN", "ports": ["3100", "8010", "9100"]}]
        self.assertEqual(set(), phone_path.ports_allowed_by(rules, [8081, 8099]))

    def test_exact_ports_are_covered(self):
        rules = [{"name": "x", "ports": ["8081", "8099"]}]
        self.assertEqual({8081, 8099}, phone_path.ports_allowed_by(rules, [8081, 8099]))

    def test_partial_coverage_is_partial(self):
        """Metro open and the API shut is the subtly worse failure: the app
        loads, then every screen says the request failed."""
        rules = [{"name": "x", "ports": ["8081"]}]
        self.assertEqual({8081}, phone_path.ports_allowed_by(rules, [8081, 8099]))

    def test_port_range_is_understood(self):
        rules = [{"name": "x", "ports": ["8000-8100"]}]
        self.assertEqual({8081, 8099}, phone_path.ports_allowed_by(rules, [8081, 8099]))

    def test_any_covers_everything(self):
        rules = [{"name": "x", "ports": ["Any"]}]
        self.assertEqual({8081, 8099}, phone_path.ports_allowed_by(rules, [8081, 8099]))

    def test_malformed_entries_do_not_widen_coverage(self):
        """A shape we failed to parse must never be read as permission."""
        rules = [{"name": "x", "ports": ["", "abc", "80-", None]}, {"name": "y"}]
        self.assertEqual(set(), phone_path.ports_allowed_by(rules, [8081, 8099]))


class FirewallCommand(unittest.TestCase):
    def test_rule_is_scoped_to_the_wifi_subnet_not_to_any(self):
        command = phone_path.open_firewall_command("192.168.1.7", [8081, 8099])
        self.assertIn("-RemoteAddresses 192.168.1.0/24", command)
        self.assertNotIn("-RemoteAddresses Any", command)

    def test_opens_only_the_two_ports_asked_for(self):
        self.assertIn("-LocalPorts 8081,8099",
                      phone_path.open_firewall_command("192.168.1.7", [8081, 8099]))

    def test_scoped_to_the_wsl_vm_creator(self):
        self.assertIn(phone_path.WSL_VM_CREATOR_ID,
                      phone_path.open_firewall_command("10.0.0.5", [8081]))


class EnvironmentHandoff(unittest.TestCase):
    """What `up` and `env` hand to Expo.

    `REACT_NATIVE_PACKAGER_HOSTNAME` is what stops Expo re-deriving the QR host
    on its own and landing on a docker bridge, so its absence is a real defect
    rather than a missing nicety.
    """

    def test_sets_packager_hostname_and_api_url_to_the_same_host(self):
        lines = phone_path.env_lines("192.168.1.7", 8081, 8099)
        self.assertIn("export REACT_NATIVE_PACKAGER_HOSTNAME=192.168.1.7", lines)
        self.assertIn("export EXPO_PUBLIC_API_URL=http://192.168.1.7:8099", lines)

    def test_api_url_never_points_at_localhost(self):
        """On a phone `localhost` is the phone. This is the default the app ships
        with, so the check is that we replaced it, not that we allow it."""
        for line in phone_path.env_lines("192.168.1.7", 8081, 8099):
            self.assertNotIn("localhost", line)
            self.assertNotIn("127.0.0.1", line)


if __name__ == "__main__":
    unittest.main()
