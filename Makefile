# Phase 3 Sprint 1 - LocalStack demo targets.
# See docs/runbooks/localstack-demo.md for end-to-end usage.
#
# scripts/demo/ is intentionally NOT a uv workspace member (spec §10.4), so
# `python -m demo` only works if `scripts/` is on PYTHONPATH. We set it here
# once for every target rather than spreading the magic across each invocation.

export PYTHONPATH := scripts

.PHONY: demo demo-up demo-down demo-keep demo-clean demo-status help

demo: ## Run the full demo (up + registry + producer + verifier + down)
	uv run python -m demo run

demo-up: ## Stand up infrastructure only (LocalStack + terraform apply)
	uv run python -m demo up

demo-down: ## Tear down LocalStack and remove the volume
	uv run python -m demo down

demo-keep: ## Run the demo but keep state (no docker compose down)
	uv run python -m demo run --keep-state

demo-clean: ## Force teardown + remove pid/log files (recovery)
	-uv run python -m demo down
	-rm -f infra/localstack/.uvicorn.pid infra/localstack/.uvicorn.log

demo-status: ## Show what's running
	uv run python -m demo status

help: ## Print this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
