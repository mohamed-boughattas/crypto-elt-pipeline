#!/usr/bin/env bash
set -uo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0
WARN=0
FAILED_RECIPES=()
WARNED_RECIPES=()
SERVER_PIDS=()

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="$PROJECT_ROOT/data/crypto.duckdb"

cleanup() {
    for pid in "${SERVER_PIDS[@]:-}"; do
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done
}
trap cleanup EXIT

pass() {
    ((PASS++)) || true
    echo -e "  ${GREEN}✓${NC} $1"
}

fail() {
    ((FAIL++)) || true
    FAILED_RECIPES+=("$1")
    echo -e "  ${RED}✗${NC} $1"
    echo -e "    ${RED}$2${NC}"
}

warn() {
    ((WARN++)) || true
    WARNED_RECIPES+=("$1")
    echo -e "  ${YELLOW}⚠${NC} $1 ${YELLOW}(non-blocking)${NC}"
    echo -e "    ${YELLOW}$2${NC}"
}

skip() {
    ((SKIP++)) || true
    echo -e "  ${YELLOW}⊘${NC} $1 ${YELLOW}($2)${NC}"
}

run_with_timeout() {
    local timeout_sec=$1
    shift

    (
        "$@" &
        local pid=$!
        (
            sleep "$timeout_sec"
            kill "$pid" 2>/dev/null
        ) &
        local watchdog=$!

        wait "$pid" 2>/dev/null
        local exit_code=$?
        kill "$watchdog" 2>/dev/null
        wait "$watchdog" 2>/dev/null || true
        return $exit_code
    )
}

run_recipe() {
    local timeout_sec="$1"
    shift
    local display_name="$1"
    shift

    local tmpfile
    tmpfile=$(mktemp)

    run_with_timeout "$timeout_sec" just "$@" > "$tmpfile" 2>&1
    local exit_code=$?

    if [ "$exit_code" -eq 0 ]; then
        pass "$display_name"
    elif [ "$exit_code" -eq 143 ]; then
        fail "$display_name" "Timed out after ${timeout_sec}s"
    else
        local last_lines
        last_lines=$(tail -3 "$tmpfile")
        fail "$display_name" "Exit code $exit_code | $last_lines"
    fi

    rm -f "$tmpfile"
}

run_recipe_warn() {
    local timeout_sec="$1"
    shift
    local display_name="$1"
    shift

    local tmpfile
    tmpfile=$(mktemp)

    run_with_timeout "$timeout_sec" just "$@" > "$tmpfile" 2>&1
    local exit_code=$?

    if [ "$exit_code" -eq 0 ]; then
        pass "$display_name"
    elif [ "$exit_code" -eq 143 ]; then
        warn "$display_name" "Timed out after ${timeout_sec}s"
    else
        local last_lines
        last_lines=$(tail -3 "$tmpfile")
        warn "$display_name" "Exit code $exit_code | $last_lines"
    fi

    rm -f "$tmpfile"
}

test_server_startup() {
    local name="$1"
    local delay="$2"

    just "$name" >/dev/null 2>&1 &
    local pid=$!
    SERVER_PIDS+=("$pid")

    sleep "$delay"

    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null
        wait "$pid" 2>/dev/null || true
        pass "$name (startup)"
    else
        wait "$pid" 2>/dev/null || true
        local exit_code=$?
        fail "$name (startup)" "Process exited early with code $exit_code"
    fi
}

DOCKER_RUNNING=false
DB_EXISTS=false

docker info >/dev/null 2>&1 && DOCKER_RUNNING=true
[ -f "$DB_PATH" ] && DB_EXISTS=true

echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo -e "${CYAN}  ${BOLD}Justfile Recipe Smoke Test${NC}"
echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo ""
echo -e "  Docker:   $DOCKER_RUNNING"
echo -e "  Database: $DB_EXISTS"
echo ""

# ── Setup ────────────────────────────────────────────
echo -e "${BOLD}[Setup]${NC}"
run_recipe 120 "setup" setup
run_recipe 30 "generate-seed" generate-seed

# ── Safe Recipes ─────────────────────────────────────
echo ""
echo -e "${BOLD}[Safe Recipes]${NC}"
run_recipe 30 "default" default
run_recipe 30 "validate-coins" validate-coins
run_recipe 30 "list-coins" list-coins
run_recipe 30 "dry-run" dry-run
run_recipe 120 "lint" lint
run_recipe 120 "typecheck" typecheck
run_recipe 60 "dead-code" dead-code
run_recipe 120 "lint-dbt" lint-dbt
run_recipe 120 "dbt-deps" dbt-deps

# ── Test Recipes ─────────────────────────────────────
echo ""
echo -e "${BOLD}[Test Recipes]${NC}"
run_recipe 180 "test" test
run_recipe 180 "test-cov" test-cov

# ── Security Recipes ─────────────────────────────────
echo ""
echo -e "${BOLD}[Security Recipes]${NC}"
run_recipe 180 "pip-audit" pip-audit
run_recipe 120 "bandit" bandit

# ── Docker Recipes (non-blocking — external API/Docker dependency) ───
echo ""
echo -e "${BOLD}[Docker Recipes — non-blocking]${NC}"
if $DOCKER_RUNNING; then
    run_recipe_warn 300 "pipeline-coin bitcoin" pipeline-coin bitcoin
else
    skip "pipeline-coin bitcoin" "Docker not running"
fi

# ── DB Recipes ───────────────────────────────────────
echo ""
echo -e "${BOLD}[DB Recipes]${NC}"
if $DB_EXISTS; then
    run_recipe 30 "status" status
else
    skip "status" "Database not populated"
fi

skip "test-dbt" "Requires full pipeline — covered in CI"
skip "test-elementary" "Requires full pipeline — covered in CI"

# ── Server Recipes ───────────────────────────────────
echo ""
echo -e "${BOLD}[Server Recipes — startup only]${NC}"
test_server_startup "dev" 10
test_server_startup "api" 8

# ── Summary ──────────────────────────────────────────
echo ""
echo -e "${CYAN}═══════════════════════════════════════════${NC}"
echo -e "  ${GREEN}Passed: ${PASS}${NC}  ${RED}Failed: ${FAIL}${NC}  ${YELLOW}Warnings: ${WARN}${NC}  ${YELLOW}Skipped: ${SKIP}${NC}"
echo -e "${CYAN}═══════════════════════════════════════════${NC}"

if [ "${#WARNED_RECIPES[@]}" -gt 0 ]; then
    echo -e "\n${YELLOW}${BOLD}Warnings (non-blocking):${NC}"
    for recipe in "${WARNED_RECIPES[@]}"; do
        echo -e "  ${YELLOW}⚠ $recipe${NC}"
    done
fi

if [ "${#FAILED_RECIPES[@]}" -gt 0 ]; then
    echo -e "\n${RED}${BOLD}Failed recipes:${NC}"
    for recipe in "${FAILED_RECIPES[@]}"; do
        echo -e "  ${RED}✗ $recipe${NC}"
    done
    exit 1
fi

echo -e "\n${GREEN}${BOLD}All recipes passed!${NC}"
exit 0
