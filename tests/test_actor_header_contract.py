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

import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_actor_headers.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, **(env or {})},
    )


def _analyse(source: str) -> list:
    """Chạy phép đọc client trên một file dựng tạm, không đụng cây thật."""

    import check_actor_headers as mod

    with tempfile.TemporaryDirectory() as tmp:
        target = pathlib.Path(tmp) / "mau.ts"
        target.write_text(source, encoding="utf-8")
        return [
            r
            for r in mod.build_graph([target])
            if r.requester and r.paths and not r.actor
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


class ACallItCannotReadIsNamed(unittest.TestCase):
    """Không đọc được một URL phải là chỗ mù CÓ TÊN, không phải im lặng.

    Đo được ngày 30/08 trên `main` 7adf961. Cùng một vi phạm, hai cách viết:

        fetch(`${BASE}/places/search`, ...)          -> HỎNG, mã 1   (đúng)
        fetch(`${BASE}${ENDPOINTS.search}`, ...)     -> ĐẠT,  mã 0   (mù)

    Cả hai đều gọi `POST /places/search` mà không gửi `X-Actor-ID`, tức đều là
    401 và một màn hình báo "sự cố máy chủ". Cách thứ hai đi lọt vì `route_paths`
    bóc ĐÚNG MỘT `${...}` ở đầu rồi đòi phần còn lại bắt đầu bằng `/`; khi phần
    còn lại lại là một biểu thức nữa, nó rơi vào `continue` — không thành đường
    dẫn, mà cũng không thành `unresolved`. Biến mất, chứ không phải được tha.

    Cổng này đã có sẵn chỗ đúng để ghi những ca như vậy: `region.unresolved`,
    và `.actor-header-unresolved.json` để ghim khi có lý do. Ghim là NÓI RA chỗ
    mù. `continue` là giấu nó, và một chỗ mù bị giấu đọc y hệt một cây sạch.
    """

    @staticmethod
    def _regions(source: str) -> list:
        import check_actor_headers as mod

        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "mau.ts"
            target.write_text(source, encoding="utf-8")
            return mod.build_graph([target])

    ENDPOINT_MAP = """
const BASE = "http://x";
const ENDPOINTS = { search: "/places/search" };
export async function traCuu(query: string): Promise<void> {
  await fetch(`${BASE}${ENDPOINTS.search}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}
"""

    def test_a_url_from_an_endpoint_map_is_recorded_as_a_blind_spot(self):
        (region,) = [r for r in self._regions(self.ENDPOINT_MAP) if r.requester]
        self.assertEqual(region.name, "traCuu")
        self.assertEqual(
            region.paths,
            set(),
            "phép đọc không phân giải được đường dẫn này — nếu nó phân giải "
            "được thì ca này phải đổi, vì lúc đó vi phạm bị bắt thẳng",
        )
        self.assertTrue(
            region.unresolved,
            "URL dựng từ `${base}${expr}` không đọc được, nhưng cổng không ghi "
            "nó vào `unresolved` — nên nó không thành đường dẫn, cũng không "
            "thành chỗ mù. Đó là im lặng, và im lặng đọc thành ĐẠT.",
        )

    def test_the_selftest_covers_this_shape_too(self):
        """Canary trong script phải phủ hình dạng này, không chỉ `fetch` literal.

        `--selftest` là thứ `scripts/gate.sh` chạy. Một canary chỉ dùng hình
        dạng mà máy quét chắc chắn đọc được thì chứng minh máy quét đỏ được
        cho hình dạng ĐÓ, và không nói gì về hình dạng đã đi lọt.
        """
        done = _run("--selftest")
        self.assertEqual(done.returncode, 0, f"{done.stdout}\n{done.stderr}")
        self.assertIn("canary mù", done.stdout)

    def test_plain_interpolated_prose_is_still_not_a_url(self):
        """Vế phải của phép cân: chuỗi hiển thị không được biến thành chỗ mù.

        `${a} và ${b}` cũng có hai biểu thức, nhưng có chữ thật ở giữa. Nếu ca
        này đỏ thì luật mới đang quét cả câu chữ tiếng Việt, và cổng sẽ đòi ghim
        những dòng không liên quan gì tới URL — đúng kiểu tiếng ồn khiến người
        ta đọc cổng này thành nhiễu rồi bỏ qua nó thật.
        """
        regions = self._regions(
            """
const BASE = "http://x";
export async function chao(ten: string, so: number): Promise<void> {
  const loi = `${ten} có ${so} món`;
  await fetch(`${BASE}/batches`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Actor-ID": ten },
    body: JSON.stringify({ loi }),
  });
}
"""
        )
        (region,) = [r for r in regions if r.requester]
        self.assertEqual(
            region.unresolved,
            [],
            f"chuỗi hiển thị bị coi là URL không đọc được: {region.unresolved}",
        )


class BlindIsNotTheSameAnswerAsBroken(unittest.TestCase):
    """Hai trạng thái khác nhau phải ra hai mã thoát khác nhau.

    Đây là chuyện đã thật sự xảy ra ở #379. Cổng gặp một URL dựng bằng biến,
    không phân giải được, và in ra `HỎNG` + mã 1 — đúng cùng một chữ và đúng
    cùng một mã với "client quên gửi header". QA đọc phán quyết đó thành FAIL,
    rồi phải tự trèo lên đọc mã nguồn mới kết luận được "sản phẩm ĐÚNG, giấy tờ
    thiếu". Người đọc sau sẽ không trèo.

    'Tôi không đọc được chỗ này' và 'chỗ này thiếu header' là hai câu khác nhau:
    câu đầu là khuyết tật của CỔNG, câu sau là khuyết tật của SẢN PHẨM. Gộp
    chúng làm một thì mã thoát mất hết thông tin, và một chỗ mù thật sẽ được sửa
    bằng cách sửa nhầm client.

    Chỗ mù VẪN đỏ — mã 2 vẫn khác 0, `gate.sh` vẫn chặn. Điều đổi là nó ĐƯỢC GỌI
    ĐÚNG TÊN. Làm nó xanh mới là sai: một chỗ cổng không đọc được có thể đang
    giấu một header thiếu thật.
    """

    #: Sản phẩm ĐÚNG — có gửi header — nhưng URL ghép từ bảng tra nên cổng
    #: không lần ra route. Đây là hình dạng của album-api.ts:158 ở #379.
    BLIND_BUT_CORRECT = """
const BASE = "http://x";
const ENDPOINTS = { search: "/places/search" };
export async function askSearch(query: string, actorId: string): Promise<void> {
  await fetch(`${BASE}${ENDPOINTS.search}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Actor-ID": actorId },
    body: JSON.stringify({ query }),
  });
}
"""

    #: Sản phẩm SAI thật — route đọc được, header không có. bug-191433.
    READABLE_AND_BROKEN = """
const BASE = "http://x";
export async function askSearch(query: string): Promise<void> {
  await fetch(`${BASE}/places/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}
"""

    def _run_with(self, source: str) -> subprocess.CompletedProcess:
        """Chạy cổng với một file mẫu ở thư mục tạm, KHÔNG đụng cây client thật.

        Bản trước thả file vào chính `apps/mobile/src` rồi xoá đi. Đo được: cây
        client bẩn 9,3 giây trên 12 giây mà file này chạy, và mọi bộ đọc khác
        soi thư mục đó trong cửa sổ ấy đều đọc lệch — kể cả chính cổng này, nó
        in "HỎNG" và trỏ vào một file không nằm trong git.
        `tests/test_gates_do_not_touch_the_client_tree.py` gác chỗ này.
        """
        import check_actor_headers as mod

        with tempfile.TemporaryDirectory(prefix="actor-exit-code-") as tmp:
            (pathlib.Path(tmp) / "mau.ts").write_text(source, encoding="utf-8")
            return _run(env={mod.EXTRA_CLIENT_DIR_ENV: tmp})

    def test_a_url_it_cannot_read_exits_two_not_one(self):
        done = self._run_with(self.BLIND_BUT_CORRECT)
        self.assertEqual(
            done.returncode,
            2,
            "chỗ cổng không đọc được URL phải ra mã 2 (không đo được), không "
            f"phải mã {done.returncode}:\n{done.stdout}\n{done.stderr}",
        )

    def test_a_missing_header_exits_one(self):
        done = self._run_with(self.READABLE_AND_BROKEN)
        self.assertEqual(
            done.returncode,
            1,
            "thiếu header thật phải ra mã 1 (sản phẩm sai):\n"
            f"{done.stdout}\n{done.stderr}",
        )

    def test_the_two_cases_do_not_print_the_same_word(self):
        """Mã thoát tách rồi mà chữ vẫn y hệt thì người đọc log vẫn bị lừa."""
        blind = self._run_with(self.BLIND_BUT_CORRECT).stdout
        broken = self._run_with(self.READABLE_AND_BROKEN).stdout
        self.assertNotIn(
            "HỎNG",
            blind,
            "chỗ mù bị gọi là HỎNG — đó chính là chữ đã làm QA đọc #379 thành "
            f"'sản phẩm sai':\n{blind}",
        )
        self.assertIn("HỎNG", broken, f"vi phạm thật phải được gọi là HỎNG:\n{broken}")

    def test_a_real_violation_wins_over_a_blind_spot(self):
        """Có cả hai thì mã phải là 1.

        Vi phạm đã xác nhận là cái hành động được; nếu chỗ mù ghi đè nó thành 2
        thì một header thiếu thật sẽ bị báo cáo là 'cổng không đọc được'.
        """
        done = self._run_with(self.BLIND_BUT_CORRECT + self.READABLE_AND_BROKEN)
        self.assertEqual(
            done.returncode,
            1,
            f"vi phạm thật bị chỗ mù che mất:\n{done.stdout}\n{done.stderr}",
        )


class TheExtraScanDirCannotQuietenTheGate(unittest.TestCase):
    """`MOBILE_ACTOR_EXTRA_CLIENT_DIR` chỉ được CỘNG THÊM, không được thay thế.

    Biến này tồn tại để ca test thả file mẫu ở thư mục tạm thay vì bẩn cây
    client thật. Nhưng một biến môi trường đổi được phạm vi quét của cổng là
    một cửa hậu: trỏ nó vào thư mục chỉ có một lời gọi sạch thì cổng thoát 0
    trong khi cây thật đang thiếu header, và phép gác `call_sites == 0` không
    bắt được vì con số đó là 1 chứ không phải 0.

    Nên tính chất phải gác là "cây thật VẪN được đọc", chứ không phải "biến này
    chạy được".
    """

    @staticmethod
    def _file_count(out: str) -> int:
        m = re.search(r"—\s*(\d+)\s*file client", out)
        assert m, f"không đọc được số file từ đầu ra:\n{out}"
        return int(m.group(1))

    def test_the_real_client_tree_is_still_scanned_when_an_extra_dir_is_given(self):
        base = self._file_count(_run().stdout)
        self.assertGreater(base, 1, "cây client thật phải có nhiều hơn 1 file")

        with tempfile.TemporaryDirectory(prefix="actor-extra-") as tmp:
            (pathlib.Path(tmp) / "mau.ts").write_text(
                "export const x = 1;\n", encoding="utf-8"
            )
            import check_actor_headers as mod

            done = _run(env={mod.EXTRA_CLIENT_DIR_ENV: tmp})

        self.assertEqual(
            self._file_count(done.stdout),
            base + 1,
            "thư mục đọc thêm phải CỘNG vào cây thật. Bằng đúng số file của "
            "thư mục tạm nghĩa là nó đã THAY THẾ cây thật — đó là cửa hậu tắt "
            f"cổng bằng một biến môi trường:\n{done.stdout}",
        )


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
