#!/usr/bin/env python3
"""Keep Codex working the plan without anybody triggering it.

The thing this replaces was a person -- me -- reading the plan, deciding what
Codex should do next, writing a prompt, and starting it. That worked while
somebody was watching, and every gap in the watching became a gap in the work.
Codex sat idle for two hours today because its quota ran out at 17:53 and
nobody noticed until 18:07.

What the loop does each round:

1. **Checkpoint, then rebuild the base from `main`.** Codex's clone was 72
   commits behind with 67 dirty files when this was written; work done on a
   stale base collides on merge and looks like work that vanished. The
   checkpoint runs first so resetting can never be what loses something.
2. **Decide what is done by running the checks**, not by asking. `plan_tasks`
   holds a command per task; the first failing one in the lane is the task.
3. **Tell it what its colleagues shipped** since the last round, so it is
   working against the repository as it is rather than as it was.
4. **Run it under the supervisor**, which grades on whether the world changed
   and alerts if it goes silent.
5. **Handle quota refusal as waiting, not as failure.** The provider says when
   it will serve again; the loop sleeps until then instead of burning restarts
   or, worse, stopping. This is the specific failure that cost today's two
   hours.

What it deliberately does NOT do: decide that work is finished. A check going
green means the loop stops re-assigning that task, nothing more. Merging still
waits on agy testing the branch.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from agent_checkpoint import snapshot_repo  # noqa: E402
from plan_tasks import TASKS  # noqa: E402

SUPERVISOR = HERE / "agent_supervisor.py"

# The provider states a wall-clock time it will serve again ("try again at
# 7:56 PM"). Parsed rather than backed off blindly: a fixed backoff either
# wastes half an hour or hammers a limit that has not lifted.
QUOTA_RE = re.compile(r"try again at (\d{1,2}):(\d{2})\s*(AM|PM)", re.IGNORECASE)
QUOTA_HIT = re.compile(r"hit your usage limit|quota exceeded|out of credits", re.I)


def emit(kind: str, message: str) -> None:
    stamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{kind} [{stamp}] {message}", flush=True)


def run(cmd: list[str] | str, cwd: pathlib.Path | None = None, timeout: int = 300):
    return subprocess.run(
        cmd,
        cwd=cwd,
        shell=isinstance(cmd, str),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def git(repo: pathlib.Path, *args: str) -> str:
    result = run(["git", *args], cwd=repo)
    return result.stdout.strip()


def task_is_done(task: dict, repo: pathlib.Path) -> bool:
    """Run the task's check against the repository.

    Anything other than a clean pass counts as not done -- including pytest's
    exit 5, which means the named test does not exist. That is the common case
    at the start and it must not read as success.
    """
    try:
        result = run(task["check"], cwd=repo, timeout=600)
    except subprocess.TimeoutExpired:
        emit("ALERT", f"check cua {task['id']} chay qua 10 phut, coi nhu chua xong")
        return False
    return result.returncode == 0


def next_task(lane: str, repo: pathlib.Path) -> tuple[dict | None, list[str]]:
    done: list[str] = []
    for task in TASKS:
        if task["lane"] != lane:
            continue
        if task_is_done(task, repo):
            done.append(task["id"])
            continue
        return task, done
    return None, done


def refresh_base(repo: pathlib.Path, source: str, agent: str) -> None:
    """Checkpoint whatever is there, then make the clone equal `main` again."""
    try:
        ref = snapshot_repo(repo, agent, "truoc khi dung lai nen tu main")
        emit("CKPT", f"da chup: {ref or '(khong co gi moi)'}")
    except Exception as problem:  # never let a failed snapshot become a reset
        emit("ALERT", f"checkpoint that bai, KHONG reset: {problem}")
        raise
    git(repo, "fetch", source)
    behind = git(repo, "rev-list", "--count", f"HEAD..{source}/main")
    dirty = len(git(repo, "status", "--porcelain").splitlines())
    if behind != "0" or dirty:
        emit("INFO", f"dung lai nen: sau main {behind} commit, {dirty} file ban")
    git(repo, "checkout", "-B", "main", f"{source}/main")
    git(repo, "reset", "--hard", f"{source}/main")
    run(["git", "clean", "-fd"], cwd=repo)


def colleagues_since(repo: pathlib.Path, hours: int) -> str:
    log = git(
        repo,
        "log",
        f"--since={hours} hours ago",
        "--pretty=%h %an %s",
        "main",
    )
    return log or "(khong co commit moi)"


def write_prompt(task: dict, done: list[str], repo: pathlib.Path, path: pathlib.Path) -> None:
    finished = ", ".join(done) if done else "(chua cai nao)"
    path.write_text(
        f"""# Việc của bạn, tự chọn từ plan — không ai giao

Bạn đang ở `{repo}`, đã được dựng lại đúng bằng `main` mới nhất.

## Đồng nghiệp vừa làm gì (24 giờ qua trên `main`)

```
{colleagues_since(repo, 24)}
```

Đọc cái đó trước. Nếu có commit chạm vào chỗ bạn sắp sửa, đọc nó trước khi viết.

## Trạng thái plan, kiểm bằng máy chứ không hỏi ai

Việc trong lane của bạn đã có check xanh: **{finished}**

Việc tiếp theo chưa xanh, và nó là việc của bạn ngay bây giờ:

# {task['title']}

## Vì sao việc này, không phải việc khác

{task['why']}

## Làm gì

{task['brief']}

## Cách máy biết bạn xong

```
{task['check']}
```

Lệnh đó phải xanh. Nó đang đỏ vì **chưa có test nào tên như thế** — pytest thoát
mã 5 khi không thu được test nào, và vòng lặp coi đó là chưa làm.

Đừng viết một test chỉ để lệnh trên xanh. Test phải **đỏ khi tính năng hỏng**.
Tự kiểm bằng cách xoá dòng quan trọng nhất trong code bạn vừa viết rồi chạy lại:
nếu vẫn xanh thì test đó không chứng minh gì cả, và hai lần trong tuần này đã có
đúng chuyện đó lọt lên `main`.

## Ràng buộc

- Nhánh riêng: `codex/{task['id']}`. Commit ngay khi xong, đừng để chờ.
- Lane của bạn: `db/`, `api/`, `payments/`, `domain/` và test backend.
  `app/web/` và `apps/mobile/` là của Claude — đừng sửa.
- Không dữ liệu người thật. `python3 scripts/repo_guard.py staged` xanh trước khi commit.
- Tài liệu và commit message tiếng Việt; comment/docstring trong code tiếng Anh.
- Toàn bộ `python3 -m pytest services/api/tests tests -q` phải xanh, không chỉ test mới.
""",
        encoding="utf-8",
    )


def quota_wait_seconds(text: str) -> int | None:
    """How long until the provider says it will serve again, or None."""
    if not QUOTA_HIT.search(text):
        return None
    match = QUOTA_RE.search(text)
    now = datetime.datetime.now()
    if not match:
        # Refused without a time. Waiting a fixed hour beats stopping, and
        # beats retrying in a tight loop against a limit that has not lifted.
        return 3600
    hour, minute, meridiem = int(match.group(1)), int(match.group(2)), match.group(3).upper()
    if meridiem == "PM" and hour != 12:
        hour += 12
    if meridiem == "AM" and hour == 12:
        hour = 0
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    # A minute of slack: asking at the exact stated second gets refused again.
    return int((target - now).total_seconds()) + 60


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--repo", default="/home/lakiet/codex-repo")
    parser.add_argument("--source", default="local", help="remote mang main toi")
    parser.add_argument("--scratch", required=True, help="noi de prompt va log")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=3000, help="moi vong, giay")
    args = parser.parse_args()

    repo = pathlib.Path(args.repo)
    scratch = pathlib.Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    for round_no in range(1, args.rounds + 1):
        emit("ROUND", f"vong {round_no}/{args.rounds}")
        refresh_base(repo, args.source, args.agent)

        task, done = next_task(args.agent, repo)
        if task is None:
            emit("DONE", f"moi viec trong lane {args.agent} da co check xanh: {done}")
            return 0
        emit("TASK", f"{task['id']} — {task['title']}")

        prompt = scratch / f"auto-{round_no}-{task['id']}.md"
        write_prompt(task, done, repo, prompt)

        result = run(
            [
                sys.executable,
                str(SUPERVISOR),
                args.agent,
                "--prompt-file",
                str(prompt),
                "--cwd",
                str(repo),
                "--timeout",
                str(args.timeout),
                "--max-restarts",
                "2",
            ],
            timeout=args.timeout + 600,
        )
        output = result.stdout + result.stderr
        (scratch / f"auto-{round_no}-{task['id']}.log").write_text(output, encoding="utf-8")

        wait = quota_wait_seconds(output)
        if wait is not None:
            until = datetime.datetime.now() + datetime.timedelta(seconds=wait)
            emit("WAIT", f"het quota, ngu toi {until:%H:%M} roi lam lai {task['id']}")
            time.sleep(wait)
            continue

        if task_is_done(task, repo):
            emit("OK", f"{task['id']} da co check xanh")
            branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
            push = run(["git", "push", args.source, f"{branch}:{branch}", "-f"], cwd=repo)
            emit(
                "PUSH" if push.returncode == 0 else "ALERT",
                f"{branch} -> {args.source}: {push.stderr.strip()[:160] or 'ok'}",
            )
        else:
            emit("ALERT", f"{task['id']} van chua xanh sau mot vong — lam lai")

    emit("STOP", f"het {args.rounds} vong")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
