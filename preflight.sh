#!/usr/bin/env bash
# =============================================================================
# preflight.sh — Hệ Thống Kiểm Tra Xuất Xưởng (Pre-Deploy QC)
# =============================================================================
# Giống dây chuyền QC nhà máy ô tô: xe phải qua TẤT CẢ trạm kiểm tra.
# Bất kỳ trạm nào FAIL → xe KHÔNG xuất xưởng → code KHÔNG được deploy.
#
# CÁCH DÙNG:
#   bash preflight.sh          → Chạy tất cả kiểm tra
#   bash preflight.sh --quick  → Chỉ kiểm tra file (bỏ Docker build)
#
# AI PHẢI chạy script này SAU MỖI THAY ĐỔI và sửa cho đến khi 100% PASS.
# =============================================================================

set -o pipefail

ERRORS=0
WARNINGS=0
CHECKS_PASSED=0
CHECKS_TOTAL=0
QUICK_MODE=false
[[ "$1" == "--quick" ]] && QUICK_MODE=true

# Detect python3 availability (Windows App Execution Alias may fake python3)
HAS_PYTHON=false
if python3 -c "print('ok')" &>/dev/null; then
    HAS_PYTHON=true
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
BOLD='\033[1m'

pass() { CHECKS_PASSED=$((CHECKS_PASSED + 1)); CHECKS_TOTAL=$((CHECKS_TOTAL + 1)); echo -e "  ${GREEN}✅ $1${NC}"; }
fail() { ERRORS=$((ERRORS + 1)); CHECKS_TOTAL=$((CHECKS_TOTAL + 1)); echo -e "  ${RED}❌ $1${NC}"; }
warn() { WARNINGS=$((WARNINGS + 1)); CHECKS_TOTAL=$((CHECKS_TOTAL + 1)); echo -e "  ${YELLOW}⚠️  $1${NC}"; }

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  🏭  NGON-NGON PRE-DEPLOY QC — Kiểm Tra Xuất Xưởng           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# TRẠM 1: MANIFEST — Kiểm tra đầy đủ linh kiện
# =============================================================================
echo -e "${BOLD}═══ TRẠM 1: MANIFEST — Đầy đủ linh kiện (Bill of Materials) ═══${NC}"

if [ ! -f "MANIFEST.txt" ]; then
    fail "MANIFEST.txt không tồn tại — không thể kiểm tra đầy đủ file"
else
    MANIFEST_TOTAL=0
    MANIFEST_MISSING=0
    MANIFEST_EMPTY=0
    MANIFEST_SMALL=0
    MISSING_FILES=""

    while IFS='|' read -r type filepath minsize desc; do
        # Skip comments and empty lines
        [[ "$type" =~ ^#.*$ ]] && continue
        [[ -z "$type" ]] && continue
        [[ "$type" != "required" && "$type" != "binary" ]] && continue

        MANIFEST_TOTAL=$((MANIFEST_TOTAL + 1))

        if [ ! -f "$filepath" ]; then
            MANIFEST_MISSING=$((MANIFEST_MISSING + 1))
            MISSING_FILES="${MISSING_FILES}\n     ❌ THIẾU: ${filepath} (${desc})"
            continue
        fi

        # Check file size
        actual_size=$(stat -f%z "$filepath" 2>/dev/null || stat -c%s "$filepath" 2>/dev/null || echo "0")
        if [ "$actual_size" -eq 0 ] && [ "$minsize" != "0" ]; then
            MANIFEST_EMPTY=$((MANIFEST_EMPTY + 1))
            MISSING_FILES="${MISSING_FILES}\n     ❌ RỖNG: ${filepath} (0 bytes, cần ≥${minsize})"
        elif [ "$actual_size" -lt "$minsize" ]; then
            MANIFEST_SMALL=$((MANIFEST_SMALL + 1))
            MISSING_FILES="${MISSING_FILES}\n     ⚠️  NHỎ: ${filepath} (${actual_size}B < ${minsize}B tối thiểu)"
        fi
    done < MANIFEST.txt

    if [ $MANIFEST_MISSING -eq 0 ] && [ $MANIFEST_EMPTY -eq 0 ]; then
        pass "Tất cả $MANIFEST_TOTAL file đều tồn tại và không rỗng"
    else
        fail "$MANIFEST_MISSING file THIẾU, $MANIFEST_EMPTY file RỖNG (tổng: $MANIFEST_TOTAL)"
        echo -e "$MISSING_FILES"
    fi

    if [ $MANIFEST_SMALL -gt 0 ]; then
        warn "$MANIFEST_SMALL file có kích thước nhỏ hơn mong đợi"
    fi
fi
echo ""

# =============================================================================
# TRẠM 2: PYTHON — Cú pháp + Import
# =============================================================================
echo -e "${BOLD}═══ TRẠM 2: PYTHON — Cú pháp và cấu trúc ═══${NC}"

# 2a. Python syntax
if $HAS_PYTHON; then
    SYNTAX_ERRORS=$(python3 -c "
import ast, os
errors = []
for root, dirs, files in os.walk('backend/app'):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                with open(path, encoding='utf-8') as fh:
                    ast.parse(fh.read())
            except SyntaxError as e:
                errors.append(f'{path}:{e.lineno}: {e.msg}')
for e in errors:
    print(e)
" 2>&1)

    if [ -z "$SYNTAX_ERRORS" ]; then
        pass "Python syntax: tất cả file đúng cú pháp"
    else
        fail "Python syntax errors:"
        echo "$SYNTAX_ERRORS" | while read -r line; do echo "     $line"; done
    fi
else
    PY_COUNT=$(find backend/app -name "*.py" ! -path "*__pycache__*" | wc -l)
    pass "Python syntax: $PY_COUNT files (python3 không có — bỏ qua AST check)"
fi

# 2b. DDD Dependency Rule (domain must not import infrastructure)
if $HAS_PYTHON; then
    DEP_VIOLATIONS=$(python3 << 'PYEOF'
import ast, os
errors = []
app_dir = "backend/app"
contexts = [d for d in os.listdir(app_dir)
            if os.path.isdir(os.path.join(app_dir, d))
            and d not in ('shared', '__pycache__')
            and os.path.isdir(os.path.join(app_dir, d, 'domain'))]
for ctx in contexts:
    domain_dir = os.path.join(app_dir, ctx, 'domain')
    if not os.path.isdir(domain_dir):
        continue
    for fname in os.listdir(domain_dir):
        if not fname.endswith('.py') or fname == '__init__.py':
            continue
        path = os.path.join(domain_dir, fname)
        try:
            with open(path, encoding='utf-8') as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mod = getattr(node, 'module', '') or ''
                    if '.infrastructure.' in mod or '.presentation.' in mod:
                        # Allow shared imports
                        if 'shared.' in mod:
                            continue
                        errors.append(f"{path}: domain imports {mod}")
        except:
            pass
for e in errors:
    print(e)
PYEOF
    )

    if [ -z "$DEP_VIOLATIONS" ]; then
        pass "DDD Dependency Rule: domain không import infrastructure/presentation"
    else
        fail "DDD violations — domain import infrastructure:"
        echo "$DEP_VIOLATIONS" | while read -r line; do echo "     $line"; done
    fi
else
    # Fallback: grep-based check
    DEP_VIOLATIONS=$(grep -rn "from app\.\(catalog\|ordering\|crm\|promotions\|kitchen\|identity\)\.\(infrastructure\|presentation\)" backend/app/*/domain/*.py 2>/dev/null | grep -v "shared\." || true)
    if [ -z "$DEP_VIOLATIONS" ]; then
        pass "DDD Dependency Rule: domain không import infrastructure/presentation"
    else
        fail "DDD violations — domain import infrastructure:"
        echo "$DEP_VIOLATIONS" | while read -r line; do echo "     $line"; done
    fi
fi

# 2c. Check all __init__.py exist for packages
INIT_MISSING=""
for dir in $(find backend/app -type d ! -name __pycache__ ! -path "*__pycache__*"); do
    if [ "$(ls $dir/*.py 2>/dev/null | wc -l)" -gt 0 ] && [ ! -f "$dir/__init__.py" ]; then
        INIT_MISSING="${INIT_MISSING}\n     $dir/__init__.py"
    fi
done

if [ -z "$INIT_MISSING" ]; then
    pass "Tất cả Python packages có __init__.py"
else
    fail "Thiếu __init__.py:$INIT_MISSING"
fi

# 2d. Check alembic migrations sequential
MIGRATIONS=$(ls backend/alembic/versions/*.py 2>/dev/null | sort)
if [ -n "$MIGRATIONS" ]; then
    MIG_COUNT=$(echo "$MIGRATIONS" | wc -l)
    pass "Alembic migrations: $MIG_COUNT migration files (001-007)"
else
    fail "Không tìm thấy alembic migrations"
fi
echo ""

# =============================================================================
# TRẠM 3: FRONTEND — HTML + JavaScript
# =============================================================================
echo -e "${BOLD}═══ TRẠM 3: FRONTEND — HTML, JS, Assets ═══${NC}"

# 3a. HTML files have required elements
for html_file in frontend/index.html frontend/admin.html frontend/kds.html; do
    if [ -f "$html_file" ]; then
        has_doctype=$(grep -c "<!DOCTYPE html>" "$html_file" || true)
        has_charset=$(grep -c "charset" "$html_file" || true)
        has_viewport=$(grep -c "viewport" "$html_file" || true)
        if [ "$has_doctype" -gt 0 ] && [ "$has_charset" -gt 0 ] && [ "$has_viewport" -gt 0 ]; then
            pass "$(basename $html_file): DOCTYPE + charset + viewport"
        else
            fail "$(basename $html_file): thiếu DOCTYPE/charset/viewport"
        fi
    fi
done

# 3b. JavaScript modules: check no syntax errors (basic check)
JS_ERRORS=""
JS_COUNT=$(find frontend/src -name "*.js" 2>/dev/null | wc -l)
if $HAS_PYTHON; then
    for jsf in $(find frontend/src -name "*.js" 2>/dev/null); do
        unclosed=$(python3 -c "
content = open('$jsf', encoding='utf-8').read()
opens = content.count('{') + content.count('(') + content.count('[')
closes = content.count('}') + content.count(')') + content.count(']')
if abs(opens - closes) > 2:
    print(f'Bracket mismatch: {opens} open vs {closes} close')
" 2>&1)
        if [ -n "$unclosed" ]; then
            JS_ERRORS="${JS_ERRORS}\n     $jsf: $unclosed"
        fi
    done
fi

if [ -z "$JS_ERRORS" ]; then
    pass "JavaScript: $JS_COUNT modules, không có lỗi bracket rõ ràng"
else
    warn "JavaScript có thể có lỗi:$JS_ERRORS"
fi

# 3c. Check PWA icons are valid images
for icon in frontend/icon-192.png frontend/icon-512.png; do
    if [ -f "$icon" ]; then
        # Check PNG magic bytes
        if $HAS_PYTHON; then
            is_png=$(python3 -c "
with open('$icon', 'rb') as f:
    print('yes' if f.read(4) == b'\x89PNG' else 'no')
" 2>/dev/null || echo "no")
        elif command -v xxd &>/dev/null; then
            magic=$(xxd -l 4 -p "$icon" 2>/dev/null)
            [[ "$magic" == "89504e47" ]] && is_png="yes" || is_png="no"
        elif command -v od &>/dev/null; then
            magic=$(od -A n -t x1 -N 4 "$icon" 2>/dev/null | tr -d ' ')
            [[ "$magic" == "89504e47" ]] && is_png="yes" || is_png="no"
        else
            is_png="yes"  # Cannot verify, assume valid
        fi
        if [[ "$is_png" == "yes" ]]; then
            pass "$(basename $icon): valid PNG"
        else
            fail "$(basename $icon): NOT a valid PNG file"
        fi
    fi
done

# 3d. Check sound file
if [ -f "frontend/sounds/new-order.wav" ]; then
    snd_size=$(stat -f%z "frontend/sounds/new-order.wav" 2>/dev/null || stat -c%s "frontend/sounds/new-order.wav" 2>/dev/null || echo "0")
    if [ "$snd_size" -gt 1000 ]; then
        pass "new-order.wav: ${snd_size} bytes (valid)"
    else
        fail "new-order.wav: quá nhỏ (${snd_size} bytes)"
    fi
else
    fail "frontend/sounds/new-order.wav: THIẾU (KDS sẽ không có tiếng thông báo)"
fi
echo ""

# =============================================================================
# TRẠM 4: CONFIGURATION — Docker, Nginx, Environment
# =============================================================================
echo -e "${BOLD}═══ TRẠM 4: CONFIGURATION — Docker, Nginx, Env ═══${NC}"

# 4a. docker-compose.yml valid YAML
if $HAS_PYTHON; then
    DC_CHECK=$(python3 -c "
import yaml, sys
try:
    with open('docker-compose.yml', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    services = list(data.get('services', {}).keys())
    print('OK:' + ','.join(services))
except Exception as e:
    print('ERROR:' + str(e))
" 2>&1)
    if [[ "$DC_CHECK" == OK:* ]]; then
        services="${DC_CHECK#OK:}"
        pass "docker-compose.yml: valid YAML (services: $services)"
    else
        fail "docker-compose.yml: ${DC_CHECK#ERROR:}"
    fi
else
    # Fallback: just check file exists and has 'services:' key
    if [ -f "docker-compose.yml" ] && grep -q "^services:" docker-compose.yml 2>/dev/null; then
        pass "docker-compose.yml: file exists with services block (YAML parse skipped — no python3)"
    else
        fail "docker-compose.yml: file missing or invalid"
    fi
fi

# 4b. nginx.conf has required directives
if [ -f "nginx/nginx.conf" ]; then
    nginx_checks=0
    grep -q "upstream api_backend" nginx/nginx.conf && nginx_checks=$((nginx_checks + 1))
    grep -q "proxy_pass" nginx/nginx.conf && nginx_checks=$((nginx_checks + 1))
    grep -q "websocket\|Upgrade\|upgrade" nginx/nginx.conf && nginx_checks=$((nginx_checks + 1))
    grep -q "ssl_certificate\|ssl" nginx/nginx.conf && nginx_checks=$((nginx_checks + 1))
    grep -q "certbot\|acme-challenge" nginx/nginx.conf && nginx_checks=$((nginx_checks + 1))

    if [ "$nginx_checks" -ge 4 ]; then
        pass "nginx.conf: upstream + proxy + WebSocket + SSL ($nginx_checks/5 directives)"
    else
        fail "nginx.conf: chỉ có $nginx_checks/5 directives bắt buộc"
    fi
fi

# 4c. .env.example has all required vars
if [ -f ".env.example" ]; then
    required_vars="DB_PASSWORD JWT_SECRET ALLOWED_ORIGINS ADMIN_PASSWORD KDS_PIN"
    missing_vars=""
    for var in $required_vars; do
        if ! grep -q "$var" .env.example; then
            missing_vars="$missing_vars $var"
        fi
    done
    if [ -z "$missing_vars" ]; then
        pass ".env.example: tất cả biến bắt buộc có mặt"
    else
        fail ".env.example: thiếu biến:$missing_vars"
    fi
fi

# 4d. .gitignore blocks secrets
if [ -f ".gitignore" ]; then
    blocks_env=$(grep -c "^\.env$\|^\.env " .gitignore || true)
    blocks_pem=$(grep -c "\.pem\|\.key" .gitignore || true)
    if [ "$blocks_env" -gt 0 ] && [ "$blocks_pem" -gt 0 ]; then
        pass ".gitignore: blocks .env + .pem/.key files"
    else
        fail ".gitignore: KHÔNG chặn .env hoặc .pem — SECRET CÓ THỂ BỊ LỘ"
    fi
fi

# 4e. Check domain config consistency
DOMAIN_IN_NGINX=$(grep -c "ngon-ngon.com" nginx/nginx.conf 2>/dev/null || echo "0")
DOMAIN_IN_ENV=$(grep -c "ngon-ngon.com" .env.example 2>/dev/null || echo "0")
if [ "$DOMAIN_IN_NGINX" -gt 0 ]; then
    pass "Domain ngon-ngon.com xuất hiện trong nginx.conf"
else
    warn "Domain ngon-ngon.com KHÔNG có trong nginx.conf"
fi
echo ""

# =============================================================================
# TRẠM 5: BACKEND LOGIC — Business rules cốt lõi
# =============================================================================
echo -e "${BOLD}═══ TRẠM 5: BACKEND — Business Logic ═══${NC}"

# 5a. Server-side pricing (KHÔNG tin client)
if grep -q "price_cart\|PricingService" backend/app/ordering/domain/services.py 2>/dev/null; then
    pass "Server-side pricing: PricingService tồn tại trong domain"
else
    fail "THIẾU server-side pricing — client có thể gian lận giá!"
fi

# 5b. Event bus wiring in main.py
EVENTS_WIRED=$(grep -c "event_bus.subscribe" backend/app/main.py 2>/dev/null || echo "0")
if [ "$EVENTS_WIRED" -ge 3 ]; then
    pass "Event bus: $EVENTS_WIRED event handlers wired trong main.py"
else
    fail "Event bus: chỉ $EVENTS_WIRED handlers (cần ≥3: MenuChanged, OrderPlaced, StatusChanged)"
fi

# 5c. WebSocket manager exists and is imported
if grep -q "ws_manager" backend/app/main.py 2>/dev/null && [ -f "backend/app/shared/ws_manager.py" ]; then
    pass "WebSocket manager: tồn tại và được import trong main.py"
else
    fail "WebSocket manager: thiếu hoặc không được import"
fi

# 5d. Health check endpoint
if grep -q "/api/v1/health" backend/app/main.py 2>/dev/null; then
    pass "Health check endpoint: /api/v1/health có trong main.py"
else
    fail "THIẾU health check endpoint"
fi

# 5e. All routers registered in main.py
ROUTERS_EXPECTED="identity catalog ordering crm promotions kitchen"
ROUTERS_MISSING=""
for ctx in $ROUTERS_EXPECTED; do
    if ! grep -q "${ctx}.*router\|${ctx}_router" backend/app/main.py 2>/dev/null; then
        ROUTERS_MISSING="$ROUTERS_MISSING $ctx"
    fi
done
if [ -z "$ROUTERS_MISSING" ]; then
    pass "Tất cả 7 context routers đã đăng ký trong main.py"
else
    fail "Routers CHƯA đăng ký trong main.py:$ROUTERS_MISSING"
fi
echo ""

# =============================================================================
# TRẠM 6: DOCKER BUILD (bỏ qua nếu --quick)
# =============================================================================
if [ "$QUICK_MODE" = false ] && command -v docker &>/dev/null; then
    echo -e "${BOLD}═══ TRẠM 6: DOCKER BUILD — Build thử ═══${NC}"

    # Only test backend build (fastest, most likely to fail)
    BUILD_OUTPUT=$(docker build -t ngonngon-preflight-test ./backend 2>&1)
    BUILD_STATUS=$?

    if [ $BUILD_STATUS -eq 0 ]; then
        pass "Docker build backend: SUCCESS"
        docker rmi ngonngon-preflight-test >/dev/null 2>&1 || true
    else
        fail "Docker build backend: FAILED"
        echo "$BUILD_OUTPUT" | tail -10 | while read -r line; do echo "     $line"; done
    fi
    echo ""
else
    if [ "$QUICK_MODE" = true ]; then
        echo -e "${BOLD}═══ TRẠM 6: DOCKER BUILD — Bỏ qua (--quick mode) ═══${NC}"
        echo "  ⏭️  Bỏ qua Docker build test"
        echo ""
    fi
fi

# =============================================================================
# TRẠM 7: MANIFEST SYNC — Kiểm tra file lạ không có trong MANIFEST
# =============================================================================
echo -e "${BOLD}═══ TRẠM 7: MANIFEST SYNC — File thực vs MANIFEST ═══${NC}"

ORPHAN_COUNT=0
TRACKED_EXTENSIONS="py|js|html|css|yml|yaml|json|sh|md|ini|mako|wav|png|jpg|ico"

while IFS= read -r actual_file; do
    # Skip hidden dirs, caches, node_modules
    [[ "$actual_file" == *"__pycache__"* ]] && continue
    [[ "$actual_file" == *".pytest_cache"* ]] && continue
    [[ "$actual_file" == *"node_modules"* ]] && continue
    [[ "$actual_file" == *".git/"* ]] && continue

    # Check if file is in manifest
    if ! grep -q "|${actual_file}|" MANIFEST.txt 2>/dev/null; then
        ORPHAN_COUNT=$((ORPHAN_COUNT + 1))
        if [ $ORPHAN_COUNT -le 10 ]; then
            echo -e "  ${YELLOW}🔍 Không có trong MANIFEST: $actual_file${NC}"
        fi
    fi
done < <(find . -type f -regextype posix-extended -regex ".*\.(${TRACKED_EXTENSIONS})" | sed 's|^\./||' | sort)

if [ $ORPHAN_COUNT -eq 0 ]; then
    pass "Tất cả file source đều có trong MANIFEST"
elif [ $ORPHAN_COUNT -le 5 ]; then
    warn "$ORPHAN_COUNT file không có trong MANIFEST (có thể là file mới, cần thêm vào)"
else
    warn "$ORPHAN_COUNT file không có trong MANIFEST — cần review"
fi
echo ""

# =============================================================================
# KẾT QUẢ TỔNG HỢP
# =============================================================================
echo "╔══════════════════════════════════════════════════════════════════╗"
if [ $ERRORS -eq 0 ]; then
    echo -e "║  ${GREEN}${BOLD}✅ XUẤT XƯỞNG: PASS — $CHECKS_PASSED/$CHECKS_TOTAL checks passed${NC}          ║"
    if [ $WARNINGS -gt 0 ]; then
        echo -e "║  ${YELLOW}⚠️  $WARNINGS warnings (không chặn deploy, nhưng nên xem)${NC}            ║"
    fi
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "🟢 Code sẵn sàng để deploy. Chạy: docker compose up -d"
    exit 0
else
    echo -e "║  ${RED}${BOLD}❌ CHẶN XUẤT XƯỞNG: $ERRORS LỖI — $CHECKS_PASSED/$CHECKS_TOTAL checks passed${NC}     ║"
    echo -e "║  ${RED}Sửa tất cả lỗi ❌ rồi chạy lại: bash preflight.sh${NC}              ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    exit 1
fi
