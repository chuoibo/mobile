"""`scripts/check_actor_headers.py` chạy được bằng pytest, và nó bắt được thật.

## Vì sao file này tồn tại

Hai lý do, và lý do thứ hai mới là lý do chính.

`test_workflow_gates_have_local_callers.py` (#148) đòi mọi script cổng phải có
người gọi ngoài workflow. Actions đang chết vì billing, nên một cổng chỉ sống
trong YAML là một cổng không chạy. Đó là lý do thứ nhất, và nó là thủ tục.

Lý do thứ hai: ba phép phân biệt trong cổng đó **đều được tìm ra bằng cách làm
sai trước**. Lần chạy đầu tiên trên một cây `main` khoẻ mạnh, nó buộc tội 18
chỗ vô tội, rồi 20, rồi 1. Mỗi lần là một giả định sai về TypeScript:

1. `messagesUrl()` chỉ DỰNG url, không gọi ai. Đòi header ở đó là tiếng ồn.
2. `checkIn -> translated -> call -> actorHeaders` là bốn chặng; một lượt lan
   không đi hết, nên mọi hàm cách helper hơn một bước đều bị buộc tội.
3. `registerPerson(person, actorId: string, ...)` nhận actor bắt buộc theo chữ
   ký — TypeScript đã cưỡng chế, cổng không được đòi thêm lần nữa.

Ba ca dưới đây ghim đúng ba chỗ đó. Không có chúng thì lần sửa sau sẽ đi lại
đúng ba vòng ấy, và lần đó không ai còn nhớ vì sao.

## Cái này KHÔNG chứng minh

Rằng cổng bắt được MỌI cách quên header. Nó chứng minh cổng đỏ được ở hình dạng
đã thật sự xảy ra (bug-191433) và xanh ở ba hình dạng hợp lệ đã thật sự bị buộc
tội oan. Phần "không chứng minh gì" đầy đủ nằm ở đầu script.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_actor_headers.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _analyse(source: str) -> list:
    """Chạy phép đọc client trên một file dựng tạm, không đụng cây thật."""

    import check_actor_headers as mod

    with tempfile.TemporaryDirectory() as tmp:
        target = pathlib.Path(tmp) / "mau.ts"
        target.write_text(source, encoding="utf-8")
        return [
            r for r in mod.build_graph([target]) if r.requester and r.paths and not r.actor
        ]


class TheCheckerIsThereAndCanBeRed(unittest.TestCase):
    """Guard the guard, trước mọi khẳng định khác.

    Một máy quét đã mất khả năng báo đỏ in ra đúng thứ mà một cây sạch in ra.
    Repo này đã bị đúng kiểu đó cắn nhiều lần — detector không có trình duyệt
    trả `[]` với mã 0 — nên câu hỏi "nó còn đỏ được không" phải hỏi trước.
    """

    def test_script_is_there(self):
        self.assertTrue(SCRIPT.is_file(), f"{SCRIPT} biến mất")

    def test_selftest_canaries_pass(self):
        done = _run("--selftest")
        self.assertEqual(
            done.returncode,
            0,
            f"canary của cổng không đạt:\n{done.stdout}\n{done.stderr}",
        )
        self.assertIn("canary xấu", done.stdout)


class TheGateCatchesTheOmissionThatHappened(unittest.TestCase):
    def test_missing_header_on_a_real_route_is_a_violation(self):
        """Đúng hình dạng của `askSearch` trước #158.

        Url đi qua một hàm dựng riêng, header viết thẳng tại chỗ và thiếu actor.
        Đó là mã đã nằm trên `main` khoảng hai tiếng ngày 29/08 trong khi mọi
        cổng khác đều xanh.
        """
        hits = _analyse(
            """
const BASE = "http://x";
export function searchUrl(base: string): string {
  return `${base.replace(/\\/$/, "")}/places/search`;
}
export async function askSearch(query: string): Promise<void> {
  await fetch(searchUrl(BASE), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}
"""
        )
        self.assertEqual([r.name for r in hits], ["askSearch"])

    def test_the_same_function_with_the_header_is_clean(self):
        hits = _analyse(
            """
const BASE = "http://x";
export function searchUrl(base: string): string {
  return `${base.replace(/\\/$/, "")}/places/search`;
}
export async function askSearch(query: string, actorId: string): Promise<void> {
  await fetch(searchUrl(BASE), {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Actor-ID": actorId },
    body: JSON.stringify({ query }),
  });
}
"""
        )
        self.assertEqual(hits, [])


class TheGateDoesNotAccuseTheInnocent(unittest.TestCase):
    """Ba ca này đều đã bị buộc tội oan một lần. Chúng ở đây để đừng lần nữa."""

    def test_a_url_builder_alone_is_not_a_call_site(self):
        """`messagesUrl()` không có header, và đúng là không nên có.

        Khẳng định thẳng vào cờ `requester` chứ không chỉ vào danh sách vi phạm.
        Một đột biến tắt phép lọc "chỉ dựng url" cho thấy vì sao: `_analyse` ở
        trên tự lọc lại, nên nếu chỉ so danh sách rỗng thì ca này vẫn xanh
        trong khi cổng thật đã hỏng. Ca dưới đây hỏi đúng thứ nó nói là hỏi.
        """
        import check_actor_headers as mod

        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "mau.ts"
            target.write_text(
                """
export function messagesUrl(base: string, contextId: string): string {
  return `${base.replace(/\\/$/, "")}/contexts/${contextId}/messages`;
}
""",
                encoding="utf-8",
            )
            (region,) = mod.build_graph([target])

        self.assertEqual(region.name, "messagesUrl")
        self.assertIn("/contexts/{}/messages", region.paths)
        self.assertFalse(
            region.requester,
            "hàm chỉ dựng url mà bị coi là chỗ gọi thì cổng sẽ đòi header ở đó",
        )

    def test_actor_reaches_through_four_hops(self):
        """`checkIn -> translated -> call -> actorHeaders`, đúng chuỗi của api.ts."""
        hits = _analyse(
            """
const BASE = "http://x";
function actorHeaders(actorId: string): Record<string, string> {
  return { "Content-Type": "application/json", "X-Actor-ID": actorId };
}
async function call<T>(path: string, { method = "POST", actorId }: Opts): Promise<T> {
  const headers = actorId ? actorHeaders(actorId) : { "Content-Type": "application/json" };
  const res = await fetch(BASE + path, { method, headers });
  return res.json() as Promise<T>;
}
async function translated<T>(refusals: unknown, path: string, options: Opts): Promise<T> {
  return call<T>(path, options);
}
export async function checkIn(contextId: string, actorId: string): Promise<void> {
  await translated<void>({}, `/contexts/${contextId}/checkins`, {
    method: "POST",
    actorId,
  });
}
"""
        )
        self.assertEqual(hits, [])

    def test_a_required_actor_parameter_needs_no_second_check(self):
        """`DangKy` truyền actor ở vị trí thứ hai, tên là `id`, không phải `actorId`.

        TypeScript đã từ chối lời gọi thiếu nó, nên cổng không có việc gì ở đây.
        Đây là ca cuối cùng còn đỏ oan trước khi luật "tham số bắt buộc" ra đời.
        """
        hits = _analyse(
            """
const BASE = "http://x";
function actorHeaders(actorId: string): Record<string, string> {
  return { "X-Actor-ID": actorId };
}
async function call<T>(path: string, { method, actorId }: Opts): Promise<T> {
  const headers = actorId ? actorHeaders(actorId) : {};
  const res = await fetch(BASE + path, { method, headers });
  return res.json() as Promise<T>;
}
export async function registerPerson(person: P, actorId: string): Promise<void> {
  await call<void>(`/people/${person.id}`, { method: "PUT", actorId });
}
export async function DangKy(): Promise<void> {
  const id = await layId();
  await registerPerson({ id, name: "x" }, id);
}
"""
        )
        self.assertEqual(hits, [])

    def test_forgetting_the_actor_in_an_options_bag_is_still_caught(self):
        """Vế còn lại của ca trên: `actorId?` là optional nên bỏ quên vẫn biên dịch."""
        hits = _analyse(
            """
const BASE = "http://x";
function actorHeaders(actorId: string): Record<string, string> {
  return { "X-Actor-ID": actorId };
}
async function call<T>(path: string, { method, actorId }: Opts): Promise<T> {
  const headers = actorId ? actorHeaders(actorId) : {};
  const res = await fetch(BASE + path, { method, headers });
  return res.json() as Promise<T>;
}
export async function docDanhSach(contextId: string): Promise<void> {
  await call<void>(`/contexts/${contextId}/outings`, { method: "GET" });
}
"""
        )
        self.assertEqual([r.name for r in hits], ["docDanhSach"])


class TheTreeItselfPasses(unittest.TestCase):
    def test_every_actor_route_the_app_calls_sends_the_header(self):
        """Phép kiểm thật, trên cây thật. Chậm hơn các ca trên vì nó dựng OpenAPI."""
        done = _run()
        self.assertEqual(
            done.returncode,
            0,
            f"cổng hợp đồng đỏ trên cây này:\n{done.stdout}\n{done.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
