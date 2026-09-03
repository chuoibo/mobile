# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Ngôn ngữ: tài liệu và commit message viết tiếng Việt; comment/docstring trong code viết tiếng Anh. Giữ đúng quy ước đó.

## Lệnh hay dùng

Chạy từ **gốc repo**:

```bash
python3 -m pytest services/api/tests tests -q      # toàn bộ: domain + API (fake repo) + repo guard
scripts/setup-hooks.sh                             # bật pre-commit repo guard — làm một lần cho mỗi clone
docker compose up -d postgres                      # Postgres 16 cho tầng test thật
```

Chạy từ `services/api/` (nơi có `pyproject.toml` với `pythonpath = ["."]`):

```bash
python -m pytest tests/domain/test_allocator_golden.py -q   # một file
python -m pytest tests -q -k "obligation and receipt"        # lọc theo tên
alembic upgrade head                                         # migrate DB local
uvicorn app.api.main:app --reload                            # API
python3 -m app.web.preview                                   # xem trang khách, KHÔNG cần DB
ruff check <file>                                            # lint — xem ghi chú dưới trước khi chạy cả cây
```

Tầng test chạy trên PostgreSQL thật (mặc định bị **skip** nếu thiếu URL — skip không phải là xanh):

```bash
cd services/api && MOBILE_TEST_DATABASE_URL='postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile' \
  MOBILE_REQUIRE_POSTGRES_TESTS=1 python -m pytest tests/postgres -q
```

Repo guard chạy tay (CI chạy cả ba dạng):

```bash
python3 scripts/repo_guard.py staged
python3 scripts/repo_guard.py tree HEAD
python3 scripts/repo_guard.py range <base-sha> <head-sha>
```

Kiểm tra migration biên dịch được, không cần database — đây là check từng bắt lỗi FK name vượt 63 ký tự:

```bash
cd services/api && python -c "
from alembic import command; from alembic.config import Config
c = Config('alembic.ini'); c.set_main_option('sqlalchemy.url','postgresql+psycopg://offline/offline')
command.upgrade(c,'head',sql=True)" >/dev/null && echo ok
```

## Kiến trúc

Lát cắt dọc duy nhất đang chạy: `POST /expenses` → allocator chia tiền → `confirm` ghi vào sổ → `POST /batches` gom nghĩa vụ → `publish` sinh envelope → `GET /g/{token}` trang khách → khách báo đã chuyển → người nhận `confirm-receipt`. Chưa có Home, chưa có tab (spec mục 14.3 cấm thiết kế Home trước khi biết hành động nào tồn tại).

Tầng, từ trong ra ngoài:

- `app/domain/` — thuần: `dict` vào, `dict` ra, ném `AllocationError`. **Không được import** `app.db`, `app.api`, `sqlalchemy`, `fastapi`, `alembic`, `pydantic`. Cưỡng chế bằng `tests/test_import_boundary.py` (parse AST), không bằng lời hứa. Lý do là bất biến 3: số dư luôn tính lại được từ sổ.
- `app/api/service.py` — workflow: gọi domain trước, rồi mới gọi repository. Repository không bao giờ tự chế allocation hay tự lưu trạng thái nghĩa vụ.
- `app/api/repository.py` — `ApiRepository` (Protocol) + `SqlAlchemyApiRepository`. Trạng thái nghĩa vụ **suy ra từ event** (`ReceiptConfirmation`), không đọc cột đã lưu; xem `app/db/repository.py` cho dạng aggregate đúng.
- `app/web/guest_view.py` — biên rò rỉ của trang khách. Template chỉ render đúng view model module này trả về; test rò rỉ nằm ở đây chứ không nằm trong file Jinja. Khách thấy envelope của chính mình, không bao giờ thấy số dư nhóm / lịch sử / allocation của người khác.

**Sản phẩm dừng ở chỗ nói mỗi người phải bỏ ra bao nhiêu và vì những khoản nào.** Chuyển tiền bằng cách nào là việc giữa hai người. `app/payments/` (VietQR EMVCo + CRC) và hai bảng tài khoản ngân hàng đã bị gỡ — đừng dựng lại mà không mở ADR trước.

Auth: cờ `MOBILE_AUTH_MODE`, **vắng mặt là `prod`** (ADR-0014). Ở `prod`, `get_actor` đọc `Authorization: Bearer` từ bảng `account_sessions` và **không tin** `X-Actor-*`; thiếu phiên là 401. Ở `dev` (compose local bật rõ) thì giữ header cũ để test và máy demo còn chạy. Phiên đầu tiên trên host sạch lấy bằng `scripts/genesis_session.py`; sau đó đổi lời mời đích danh lấy phiên qua `POST /sessions`.

`/healthz` cố ý **không** chạm database: restart API không sửa được Postgres.

## Ba luật về tiền — đổi thì mở ADR trước, đừng sửa code trước

1. **Số nguyên đồng.** Không `float`, không `Decimal`, kể cả ở giá trị trung gian. `allocator.py` dùng `Fraction` để giữ hữu tỉ chính xác.
2. **`Σ` phân bổ `=` đúng tổng khoản chi**, 100%. 41 golden vector tính tay giữ điều này.
3. **Số dư tính lại được từ sổ**; cache không bao giờ là nguồn sự thật.

Thêm: sửa khoản chi tạo **phiên bản mới** chứ không ghi đè; `receiver_confirmed` **không phải** bằng chứng ngân hàng; `completed` chỉ do domain transition sinh ra, không có nút "đánh dấu xong".

## Mỗi tầng test chứng minh được gì

Đọc kỹ chỗ này trước khi tin một dấu xanh:

| Tầng | Chứng minh | Không chứng minh |
|---|---|---|
| `tests/domain/golden/*.json` + `test_golden_selfcheck.py` | Corpus nhất quán nội tại theo ADR-0004 | Tác giả corpus đọc đúng contract — cùng một người viết cả hai |
| `test_selfcheck_catches_mutants.py` | Self-check thực sự đỏ khi đáp án sai | — |
| `tests/api/` với fake repository (`tests/api/conftest.py`) | Orchestration HTTP ↔ domain | Bất kỳ câu SQL, index, view, trigger nào |
| `tests/postgres/` | `SqlAlchemyApiRepository` thật sau khi Alembic migrate một schema riêng | Mọi method, mọi race, mọi query plan |
| `tests/db/test_migration_matches_models.py` | Migration khớp models, không cần DB | — |
| QA hình ảnh + thăm dò (agy) — ADR-0010 | Trang render được, đọc được, không lộ dữ liệu người khác, ở các trạng thái và thiết bị **đã quét** | **Mã QR có quét được bằng app ngân hàng thật không** · người thật có hiểu không · ô nào **chưa** quét · rằng agy không tự sửa môi trường để ra xanh |

Hàng cuối cần đọc kỹ cột phải. Tác giả plugin đã quan sát được agy **tự sửa môi trường của chính nó** (vá package đã cài, mock-stub dependency) để ép một lệnh pass. Digest của agy **không phải bằng chứng**; người giao việc chạy lại cổng trong cây sạch.

SQLite bị từ chối có chủ ý: schema production dựa vào JSONB, partial unique index, view và trigger append-only. Thêm hành vi persistence mới thì **thêm ca live tương ứng**; mở rộng fake rồi coi đó là bằng chứng DB là nói dối.

## Quy trình — đây là phần dễ vi phạm nhất

Nguồn sự thật: `docs/team/charter.md`, `docs/decisions/ADR-*.md`, `docs/architecture/00-layout-va-so-huu.md`. Đọc trước khi đổi hành vi.

- **Ranh giới sở hữu** (chốt 2026-08-27): Claude giữ `app/web/` (template, câu chữ, style) và `apps/mobile/`. Codex giữ `db/`, `api/`, `domain/` và test backend. Ở trang khách: route và truy cập dữ liệu là của Codex, template không bao giờ tự query.
- **Nhánh**: `<owner>/p0-w<N>-<slug>`, slug phải là Work ID cụ thể — `backend`/`research` là sai.
- **PR (ADR-0007)**: review sống trên GitHub PR, không phải file. Verdict đúng ba giá trị: `APPROVE` / `REQUEST_CHANGES` / `REJECT`. `APPROVE` → merge ngay, ai bấm nút không quan trọng. `REQUEST_CHANGES` → trả về cho tác giả, không thương lượng qua comment rồi merge lén. **Không tự review PR của chính mình.** Leader chỉ đọc `main`, nên mô tả PR phải nói *cái gì đổi và vì sao*, đừng bắt người đọc suy từ diff.
- **Blocker chỉ hợp lệ** khi thuộc 5 loại: vi phạm spec/cổng · sai tiền · quyền riêng tư/bảo mật/consent · hỏng tính hợp lệ thí nghiệm · không tái lập được. Đặt tên, phong cách, "tôi thích cách kia hơn" là suggestion. Blocker phải kèm dẫn chứng · hậu quả · tiêu chí gỡ chặn.
- **Review doc dài** (khi cần lập luận hơn một comment) commit lên chính nhánh đang được review, đặt ở `docs/claude/<YYYY-MM-DD>/` hoặc `docs/codex/<YYYY-MM-DD>/`, kèm commit SHA · protocol_version · verdict · blocker còn mở · bằng chứng đã xem.
- `docs/codex/QUEUE.md` là hàng đợi việc đang mở giữa hai engineer — đọc khi cần biết cái gì còn nợ.

## Bẫy đã biết

- **`apps/mobile/` (378 file) và `packages/shared/` ĐÃ ở trên `main`** từ 2026-08-30; dòng cũ nói ngược là sai. Hai job `shared` và `mobile` trong `.github/workflows/test.yml` vẫn tự phát hiện thư mục trước khi chạy — giữ nguyên cách đó, đừng "sửa" thành vô điều kiện. **Và `apps/mobile/` chứa HAI app**: vỏ RuDi expo-router (`app/**` → `src/rudi/`, cái ship) và cây legacy (`App.tsx` → `src/screens/**`, chỉ tới qua `/legacy`); ADR-0016 quyết hội tụ về vỏ RuDi và xoá legacy theo từng mảng.
- **`phase0/` và `docs/protocol/v1/` đóng băng tại chỗ.** Không sửa, không xoá. `protocol_version` là snapshot bất biến: cần đổi thì ADR cho phép tạo `v2`, không sửa `v1`.
- **Repo guard fail closed** với binary, file text > 2 MiB, symlink, gitlink mới. Muốn thêm artifact thì pin `path` + `sha256` + `rules` + `reason` vào `.repo-guard-allowlist.json` — đổi một byte là phải review lại.
- **Không bao giờ đưa vào Git**: ảnh bill, số tài khoản, tên người tham gia, transcript thô, file export, `.env` thật. `.gitignore` không phải nơi lưu an toàn; dữ liệu thật nằm ngoài repo và ngoài mọi worktree.
- **Branch protection chưa bật** (`W9a-E`): GitHub free + repo private không cho. Nên mọi luật merge ở trên là **kỷ luật**, không phải cưỡng chế — hook local vẫn bị `--no-verify` đi qua.
- **Ruff được cấu hình nhưng cây hiện không sạch** (`ruff check app tests` ra 11 lỗi, `ruff format --check` đòi sửa 27 file) và **CI không gate nó**. Chạy ruff trên file mình đang sửa; đừng chạy `--fix`/`format` cả cây, diff format 27 file sẽ nhấn chìm thay đổi thật và làm PR không review được.
- `requirements-dev.txt` pin cứng để CI và máy dev giải cùng một cây; dependency ứng dụng khai ở `pyproject.toml`. Thêm phụ thuộc thì sửa cả hai chỗ.
- **Chưa có bằng chứng hành vi nào** (ADR-0006 gác Giai đoạn 0 theo quyết định của leader). Đừng đọc bộ test xanh thành "sản phẩm này đúng".
