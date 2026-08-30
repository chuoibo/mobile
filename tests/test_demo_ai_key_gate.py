"""The stale-key gate has to bite, and has to bite for the right reason.

These tests never start a container and never call the model API. `docker` is
replaced by a router that answers on the argv it is given, and the liveness
ping by a stub, so every state a demo machine can be in is describable here --
including states that only exist for the few minutes after a key rotation.

What a stub cannot speak for is whether the gate reads a REAL machine
correctly, so that was measured by hand on 2026-08-30 and recorded in the pull
request, both directions on the same box:

    8099 before `docker restart`  -> exit 1, "giữ khoá KHÁC với .env" (39 vs 53)
    8099 after  `docker restart`  -> exit 0

The 39/53 lengths below are the ones that machine really reported, not numbers
invented here: a fake that agrees with itself is not evidence.

The case this file exists for is `test_transport_failure_is_not_a_pass`. Every
other red state is one somebody would eventually notice; a gate that reports
ĐẠT because it could not reach the network is the failure mode this whole
ticket was about -- a green light over a dead hero path.
"""

from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "check_demo_ai_key.py"

# Lengths the demo machine really reported while the hero path was down.
OLD_KEY = "k" * 39
NEW_KEY = "n" * 53

COMPOSE_DIR = "/home/lakiet/mobile"
PS_LINE = "mobile-local-api-1\t0.0.0.0:8099->8000/tcp, [::]:8099->8000/tcp"


def load_gate():
    spec = importlib.util.spec_from_file_location("check_demo_ai_key", GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeDocker:
    """Answers `docker ps`, `docker exec printenv`, `docker inspect` and the
    dotenv resolver, routed by argv rather than by call order.

    Routing by order would let a gate that starts asking its questions in a
    different sequence silently read the container's key as the `.env` key --
    which, in a gate whose entire job is comparing those two, would pass every
    test while comparing a value to itself.
    """

    def __init__(
        self,
        *,
        ps=PS_LINE,
        container_key=OLD_KEY,
        env_key=NEW_KEY,
        compose_dir=COMPOSE_DIR,
        ps_returncode=0,
    ):
        self.ps = ps
        self.container_key = container_key
        self.env_key = env_key
        self.compose_dir = compose_dir
        self.ps_returncode = ps_returncode
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        if argv[:2] == ["docker", "ps"]:
            return subprocess.CompletedProcess(argv, self.ps_returncode, self.ps, "")
        if argv[:2] == ["docker", "exec"]:
            return subprocess.CompletedProcess(argv, 0, self.container_key, "")
        if argv[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(argv, 0, self.compose_dir, "")
        if argv[0] == "sh":
            return subprocess.CompletedProcess(argv, 0, self.env_key, "")
        raise AssertionError(f"cổng gọi lệnh không lường trước: {argv}")


class PortMatching(unittest.TestCase):
    """A machine on 18099 is not the machine on 8099."""

    def setUp(self):
        self.gate = load_gate()

    def test_matches_the_published_port(self):
        names = self.gate.container_for_port(PS_LINE, 8099)
        self.assertEqual(names, ["mobile-local-api-1"])

    def test_does_not_match_a_longer_port_containing_it(self):
        line = "other-api-1\t0.0.0.0:18099->8000/tcp"
        self.assertEqual(self.gate.container_for_port(line, 8099), [])

    def test_does_not_match_the_container_side_port(self):
        # 8000 is the port INSIDE every one of these containers. Matching it
        # would return every API container on the machine.
        self.assertEqual(self.gate.container_for_port(PS_LINE, 8000), [])

    def test_reports_every_match_so_caller_can_refuse(self):
        two = PS_LINE + "\nsecond-api-1\t0.0.0.0:8099->8000/tcp"
        self.assertEqual(len(self.gate.container_for_port(two, 8099)), 2)


class PingClassification(unittest.TestCase):
    def setUp(self):
        self.gate = load_gate()

    def test_200_is_live(self):
        live, _ = self.gate.classify_ping(200, None)
        self.assertTrue(live)

    def test_rotated_out_key_is_dead(self):
        # The exact answer the revoked key gave on 2026-08-30.
        live, reason = self.gate.classify_ping(400, "INVALID_ARGUMENT")
        self.assertFalse(live)
        self.assertIn("từ chối", reason)

    def test_exhausted_quota_is_dead_and_named_as_quota(self):
        live, reason = self.gate.classify_ping(429, "RESOURCE_EXHAUSTED")
        self.assertFalse(live)
        self.assertIn("quota", reason)

    def test_permission_denied_is_dead(self):
        live, _ = self.gate.classify_ping(403, "PERMISSION_DENIED")
        self.assertFalse(live)

    def test_upstream_500_is_not_called_live(self):
        live, _ = self.gate.classify_ping(500, None)
        self.assertFalse(live)


class Verdicts(unittest.TestCase):
    def setUp(self):
        self.gate = load_gate()

    def run_gate(self, docker, ping=(200, None), ping_raises=None):
        with mock.patch.object(self.gate.subprocess, "run", docker):
            if ping_raises is not None:
                target = mock.Mock(side_effect=ping_raises)
            else:
                target = mock.Mock(return_value=ping)
            with mock.patch.object(self.gate, "ping_gemini", target):
                return self.gate.main(["--base-url", "http://127.0.0.1:8099"])

    def test_stale_container_key_is_red(self):
        """The bug: container started before the rotation, .env after it."""
        code = self.run_gate(FakeDocker(container_key=OLD_KEY, env_key=NEW_KEY))
        self.assertEqual(code, self.gate.EXIT_BROKEN)

    def test_matching_live_key_is_green(self):
        code = self.run_gate(FakeDocker(container_key=NEW_KEY, env_key=NEW_KEY))
        self.assertEqual(code, self.gate.EXIT_OK)

    def test_matching_but_revoked_key_is_red(self):
        """Same key both sides is not enough -- both can be the dead one."""
        code = self.run_gate(
            FakeDocker(container_key=OLD_KEY, env_key=OLD_KEY),
            ping=(400, "INVALID_ARGUMENT"),
        )
        self.assertEqual(code, self.gate.EXIT_BROKEN)

    def test_container_without_any_key_is_red(self):
        code = self.run_gate(FakeDocker(container_key="", env_key=NEW_KEY))
        self.assertEqual(code, self.gate.EXIT_BROKEN)

    def test_transport_failure_is_not_a_pass(self):
        """No network means UNKNOWN. Calling that ĐẠT is the whole disease.

        This is the one case worth breaking the build over: every other red
        state announces itself, but a gate that goes green when it could not
        measure prints a passing verdict over a hero path that may be dead.
        """
        code = self.run_gate(
            FakeDocker(container_key=NEW_KEY, env_key=NEW_KEY),
            ping_raises=OSError("Network is unreachable"),
        )
        self.assertEqual(code, self.gate.EXIT_CANNOT_RUN)
        self.assertNotEqual(code, self.gate.EXIT_OK)

    def test_no_container_on_that_port_cannot_run(self):
        code = self.run_gate(FakeDocker(ps=""))
        self.assertEqual(code, self.gate.EXIT_CANNOT_RUN)

    def test_ambiguous_port_refuses_rather_than_guesses(self):
        two = PS_LINE + "\nsecond-api-1\t0.0.0.0:8099->8000/tcp"
        code = self.run_gate(FakeDocker(ps=two))
        self.assertEqual(code, self.gate.EXIT_CANNOT_RUN)

    def test_docker_ps_failing_cannot_run(self):
        code = self.run_gate(FakeDocker(ps="", ps_returncode=1))
        self.assertEqual(code, self.gate.EXIT_CANNOT_RUN)

    def test_no_key_configured_anywhere_cannot_run(self):
        """A machine with no key at all is check_ai_key.sh's fault to report."""
        code = self.run_gate(FakeDocker(container_key=OLD_KEY, env_key=""))
        self.assertEqual(code, self.gate.EXIT_CANNOT_RUN)


class ResolverChoice(unittest.TestCase):
    """A worktree has no .env; the container names the checkout that does."""

    def setUp(self):
        self.gate = load_gate()

    def test_prefers_the_compose_projects_own_resolver(self):
        chosen = self.gate.resolver_for(str(REPO_ROOT))
        self.assertEqual(chosen, REPO_ROOT / "scripts" / "env_value.sh")

    def test_falls_back_when_the_project_dir_has_no_resolver(self):
        chosen = self.gate.resolver_for("/nonexistent/project")
        self.assertEqual(chosen, self.gate.ENV_VALUE)

    def test_unlabelled_container_falls_back(self):
        self.assertEqual(self.gate.resolver_for(None), self.gate.ENV_VALUE)


class NeverLeaksTheKey(unittest.TestCase):
    """The repo rule: report the NAME of a secret, never its content."""

    def setUp(self):
        self.gate = load_gate()

    def test_stale_verdict_prints_lengths_not_values(self):
        docker = FakeDocker(container_key=OLD_KEY, env_key=NEW_KEY)
        with mock.patch.object(self.gate.subprocess, "run", docker):
            with mock.patch.object(
                self.gate, "ping_gemini", mock.Mock(return_value=(200, None))
            ):
                with mock.patch("sys.stderr") as err:
                    self.gate.main(["--base-url", "http://127.0.0.1:8099"])
        printed = "".join(str(c.args[0]) for c in err.write.call_args_list if c.args)
        self.assertNotIn(OLD_KEY, printed)
        self.assertNotIn(NEW_KEY, printed)
        self.assertIn("39", printed)
        self.assertIn("53", printed)


if __name__ == "__main__":
    unittest.main()
