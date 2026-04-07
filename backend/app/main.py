"""
Ngon-Ngon API — DDD Phase 6: CRM + PROMOTIONS SPLIT
======================================================
7 Bounded Contexts:

✅ Phase 1-2: Shared Kernel + Ordering Context
✅ Phase 3:   Catalog Context
✅ Phase 4:   Growth Context (đã tách)
✅ Phase 5:   Kitchen + Identity Contexts
✅ Phase 6:   Growth → CRM + Promotions (tách context)

CONTEXT MAP:
                    Identity
                   (auth/JWT)
                  ↗    ↑    ↖
           Admin    Kitchen    WS
                      |
                      | reuses UpdateStatusUseCase
                      ↓
  Catalog ──(giá)──→ Ordering ──(OrderPlaced event)──→ CRM
                                                        (Loyalty/Referral)
                                 Promotions
                                 (Flags/Upsell/CrossSell)

EVENT BUS WIRING:
    MenuChanged        → on_menu_changed (WS broadcast)
    OrderPlaced        → on_order_placed_track_customer (CRM: spend-based loyalty)
    OrderPlaced        → on_order_placed_broadcast_ws (WS: admin panel)
    OrderStatusChanged → on_status_changed_broadcast_ws (WS: admin + KDS)

ROUTERS:
    /api/v1/menu, /products, /toppings  → Catalog (public)
    /api/v1/admin/products, /categories → Catalog (admin)
    /api/v1/orders                      → Ordering
    /api/v1/crm/*                       → CRM (customer, loyalty, referral, reviews, analytics)
    /api/v1/promotions/*                → Promotions (flags, upsell, cross-sell)
    /api/v1/kds/*                       → Kitchen
    /api/v1/admin/login                 → Identity
    /api/v1/admin/orders, /dashboard    → Admin
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine

# --- DDD Event Imports ---
from app.catalog.domain.events import MenuChanged
from app.catalog.application.event_handlers import on_menu_changed
from app.ordering.domain.events import OrderPlaced, OrderStatusChanged
from app.ordering.application.event_handlers import (
    on_order_placed_broadcast_ws,
    on_status_changed_broadcast_ws,
)
from app.crm.application.event_handlers import create_customer_tracking_handler
from app.shared.events import event_bus
from app.shared.exceptions import DomainError, DuplicateError, NotFoundError

# =============================================================================
# Logging
# =============================================================================
logging.basicConfig(
    level=logging.DEBUG if settings.ENV == "development" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ngonngon")


# =============================================================================
# Wire Event Handlers (cross-context communication)
# =============================================================================
def _wire_events():
    """
    Subscribe event handlers — called once at startup.

    WHY event bus thay vì direct import:
    - Ordering KHÔNG import Growth, Kitchen, Notification
    - Thêm context mới = thêm 1 dòng subscribe, KHÔNG sửa Ordering
    - Remove context = bỏ 1 dòng subscribe, KHÔNG sửa Ordering

    EVENT MAP:
        Publisher       Event               → Handler                    Context
        ─────────       ─────               ─ ───────                    ───────
        Catalog         MenuChanged         → on_menu_changed            Shared (WS)
        Ordering        OrderPlaced         → track_customer             CRM
        Ordering        OrderPlaced         → broadcast_ws               Shared (WS)
        Ordering        OrderStatusChanged  → broadcast_status_ws        Shared (WS)
    """
    from app.database import async_session

    # Catalog → WS: menu change broadcast
    event_bus.subscribe(MenuChanged, on_menu_changed)

    # Ordering → CRM: customer tracking (spend-based loyalty)
    event_bus.subscribe(
        OrderPlaced,
        create_customer_tracking_handler(async_session),
    )

    # Ordering → WS: real-time broadcast to admin panel + KDS
    event_bus.subscribe(OrderPlaced, on_order_placed_broadcast_ws)
    event_bus.subscribe(OrderStatusChanged, on_status_changed_broadcast_ws)

    # Flash Sale → WS: real-time broadcast to admin panel
    from app.promotions.domain.events import (
        FlashSaleActivated,
        FlashSaleClaimed,
        FlashSaleEnded,
    )
    from app.promotions.application.event_handlers import (
        on_flash_sale_activated,
        on_flash_sale_claimed,
        on_flash_sale_ended,
    )
    event_bus.subscribe(FlashSaleActivated, on_flash_sale_activated)
    event_bus.subscribe(FlashSaleClaimed, on_flash_sale_claimed)
    event_bus.subscribe(FlashSaleEnded, on_flash_sale_ended)

    logger.info("✅ Event handlers wired (all contexts + Flash Sale)")


# =============================================================================
# Lifespan
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    from app.database import async_session
    from app.promotions.infrastructure.scheduler import flash_sale_tick_loop

    _wire_events()

    # Start Flash Sale background scheduler
    scheduler_task = asyncio.create_task(
        flash_sale_tick_loop(async_session, event_bus)
    )

    logger.info("🚀 Ngon-Ngon API started (DDD Phase 6 — 7 contexts + Flash Sale)")
    yield

    # Stop scheduler gracefully
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass

    await engine.dispose()
    logger.info("👋 Ngon-Ngon API shut down")


# =============================================================================
# Sanitization utility — import from shared kernel
# =============================================================================
from app.shared.utils import sanitize_string


# =============================================================================
# App Factory
# =============================================================================
def create_app() -> FastAPI:
    application = FastAPI(
        title="Ngon-Ngon API",
        version="6.0.0-ddd",
        docs_url="/api/docs" if settings.ENV != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # --- CORS ---
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    # --- Request ID + Timing Middleware ---
    @application.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = uuid.uuid4().hex[:8]
        request.state.request_id = request_id

        start = time.time()
        response = await call_next(request)
        ms = round((time.time() - start) * 1000, 1)

        response.headers["X-Request-ID"] = request_id
        if request.url.path != "/api/v1/health":
            logger.info(
                f"{request.method} {request.url.path} → {response.status_code} "
                f"({ms}ms) [rid={request_id}]"
            )
        return response

    # --- Domain Exception Handlers ---
    @application.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": exc.message})

    @application.exception_handler(DuplicateError)
    async def duplicate_handler(request: Request, exc: DuplicateError):
        return JSONResponse(status_code=409, content={"detail": exc.message})

    @application.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        return JSONResponse(status_code=400, content={"detail": exc.message})

    # --- Global Exception Handler ---
    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", "unknown")
        logger.error(
            f"Unhandled error [rid={rid}]: {type(exc).__name__}: {exc}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Đã có lỗi xảy ra, vui lòng thử lại sau.",
                    "request_id": rid,
                },
            },
        )

    # =========================================================================
    # ROUTERS — All 6 Bounded Contexts
    # =========================================================================

    # ✅ Identity Context (Phase 5) — POST /admin/login
    from app.identity.presentation.router import router as identity_router
    application.include_router(
        identity_router, prefix="/api/v1/admin", tags=["Identity"]
    )

    # ✅ Catalog Context (Phase 3) — Public menu API
    from app.catalog.presentation.router import router as catalog_public_router
    application.include_router(
        catalog_public_router, prefix="/api/v1", tags=["Catalog"]
    )

    # ✅ Catalog Context (Phase 3) — Admin CRUD
    from app.catalog.presentation.admin_router import router as catalog_admin_router
    application.include_router(
        catalog_admin_router, prefix="/api/v1/admin", tags=["Catalog Admin"]
    )

    # ✅ Ordering Context (Phase 2) — POST /orders, GET /orders/{id}
    from app.ordering.presentation.router import router as ordering_router
    application.include_router(
        ordering_router, prefix="/api/v1", tags=["Ordering"]
    )

    # ✅ CRM Context (Phase 6) — /crm/* (customer, loyalty, referral, reviews, analytics, settings)
    from app.crm.presentation.router import router as crm_router
    application.include_router(
        crm_router, prefix="/api/v1/crm", tags=["CRM"]
    )

    # ✅ Promotions Context (Phase 6) — /promotions/* (flags, upsell, cross-sell)
    from app.promotions.presentation.router import router as promotions_router
    application.include_router(
        promotions_router, prefix="/api/v1/promotions", tags=["Promotions"]
    )

    # ✅ Flash Sale — /promotions/flash-sales/* (4 endpoints)
    from app.promotions.presentation.flash_sale_router import router as flash_sale_router
    application.include_router(
        flash_sale_router, prefix="/api/v1/promotions", tags=["Flash Sales"]
    )

    # ✅ Kitchen Context (Phase 5) — /kds/* (3 endpoints)
    from app.kitchen.presentation.router import router as kitchen_router
    application.include_router(
        kitchen_router, prefix="/api/v1/kds", tags=["Kitchen"]
    )

    # ✅ Ordering Context — Admin: orders + dashboard
    from app.ordering.presentation.admin_router import router as ordering_admin_router
    application.include_router(
        ordering_admin_router, prefix="/api/v1/admin", tags=["Admin Orders"]
    )

    # --- WebSocket: Real-time order notifications ---
    from fastapi import WebSocket, WebSocketDisconnect
    from app.shared.ws_manager import ws_manager
    from app.identity.infrastructure.auth import token_service

    @application.websocket("/api/v1/ws/orders")
    async def ws_order_notifications(websocket: WebSocket):
        ws_token = websocket.query_params.get("token", "")
        username = token_service.decode_token(ws_token)
        if not username:
            # PHẢI accept() trước khi close() — nếu không Starlette trả 403
            # vì WebSocket handshake vẫn ở HTTP phase
            await websocket.accept()
            await websocket.close(
                code=4001, reason="Token không hợp lệ hoặc đã hết hạn"
            )
            return

        await ws_manager.connect(websocket)
        try:
            import json

            await websocket.send_text(
                json.dumps(
                    {
                        "type": "connected",
                        "message": f"Xin chào {username}! Đang lắng nghe đơn hàng mới...",
                        "active_admins": ws_manager.active_count,
                    }
                )
            )

            while True:
                data = await websocket.receive_text()
                if data == "pong":
                    continue
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
        except Exception:
            ws_manager.disconnect(websocket)

    # --- Health Check ---
    @application.get("/api/v1/health", include_in_schema=False)
    async def health_check():
        from sqlalchemy import text
        from app.database import async_session

        try:
            async with async_session() as db:
                await db.execute(text("SELECT 1"))
            return {
                "status": "healthy",
                "service": "ngonngon-api",
                "version": "6.0.0-ddd",
                "db": "connected",
            }
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "db": str(type(e).__name__)},
            )

    return application


app = create_app()
