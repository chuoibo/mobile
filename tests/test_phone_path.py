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


def node(version: str, bin_dir: str | None = None, source: str = "nvm"):
    return phone_path.NodeCandidate(phone_path.parse_version(version), bin_dir, source)


# The range react-native 0.86.3 and metro 0.84.5 actually declare, copied off
# their installed package.json rather than invented, because the point of these
# tests is that we read a real one correctly.
RN_RANGE = "^20.19.4 || ^22.13.0 || ^24.3.0 || >= 25.0.0"


class NodeRange(unittest.TestCase):
    """Whether an interpreter can run Metro.

    The failure being prevented: Node 18 is what Debian and Ubuntu install as
    `nodejs`, and under it `expo start` prints one "outdated" line and then dies
    with `configs.toReversed is not a function` -- an error that points at the
    app instead of at the interpreter, and costs an afternoon.
    """

    def test_accepts_the_versions_this_machine_has(self):
        self.assertIs(phone_path.version_satisfies((20, 20, 2), RN_RANGE), True)
        self.assertIs(phone_path.version_satisfies((22, 23, 2), RN_RANGE), True)

    def test_rejects_the_node_debian_ships(self):
        self.assertIs(phone_path.version_satisfies((18, 19, 1), RN_RANGE), False)

    def test_caret_does_not_leak_past_its_major(self):
        """`^20.19.4` must not accept 21.x, and must not accept 20.19.3 either.

        Getting this wrong in the permissive direction is the dangerous one: it
        reports a green check and then Metro dies anyway.
        """
        self.assertIs(phone_path.version_satisfies((21, 0, 0), "^20.19.4"), False)
        self.assertIs(phone_path.version_satisfies((20, 19, 3), "^20.19.4"), False)
        self.assertIs(phone_path.version_satisfies((20, 19, 4), "^20.19.4"), True)

    def test_open_ended_alternative_is_honoured(self):
        self.assertIs(phone_path.version_satisfies((26, 1, 0), RN_RANGE), True)

    def test_and_within_one_alternative(self):
        self.assertIs(phone_path.version_satisfies((20, 5, 0), ">=20.0.0 <21.0.0"), True)
        self.assertIs(phone_path.version_satisfies((21, 5, 0), ">=20.0.0 <21.0.0"), False)

    def test_unreadable_range_is_unknown_not_unsupported(self):
        """A range we cannot parse must not harden into "your Node is wrong".

        npm ranges have shapes this does not model (`x` wildcards, hyphen
        ranges). Answering False there would block a machine that is fine, and
        the person would have no way to tell the two apart.
        """
        self.assertIsNone(phone_path.version_satisfies((20, 20, 2), "20.x || 22.x"))
        self.assertIsNone(phone_path.version_satisfies((20, 20, 2), "18.0.0 - 22.0.0"))

    def test_prerelease_style_suffix_still_parses(self):
        self.assertEqual(phone_path.parse_version("v25.0.0-nightly"), (25, 0, 0))
        self.assertIsNone(phone_path.parse_version("not a version"))


class NodeSelection(unittest.TestCase):
    """Choosing an interpreter when the one on PATH cannot run Metro."""

    def test_picks_the_newest_that_fits_and_ignores_the_rest(self):
        chosen = phone_path.choose_node(
            [node("v18.19.1"), node("v20.20.2"), node("v22.23.2"), node("v19.9.0")],
            RN_RANGE,
        )
        self.assertEqual(chosen.version, (22, 23, 2))

    def test_returns_none_when_nothing_installed_fits(self):
        self.assertIsNone(phone_path.choose_node([node("v18.19.1"), node("v16.20.2")], RN_RANGE))

    def test_no_substitute_is_looked_for_when_path_node_is_already_fine(self):
        """A plan that swapped interpreters on a healthy machine would be a bug:
        it would silently run Metro under a Node the person never chose."""
        plan = phone_path.NodePlan(RN_RANGE, "react-native", node("v22.23.2", source="PATH"))
        self.assertIsNone(plan.substitute)
        self.assertEqual(plan.chosen.version, (22, 23, 2))

    def test_node_plan_itself_leaves_a_working_path_node_alone(self):
        """The assertion above builds the plan by hand, so it cannot see the
        guard inside `node_plan` -- and with that guard deleted every test here
        still passed. This one calls `node_plan` for real.

        What it protects: on a machine whose PATH Node is fine but which also
        has newer versions installed, an unguarded plan swaps the interpreter
        anyway. Metro then runs under a Node the developer never selected, and
        the only trace is one line of output nobody reads twice.
        """
        import json
        import tempfile

        on_path = phone_path.node_on_path()
        if on_path is None:
            self.skipTest("không có node trên PATH")
        # A range the PATH interpreter certainly satisfies.
        spec = f">={on_path.version[0]}.0.0"
        if not phone_path.choose_node(phone_path.installed_nodes(), spec):
            self.skipTest("không có bản cài sẵn nào để nhầm sang — không kiểm được")

        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "node_modules" / "react-native"
            pkg.mkdir(parents=True)
            (pkg / "package.json").write_text(json.dumps({"engines": {"node": spec}}))
            plan = phone_path.node_plan(Path(tmp))

        self.assertIsNone(
            plan.substitute,
            f"đã đổi sang {plan.substitute and plan.substitute.text} dù "
            f"{on_path.text} trên PATH đã thoả {spec}",
        )
        self.assertEqual(plan.chosen.version, on_path.version)


class NodeReport(unittest.TestCase):
    """What `check` says about Node. The wording carries the diagnosis."""

    def test_old_path_node_with_a_way_out_is_a_warning_naming_the_substitute(self):
        plan = phone_path.NodePlan(
            RN_RANGE, "react-native", node("v18.19.1", source="PATH"), node("v20.20.2")
        )
        finding = phone_path.node_finding(plan)
        self.assertEqual(finding.status, phone_path.WARN)
        self.assertIn("v20.20.2", finding.detail)

    def test_old_path_node_with_no_way_out_fails_and_names_the_real_error(self):
        """`configs.toReversed` is the string a person will paste into a search
        box. Putting it in the remedy is what connects the two."""
        plan = phone_path.NodePlan(RN_RANGE, "react-native", node("v18.19.1", source="PATH"))
        finding = phone_path.node_finding(plan)
        self.assertEqual(finding.status, phone_path.FAIL)
        self.assertIn("toReversed", finding.remedy)

    def test_supported_path_node_passes(self):
        plan = phone_path.NodePlan(RN_RANGE, "react-native", node("v22.23.2", source="PATH"))
        self.assertEqual(phone_path.node_finding(plan).status, phone_path.OK)

    def test_missing_node_modules_warns_rather_than_blaming_the_version(self):
        plan = phone_path.NodePlan(None, "", node("v22.23.2", source="PATH"))
        finding = phone_path.node_finding(plan)
        self.assertEqual(finding.status, phone_path.WARN)
        self.assertIn("npm ci", finding.remedy)


class NodeRangeFromDisk(unittest.TestCase):
    """The requirement is read from the installed toolchain, not hardcoded here.

    Hardcoding would keep reporting a green Node check against a range that
    stopped existing the day someone upgraded React Native.
    """

    def test_reads_engines_from_react_native(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "node_modules" / "react-native"
            pkg.mkdir(parents=True)
            (pkg / "package.json").write_text(json.dumps({"engines": {"node": ">=20.19.4"}}))
            spec, source = phone_path.node_engine_range(Path(tmp))
        self.assertEqual((spec, source), (">=20.19.4", "react-native"))

    def test_absent_node_modules_reports_nothing_rather_than_a_guess(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(phone_path.node_engine_range(Path(tmp)), (None, ""))

    def test_the_installed_tree_declares_a_range_we_can_read(self):
        """Guards the seam between the two halves: a real range off this repo's
        node_modules must produce a definite verdict, not `unknown`."""
        spec, source = phone_path.node_engine_range()
        if spec is None:
            self.skipTest("apps/mobile/node_modules chưa cài")
        self.assertIn(source, ("react-native", "metro"))
        self.assertIsNotNone(
            phone_path.version_satisfies((20, 20, 2), spec),
            f"không đọc được dải thật {spec!r} — version_satisfies cần hiểu thêm cú pháp",
        )


if __name__ == "__main__":
    unittest.main()
