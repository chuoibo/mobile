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

COMPOSE ?= docker compose

# --wait đứng chờ tới khi postgres "healthy" và migrate thoát mã 0. Có giới
# hạn vì một lệnh treo vô hạn tệ hơn một lệnh báo đỏ.
WAIT_TIMEOUT ?= 300

.DEFAULT_GOAL := help
.PHONY: help up down clean logs ps migrate seed smoke

help: ## In danh sách lệnh
	@echo "Lệnh có sẵn:"
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
	  | sed -E 's/^([a-z-]+):.*## (.*)/  make \1|\2/' \
	  | column -t -s '|'

up: ## Dựng ảnh, chạy migration, bật API, seed dữ liệu mẫu, rồi tự kiểm
	$(COMPOSE) up -d --build --wait --wait-timeout $(WAIT_TIMEOUT)
	@$(MAKE) --no-print-directory seed
	@$(MAKE) --no-print-directory smoke

down: ## Tắt hệ, GIỮ dữ liệu trong volume
	$(COMPOSE) down

clean: ## Tắt hệ và XOÁ volume Postgres — mất sạch dữ liệu local
	$(COMPOSE) down -v

logs: ## Bám log API và Postgres
	$(COMPOSE) logs -f api postgres

ps: ## Trạng thái các service
	$(COMPOSE) ps

migrate: ## Chỉ chạy `alembic upgrade head` (up đã tự chạy rồi)
	$(COMPOSE) run --rm migrate

seed: ## Chỉ seed dữ liệu mẫu — chạy lại là no-op, không nhân đôi
	@$(COMPOSE) ps --services --filter status=running | grep -qx api || { \
	  echo "API chưa chạy. Chạy 'make up' trước." >&2; exit 1; }
	@# --no-deps là bắt buộc, không phải tối ưu. `compose run` không có nó sẽ
	@# chạy lại `migrate` (service đã exited thì nó coi là phải dựng lại) rồi
	@# recreate luôn `api` vì phụ thuộc vừa đổi — tức là seed tự đá sập cái
	@# API mà nó sắp gọi. Điều kiện "api đang chạy" đã kiểm ở trên rồi.
	$(COMPOSE) run --rm --no-deps seed

smoke: ## Gọi thật /healthz qua cổng đã publish và in địa chỉ ra
	@addr="$$($(COMPOSE) port api 8000 2>/dev/null)"; \
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
