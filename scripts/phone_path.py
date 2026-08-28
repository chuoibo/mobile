#!/usr/bin/env python3
"""Open the path from `expo start` to a real phone, and refuse to pretend it is open.

The app had never once run on a physical device. Nothing missing was app code --
it is all environment, and every piece of it fails *quietly*:

  * `npx expo start` from a non-interactive shell meets "port 8081 is being used",
    cannot ask which port to use instead, prints "Skipping dev server" and exits
    **0**. A green exit code and no server behind it.
  * Expo chooses the address it writes into the QR from the host's interfaces.
    This machine carries eight docker bridges and a Tailscale interface; an
    address picked off any of them encodes a host the phone cannot route to.
  * `localhost` inside the app means *the phone*. A build that keeps the default
    reaches nothing, and reports only that a request failed.
  * On WSL2 mirrored networking the VM answers on its LAN address when asked from
    inside the VM, while the Hyper-V firewall drops that same connection when it
    arrives from the LAN. Every probe run on this machine passes. The phone still
    times out.
  * The `node` a developer happens to have on PATH decides whether Metro starts
    at all. React Native 0.86 wants `^20.19.4 || ^22.13.0 || ^24.3.0 || >= 25`;
    on the 18.x that ships with Debian/Ubuntu it prints one "outdated" line and
    then dies inside metro-config with `configs.toReversed is not a function` --
    which reads like a bug in the app, not like a wrong interpreter.

That last one is why this file exists. It cannot be found by testing from here --
the loopback path works -- so it is read out of the firewall configuration
instead of guessed at from a successful local curl.

    scripts/phone_path.py check          # is the path open? exits 1 when not
    scripts/phone_path.py env            # eval "$(...)" -- the two variables
    scripts/phone_path.py up             # check, then start Metro on the LAN
    scripts/phone_path.py open-firewall  # WSL only, asks Windows for elevation
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

# The GUID Windows files every WSL2 distribution under. Hyper-V firewall rules
# are scoped per "VM creator", and WSL is one creator for all distributions --
# so a rule added here applies to every distro, which is worth knowing before
# adding one.
WSL_VM_CREATOR_ID = "{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}"

MOBILE_DIR = Path(__file__).resolve().parent.parent / "apps" / "mobile"

DEFAULT_METRO_PORT = 8081
# Matches the fallback compiled into apps/mobile/src/api.ts. Keeping the two the
# same means a developer who ignores this script entirely still lands somewhere
# that works on a desktop browser.
DEFAULT_API_PORT = 8099

OK, FAIL, WARN, SKIP = "ok", "FAIL", "warn", "skip"


@dataclass
class Finding:
    """One checked thing. `remedy` is printed only when the check did not pass."""

    name: str
    status: str
    detail: str
    remedy: str = ""


@dataclass
class Interface:
    name: str
    address: str

    @property
    def ip(self) -> ipaddress.IPv4Address:
        return ipaddress.ip_address(self.address)


@dataclass
class NodeCandidate:
    """One Node interpreter this machine can run. `bin_dir` is None for PATH."""

    version: tuple[int, int, int]
    bin_dir: str | None
    source: str

    @property
    def text(self) -> str:
        return "v" + ".".join(str(n) for n in self.version)


@dataclass
class NodePlan:
    """Which interpreter `up` will run Metro under, and why.

    `substitute` is set only when the interpreter on PATH cannot run Metro and
    another installed one can. Keeping the decision in one object means `check`
    and `up` cannot describe it differently.
    """

    spec: str | None
    spec_source: str
    on_path: NodeCandidate | None
    substitute: NodeCandidate | None = None

    @property
    def chosen(self) -> NodeCandidate | None:
        return self.substitute or self.on_path


@dataclass
class AddressChoice:
    """The address chosen for the QR, plus why every other candidate lost.

    The rejections are part of the output on purpose. When this picks wrong, the
    person debugging needs to see the address it passed over and the reason, not
    just the winner.
    """

    chosen: Interface | None
    rejected: list[tuple[Interface, str]] = field(default_factory=list)


# --- pure logic, unit-tested in tests/test_phone_path.py ---------------------

# Interfaces a phone can never route to, matched by name. Docker publishes host
# ports on these too, so they answer locally and look healthy.
_VIRTUAL_PREFIXES = ("docker", "br-", "veth", "virbr", "lo", "tailscale", "wg", "tun", "tap")


def classify_interface(iface: Interface, default_iface: str | None) -> str | None:
    """Return the reason `iface` cannot carry the QR, or None if it can.

    Ordered most-specific first so the reason printed is the informative one: a
    Tailscale address is rejected for being Tailscale, not for being on a
    tunnel-shaped interface name.
    """
    ip = iface.ip
    if ip.is_loopback:
        return "loopback"
    if ip.is_link_local:
        return "link-local, không có DHCP"
    # 100.64.0.0/10. Tailscale works from a phone, but only a phone that has
    # joined the tailnet -- so it is a deliberate choice (--tailscale), never a
    # default. Silently handing out a CGNAT address looks identical to success
    # right up until the phone cannot resolve it.
    if ip in ipaddress.ip_network("100.64.0.0/10"):
        return "Tailscale/CGNAT — chỉ máy đã vào tailnet mới tới được"
    if iface.name.startswith(_VIRTUAL_PREFIXES):
        return "giao diện ảo, điện thoại không route tới được"
    if not ip.is_private:
        return "địa chỉ công cộng, không phải LAN"
    if default_iface and iface.name != default_iface:
        return f"không phải giao diện của default route ({default_iface})"
    return None


def pick_lan_address(interfaces: Sequence[Interface], default_iface: str | None) -> AddressChoice:
    """Choose the one address a phone on the same Wi-Fi can open."""
    chosen: Interface | None = None
    rejected: list[tuple[Interface, str]] = []
    for iface in interfaces:
        reason = classify_interface(iface, default_iface)
        if reason is None and chosen is None:
            chosen = iface
        elif reason is None:
            rejected.append((iface, "đã chọn địa chỉ khác trước"))
        else:
            rejected.append((iface, reason))
    return AddressChoice(chosen=chosen, rejected=rejected)


def parse_ip_addr(output: str) -> list[Interface]:
    """Parse `ip -4 -o addr show` into interfaces, in kernel order."""
    found: list[Interface] = []
    for line in output.splitlines():
        match = re.match(r"^\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)/", line)
        if match:
            found.append(Interface(name=match.group(1), address=match.group(2)))
    return found


def parse_default_iface(output: str) -> str | None:
    """Pull the interface name out of `ip route show default`."""
    match = re.search(r"\bdev\s+(\S+)", output)
    return match.group(1) if match else None


_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def parse_version(text: str) -> tuple[int, int, int] | None:
    """Parse `v20.19.4` or `20.19.4`. None when it is not a version at all."""
    match = _VERSION_RE.match(text.strip())
    return (int(match.group(1)), int(match.group(2)), int(match.group(3))) if match else None


def _comparator(version: tuple[int, int, int], part: str) -> bool | None:
    """Evaluate one comparator such as `^20.19.4` or `>=24.3.0`.

    None means "this syntax is not modelled here" -- see version_satisfies for
    why that is deliberately not the same answer as False.
    """
    part = part.strip()
    if not part:
        return True
    for op in (">=", "<=", ">", "<", "=", "^", "~"):
        if not part.startswith(op):
            continue
        target = parse_version(part[len(op) :])
        if target is None:
            return None
        if op == ">=":
            return version >= target
        if op == "<=":
            return version <= target
        if op == ">":
            return version > target
        if op == "<":
            return version < target
        if op == "=":
            return version == target
        if op == "~":
            return target <= version < (target[0], target[1] + 1, 0)
        # `^`: up to the next non-zero left-most component.
        if target[0]:
            upper = (target[0] + 1, 0, 0)
        elif target[1]:
            upper = (0, target[1] + 1, 0)
        else:
            upper = (0, 0, target[2] + 1)
        return target <= version < upper
    target = parse_version(part)
    return None if target is None else version == target


def version_satisfies(version: tuple[int, int, int], spec: str) -> bool | None:
    """Does `version` satisfy an npm `engines.node` range?

    Handles the shapes npm actually writes: `||` between alternatives, spaces
    for AND inside one alternative. Returns None -- not False -- when a range
    uses syntax this does not model. A range we cannot read must never harden
    into "your Node is wrong" on a machine where it is fine; unknown is its own
    answer and is reported as such.
    """
    unknown = False
    for clause in spec.split("||"):
        # `>= 20.19.4` and `>=20.19.4` are the same range; glue the operator to
        # its version before splitting on whitespace for the AND parts.
        clause = re.sub(r"([<>=~^]+)\s+", r"\1", clause).strip()
        if not clause:
            continue
        results = [_comparator(version, part) for part in clause.split()]
        if any(result is None for result in results):
            unknown = True
        elif all(results):
            return True
    return None if unknown else False


def choose_node(candidates: Sequence[NodeCandidate], spec: str) -> NodeCandidate | None:
    """The newest installed interpreter that satisfies `spec`, or None."""
    fit = [c for c in candidates if version_satisfies(c.version, spec) is True]
    return max(fit, key=lambda c: c.version) if fit else None


def ports_allowed_by(rules: Sequence[dict], ports: Sequence[int]) -> set[int]:
    """Which of `ports` an inbound-allow rule already covers.

    Windows reports port lists as strings and ranges as "8000-8100", so both
    shapes have to be understood. A rule that says "Any" covers everything.
    """
    covered: set[int] = set()
    for rule in rules:
        for spec in rule.get("ports") or []:
            text = str(spec).strip()
            if text.lower() == "any":
                return set(ports)
            if "-" in text:
                low, _, high = text.partition("-")
                try:
                    span = range(int(low), int(high) + 1)
                except ValueError:
                    continue
                covered.update(p for p in ports if p in span)
            elif text.isdigit():
                value = int(text)
                if value in ports:
                    covered.add(value)
    return covered


# --- environment probes -----------------------------------------------------


def run(cmd: Sequence[str], timeout: int = 20) -> tuple[int, str]:
    try:
        done = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/sys/kernel/osrelease").read_text().lower()
    except OSError:
        return False


def powershell() -> str | None:
    return shutil.which("powershell.exe") or shutil.which("pwsh.exe")


def port_is_free(port: int) -> bool:
    """True when nothing is listening. Checked on 0.0.0.0, which is where Metro binds."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def http_status(url: str, timeout: float = 4.0) -> int | str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return f"không tới được ({exc.__class__.__name__})"


def node_engine_range(mobile: Path = MOBILE_DIR) -> tuple[str | None, str]:
    """The Node range the *installed* toolchain declares, and which package said it.

    Read out of node_modules instead of being written down here. The requirement
    moves when the app upgrades React Native, and a constant in this file would
    go stale while still looking authoritative -- reporting "your Node is fine"
    against a range that no longer exists.
    """
    for package in ("react-native", "metro"):
        try:
            data = json.loads((mobile / "node_modules" / package / "package.json").read_text())
        except (OSError, json.JSONDecodeError):
            continue
        spec = (data.get("engines") or {}).get("node")
        if spec:
            return str(spec), package
    return None, ""


def node_on_path() -> NodeCandidate | None:
    if not shutil.which("node"):
        return None
    code, output = run(["node", "--version"], timeout=10)
    version = parse_version(output) if code == 0 else None
    return NodeCandidate(version, None, "PATH") if version else None


def installed_nodes() -> list[NodeCandidate]:
    """Interpreters a version manager has on disk but has not put on PATH.

    These are the way out when PATH points at a Node too old to run Metro: the
    person already has a usable one, it is just not selected.
    """
    found: list[NodeCandidate] = []
    roots = (
        (Path.home() / ".nvm" / "versions" / "node", "bin", "nvm"),
        (Path.home() / ".fnm" / "node-versions", "installation/bin", "fnm"),
    )
    for root, suffix, source in roots:
        try:
            entries = sorted(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            version = parse_version(entry.name)
            bin_dir = entry / suffix
            if version and (bin_dir / "node").exists():
                found.append(NodeCandidate(version, str(bin_dir), source))
    return found


def node_plan(mobile: Path = MOBILE_DIR) -> NodePlan:
    """Decide once which interpreter runs Metro, so check and up agree."""
    spec, spec_source = node_engine_range(mobile)
    plan = NodePlan(spec=spec, spec_source=spec_source, on_path=node_on_path())
    if not spec or (plan.on_path and version_satisfies(plan.on_path.version, spec) is not False):
        return plan
    plan.substitute = choose_node(installed_nodes(), spec)
    return plan


def hyperv_inbound(ports: Sequence[int]) -> dict | None:
    """Read the WSL VM's inbound firewall posture from Windows.

    Returns None when this is not WSL or PowerShell cannot be reached -- absence
    of an answer is reported as unknown, never as "fine".
    """
    shell = powershell()
    if not shell:
        return None
    script = f"""
$vm = '{WSL_VM_CREATOR_ID}'
$setting = Get-NetFirewallHyperVVMSetting -PolicyStore ActiveStore -ErrorAction SilentlyContinue |
  Where-Object {{ $_.Name -eq $vm }}
$rules = @(Get-NetFirewallHyperVRule -PolicyStore ActiveStore -ErrorAction SilentlyContinue |
  Where-Object {{ $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' -and $_.Enabled -eq 'True' -and
                  ($_.VMCreatorId -eq $vm -or $_.VMCreatorId -eq 'Any') -and $_.Protocol -eq 'TCP' }} |
  ForEach-Object {{ @{{ name = $_.DisplayName; ports = @($_.LocalPorts) }} }})
@{{ inbound = [string]$setting.DefaultInboundAction; rules = $rules }} | ConvertTo-Json -Depth 5 -Compress
"""
    code, output = run([shell, "-NoProfile", "-NonInteractive", "-Command", script], timeout=60)
    if code != 0:
        return None
    # PowerShell prepends warnings on stdout often enough that the JSON has to be
    # located rather than assumed to start at byte zero.
    start = output.find("{")
    if start < 0:
        return None
    try:
        data = json.loads(output[start:])
    except json.JSONDecodeError:
        return None
    rules = data.get("rules") or []
    if isinstance(rules, dict):  # ConvertTo-Json unwraps a single-element array
        rules = [rules]
    data["rules"] = rules
    data["covered"] = sorted(ports_allowed_by(rules, ports))
    return data


# --- the checks -------------------------------------------------------------


def lan_subnet(address: str) -> str:
    """The /24 the address sits in, for scoping a firewall rule to this Wi-Fi."""
    return str(ipaddress.ip_network(f"{address}/24", strict=False))


def open_firewall_command(address: str, ports: Sequence[int]) -> str:
    """The exact PowerShell that opens the path, scoped as narrowly as it can be.

    Narrower than the rule already on this machine, which opens its ports to
    `Any`: this is limited to the current Wi-Fi subnet, so it stops applying the
    moment the laptop is on a different network.
    """
    port_list = ",".join(str(p) for p in ports)
    return (
        "New-NetFirewallHyperVRule -Name 'RuDi-ExpoGo' "
        "-DisplayName 'Rủ Đi — Expo Go + API cho điện thoại thật' "
        f"-VMCreatorId '{WSL_VM_CREATOR_ID}' -Direction Inbound -Protocol TCP "
        f"-LocalPorts {port_list} -RemoteAddresses {lan_subnet(address)} -Action Allow"
    )


def node_finding(plan: NodePlan) -> Finding:
    """Report which Node runs Metro, before the run rather than after it fails."""
    if plan.spec is None:
        return Finding(
            "Node cho Expo",
            WARN,
            "chưa đọc được yêu cầu (apps/mobile/node_modules trống?)",
            "Chạy `npm ci` trong apps/mobile. Chưa cài thì `expo start` cũng "
            "chưa chạy được, và lý do sẽ không phải phiên bản Node.",
        )
    required = f"{plan.spec} (theo {plan.spec_source})"
    if plan.on_path is None:
        return Finding(
            "Node cho Expo",
            FAIL,
            f"không có `node` trên PATH; cần {required}",
            "Cài Node LTS: https://nodejs.org — hoặc `nvm install 20`.",
        )
    verdict = version_satisfies(plan.on_path.version, plan.spec)
    if verdict is True:
        return Finding("Node cho Expo", OK, f"{plan.on_path.text} hợp lệ; cần {required}")
    if verdict is None:
        return Finding(
            "Node cho Expo",
            WARN,
            f"{plan.on_path.text}; không đọc được dải {required}",
            "Không đọc được nghĩa là CHƯA BIẾT. Nếu Metro chết ngay khi khởi "
            "động, phiên bản Node là chỗ đáng nghi đầu tiên.",
        )
    if plan.substitute:
        # Not a FAIL: the run is going to work, because `up` swaps the
        # interpreter for the child process. Say so, and say what it swapped to.
        return Finding(
            "Node cho Expo",
            WARN,
            f"PATH đang là {plan.on_path.text}, quá cũ; `up` sẽ dùng "
            f"{plan.substitute.text} ({plan.substitute.source})",
            f"Chỉ áp dụng cho tiến trình `up` chạy ra. Lệnh npm/npx bạn gõ tay "
            f"vẫn là {plan.on_path.text}; cần {required}.",
        )
    return Finding(
        "Node cho Expo",
        FAIL,
        f"{plan.on_path.text} quá cũ, và máy không có bản nào khác; cần {required}",
        "Metro sẽ chết bằng `configs.toReversed is not a function` — đó là Node "
        "cũ, không phải lỗi app. Cài bản mới: `nvm install 20 && nvm use 20`.",
    )


def gather(metro_port: int, api_port: int) -> tuple[list[Finding], Interface | None]:
    findings: list[Finding] = [node_finding(node_plan())]

    _, addr_out = run(["ip", "-4", "-o", "addr", "show"])
    _, route_out = run(["ip", "route", "show", "default"])
    choice = pick_lan_address(parse_ip_addr(addr_out), parse_default_iface(route_out))
    host = choice.chosen

    if host is None:
        passed_over = "; ".join(f"{i.name} {i.address} ({why})" for i, why in choice.rejected)
        findings.append(
            Finding(
                "Địa chỉ LAN",
                FAIL,
                "không tìm được địa chỉ nào điện thoại tới được",
                f"Đã bỏ qua: {passed_over or 'không có giao diện nào'}. "
                "Máy này có đang nối Wi-Fi không? Đặt tay bằng --host <ip>.",
            )
        )
        return findings, None

    findings.append(Finding("Địa chỉ LAN", OK, f"{host.address} ({host.name})"))

    # Metro port. The failure this guards is not a crash: expo prints "Skipping
    # dev server" and exits 0, so the caller sees success and no server.
    if port_is_free(metro_port):
        findings.append(Finding("Cổng Metro", OK, f"{metro_port} còn trống"))
    else:
        findings.append(
            Finding(
                "Cổng Metro",
                FAIL,
                f"{metro_port} đang bị chiếm",
                f"`expo start` sẽ hỏi đổi cổng, và trong shell không tương tác nó "
                f"in 'Skipping dev server' rồi thoát mã 0 — xanh mà không có server. "
                f"Chạy lại với --metro-port <cổng khác>, hoặc: "
                f"ss -tlnp | grep {metro_port}",
            )
        )

    # The API, asked for over the LAN address rather than over loopback. This
    # does not prove the phone can reach it (see the firewall check) but it does
    # catch a server bound to 127.0.0.1, which no firewall change would fix.
    url = f"http://{host.address}:{api_port}/healthz"
    status = http_status(url)
    if status == 200:
        findings.append(Finding("API nghe trên LAN", OK, f"{url} -> 200"))
    else:
        findings.append(
            Finding(
                "API nghe trên LAN",
                FAIL,
                f"{url} -> {status}",
                "API chưa chạy, hoặc đang nghe trên 127.0.0.1 (điện thoại không "
                "tới được loopback của máy khác). Chạy: uvicorn app.api.main:app "
                f"--host 0.0.0.0 --port {api_port}",
            )
        )

    # The one that cannot be reproduced from this machine.
    if not is_wsl():
        findings.append(
            Finding("Tường lửa", SKIP, "không phải WSL — kiểm tường lửa của máy bằng tay")
        )
        return findings, host

    firewall = hyperv_inbound([metro_port, api_port])
    if firewall is None:
        findings.append(
            Finding(
                "Tường lửa WSL",
                WARN,
                "không đọc được cấu hình (thiếu powershell.exe?)",
                "Không đọc được nghĩa là CHƯA BIẾT, không phải là mở.",
            )
        )
        return findings, host

    blocked = sorted({metro_port, api_port} - set(firewall.get("covered") or []))
    default_blocks = str(firewall.get("inbound", "")).lower() == "block"
    if not default_blocks:
        findings.append(
            Finding("Tường lửa WSL", OK, f"mặc định inbound = {firewall.get('inbound')}")
        )
    elif not blocked:
        names = ", ".join(sorted({str(r.get("name")) for r in firewall["rules"]}))
        findings.append(Finding("Tường lửa WSL", OK, f"đã có luật mở {metro_port}, {api_port} ({names})"))
    else:
        findings.append(
            Finding(
                "Tường lửa WSL",
                FAIL,
                f"inbound mặc định = Block, cổng {', '.join(map(str, blocked))} chưa có luật mở",
                "Đây là lỗi KHÔNG tái lập được từ máy này: mọi lệnh curl chạy ở đây "
                "vẫn 200, vì gói tin không đi qua tường lửa Hyper-V. Điện thoại thì "
                "treo tới khi hết giờ. Mở bằng:\n"
                "      scripts/phone_path.py open-firewall",
            )
        )
    return findings, host


# --- commands ---------------------------------------------------------------

_MARK = {OK: "  ok  ", FAIL: " FAIL ", WARN: " warn ", SKIP: " skip "}


def report(findings: Sequence[Finding]) -> bool:
    print("\nĐường từ máy này tới điện thoại thật\n")
    for finding in findings:
        print(f"  [{_MARK[finding.status]}]  {finding.name:<22}  {finding.detail}")
    broken = [f for f in findings if f.status == FAIL]
    for finding in (f for f in findings if f.status != OK and f.remedy):
        print(f"\n  → {finding.name}: {finding.remedy}")
    print()
    return not broken


def cmd_check(args: argparse.Namespace) -> int:
    findings, host = gather(args.metro_port, args.api_port)
    ok = report(findings)
    if ok and host:
        print(f"  Mở được. `scripts/phone_path.py up` sẽ phát QR trỏ tới {host.address}.\n")
    return 0 if ok else 1


def env_lines(host: str, metro_port: int, api_port: int) -> list[str]:
    return [
        # Without this Expo re-runs its own interface guesswork and can encode a
        # docker bridge address into the QR.
        f"export REACT_NATIVE_PACKAGER_HOSTNAME={host}",
        f"export EXPO_PUBLIC_API_URL=http://{host}:{api_port}",
        f"export RCT_METRO_PORT={metro_port}",
    ]


def cmd_env(args: argparse.Namespace) -> int:
    _, route_out = run(["ip", "route", "show", "default"])
    _, addr_out = run(["ip", "-4", "-o", "addr", "show"])
    host = args.host or (
        pick_lan_address(parse_ip_addr(addr_out), parse_default_iface(route_out)).chosen
    )
    if host is None:
        print("# không tìm được địa chỉ LAN", file=sys.stderr)
        return 1
    address = host if isinstance(host, str) else host.address
    print("\n".join(env_lines(address, args.metro_port, args.api_port)))
    return 0


def cmd_up(args: argparse.Namespace) -> int:
    findings, host = gather(args.metro_port, args.api_port)
    ok = report(findings)
    if not ok and not args.force:
        print("  Dừng lại vì đường chưa thông. Bỏ qua bằng --force nếu bạn biết mình đang làm gì.\n")
        return 1
    if host is None:
        return 1

    address = args.host or host.address
    env = dict(os.environ)
    for line in env_lines(address, args.metro_port, args.api_port):
        key, _, value = line[len("export ") :].partition("=")
        env[key] = value

    # Pin the interpreter for the child process. Which `node` is on PATH is an
    # accident of how each person set their machine up, and on the 18.x Debian
    # ships it decides whether Metro starts at all -- so the path to a phone
    # must not inherit that accident. Announced, never silent: the swap applies
    # to this process only, and anyone debugging needs to know it happened.
    plan = node_plan()
    if plan.substitute:
        env["PATH"] = plan.substitute.bin_dir + os.pathsep + env.get("PATH", "")
        print(
            f"  Node: dùng {plan.substitute.text} ({plan.substitute.source}) thay cho "
            f"{plan.on_path.text} trên PATH — Expo cần {plan.spec}"
        )

    print(f"  QR sẽ trỏ tới  exp://{address}:{args.metro_port}")
    print(f"  App sẽ gọi API http://{address}:{args.api_port}")
    print("  Mở Expo Go trên điện thoại (cùng Wi-Fi) và quét mã.\n")

    mobile = MOBILE_DIR
    # --lan rather than the default: the default is --lan already, but stating it
    # means a stray EXPO_TUNNEL/offline setting in someone's shell cannot quietly
    # switch the transport out from under the address just verified.
    cmd = ["npx", "expo", "start", "--lan", "--port", str(args.metro_port), *args.passthrough]
    return subprocess.run(cmd, cwd=mobile, env=env, check=False).returncode


def cmd_open_firewall(args: argparse.Namespace) -> int:
    if not is_wsl():
        print("Không phải WSL — không có tường lửa Hyper-V để mở.", file=sys.stderr)
        return 1
    shell = powershell()
    if not shell:
        print("Không tìm thấy powershell.exe.", file=sys.stderr)
        return 1
    _, addr_out = run(["ip", "-4", "-o", "addr", "show"])
    _, route_out = run(["ip", "route", "show", "default"])
    host = pick_lan_address(parse_ip_addr(addr_out), parse_default_iface(route_out)).chosen
    if host is None:
        print("Không tìm được địa chỉ LAN.", file=sys.stderr)
        return 1

    ports = [args.metro_port, args.api_port]
    inner = open_firewall_command(host.address, ports)
    print("\nSẽ chạy trên Windows, cần quyền Administrator (Windows sẽ hiện hộp UAC):\n")
    print(f"  {inner}\n")
    print(f"Mở đúng 2 cổng TCP {ports[0]} và {ports[1]}, chỉ cho {lan_subnet(host.address)}.")
    print("Gỡ bằng:  Remove-NetFirewallHyperVRule -Name 'RuDi-ExpoGo'\n")
    if not args.yes:
        try:
            if input("Chạy? [y/N] ").strip().lower() not in ("y", "yes"):
                print("Bỏ qua.")
                return 1
        except EOFError:
            print("Không tương tác được; chạy lại với --yes, hoặc dán lệnh trên vào "
                  "PowerShell (Admin).", file=sys.stderr)
            return 1

    # Remove-then-add so re-running after the Wi-Fi subnet changed updates the
    # rule instead of stacking a second one beside it.
    script = (
        f"Remove-NetFirewallHyperVRule -Name 'RuDi-ExpoGo' -ErrorAction SilentlyContinue; {inner}"
    )
    encoded = script.replace("'", "''")
    code, output = run(
        [shell, "-NoProfile", "-Command",
         f"Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-Command','{encoded}'"],
        timeout=180,
    )
    if code != 0:
        print(output.strip()[:500], file=sys.stderr)
        print("\nKhông chạy được. Dán lệnh ở trên vào PowerShell (Admin).", file=sys.stderr)
        return 1
    firewall = hyperv_inbound(ports)
    still = sorted(set(ports) - set((firewall or {}).get("covered") or []))
    if still:
        print(f"Đã chạy nhưng cổng {still} vẫn chưa mở — kiểm lại bằng `check`.", file=sys.stderr)
        return 1
    print(f"Mở rồi: {ports}. Chạy `scripts/phone_path.py check` để xác nhận.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="phone_path.py", description="Đường từ máy này tới Expo Go trên điện thoại thật."
    )
    parser.add_argument("--metro-port", type=int, default=int(os.environ.get("MOBILE_METRO_PORT", DEFAULT_METRO_PORT)))
    parser.add_argument("--api-port", type=int, default=int(os.environ.get("MOBILE_API_PORT", DEFAULT_API_PORT)))
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="kiểm đường, thoát 1 nếu chưa thông").set_defaults(func=cmd_check)

    p_env = sub.add_parser("env", help='in các dòng export; dùng: eval "$(... env)"')
    p_env.add_argument("--host", help="ép địa chỉ thay vì tự dò")
    p_env.set_defaults(func=cmd_env)

    p_up = sub.add_parser("up", help="kiểm rồi chạy Metro trên LAN")
    p_up.add_argument("--host", help="ép địa chỉ thay vì tự dò")
    p_up.add_argument("--force", action="store_true", help="chạy kể cả khi kiểm đỏ")
    p_up.add_argument("passthrough", nargs="*", help="cờ truyền thẳng cho `expo start`")
    p_up.set_defaults(func=cmd_up)

    p_fw = sub.add_parser("open-firewall", help="WSL: mở 2 cổng cho LAN, cần Administrator")
    p_fw.add_argument("--yes", action="store_true", help="không hỏi lại")
    p_fw.set_defaults(func=cmd_open_firewall)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
