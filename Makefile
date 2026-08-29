# Một lệnh dựng cả hệ trên máy dev: `make up`.
#
# Cần sẵn: docker (có compose v2), make, curl. Không cần Python trên máy —
# API, migration và seed đều chạy trong ảnh đã dựng.
#
# `make up` publish API ra http://127.0.0.1:8099 — cùng con số mà app và
# scripts/phone_path.py mặc định dùng. Đổi khi 8099 hoặc 5432 đã bận:
#   MOBILE_API_PORT=8100 MOBILE_POSTGRES_PORT=5433 make up
# hoặc ghi hai dòng đó vào .env ở gốc repo — compose tự đọc, và .env đã bị
# .gitignore chặn nên không lỡ tay commit.
#
# PHẠM VI: mọi lệnh ở đây thao tác lên MỘT bộ container dùng chung cho cả máy,
# không phải bộ riêng của thư mục bạn đang đứng. Máy này có nhiều worktree của
# cùng một repo, và chúng cố ý chia nhau một Postgres, một API — link trang
# khách in ra ở worktree này phải mở được ở worktree kia. Hệ quả phải nhớ:
# `make down` tắt API mà lane khác đang gọi, và `make clean` xoá database của
# họ. Muốn một bộ riêng thì đặt MOBILE_PROJECT (xem `make help`).

COMPOSE ?= docker compose

# Tên project mà compose sẽ dùng. Thứ tự này khớp đúng thứ tự ưu tiên của
# compose (COMPOSE_PROJECT_NAME đè lên `name:` trong file), nên con số `make`
# in ra và con số docker thật sự dùng không bao giờ lệch nhau.
MOBILE_PROJECT ?= mobile-local
# Fold to lower case the way Compose itself does. Without this, `make` prints
# and confirms the name as typed while Compose quietly acts on the folded one:
# `MOBILE_PROJECT=QA47 make clean CONFIRM=QA47` passed `-p QA47` and destroyed
# `qa47`, a different lane's stack. A destructive command has to name the thing
# it destroys, and the only way to be sure is to do the folding here.
PROJECT := $(shell printf '%s' '$(if $(COMPOSE_PROJECT_NAME),$(COMPOSE_PROJECT_NAME),$(MOBILE_PROJECT))' | tr 'A-Z' 'a-z')
export MOBILE_PROJECT

# `-p` truyền thẳng, không dựa vào việc compose đọc được biến môi trường. Một
# lệnh xoá dữ liệu thì cái tên nó in ra và cái tên nó xoá phải là một, bằng
# cấu tạo chứ không bằng may mắn.
DC = $(COMPOSE) -p $(PROJECT)

# --wait đứng chờ tới khi postgres "healthy" và migrate thoát mã 0. Có giới
# hạn vì một lệnh treo vô hạn tệ hơn một lệnh báo đỏ.
WAIT_TIMEOUT ?= 300

.DEFAULT_GOAL := help
.PHONY: help gate test-db test-ai up down clean logs ps migrate db-check seed demo smoke

# `demo` phải gọi đúng bộ container mà `up` vừa dựng. Trên nhánh này biến đó là
# $(COMPOSE); PR #60 (đang mở, cùng lane) đổi nó thành $(DC) = compose kèm
# `-p <project>`. Viết như dưới thì dòng lệnh đúng ở cả hai nền, và khi #60 vào
# main nó tự chuyển sang $(DC) — không ai phải nhớ quay lại sửa, và hai PR
# không tranh nhau cùng một dòng.
DEMO_COMPOSE = $(if $(DC),$(DC),$(COMPOSE))

# Cảnh báo khi thiếu khoá AI. Để trong script chứ không viết thẳng vào recipe
# vì recipe không test được nếu không dựng Docker; script thì chạy và kiểm
# được một mình (tests/test_stack_carries_gemini_key.py).
KEY_CHECK = sh scripts/check_ai_key.sh
# Và khoá danh tính. Tách khỏi KEY_CHECK vì hậu quả khác hẳn: thiếu khoá AI
# thì đọc bill chết, thiếu khoá này thì KHÔNG AI ĐĂNG NHẬP ĐƯỢC.
IDENTITY_KEY_CHECK = sh scripts/check_identity_key.sh

help: ## In danh sách lệnh
	@echo "Lệnh có sẵn:"
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
	  | sed -E 's/^([a-z-]+):.*## (.*)/  make \1|\2/' \
	  | column -t -s '|'
	@echo
	@echo "Project compose hiện tại: $(PROJECT)"
	@echo "Một project cho cả máy, dùng chung giữa mọi worktree. Nên:"
	@echo "  - make down  tắt API mà worktree khác đang gọi."
	@echo "  - make clean XOÁ database của mọi worktree, không riêng thư mục này."
	@echo "    Vì vậy nó bắt gõ ra:  make clean CONFIRM=$(PROJECT)"
	@echo
	@echo "Muốn một bộ riêng, không đụng ai (QA soi một PR, thử migration bẩn):"
	@echo "  MOBILE_PROJECT=qa47 MOBILE_API_PORT=8199 MOBILE_POSTGRES_PORT=5434 make up"
	@echo "  MOBILE_PROJECT=qa47 make clean CONFIRM=qa47      # dọn đúng bộ đó thôi"

# Đứng trước `up` vì nó trả lời câu hỏi đứng trước: "cây này có lành không".
# GitHub Actions ngừng khởi động job từ 07:45Z ngày 29/08 vì billing — 100 run
# gần nhất là 100 hỏng, 0 đạt — nên trong lúc đó đây là cổng DUY NHẤT còn chạy
# được. Thân cổng nằm ở scripts/gate.sh chứ không viết thẳng vào recipe: recipe
# không test được nếu không có make, còn script thì tests/ gọi được.
gate: ## Chạy các cổng của CI ngay tại máy — ONLY="api mobile" chọn chặng, STRICT=1 coi bỏ-qua là hỏng
	@scripts/gate.sh $(if $(STRICT),--strict) $(ONLY)

# Tầng duy nhất chứng minh SQL, index, view và trigger thật. 224 ca, 17 giây,
# và trước hôm nay gần như không ai chạy: phải tự biết chuỗi kết nối, mà máy
# này có mười container Postgres của năm worktree nên đoán nhầm là chuyện
# thường. Nay nó tự dựng database riêng rồi tự xoá, KHÔNG đụng bộ `make up`
# của bất kỳ lane nào — nên không cần `make up` trước, và chạy được song song
# với người khác.
test-db: ## Chạy tầng PostgreSQL thật trên database dùng một lần — ARGS="-k ten" lọc ca
	@scripts/postgres_tier.sh $(ARGS)

# Tầng DUY NHẤT gọi model thật. Mọi test khác của chụp bill và gợi ý đều chạy
# trên reader giả, nên chúng chứng minh điều phối chứ không chứng minh AI.
# Trước hôm nay 33 ca này chỉ có một trạng thái: bỏ qua — không workflow, không
# chặng cổng, không target nào đặt hai biến bật chúng lên. Khoá hết hạn, quota
# cạn hay tên model bị khai tử đều không làm đỏ được thứ gì.
#
# TỐN QUOTA THẬT, cùng cái quota mà buổi demo chạy trên đó: 34 ca, ~3 phút.
# Lọc bớt bằng ARGS khi chỉ cần soi một mảng.
test-ai: ## Chạy tầng Gemini sống — gọi model thật, tốn quota. ARGS="-k receipt" lọc ca
	@scripts/gemini_tier.sh $(ARGS)

up: ## Dựng ảnh, chạy migration, bật API, seed dữ liệu mẫu, rồi tự kiểm
	@# Trước `docker build`, không phải sau: build mất vài phút, và một cảnh
	@# báo in ra sau đó thì đã trôi khỏi màn hình. In ở đây thì còn kịp Ctrl-C.
	@# Cảnh báo, không chặn — xem đầu file scripts/check_ai_key.sh.
	@$(KEY_CHECK)
	@$(IDENTITY_KEY_CHECK)
	@echo "Project compose: $(PROJECT) (dùng chung cho mọi worktree trên máy này)"
	@$(DC) up -d --build --wait --wait-timeout $(WAIT_TIMEOUT) || { \
	  echo >&2; \
	  echo "make up thất bại — dòng lỗi của docker nằm ngay phía trên." >&2; \
	  echo "Hay gặp nhất là cổng đã có người giữ: 'address already in use' hoặc" >&2; \
	  echo "'port is already allocated'. Đổi cổng, không phải sửa file:" >&2; \
	  echo "    MOBILE_API_PORT=8199 MOBILE_POSTGRES_PORT=5434 make up" >&2; \
	  echo "Nếu người giữ cổng là bộ container của chính repo này thì 'make ps'" >&2; \
	  echo "sẽ thấy nó, và bạn không cần dựng lại." >&2; \
	  echo >&2; \
	  echo "!! API CŨ CÓ THỂ VẪN ĐANG GIỮ CỔNG VÀ PHỤC VỤ MÃ CŨ." >&2; \
	  echo "   'api' phụ thuộc 'migrate' bằng service_completed_successfully, nên" >&2; \
	  echo "   migrate hỏng thì compose dừng TRƯỚC khi thay container api — container" >&2; \
	  echo "   cũ không bị đụng tới và vẫn trả lời. Ngày 29/08 khoảng trống đó để máy" >&2; \
	  echo "   demo phục vụ mã trước hai lần merge suốt sáu tiếng, trong khi /healthz" >&2; \
	  echo "   vẫn 200 — nó cố ý không chạm database, và không biết gì về route." >&2; \
	  echo "   Đừng tin cổng còn trả lời nghĩa là còn dùng được. Hỏi thẳng:" >&2; \
	  echo "       make smoke" >&2; \
	  exit 1; }
	@$(MAKE) --no-print-directory seed
	@$(MAKE) --no-print-directory smoke

down: ## Tắt hệ, GIỮ dữ liệu trong volume
	@echo "Tắt project '$(PROJECT)' — dùng chung, nên worktree khác cũng mất API."
	$(DC) down

clean: ## Tắt hệ và XOÁ volume Postgres của cả máy — cần CONFIRM=<tên project>
	@if [ "$(CONFIRM)" != "$(PROJECT)" ]; then \
	  echo "Từ chối: make clean xoá volume Postgres của project '$(PROJECT)'." >&2; \
	  echo >&2; \
	  echo "Project đó KHÔNG thuộc riêng thư mục này. Mọi worktree trên máy" >&2; \
	  echo "dùng chung nó, nên dữ liệu mất là mất của cả đội — kể cả đợt thu" >&2; \
	  echo "mà lane khác đang mở dở trên trình duyệt." >&2; \
	  echo >&2; \
	  echo "Sẽ bị xoá: volume $(PROJECT)_mobile-postgres-data ('make ps' xem container)." >&2; \
	  echo >&2; \
	  echo "Chắc thì gõ đúng tên project ra:" >&2; \
	  echo "    make clean CONFIRM=$(PROJECT)" >&2; \
	  echo "Chỉ muốn tắt mà giữ dữ liệu:   make down" >&2; \
	  echo "Muốn một bộ riêng để phá:      MOBILE_PROJECT=thu-nghiem make up" >&2; \
	  exit 1; \
	fi
	$(DC) down -v

logs: ## Bám log API và Postgres
	$(DC) logs -f api postgres

ps: ## Trạng thái các service
	@echo "Project compose: $(PROJECT)"
	$(DC) ps

migrate: ## Chỉ chạy `alembic upgrade head` (up đã tự chạy rồi)
	$(DC) run --rm migrate

db-check: ## Hỏi database xem nó có ở đúng head mà mã đang phục vụ mong đợi không
	@# Chạy alembic TRONG ẢNH ĐANG PHỤC VỤ, không phải trong worktree này. Máy
	@# này có năm worktree chung một stack; câu hỏi đúng là "schema có khớp code
	@# đang chạy không", và chỉ cái ảnh đó trả lời được. So với worktree thì trên
	@# nhánh có migration chưa merge, cổng sẽ báo database "đứng sau" rồi bảo
	@# bạn migrate nó lên revision của nhánh — đúng nước đi đã tạo ra sự cố
	@# 29/08. Xem đầu scripts/check_db_revision.sh.
	@#
	@# --no-deps vì postgres đã chạy rồi; không có nó thì `run` dựng lại chuỗi
	@# phụ thuộc và có thể recreate `api` mà lane khác đang gọi.
	@sh scripts/check_db_revision.sh $(DC) run --rm --no-deps -T migrate alembic

seed: ## Chỉ seed dữ liệu mẫu — chạy lại là no-op, không nhân đôi
	@$(DC) ps --services --filter status=running | grep -qx api || { \
	  echo "API chưa chạy. Chạy 'make up' trước." >&2; exit 1; }
	@# --no-deps là bắt buộc, không phải tối ưu. `compose run` không có nó sẽ
	@# chạy lại `migrate` (service đã exited thì nó coi là phải dựng lại) rồi
	@# recreate luôn `api` vì phụ thuộc vừa đổi — tức là seed tự đá sập cái
	@# API mà nó sắp gọi. Điều kiện "api đang chạy" đã kiểm ở trên rồi.
	$(DC) run --rm --no-deps seed

demo: ## Dựng hệ rồi nạp dữ liệu demo "Team Đà Lạt" — 7 người, 3 chuyến, còn nợ thật
	@$(MAKE) --no-print-directory up
	@# Gọi thẳng `up` chứ không tự dựng lại stack: hai đường khởi động là hai
	@# đường để lệch nhau, và `up` là đường đã có người kiểm. Hệ quả phải nói
	@# ra: `up` cũng chạy `make seed`, nên máy sẽ có thêm nhóm "Nhóm mẫu (dữ
	@# liệu tổng hợp)" bên cạnh "Team Đà Lạt". Nó có nhãn rõ ràng, không phải
	@# dữ liệu lẫn lộn — nhưng nó CÓ hiện trên màn danh sách nhóm.
	@# --no-deps: xem ghi chú ở `seed`, cùng một cái bẫy.
	$(DEMO_COMPOSE) run --rm --no-deps demo

smoke: ## Gọi thật /healthz qua cổng đã publish và in địa chỉ ra
	@# `smoke` là việc cuối `up` chạy, nên nó giữ màn hình cuối cùng. Nhắc lại
	@# ở đây để cảnh báo không bị chôn dưới log build. Nó cũng đúng chỗ khi gọi
	@# riêng: `smoke` trả lời "bộ này dùng được không", và "API sống nhưng
	@# không đọc được bill" là đúng loại câu trả lời đó.
	@$(KEY_CHECK) --brief
	@addr="$$($(DC) port api 8000 2>/dev/null)"; \
	if [ -z "$$addr" ]; then \
	  echo "API chưa chạy. Chạy 'make up' trước." >&2; exit 1; \
	fi; \
	url="http://127.0.0.1:$${addr##*:}"; \
	printf 'GET %s/healthz -> ' "$$url"; \
	curl -fsS --max-time 10 "$$url/healthz" || { \
	  echo; echo "API không trả lời. 'make logs' để xem vì sao." >&2; exit 1; }; \
	echo; \
	echo "API sẵn sàng:  $$url"; \
	echo "Tài liệu API:  $$url/docs"
	@# Vế thứ hai: tiến trình đang giữ cổng có phải MÃ HIỆN TẠI không. /healthz
	@# trả lời "có tiến trình phục vụ", và một container dựng từ trước hai lần
	@# merge trả lời y hệt. Ngày 29/08 nó trả lời như thế suốt sáu tiếng trong
	@# khi thiếu 5 route, và cả đội đọc dấu healthy đó là "máy demo dùng được".
	@#
	@# Phần này BỎ QUA khi máy không có fastapi cho python3, vì đầu file Makefile
	@# hứa `make up` chỉ cần docker+make+curl và một cổng mới không được phép rút
	@# lại lời hứa đó. Bỏ qua thì NÓI RA — bỏ qua im lặng là cổng chết.
	@addr="$$($(DC) port api 8000 2>/dev/null)"; \
	url="http://127.0.0.1:$${addr##*:}"; \
	if python3 -c "import fastapi" >/dev/null 2>&1; then \
	  python3 scripts/check_server_routes.py --url "$$url"; \
	else \
	  echo "BỎ QUA cổng route: máy này không có fastapi cho python3, nên không"; \
	  echo "  dựng được danh sách route của cây để đối chiếu. Bật lên bằng:"; \
	  echo "      pip install -r services/api/requirements-dev.txt"; \
	fi
	@# /healthz cố ý không chạm database, nên nó KHÔNG trả lời được "database có
	@# đúng schema không". Ngày 29/08 khoảng trống đó để cả bộ báo khoẻ suốt
	@# nhiều giờ trong khi database đứng ở một revision không nhánh nào giữ và
	@# mọi route đụng bảng `outings` trả 500. Đây là vế còn lại của câu hỏi
	@# "bộ này dùng được không".
	@$(MAKE) --no-print-directory db-check
