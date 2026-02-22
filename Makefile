md-check: ## Check Markdown formatting
	.venv/bin/mdformat --check .

md-fix: ## Auto-fix Markdown formatting
	.venv/bin/mdformat .

check: lint format lint-frontend format-frontend md-check ## Run all checks (lint + format + markdown)

fix: lint-fix format-fix lint-frontend-fix format-frontend-fix md-fix ## Auto-fix all lint, format, and markdown issues
