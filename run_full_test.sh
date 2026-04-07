#!/bin/bash
# =============================================================================
# COMPREHENSIVE TEST & ANALYSIS SCRIPT
# Runs all tests, checks imports, validates frontend, generates one report
# =============================================================================

REPORT="/home/claude/TEST_REPORT.md"
echo "# NGON-NGON FULL TEST REPORT" > "$REPORT"
echo "Generated: $(date)" >> "$REPORT"
echo "" >> "$REPORT"

# =============================================================================
# 1. PYTHON IMPORT CHAIN ANALYSIS
# =============================================================================
echo "## 1. Import Chain Analysis" >> "$REPORT"
echo "" >> "$REPORT"

# Check if conftest.py imports exist
echo "### conftest.py imports:" >> "$REPORT"
cd /home/claude/backend

# Check every import in conftest
python3 -c "
import sys
sys.path.insert(0, '.')
errors = []

# Test conftest imports one by one
imports_to_test = [
    ('app.database', 'Base, get_db'),
    ('app.main', 'create_app'),
    ('app.models', 'Category, Product, ProductSize, Topping, AdminUser, Order, OrderItem, LayoutType'),
    ('app.identity.infrastructure.auth', 'create_access_token, hash_password'),
]

for module, names in imports_to_test:
    try:
        mod = __import__(module, fromlist=names.split(', '))
        for name in names.split(', '):
            if not hasattr(mod, name.strip()):
                errors.append(f'MISSING: {module}.{name.strip()}')
            else:
                print(f'OK: {module}.{name.strip()}')
    except Exception as e:
        errors.append(f'IMPORT ERROR: {module} -> {e}')

# Check if app.services exists (conftest imports from it)
try:
    import app.services
    print('OK: app.services module exists')
except:
    errors.append('MISSING MODULE: app.services (conftest.py line 23 imports from it)')

if errors:
    print('\\n--- ERRORS ---')
    for e in errors:
        print(f'  {e}')
" >> "$REPORT" 2>&1

echo "" >> "$REPORT"

# =============================================================================
# 2. CHECK ALL CROSS-MODULE IMPORTS IN THE PROJECT
# =============================================================================
echo "## 2. Cross-module Import Checks" >> "$REPORT"
echo "" >> "$REPORT"

python3 -c "
import ast, os, sys
sys.path.insert(0, '.')

errors = []
for root, dirs, files in os.walk('app'):
    for f in files:
        if f.endswith('.py'):
            fpath = os.path.join(root, f)
            try:
                with open(fpath) as fh:
                    tree = ast.parse(fh.read())
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        if isinstance(node, ast.ImportFrom) and node.module:
                            mod = node.module
                            if mod.startswith('app.'):
                                try:
                                    __import__(mod)
                                except Exception as e:
                                    errors.append(f'{fpath}: import {mod} -> {e}')
            except SyntaxError as e:
                errors.append(f'{fpath}: SYNTAX ERROR -> {e}')

if errors:
    print('IMPORT ERRORS FOUND:')
    for e in errors:
        print(f'  {e}')
else:
    print('All internal imports OK')
" >> "$REPORT" 2>&1

echo "" >> "$REPORT"

# =============================================================================
# 3. RUN PYTEST (with the known conftest issue)
# =============================================================================
echo "## 3. Pytest Results" >> "$REPORT"
echo "" >> "$REPORT"

cd /home/claude/backend
python -m pytest tests/ -v --tb=long 2>&1 >> "$REPORT"
PYTEST_EXIT=$?
echo "" >> "$REPORT"
echo "Pytest exit code: $PYTEST_EXIT" >> "$REPORT"
echo "" >> "$REPORT"

# =============================================================================
# 4. TRY STARTING THE APP (without DB, just check if it loads)
# =============================================================================
echo "## 4. App Startup Check" >> "$REPORT"
echo "" >> "$REPORT"

python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from app.main import create_app
    app = create_app()
    routes = [r.path for r in app.routes]
    print(f'App created successfully with {len(routes)} routes:')
    for r in sorted(routes):
        print(f'  {r}')
except Exception as e:
    print(f'APP STARTUP FAILED: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
" >> "$REPORT" 2>&1

echo "" >> "$REPORT"

# =============================================================================
# 5. CHECK ALL ROUTERS INDIVIDUALLY  
# =============================================================================
echo "## 5. Individual Router Import Check" >> "$REPORT"
echo "" >> "$REPORT"

python3 -c "
import sys
sys.path.insert(0, '.')

routers = [
    'app.identity.presentation.router',
    'app.catalog.presentation.router',
    'app.catalog.presentation.admin_router',
    'app.ordering.presentation.router',
    'app.ordering.presentation.admin_router',
    'app.growth.presentation.router',
    'app.kitchen.presentation.router',
]

for r in routers:
    try:
        mod = __import__(r, fromlist=['router'])
        routes = [(route.path, list(route.methods)) for route in mod.router.routes]
        print(f'OK: {r} ({len(routes)} endpoints)')
        for path, methods in routes:
            print(f'    {methods} {path}')
    except Exception as e:
        print(f'FAIL: {r} -> {type(e).__name__}: {e}')
" >> "$REPORT" 2>&1

echo "" >> "$REPORT"

# =============================================================================
# 6. CHECK SCHEMAS / PYDANTIC MODELS
# =============================================================================
echo "## 6. Schema Validation" >> "$REPORT"
echo "" >> "$REPORT"

python3 -c "
import sys
sys.path.insert(0, '.')

schemas = [
    'app.ordering.presentation.schemas',
    'app.catalog.presentation.schemas',
    'app.schemas',
]

for s in schemas:
    try:
        mod = __import__(s, fromlist=['__all__'])
        names = [n for n in dir(mod) if not n.startswith('_')]
        print(f'OK: {s} -> {names}')
    except Exception as e:
        print(f'FAIL: {s} -> {type(e).__name__}: {e}')
" >> "$REPORT" 2>&1

echo "" >> "$REPORT"

# =============================================================================
# 7. CHECK EVENT BUS WIRING
# =============================================================================
echo "## 7. Event Bus Wiring Check" >> "$REPORT"
echo "" >> "$REPORT"

python3 -c "
import sys
sys.path.insert(0, '.')

try:
    from app.shared.events import event_bus
    print(f'EventBus OK, type: {type(event_bus).__name__}')
    
    from app.catalog.domain.events import MenuChanged
    from app.catalog.application.event_handlers import on_menu_changed
    from app.ordering.domain.events import OrderPlaced, OrderStatusChanged
    from app.ordering.application.event_handlers import on_order_placed_broadcast_ws, on_status_changed_broadcast_ws
    from app.growth.application.event_handlers import create_customer_tracking_handler
    print('All event imports OK')
except Exception as e:
    print(f'Event wiring FAIL: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
" >> "$REPORT" 2>&1

echo "" >> "$REPORT"

# =============================================================================
# 8. FRONTEND ANALYSIS
# =============================================================================
echo "## 8. Frontend Analysis" >> "$REPORT"
echo "" >> "$REPORT"

echo "### Files:" >> "$REPORT"
find /home/claude/frontend -type f | sort >> "$REPORT"
echo "" >> "$REPORT"

# Check API endpoint references in frontend
echo "### API endpoints referenced in frontend JS:" >> "$REPORT"
grep -rohn '/api/v1/[a-z/_-]*' /home/claude/frontend/src/ /home/claude/frontend/*.html 2>/dev/null | sort -u >> "$REPORT"
echo "" >> "$REPORT"

# Check for common JS issues
echo "### JS syntax check (basic):" >> "$REPORT"
for jsfile in $(find /home/claude/frontend/src -name "*.js" -type f); do
    node --check "$jsfile" 2>&1 && echo "OK: $jsfile" || echo "FAIL: $jsfile"
done >> "$REPORT" 2>&1
echo "" >> "$REPORT"

# Check Service Worker
echo "### Service Worker:" >> "$REPORT"
node --check /home/claude/frontend/sw.js 2>&1 >> "$REPORT"
echo "" >> "$REPORT"

# =============================================================================
# 9. NGINX CONFIG CHECK
# =============================================================================
echo "## 9. Nginx Config" >> "$REPORT"
echo "" >> "$REPORT"
echo "### Proxy pass targets:" >> "$REPORT"
grep -n "proxy_pass\|location\|upstream" /home/claude/nginx/nginx.conf >> "$REPORT"
echo "" >> "$REPORT"

# =============================================================================
# 10. DATABASE MIGRATION FILES
# =============================================================================
echo "## 10. Alembic Migrations" >> "$REPORT"
echo "" >> "$REPORT"
ls -la /home/claude/backend/alembic/versions/ >> "$REPORT"
echo "" >> "$REPORT"

# =============================================================================
# SUMMARY
# =============================================================================
echo "## SUMMARY" >> "$REPORT"
echo "" >> "$REPORT"
echo "Report complete. Check sections above for FAIL/ERROR markers." >> "$REPORT"

echo "===== REPORT GENERATED: $REPORT ====="
cat "$REPORT"
