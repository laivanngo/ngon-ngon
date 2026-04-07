#!/usr/bin/env bash
# =============================================================================
# validate.sh V3.0 — HỆ THỐNG KIỂM DUYỆT CODE TỰ ĐỘNG (Backend + Frontend)
# =============================================================================
# CÁCH DÙNG: bash validate.sh
# AI phải chạy script này và sửa lỗi cho đến khi PASS trước khi báo "xong".
# =============================================================================

APP_DIR="backend/app"
TEST_DIR="backend/tests"
FE_SRC="frontend/src"
FE_LEGACY="frontend/js"
ERRORS=0
WARNINGS=0

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🛡️  NGON-NGON CODE VALIDATOR V3.0                          ║"
echo "║  Backend (DDD) + Frontend (Vite/ES Modules)                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "═══════════════════ BACKEND CHECKS ═══════════════════"
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 1: Python Syntax (AST)
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 1: Python Syntax ━━━"
SYNTAX_ERRORS=$(python3 -c "
import ast, os
errors = []
for root, dirs, files in os.walk('$APP_DIR'):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                with open(path) as fh:
                    ast.parse(fh.read())
            except SyntaxError as e:
                errors.append(f'{path}:{e.lineno}: {e.msg}')
for e in errors:
    print(e)
" 2>&1)

if [ -z "$SYNTAX_ERRORS" ]; then
    echo "  ✅ Tất cả file Python đúng cú pháp"
else
    echo "  ❌ Lỗi cú pháp:"
    echo "$SYNTAX_ERRORS" | while read -r line; do echo "     $line"; done
    ERRORS=$((ERRORS + 1))
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 2: Linter (Ruff nếu có, fallback grep)
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 2: Linter ━━━"
if command -v ruff &> /dev/null; then
    RUFF_OUTPUT=$(ruff check "$APP_DIR" --select E,F,W --ignore E501 2>&1 || true)
    if [ -z "$RUFF_OUTPUT" ] || echo "$RUFF_OUTPUT" | grep -q "All checks passed"; then
        echo "  ✅ Ruff: code sạch"
    else
        RUFF_COUNT=$(echo "$RUFF_OUTPUT" | grep -c ":" 2>/dev/null || echo "0")
        echo "  ⚠️  Ruff phát hiện $RUFF_COUNT vấn đề:"
        echo "$RUFF_OUTPUT" | head -15 | while read -r line; do echo "     $line"; done
        WARNINGS=$((WARNINGS + 1))
    fi
else
    CAMEL_FUNCS=$(grep -rn "def [a-z][a-z]*[A-Z]" "$APP_DIR" --include="*.py" \
        | grep -v "__pycache__" | grep -v "# noqa" || true)
    if [ -z "$CAMEL_FUNCS" ]; then
        echo "  ✅ Functions đúng snake_case (Ruff chưa cài — khuyên: pip install ruff)"
    else
        echo "  ❌ Phát hiện camelCase functions:"
        echo "$CAMEL_FUNCS" | while read -r line; do echo "     $line"; done
        ERRORS=$((ERRORS + 1))
    fi
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 3: Dependency Rule (AST — Domain không import Infrastructure)
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 3: Dependency Rule (AST) ━━━"
DEPENDENCY_RESULT=$(python3 << 'PYEOF'
import ast, os, sys

app_dir = "backend/app"
errors = []
contexts = [d for d in os.listdir(app_dir)
            if os.path.isdir(os.path.join(app_dir, d))
            and d not in ('shared', '__pycache__')
            and os.path.isdir(os.path.join(app_dir, d, 'domain'))]

for ctx in contexts:
    for layer, forbidden in [('domain', ['infrastructure', 'presentation']),
                              ('application', ['presentation'])]:
        layer_dir = os.path.join(app_dir, ctx, layer)
        if not os.path.isdir(layer_dir):
            continue
        for root, _, files in os.walk(layer_dir):
            for f in files:
                if not f.endswith('.py'): continue
                path = os.path.join(root, f)
                try:
                    tree = ast.parse(open(path, encoding='utf-8').read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        mod = node.module
                        for bad in forbidden:
                            if f'app.{ctx}.{bad}' in mod:
                                errors.append(f'  [{layer}→{bad}] {path}: {mod}')
                        if layer == 'domain' and mod.startswith('sqlalchemy'):
                            errors.append(f'  [domain→sqlalchemy] {path}: {mod}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
else:
    print('OK')
PYEOF
)

if [ "$?" -eq 0 ] && [ "$DEPENDENCY_RESULT" = "OK" ]; then
    echo "  ✅ Domain/Application tuân thủ dependency rule"
else
    echo "  ❌ Vi phạm dependency rule:"
    echo "$DEPENDENCY_RESULT"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 4: Boundary Rule — Cross-context imports (AST + whitelist)
# Whitelist dựa trên kiến trúc Port+Adapter hiện tại.
# Khi tạo Port/Adapter MỚI hợp lệ → thêm pattern vào whitelist bên dưới.
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 4: Boundary Rule (AST) ━━━"
BOUNDARY_RESULT=$(python3 << 'PYEOF'
import ast, os, sys

app_dir = "backend/app"
errors = []
contexts = [d for d in os.listdir(app_dir)
            if os.path.isdir(os.path.join(app_dir, d))
            and d not in ('shared', '__pycache__')
            and os.path.isdir(os.path.join(app_dir, d, 'domain'))]

# Cross-context imports HỢP LỆ theo kiến trúc hiện tại.
# Quy tắc: import từ domain/ (interfaces, events, ports) của context khác = OK.
#           import từ infrastructure/ hoặc application/ của context khác = VI PHẠM.
# Ngoại lệ: auth middleware, config, database.
always_allowed = [
    'app.identity.presentation.middleware',  # Auth (cross-cutting)
    'app.identity.domain.entities',          # CurrentAdmin type
    'app.identity.infrastructure.auth',      # Token utils
    'app.shared.',                           # Shared kernel
    'app.database',                          # DB session
    'app.config',                            # Settings
]

def is_allowed(import_path, source_ctx):
    # Same context = always OK
    if import_path.startswith(f'app.{source_ctx}.'):
        return True
    # Not an app import = OK
    if not import_path.startswith('app.'):
        return True
    # Always-allowed list
    for pattern in always_allowed:
        if import_path.startswith(pattern):
            return True
    # Cross-context: only domain layer imports are OK (ports, events, entities)
    for ctx in contexts:
        if import_path.startswith(f'app.{ctx}.domain.'):
            return True
    # Cross-context adapter imports in infrastructure/ and dependencies.py = OK
    # (This is where Port implementations live)
    return False

for ctx in contexts:
    ctx_dir = os.path.join(app_dir, ctx)
    for root, _, files in os.walk(ctx_dir):
        for f in files:
            if not f.endswith('.py'): continue
            path = os.path.join(root, f)
            try:
                tree = ast.parse(open(path, encoding='utf-8').read())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if not is_allowed(node.module, ctx):
                        # Check if source file is allowed to import cross-context adapters:
                        # - infrastructure/ : implements adapters for ports
                        # - presentation/   : wires dependencies (composition root)
                        # - application/event_handlers.py : wiring code at context boundary
                        #   (event handlers are called by EventBus, not via Presentation,
                        #    so they need to construct their own adapter dependencies)
                        rel = os.path.relpath(path, os.path.join(app_dir, ctx))
                        if rel.startswith('infrastructure') or rel.startswith('presentation'):
                            continue
                        if 'event_handlers' in os.path.basename(path):
                            continue
                        errors.append(f'  {path}: from {node.module}')

if errors:
    for e in errors: print(e)
    sys.exit(1)
else:
    print('OK')
PYEOF
)

if [ "$?" -eq 0 ] && [ "$BOUNDARY_RESULT" = "OK" ]; then
    echo "  ✅ Boundary clean — không có cross-context import vi phạm"
else
    echo "  ❌ Cross-context import vi phạm:"
    echo "$BOUNDARY_RESULT"
    echo "  → Giải pháp: dùng Port (ABC) trong domain/, Adapter trong infrastructure/"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 5: __init__.py có docstring
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 5: __init__.py docstring ━━━"
MISSING_DOCS=""
for init_file in $(find "$APP_DIR" -name "__init__.py" | sort); do
    if [ ! -s "$init_file" ] || ! head -1 "$init_file" | grep -q '"""'; then
        MISSING_DOCS="$MISSING_DOCS
     $init_file"
    fi
done

if [ -z "$MISSING_DOCS" ]; then
    echo "  ✅ Tất cả __init__.py có docstring"
else
    echo "  ⚠️  Thiếu docstring:"
    echo "$MISSING_DOCS"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 6: Legacy files đã xóa — đảm bảo không ai tạo lại
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 6: Legacy files ━━━"
LEGACY_FOUND=false
for legacy_file in models.py schemas.py ws_manager.py; do
    if [ -f "$APP_DIR/$legacy_file" ]; then
        echo "  ❌ app/$legacy_file đã bị tạo lại! File này đã được loại bỏ."
        echo "     → Đặt code vào đúng Bounded Context thay vì tạo lại file legacy."
        ERRORS=$((ERRORS + 1))
        LEGACY_FOUND=true
    fi
done
if [ "$LEGACY_FOUND" = false ]; then
    echo "  ✅ Không có legacy files (models.py, schemas.py, ws_manager.py đã xóa)"
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 7: Pydantic field 'type'
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 7: Pydantic field 'type' ━━━"
TYPE_FIELDS=$(grep -rn "^\s*type:\s*\(str\|int\|bool\|float\)" "$APP_DIR" --include="*.py" \
    | grep -v "__pycache__" | grep -v "# noqa" \
    | grep -v "delivery_type\|event_type\|token_type\|reward_type\|mime_type" || true)

if [ -z "$TYPE_FIELDS" ]; then
    echo "  ✅ Không có field 'type' shadow built-in"
else
    echo "  ⚠️  Field 'type' — nên đổi tên + alias=\"type\":"
    echo "$TYPE_FIELDS" | while read -r line; do echo "     $line"; done
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 8: DRY — Constants không bị duplicate
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 8: DRY ━━━"
DRY_OK=true

PHONE_DEFS=$(grep -rn "re.compile.*0\[35789\]" "$APP_DIR" --include="*.py" \
    | grep -v "__pycache__" | grep -v "shared/constants.py" || true)
if [ -n "$PHONE_DEFS" ]; then
    echo "  ⚠️  VN_PHONE_REGEX duplicate — import từ shared/constants.py"
    WARNINGS=$((WARNINGS + 1)); DRY_OK=false
fi

MONEY_DEFS=$(grep -rn "^class Money" "$APP_DIR" --include="*.py" \
    | grep -v "__pycache__" | grep -v "shared/value_objects.py" || true)
if [ -n "$MONEY_DEFS" ]; then
    echo "  ⚠️  Money class duplicate — import từ shared/value_objects.py"
    WARNINGS=$((WARNINGS + 1)); DRY_OK=false
fi

if [ "$DRY_OK" = true ]; then
    echo "  ✅ Không có duplicate constants"
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 9: Alembic — ORM model thay đổi mà thiếu migration
# (Thực tế: so sánh timestamp orm_models.py vs migration mới nhất)
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 9: Alembic Migration ━━━"
if [ -d "backend/alembic/versions" ]; then
    # Tìm file orm_models.py mới nhất (theo modification time)
    NEWEST_ORM=$(find "$APP_DIR" -name "orm_models.py" -newer "backend/alembic/versions" 2>/dev/null \
        | grep -v "__pycache__" || true)
    if [ -n "$NEWEST_ORM" ]; then
        echo "  ⚠️  ORM model có thể đã thay đổi mà chưa có migration mới:"
        echo "$NEWEST_ORM" | while read -r line; do echo "     $line"; done
        echo "     → Kiểm tra: cần tạo alembic revision --autogenerate?"
        WARNINGS=$((WARNINGS + 1))
    else
        echo "  ✅ ORM models và migrations đồng bộ"
    fi
else
    echo "  ⚠️  Không tìm thấy backend/alembic/versions/"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 10: Unit Tests (chạy từ đúng thư mục backend/)
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 10: Unit Tests ━━━"
if [ -d "$TEST_DIR/unit" ]; then
    if command -v pytest &> /dev/null || python3 -m pytest --version &> /dev/null; then
        PYTEST_OUTPUT=$(cd backend && python -m pytest tests/unit/ -q --tb=short 2>&1 || true)
        if echo "$PYTEST_OUTPUT" | grep -q "passed" && ! echo "$PYTEST_OUTPUT" | grep -q " failed"; then
            PASSED=$(echo "$PYTEST_OUTPUT" | grep -o "[0-9]* passed" | head -1)
            echo "  ✅ Unit tests PASS ($PASSED)"
        elif echo "$PYTEST_OUTPUT" | grep -q "no tests ran\|collected 0"; then
            echo "  ⚠️  Không có test nào chạy được (có thể thiếu dependencies)"
            WARNINGS=$((WARNINGS + 1))
        else
            echo "  ❌ Unit tests FAIL:"
            echo "$PYTEST_OUTPUT" | tail -10 | while read -r line; do echo "     $line"; done
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo "  ℹ️  Pytest chưa cài. Nhắc: AI PHẢI viết test cho logic mới."
    fi
else
    echo "  ⚠️  Không tìm thấy $TEST_DIR/unit/"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

echo "═══════════════════ FRONTEND CHECKS ═══════════════════"
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 11: Frontend src/ structure exists (nếu đã bắt đầu migrate)
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 11: Frontend Structure ━━━"
if [ -d "$FE_SRC" ]; then
    echo "  ✅ frontend/src/ tồn tại"

    # Check shared/api.js exists
    if [ -f "$FE_SRC/shared/api.js" ]; then
        echo "  ✅ src/shared/api.js (centralized API) tồn tại"
    else
        echo "  ⚠️  Chưa có src/shared/api.js — cần tạo khi bắt đầu Phase 1"
        WARNINGS=$((WARNINGS + 1))
    fi

    # Check entry files
    for entry in admin/main.js customer/main.js kds/main.js; do
        if [ -f "$FE_SRC/$entry" ]; then
            echo "  ✅ src/$entry tồn tại"
        fi
    done
else
    echo "  ℹ️  frontend/src/ chưa tồn tại — Frontend migration chưa bắt đầu"
    echo "     (Sẽ tạo khi thực hiện Phase 1 theo AI_GUIDE.md Section 5.7)"
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 12: Không có code mới trong legacy js/ folder
# (Chỉ check nếu src/ đã tồn tại = migration đã bắt đầu)
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 12: No New Code in Legacy js/ ━━━"
if [ -d "$FE_SRC" ] && [ -d "$FE_LEGACY" ]; then
    # So sánh: nếu có file mới trong js/ mà không phải file legacy gốc
    LEGACY_KNOWN="api.js app.js cart.js growth.js"
    NEW_IN_LEGACY=""
    for f in "$FE_LEGACY"/*.js; do
        [ -f "$f" ] || continue
        fname=$(basename "$f")
        if ! echo "$LEGACY_KNOWN" | grep -qw "$fname"; then
            NEW_IN_LEGACY="$NEW_IN_LEGACY\n     $f"
        fi
    done
    if [ -z "$NEW_IN_LEGACY" ]; then
        echo "  ✅ Không có file JS mới trong legacy js/"
    else
        echo "  ❌ Phát hiện file MỚI trong legacy js/ (phải đặt trong src/):"
        echo -e "$NEW_IN_LEGACY"
        ERRORS=$((ERRORS + 1))
    fi
elif [ ! -d "$FE_SRC" ]; then
    echo "  ℹ️  Bỏ qua — migration chưa bắt đầu"
else
    echo "  ✅ Legacy js/ đã được xóa"
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 13: File JS không quá 200 dòng
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 13: JS File Size (≤ 200 lines) ━━━"
if [ -d "$FE_SRC" ]; then
    LONG_FILES=""
    while IFS= read -r jsfile; do
        lines=$(wc -l < "$jsfile")
        if [ "$lines" -gt 200 ]; then
            LONG_FILES="$LONG_FILES\n     $jsfile ($lines dòng)"
        fi
    done < <(find "$FE_SRC" -name "*.js" -type f 2>/dev/null)

    if [ -z "$LONG_FILES" ]; then
        echo "  ✅ Tất cả file JS trong src/ ≤ 200 dòng"
    else
        echo "  ⚠️  File JS quá 200 dòng — nên tách module:"
        echo -e "$LONG_FILES"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "  ℹ️  Bỏ qua — frontend/src/ chưa tồn tại"
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 14: Không dùng fetch() trực tiếp (phải qua api.js)
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 14: No Direct fetch() ━━━"
if [ -d "$FE_SRC" ]; then
    DIRECT_FETCH=$(grep -rn "fetch(" "$FE_SRC" --include="*.js" \
        | grep -v "shared/api.js" \
        | grep -v "shared/customer-api.js" \
        | grep -v "// legacy" \
        | grep -v "// noqa" \
        | grep -v "sw.js" || true)

    if [ -z "$DIRECT_FETCH" ]; then
        echo "  ✅ Tất cả API calls đi qua shared/api.js hoặc shared/customer-api.js"
    else
        echo "  ❌ Phát hiện fetch() trực tiếp (phải dùng api.js hoặc customer-api.js):"
        echo "$DIRECT_FETCH" | while read -r line; do echo "     $line"; done
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "  ℹ️  Bỏ qua — frontend/src/ chưa tồn tại"
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 15: Không dùng IIFE trong code mới (src/)
# Pattern IIFE thực sự: `= (() =>` hoặc `(function()` ở đầu dòng/sau =
# KHÔNG match: setTimeout(() =>, setInterval(() =>, .then(() =>
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 15: No New IIFE Modules ━━━"
if [ -d "$FE_SRC" ]; then
    IIFE_FOUND=$(grep -rn "=\s*(().*=>" "$FE_SRC" --include="*.js" \
        | grep -v "// legacy" \
        | grep -v "// noqa" || true)
    IIFE_FOUND2=$(grep -rn "^\s*(function()" "$FE_SRC" --include="*.js" \
        | grep -v "// legacy" \
        | grep -v "// noqa" || true)
    IIFE_ALL="$IIFE_FOUND$IIFE_FOUND2"

    if [ -z "$IIFE_ALL" ]; then
        echo "  ✅ Không có IIFE mới — đúng ES Module pattern"
    else
        echo "  ⚠️  Phát hiện IIFE pattern trong src/ (nên dùng ES Modules):"
        echo "$IIFE_ALL" | head -5 | while read -r line; do echo "     $line"; done
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "  ℹ️  Bỏ qua — frontend/src/ chưa tồn tại"
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 16: Không thêm window.xxx globals
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 16: No New Globals (window.xxx) ━━━"
if [ -d "$FE_SRC" ]; then
    GLOBALS_FOUND=$(grep -rn "window\.\w\+\s*=" "$FE_SRC" --include="*.js" \
        | grep -v "// legacy" \
        | grep -v "// noqa" \
        | grep -v "window.location" \
        | grep -v "window.addEventListener" \
        | grep -v "window.open" \
        | grep -v "window.scrollTo" \
        | grep -v "window.innerWidth\|window.innerHeight" || true)

    if [ -z "$GLOBALS_FOUND" ]; then
        echo "  ✅ Không có global assignment mới"
    else
        echo "  ⚠️  Phát hiện window.xxx = ... (nên dùng import/export):"
        echo "$GLOBALS_FOUND" | while read -r line; do echo "     $line"; done
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "  ℹ️  Bỏ qua — frontend/src/ chưa tồn tại"
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 17: Inline scripts trong HTML ≤ 5 dòng
# (Chỉ check nếu migration đã bắt đầu)
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 17: No Long Inline Scripts in HTML ━━━"
if [ -d "$FE_SRC" ]; then
    HTML_INLINE_ISSUES=""
    for htmlfile in frontend/admin.html frontend/index.html frontend/kds.html; do
        [ -f "$htmlfile" ] || continue
        # Đếm dòng giữa <script> và </script> (inline, không có src=)
        INLINE_LINES=$(awk '
            /<script[^>]*>/ && !/<script[^>]*src=/ { counting=1; count=0; next }
            /<\/script>/ { if(counting && count > 5) print FILENAME": "count" dòng inline script"; counting=0 }
            counting { count++ }
        ' "$htmlfile")
        if [ -n "$INLINE_LINES" ]; then
            HTML_INLINE_ISSUES="$HTML_INLINE_ISSUES\n     $INLINE_LINES"
        fi
    done

    if [ -z "$HTML_INLINE_ISSUES" ]; then
        echo "  ✅ HTML files không có inline script dài"
    else
        echo "  ⚠️  HTML có inline script > 5 dòng (tách ra file .js trong src/):"
        echo -e "$HTML_INLINE_ISSUES"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "  ℹ️  Bỏ qua — migration chưa bắt đầu (inline scripts là legacy hiện tại)"
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 18: Vite config và package.json
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 18: Vite Setup ━━━"
if [ -d "$FE_SRC" ]; then
    VITE_OK=true
    if [ -f "frontend/package.json" ]; then
        echo "  ✅ frontend/package.json tồn tại"
        if grep -q "vite" "frontend/package.json"; then
            echo "  ✅ Vite có trong dependencies"
        else
            echo "  ❌ Vite CHƯA có trong package.json — chạy: cd frontend && npm install --save-dev vite"
            ERRORS=$((ERRORS + 1)); VITE_OK=false
        fi
    else
        echo "  ❌ Thiếu frontend/package.json — chạy: cd frontend && npm init -y"
        ERRORS=$((ERRORS + 1)); VITE_OK=false
    fi

    if [ -f "frontend/vite.config.js" ]; then
        echo "  ✅ frontend/vite.config.js tồn tại"
    else
        echo "  ❌ Thiếu frontend/vite.config.js — xem AI_GUIDE.md Section 5.5.2"
        ERRORS=$((ERRORS + 1)); VITE_OK=false
    fi
else
    echo "  ℹ️  Bỏ qua — frontend/src/ chưa tồn tại"
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 19: Không cài React/Vue/Angular
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 19: No Framework Installed ━━━"
if [ -f "frontend/package.json" ]; then
    FRAMEWORKS=$(grep -E '"(react|vue|angular|svelte|solid-js|preact)"' "frontend/package.json" || true)
    if [ -z "$FRAMEWORKS" ]; then
        echo "  ✅ Không có framework nào — đúng Vanilla JS policy"
    else
        echo "  ❌ PHÁT HIỆN FRAMEWORK — vi phạm policy Vanilla JS:"
        echo "     $FRAMEWORKS"
        echo "     → Xóa và dùng Vanilla JS + Vite theo AI_GUIDE.md"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "  ℹ️  Bỏ qua — chưa có package.json"
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 20: ES Module exports (mỗi file trong src/ phải export gì đó)
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 20: ES Module Exports ━━━"
if [ -d "$FE_SRC" ]; then
    NO_EXPORT=""
    while IFS= read -r jsfile; do
        if ! grep -q "export " "$jsfile"; then
            NO_EXPORT="$NO_EXPORT\n     $jsfile"
        fi
    done < <(find "$FE_SRC" -name "*.js" -type f 2>/dev/null)

    if [ -z "$NO_EXPORT" ]; then
        echo "  ✅ Tất cả file JS trong src/ đều có export"
    else
        echo "  ⚠️  File JS không có export (mỗi module phải export rõ ràng):"
        echo -e "$NO_EXPORT"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "  ℹ️  Bỏ qua — frontend/src/ chưa tồn tại"
fi
echo ""

# ─────────────────────────────────────────────────────────
# CHECK 21: Vite build (nếu Vite đã cài)
# ─────────────────────────────────────────────────────────
echo "━━━ CHECK 21: Vite Build ━━━"
if [ -d "$FE_SRC" ] && [ -f "frontend/package.json" ] && [ -d "frontend/node_modules/.bin" ]; then
    if [ -x "frontend/node_modules/.bin/vite" ]; then
        BUILD_OUTPUT=$(cd frontend && npx vite build 2>&1 || true)
        if echo "$BUILD_OUTPUT" | grep -q "built in\|✓"; then
            echo "  ✅ Vite build thành công"
        else
            echo "  ❌ Vite build FAIL:"
            echo "$BUILD_OUTPUT" | tail -10 | while read -r line; do echo "     $line"; done
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo "  ⚠️  Vite chưa cài — chạy: cd frontend && npm install"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "  ℹ️  Bỏ qua — Vite chưa được setup"
fi
echo ""

# ─────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════════╗"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "║  ✅ TẤT CẢ ĐỀU PASS — CODE ĐẠT CHUẨN                      ║"
elif [ $ERRORS -eq 0 ]; then
    echo "║  ⚠️  PASS với $WARNINGS cảnh báo (không nghiêm trọng)         ║"
    echo "║  Code chạy được, nên sửa cảnh báo khi có thời gian.         ║"
else
    echo "║  ❌ FAIL — $ERRORS LỖI!                                       ║"
    echo "║  AI KHÔNG ĐƯỢC BÁO 'XONG'. Sửa lỗi → chạy lại validate.sh  ║"
fi
echo "╚══════════════════════════════════════════════════════════════╝"

exit $ERRORS
