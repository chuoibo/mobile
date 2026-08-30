#!/usr/bin/env python3
"""Does the AI key the RUNNING machine actually holds still work?

    scripts/check_demo_ai_key.py --base-url http://127.0.0.1:8099

## The failure this exists to catch

On 2026-08-30 the leader rotated `GEMINI_API_KEY` at 22:19:45. `.env` got the
new key immediately. The demo container on 8099 had started three hours
earlier, and a container reads its environment once, at startup -- so it went
on presenting a key that no longer existed.

Everything an operator would think to check stayed green. `/healthz` returned
200 (it does not touch the model, and by design does not touch the database
either). `/openapi.json` listed all 76 routes including the four of the photo
-> items join. `check_ai_key.sh` was silent, because it asks whether a key is
CONFIGURED and one was. The only broken thing was the hero path itself:

    POST /receipts/scan -> 502 {"code":"receipt_reader_unavailable"}

reproduced 3/3, in ~0.45s. That timing is the tell -- an upstream that rejects
you answers far faster than one that reads an image -- but nobody reads timings
on a machine that looks healthy.

## Why the existing checks could not see it

`check_ai_key.sh` compares against ABSENCE. It resolves the key the way Compose
would and warns when there is none. After a rotation there is a key in both
places; they are simply different keys, and "different" is invisible to a check
whose only question is "empty?".

`hero_walk.sh` does measure the real thing, end to end, through the real model.
But one walk costs a real Gemini call, so the cheap default stage asserts a
RECORDED verdict is recent rather than walking again. That is the right trade
and its own header says what it buys: a machine that broke five minutes ago
stays green until the verdict expires. On the day of the rotation the recorded
verdict was 33 minutes old and still passing, so the gate reported ĐẠT for a
hero path that had been dead for half an hour.

So the hole is specific: between two expensive walks, nothing asks whether the
machine can still reach the model. This fills exactly that hole, cheaply enough
to run every time -- the staleness comparison costs nothing at all, and the
liveness ping is a five-token prompt rather than an image.

## What it proves, and what it refuses to claim

Proves, about the machine at `--base-url`:

  - a key is configured for Compose, and the running container has one
  - the container's key is the SAME key `.env` now holds  (catches rotation)
  - that key is still accepted by the model API          (catches revocation,
                                                          and exhausted quota)

Refuses to claim:

  - that `POST /receipts/scan` returns items. A live key is necessary, not
    sufficient: the reader can still fail on prompt, parsing, or the image.
    Only `hero_walk.sh` answers that, and it costs a real read to do it.
  - anything about a machine other than the one on that port.
  - anything about the future. A key can die one second after this exits 0;
    that is why this is cheap enough to run again rather than to cache.

## Fail closed

A key never appears in output -- not the value, not a hash of it. Lengths and
MATCH/MISMATCH are enough to act on, and the repo rule is that a check reports
the NAME of a variable, never its content.

Exit codes, kept distinct because collapsing them is how "could not measure"
becomes "measured fine":

    0  the running machine can reach the model
    1  it cannot, and the reason is named
    2  could not be determined -- NOT a pass
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_VALUE = REPO_ROOT / "scripts" / "env_value.sh"

EXIT_OK = 0
EXIT_BROKEN = 1
EXIT_CANNOT_RUN = 2

KEY_NAME = "GEMINI_API_KEY"

# The same endpoint and model the receipt reader uses. Pointing the liveness
# ping at a different model would answer a question nobody asked: keys can be
# restricted per model, so "some model accepts this" is not "the reader's model
# accepts this".
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# Smallest prompt that still exercises authentication. The reply is discarded;
# only the HTTP status is read.
PING_BODY = {"contents": [{"parts": [{"text": "ok"}]}]}


def container_for_port(ps_output: str, port: int) -> list[str]:
    """Names of running containers publishing `port` on the host.

    Matching is on ":<port>->" rather than on the bare number, so that a
    machine on 18099 is not read as the machine on 8099. Returns every match;
    the caller decides that more than one is an ambiguity it cannot resolve
    rather than a coin to flip.
    """
    needle = f":{port}->"
    names = []
    for line in ps_output.splitlines():
        if "\t" not in line:
            continue
        name, ports = line.split("\t", 1)
        if needle in ports:
            names.append(name.strip())
    return names


def classify_ping(status: int | None, api_status: str | None) -> tuple[bool, str]:
    """Turn a model-API response into (key_is_live, human reason).

    A rejection is a real answer about a real key, so it is BROKEN, not
    cannot-run. The distinction that matters is between "the API told us no"
    and "we never reached the API"; the latter is raised as an exception by the
    caller and never arrives here.
    """
    if status == 200:
        return True, "khoá còn sống"
    detail = f"HTTP {status}" + (f" {api_status}" if api_status else "")
    if api_status == "RESOURCE_EXHAUSTED" or status == 429:
        return False, f"hết quota — {detail}"
    if status in (400, 401, 403):
        # 400 INVALID_ARGUMENT is what a rotated-out key returns; 403
        # PERMISSION_DENIED is what a key with the model removed returns.
        return False, f"khoá bị từ chối — {detail}"
    return False, f"model API trả lỗi — {detail}"


def resolver_for(compose_dir: str | None) -> Path:
    """Which copy of `env_value.sh` speaks for the machine being asked about.

    This gate is normally run from a worktree, and a worktree has no `.env` --
    the real one sits in the checkout Compose was invoked from. Resolving the
    key against the worktree would compare the container's key to nothing at
    all and report "chưa đặt" about a machine running on a perfectly good key.

    So the container is asked which project it belongs to, and that project's
    own resolver is used. Same script, same repo, `.env` next to the
    docker-compose.yml that actually built the container.
    """
    if compose_dir:
        sibling = Path(compose_dir) / "scripts" / "env_value.sh"
        if sibling.is_file():
            return sibling
    return ENV_VALUE


def read_env_key(resolver: Path) -> str:
    """What Compose would resolve for the key, via the shared resolver.

    Delegating to `env_value.sh` rather than parsing `.env` here is deliberate:
    a second dotenv parser is a second chance to disagree with Compose, and
    that disagreement is the bug `env_value.sh` was extracted to end. Its
    precedence is kept as-is, shell before `.env`, because the claim being made
    is "the container holds the key Compose would hand it today".
    """
    done = subprocess.run(
        ["sh", str(resolver), KEY_NAME],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return done.stdout.strip()


def compose_dir_of(name: str) -> str | None:
    """The directory Compose was run from for this container, per its labels."""
    done = subprocess.run(
        [
            "docker",
            "inspect",
            name,
            "--format",
            '{{index .Config.Labels "com.docker.compose.project.working_dir"}}',
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    value = done.stdout.strip()
    return value or None


def read_container_key(name: str) -> str:
    done = subprocess.run(
        ["docker", "exec", name, "printenv", KEY_NAME],
        capture_output=True,
        text=True,
        timeout=15,
    )
    # `printenv` exits non-zero when the variable is unset; an unset key is an
    # answer ("the container has none"), not a failure to measure.
    return done.stdout.strip()


def ping_gemini(key: str, timeout: float) -> tuple[int | None, str | None]:
    """Ask the model API whether it still accepts this key.

    Returns (http_status, api_status_string). Raises on transport failure so
    the caller can tell "no network" apart from "key refused" -- collapsing
    those two is how an offline runner reports a dead key as a live one, or
    the reverse.
    """
    request = urllib.request.Request(
        GEMINI_ENDPOINT.format(model=GEMINI_MODEL),
        data=json.dumps(PING_BODY).encode(),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        api_status = None
        try:
            api_status = json.loads(body).get("error", {}).get("status")
        except Exception:  # noqa: BLE001 - a non-JSON error body is still an answer
            api_status = None
        return exc.code, api_status


def die(message: str) -> int:
    print(f"KHÔNG ĐỐI CHIẾU ĐƯỢC — {message}", file=sys.stderr)
    return EXIT_CANNOT_RUN


def broken(message: str) -> int:
    print(f"HỎNG — {message}", file=sys.stderr)
    return EXIT_BROKEN


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Khoá AI mà máy đang chạy thực sự giữ có còn dùng được không"
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8099",
        help="máy cần hỏi; cổng của nó dùng để tìm container (mặc định máy demo)",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--container",
        default=None,
        help="chỉ định thẳng tên container, bỏ qua bước tìm theo cổng",
    )
    args = parser.parse_args(argv)

    port = urlparse(args.base_url).port
    if port is None:
        return die(f"--base-url không có cổng: {args.base_url}")

    name = args.container
    if name is None:
        try:
            done = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"],
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception as exc:  # noqa: BLE001 - docker missing, hung, denied
            return die(f"không chạy được `docker ps`: {exc}")
        if done.returncode != 0:
            return die(f"`docker ps` thất bại: {done.stderr.strip()}")

        names = container_for_port(done.stdout, port)
        if not names:
            return die(
                f"không có container nào đang publish cổng {port}.\n"
                f"  Máy ở {args.base_url} có phải container trên máy này không?"
            )
        if len(names) > 1:
            return die(
                f"có {len(names)} container cùng publish cổng {port}: {', '.join(names)}.\n"
                "  Chỉ định thẳng:  --container <tên>"
            )
        name = names[0]

    try:
        container_key = read_container_key(name)
    except Exception as exc:  # noqa: BLE001 - exec can fail many ways
        return die(f"không đọc được biến môi trường trong container {name}: {exc}")

    # Asked BEFORE the reference key is resolved, and that order is the point:
    # a container with no key cannot read a bill no matter what any `.env`
    # says, so there is nothing to compare against and no reason to need a
    # comparison. Resolving the reference first -- as this did until the canary
    # run against 8299 and 8489 caught it -- turns a machine that is definitely
    # broken into "chưa kết luận được": a weaker answer about a worse machine.
    if not container_key:
        return broken(
            f"container {name} KHÔNG có {KEY_NAME}.\n"
            "  Đường hero sẽ trả 503 receipt_reader_not_configured ở bước quét bill.\n"
            "  Compose chỉ chuyển biến nào service khai, nên dựng lại container\n"
            "  chưa chắc sửa được. Xem:  sh scripts/check_ai_key.sh"
        )

    try:
        compose_dir = compose_dir_of(name)
    except Exception:  # noqa: BLE001 - inspect failing is not fatal, only less precise
        compose_dir = None
    resolver = resolver_for(compose_dir)
    env_key = read_env_key(resolver)
    if not env_key:
        # No reference anywhere is a different fault with its own gate and its
        # own advice; saying so and stopping beats guessing which key is right.
        return die(
            f"{KEY_NAME} chưa đặt ở .env lẫn shell của dự án {compose_dir or '(không rõ)'}"
            " — không có gì để đối chiếu.\n"
            "  Đây là lỗi khác, xem:  sh scripts/check_ai_key.sh"
        )

    if container_key != env_key:
        # The rotation case, and the reason this file exists. Lengths are the
        # only thing printed: they are enough to see that these are two
        # different keys, and they reveal nothing usable.
        return broken(
            f"container {name} giữ khoá KHÁC với .env — khoá cũ, đọc lúc nó khởi động.\n"
            f"  container: {len(container_key)} ký tự | .env: {len(env_key)} ký tự\n"
            "  Mọi lời gọi model từ máy này sẽ hỏng; POST /receipts/scan trả\n"
            "  502 receipt_reader_unavailable và đường hero đứt ở chặng quét bill.\n"
            f"  Nạp khoá mới (KHÔNG dựng lại dữ liệu):  docker restart {name}"
        )

    try:
        status, api_status = ping_gemini(container_key, args.timeout)
    except Exception as exc:  # noqa: BLE001 - transport, DNS, proxy, timeout
        # Not reaching the API says nothing about the key. Green here would be
        # the exact lie this gate was written to stop.
        return die(
            f"không gọi được model API để thử khoá: {exc}\n"
            "  Máy này có ra được internet không? Chưa kết luận được khoá sống hay chết."
        )

    live, reason = classify_ping(status, api_status)
    if not live:
        return broken(
            f"container {name} và .env cùng một khoá, nhưng khoá đó {reason}.\n"
            "  POST /receipts/scan sẽ trả 502 receipt_reader_unavailable.\n"
            "  Khoá cần được cấp lại — dựng lại container KHÔNG sửa được ca này."
        )

    print(
        f"ĐẠT — container {name} (cổng {port}) giữ đúng khoá trong .env, "
        f"và model API còn nhận khoá đó.\n"
        "  KHÔNG chứng minh /receipts/scan đọc ra món: khoá sống là điều kiện cần,\n"
        "  không phải điều kiện đủ. Muốn biết đường hero đi được:  make hero-walk"
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
