"""
Seed Script — Import data từ const M gốc vào PostgreSQL
=========================================================
Chạy 1 lần khi deploy lần đầu:
    docker compose exec api python -m scripts.seed

Hoặc reset toàn bộ data:
    docker compose exec api python -m scripts.seed --reset

WHY script riêng thay vì SQL dump:
- Data gốc nằm trong JavaScript, cần transform sang relational schema
- Script có logic (map category slug, check duplicate, hash password)
- Có thể chạy lại an toàn (idempotent: check trước khi insert)

DATA SOURCE: Toàn bộ data dưới đây copy từ const M={...} trong file HTML gốc
"""

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# WHY dynamic path: "/app" only works in Docker container.
# This makes it work in both Docker AND local dev (python -m scripts.seed)
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from app.config import settings
from app.database import async_session, engine, Base
from app.shared.orm_models import Store  # multi-tenant
from app.catalog.infrastructure.orm_models import (
    Category, Product, ProductSize, Topping, TimeDeal, LayoutType,
)
from app.identity.infrastructure.orm_models import AdminUser
from app.identity.infrastructure.auth import hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed")


# =============================================================================
# Menu Data — 1:1 từ const M gốc
# =============================================================================
# Cấu trúc: {slug: {name, emoji, layout, items: [...]}}
# Mỗi item giữ nguyên field từ JS: id→legacy_id, n→name, d→description, p→price...

CATEGORIES = [
    {"slug": "hot", "name": "Bán Chạy Nhất", "emoji": "🔥", "layout": "grid", "sort": 0},
    {"slug": "combo", "name": "Combo Tiết Kiệm", "emoji": "💰", "layout": "combo", "sort": 1},
    {"slug": "trasua", "name": "Trà Sữa", "emoji": "🧋", "layout": "list", "sort": 2},
    {"slug": "caphe", "name": "Cà Phê · Cacao · Matcha", "emoji": "☕", "layout": "list", "sort": 3},
    {"slug": "tra", "name": "Trà Trái Cây", "emoji": "🍵", "layout": "list", "sort": 4},
    {"slug": "lanh", "name": "Soda · Nước Ép", "emoji": "🫧", "layout": "list", "sort": 5},
    {"slug": "suachua", "name": "Sữa Chua Trái Cây", "emoji": "🥛", "layout": "list", "sort": 6},
    {"slug": "sinhto", "name": "Sinh Tố · Chè · Kem", "emoji": "🥤", "layout": "list", "sort": 7},
    {"slug": "anvat", "name": "Ăn Vặt · Đồ Chiên", "emoji": "🍗", "layout": "list", "sort": 8},
    {"slug": "khac", "name": "Nước Ngọt · Món Khác · Topping", "emoji": "🍮", "layout": "list", "sort": 9},
]

# --- Products per category ---
# Format: (legacy_id, name, desc, base_price, emoji, badge, bg_class, sold_count, is_drink, image_path, sizes, combo_fields)
# sizes: [(label, price), ...]
# combo_fields: (combo_desc, original_price, save_amount) or None

PRODUCTS = {
    "hot": [
        ("h9", "Chân Gà Sốt Thái", "Cay nồng sần sật, sốt Thái đậm đà", 60, "🍗", "hot", "s", 278, False, "images/chan-ga-sot-thai.jpg", [], None),
        ("h10", "Cà Phê Sữa Gấu", "Sữa gấu béo thơm, cà phê đậm", 30, "☕", "best", "c", 189, True, None, [], None),
        ("h11", "Matcha Sữa Gấu", "Matcha đắng dịu, sữa gấu béo ngậy", 30, "🍵", "hot", "k", 156, True, None, [], None),
        ("h3", "Trà Sữa Full Topping", "Đầy đủ topping, béo thơm đậm vị", 25, "🧋", "hot", "d", 456, True, None, [("L", 25)], None),
        ("h8", "Sinh Tố Bơ", "Bơ sáp béo mịn, đá xay mát lạnh", 25, "🥑", "best", "d", 445, True, None, [], None),
        ("h6", "Sữa Chua Trân Châu Đường Đen", "Chua mát, trân châu dẻo thơm đường đen", 25, "🥛", "hot", "y", 312, True, None, [("L", 25)], None),
        ("h4", "Trà Sữa Khoai Môn", "Béo bùi khoai môn, thơm dịu nhẹ", 22, "🧋", "best", "d", 389, True, None, [("L", 22)], None),
        ("h1", "Trà Tắc Mật Ong", "Chua ngọt thanh mát, mật ong thơm", 20, "🍋", "hot", "t", 342, True, None, [("XL", 20)], None),
        ("h2", "Trà Đào", "Đào tươi thơm ngát, ngọt dịu tự nhiên", 20, "🍑", "best", "t", 298, True, None, [("L", 20)], None),
        ("h7", "Cacao Sữa Đá", "Cacao thơm nồng, ngọt béo mịn", 20, "🍫", "best", "k", 267, True, None, [], None),
        ("h12", "Trà Xoài", "Xoài chín thơm ngát, ngọt tự nhiên", 20, "🥭", "hot", "t", 234, True, None, [("L", 20)], None),
        ("h5", "Cà Phê Sữa Đá (phin)", "Phin đậm đà, đắng nhẹ hậu ngọt", 15, "☕", "hot", "c", 521, True, None, [], None),
    ],
    "combo": [
        ("c5", "Combo Team 5 Người", None, 95, "👥🧋", None, "x", 0, True, None, [], ("5 Trà sữa trân châu bất kỳ size L", 110, 15)),
        ("c4", "Combo Ăn Vặt", None, 85, "🍗🍋", None, "x", 0, True, None, [], ("1 Chân gà sốt Thái + 2 Trà tắc mật ong XL", 100, 15)),
        ("c3", "Combo Giải Khát", None, 40, "🥤🍑", None, "x", 0, True, None, [], ("1 Sinh tố bơ + 1 Trà đào size L", 45, 5)),
        ("c1", "Combo Trà Sữa Đôi", None, 40, "🧋🧋", None, "x", 0, True, None, [], ("2 Trà sữa trân châu size L", 44, 4)),
        ("c6", "Combo Trưa Mát", None, 39, "🥛🍧", None, "x", 0, True, None, [], ("1 Sữa chua trân châu ĐĐ + 1 Chè Thái", 45, 6)),
        ("c2", "Combo Văn Phòng", None, 33, "🧋☕", None, "x", 0, True, None, [], ("1 Trà sữa L + 1 Cà phê sữa đá", 37, 4)),
    ],
    "trasua": [
        ("ts17", "Trà Sữa Kem Socola", "Kem socola béo phủ, trà sữa thơm", 22, "🍫", None, "d", 0, True, None, [("M",22),("L",25),("XL",30)], None),
        ("ts18", "Trà Sữa Kem Dừa", "Kem dừa mát lạnh, béo thơm tự nhiên", 22, "🥥", None, "d", 0, True, None, [("M",22),("L",25),("XL",30)], None),
        ("ts19", "Trà Sữa Kem Đậu", "Kem đậu mịn, vị bùi dịu nhẹ", 22, "🧋", None, "d", 0, True, None, [("M",22),("L",25),("XL",30)], None),
        ("ts16", "Sữa Tươi Trân Châu Đường Đen", "Sữa tươi thơm, trân châu dẻo đường đen", 25, "🥛", None, "d", 0, True, None, [], None),
        ("ts1", "Trà Sữa Trân Châu", "Trân châu dẻo dai, vị béo thơm", 20, "🧋", "best", "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts2", "Trà Sữa Thái Xanh", "Đặc trưng Thái Lan, thơm lá dứa", 20, "🧋", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts3", "Trà Sữa Matcha", "Matcha Nhật đắng nhẹ, ngọt dịu", 20, "🍵", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts4", "Trà Sữa Socola", "Socola đậm vị, hòa quyện trà sữa", 20, "🍫", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts5", "Trà Sữa Bánh Flan", "Flan mềm mịn, caramel thơm ngọt", 20, "🍮", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts6", "Trà Sữa Nho", "Nho tím ngọt thanh, thoang mát", 20, "🍇", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts7", "Trà Sữa Dâu", "Dâu tây chua nhẹ, hương ngọt dịu", 20, "🍓", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts8", "Trà Sữa Mật Ong", "Mật ong thơm, vị ngọt ấm tự nhiên", 20, "🍯", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts9", "Trà Sữa Đào", "Đào tươi thơm, hòa quyện trà sữa", 20, "🍑", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts10", "Trà Sữa Vải", "Vải thiều ngọt lịm, mát lạnh", 20, "🫐", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts11", "Trà Sữa Việt Quất", "Việt quất tím thanh, chút chua nhẹ", 20, "🫐", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts12", "Trà Sữa Bạc Hà", "Bạc hà the mát, sảng khoái", 20, "🌿", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts13", "Trà Sữa Măng Cầu", "Măng cầu ngọt thanh, béo nhẹ", 20, "🧋", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts14", "Trà Sữa Vị Cà Phê", "Cà phê nhẹ hòa trà sữa thơm", 20, "☕", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
        ("ts15", "Trà Sữa Dưa Lưới", "Dưa lưới ngọt mát, thanh nhẹ", 20, "🍈", None, "d", 0, True, None, [("M",20),("L",22),("XL",25)], None),
    ],
    "caphe": [
        ("cf14", "Cà Phê Sữa Gấu", "Sữa gấu béo thơm, cà phê phin đậm", 30, "☕", "best", "c", 0, True, None, [], None),
        ("cf15", "Matcha Sữa Gấu", "Matcha Nhật, sữa gấu béo mịn", 30, "🍵", None, "k", 0, True, None, [], None),
        ("cf16", "Cacao Sữa Gấu", "Cacao nguyên chất, sữa gấu thơm", 30, "🍫", None, "k", 0, True, None, [], None),
        ("cf13", "Matcha Latte Kem Muối", "Matcha đắng nhẹ, kem muối béo", 25, "🍵", None, "k", 0, True, None, [], None),
        ("cf10", "Cacao Sữa Kem Muối", "Cacao nồng, kem muối mặn ngọt", 20, "🍫", None, "k", 0, True, None, [], None),
        ("cf11", "Cacao Cà Phê", "Cacao hòa cà phê, đậm đà tỉnh táo", 20, "🍫", None, "k", 0, True, None, [], None),
        ("cf12", "Matcha Latte", "Matcha Nhật mịn, sữa tươi thơm", 20, "🍵", None, "k", 0, True, None, [], None),
        ("cf5", "Bạc Sỉu Đá (máy)", "Nhiều sữa ít cà phê, ngọt nhẹ", 17, "☕", None, "c", 0, True, None, [], None),
        ("cf6", "Bạc Sỉu Đá (phin)", "Phin chậm, nhiều sữa, béo ngọt", 17, "☕", None, "c", 0, True, None, [], None),
        ("cf7", "Cà Phê Muối (máy)", "Kem muối mặn ngọt, cà phê đậm", 17, "☕", None, "c", 0, True, None, [], None),
        ("cf8", "Cà Phê Muối (phin)", "Phin đậm đà, phủ kem muối béo", 17, "☕", None, "c", 0, True, None, [], None),
        ("cf3", "Cà Phê Sữa Đá (máy)", "Pha máy tiện lợi, vị đậm vừa", 15, "☕", None, "c", 0, True, None, [], None),
        ("cf4", "Cà Phê Sữa Đá (phin)", "Phin đậm đà, đắng nhẹ hậu ngọt", 15, "☕", "hot", "c", 0, True, None, [], None),
        ("cf9", "Cacao Sữa Đá", "Cacao thơm nồng, ngọt mát", 15, "🍫", None, "k", 0, True, None, [("M",15),("L",20)], None),
        ("cf1", "Cà Phê Đen Đá (máy)", "Đen đắng, tỉnh táo buổi sáng", 12, "☕", None, "c", 0, True, None, [], None),
        ("cf2", "Cà Phê Đen Đá (phin)", "Phin chậm rãi, đậm vị truyền thống", 15, "☕", None, "c", 0, True, None, [], None),
    ],
    "tra": [
        ("tr1", "Trà Dâu Tây", "Dâu tươi chua ngọt, thơm tự nhiên", 20, "🍓", None, "t", 0, True, None, [("L",20),("XL",25)], None),
        ("tr2", "Trà Măng Cầu", "Măng cầu ngọt thanh, mát lạnh", 20, "🍵", None, "t", 0, True, None, [("L",20),("XL",25)], None),
        ("tr4", "Trà Chanh Mật Ong", "Chanh tươi vắt, mật ong thơm", 20, "🍋", None, "t", 0, True, None, [("L",20),("XL",25)], None),
        ("tr5", "Trà Tắc Xí Muội", "Tắc chua, xí muội mặn ngọt", 20, "🍋", None, "t", 0, True, None, [("L",20),("XL",25)], None),
        ("tr6", "Trà Chanh Xí Muội", "Chanh vàng chua mát, xí muội đậm", 20, "🍋", None, "t", 0, True, None, [("L",20),("XL",25)], None),
        ("tr7", "Trà Vải", "Vải thiều ngọt lịm, thơm nhẹ", 20, "🫐", None, "t", 0, True, None, [("L",20),("XL",25)], None),
        ("tr8", "Trà Me", "Me chua thanh, giải khát cực đã", 20, "🍵", None, "t", 0, True, None, [("L",20),("XL",25)], None),
        ("tr9", "Trà Kiwi", "Kiwi xanh chua nhẹ, vitamin C", 20, "🥝", None, "t", 0, True, None, [("L",20),("XL",25)], None),
        ("tr10", "Trà Việt Quất", "Việt quất tím, chút chát thanh", 20, "🫐", None, "t", 0, True, None, [("L",20),("XL",25)], None),
        ("tr11", "Trà Tắc Thái Xanh", "Tắc Thái chua thanh, xanh mát", 20, "🍵", None, "t", 0, True, None, [("L",20),("XL",25)], None),
        ("tr12", "Hồng Trà Mật Ong", "Hồng trà thơm, mật ong ngọt dịu", 20, "🍯", None, "t", 0, True, None, [("L",20),("XL",25)], None),
        ("tr14", "Hồng Trà Trân Châu Trắng", "Hồng trà đậm, trân châu trắng dẻo", 20, "🧋", None, "t", 0, True, None, [], None),
        ("tr15", "Trà Nho", "Nho tím ngọt, trà thanh mát", 20, "🍇", None, "t", 0, True, None, [("L",20),("XL",25)], None),
        ("tr16", "Trà Chanh Dây", "Chanh dây chua ngọt, hạt giòn", 20, "🍋", None, "t", 0, True, None, [("L",20),("XL",25)], None),
        ("tr17", "Trà Tắc Mật Ong", "Best seller — chua ngọt thanh mát", 20, "🍋", "hot", "t", 0, True, None, [("XL",20)], None),
        ("tr18", "Trà Đào", "Đào tươi thơm ngát, ngọt tự nhiên", 20, "🍑", "best", "t", 0, True, None, [("L",20)], None),
        ("tr19", "Trà Xoài", "Xoài chín mọng, ngọt thơm", 20, "🥭", None, "t", 0, True, None, [("L",20)], None),
        ("tr3", "Trà Bí Đao Hạt Chia", "Bí đao thanh mát, hạt chia bổ dưỡng", 15, "🍵", None, "t", 0, True, None, [], None),
        ("tr13", "Hồng Trà Trân Châu Đen", "Hồng trà ngọt, trân châu đen dẻo", 15, "🧋", None, "t", 0, True, None, [], None),
    ],
    "lanh": [
        ("ne2", "Nước Ép Dứa Tươi", "Dứa thơm, ép nguyên trái mát lạnh", 25, "🍍", None, "j", 0, True, None, [], None),
        ("sd1", "Soda Xoài", "Xoài ngọt, soda sủi tăm mát lạnh", 25, "🥭", None, "o", 0, True, None, [("XL",25)], None),
        ("sd2", "Soda Dâu", "Dâu tây chua nhẹ, sủi bọt sảng khoái", 25, "🍓", None, "o", 0, True, None, [("XL",25)], None),
        ("sd3", "Soda Nho", "Nho ngọt thanh, ga mát lạnh", 25, "🍇", None, "o", 0, True, None, [("XL",25)], None),
        ("sd4", "Soda Đào", "Đào thơm, soda tươi mát", 25, "🍑", None, "o", 0, True, None, [("XL",25)], None),
        ("sd5", "Soda Me", "Me chua thanh, sủi bọt giải nhiệt", 25, "🫧", None, "o", 0, True, None, [("XL",25)], None),
        ("sd6", "Soda Kiwi", "Kiwi xanh, chua nhẹ sảng khoái", 25, "🥝", None, "o", 0, True, None, [("XL",25)], None),
        ("sd7", "Soda Việt Quất", "Việt quất tím, ga mát thanh", 25, "🫐", None, "o", 0, True, None, [("XL",25)], None),
        ("sd8", "Soda Vải", "Vải thiều ngọt, sủi bọt tươi", 25, "🫧", None, "o", 0, True, None, [("XL",25)], None),
        ("sd9", "Soda Măng Cầu", "Măng cầu ngọt dịu, ga mát", 25, "🫧", None, "o", 0, True, None, [("XL",25)], None),
        ("sd10", "Soda Mật Ong", "Mật ong thơm, soda tươi mát", 25, "🍯", None, "o", 0, True, None, [("XL",25)], None),
        ("sd11", "Soda Chanh Dây", "Chanh dây chua ngọt, sủi tăm", 25, "🍋", None, "o", 0, True, None, [("XL",25)], None),
        ("sd13", "Soda Bạc Hà", "Bạc hà the mát, ga sủi sảng khoái", 25, "🌿", None, "o", 0, True, None, [("XL",25)], None),
        ("ne1", "Nước Ép Cà Rốt", "Cà rốt tươi, bổ mắt giàu vitamin", 20, "🥕", None, "j", 0, True, None, [], None),
        ("ne3", "Nước Ép Dứa + Cà Rốt", "Dứa chua ngọt, cà rốt bổ dưỡng", 20, "🍍", None, "j", 0, True, None, [], None),
        ("ne4", "Nước Ép Dứa + Cam", "Dứa cam tươi, vitamin C dồi dào", 20, "🍊", None, "j", 0, True, None, [], None),
        ("ne5", "Nước Ép Cam + Cà Rốt", "Cam vàng ngọt, cà rốt thanh mát", 20, "🍊", None, "j", 0, True, None, [], None),
        ("ne6", "Nước Ép Ổi", "Ổi hồng ngọt, mát lành tự nhiên", 20, "🍈", None, "j", 0, True, None, [], None),
        ("ne7", "Nước Ép Dưa Hấu", "Dưa hấu đỏ, mát lạnh giải nhiệt", 20, "🍉", None, "j", 0, True, None, [], None),
        ("ne8", "Nước Chanh Dây", "Chanh dây tươi, chua ngọt hạt giòn", 20, "🍋", None, "j", 0, True, None, [], None),
        ("ne9", "Nước Cam Vắt", "Cam vắt tay, ngọt tươi tự nhiên", 20, "🍊", None, "j", 0, True, None, [], None),
        ("sd12", "Soda Chanh", "Chanh tươi vắt, soda trong mát", 20, "🍋", None, "o", 0, True, None, [("XL",20)], None),
    ],
    "suachua": [
        ("sc12", "Sữa Chua Trân Châu Đường Đen", "Chua mát, trân châu dẻo đường đen", 25, "🥛", "hot", "y", 0, True, None, [("L",25)], None),
        ("sc1", "Sữa Chua Xoài", "Xoài chín ngọt, sữa chua mát lạnh", 25, "🥭", None, "y", 0, True, None, [("L",25)], None),
        ("sc2", "Sữa Chua Đào", "Đào tươi thơm, chua ngọt hài hòa", 25, "🍑", None, "y", 0, True, None, [("L",25)], None),
        ("sc3", "Sữa Chua Kiwi", "Kiwi xanh chua nhẹ, giàu vitamin", 25, "🥝", None, "y", 0, True, None, [("L",25)], None),
        ("sc4", "Sữa Chua Me", "Me chua thanh, sữa chua mát dịu", 25, "🫧", None, "y", 0, True, None, [("L",25)], None),
        ("sc5", "Sữa Chua Việt Quất", "Việt quất tím thanh, chua nhẹ", 25, "🫐", None, "y", 0, True, None, [("L",25)], None),
        ("sc6", "Sữa Chua Cà Phê", "Cà phê hòa sữa chua, tỉnh táo mát", 25, "☕", None, "y", 0, True, None, [("L",25)], None),
        ("sc7", "Sữa Chua Cacao", "Cacao nồng, sữa chua thanh mát", 25, "🍫", None, "y", 0, True, None, [("L",25)], None),
        ("sc8", "Sữa Chua Matcha", "Matcha Nhật, sữa chua xanh mát", 25, "🍵", None, "y", 0, True, None, [("L",25)], None),
        ("sc9", "Sữa Chua Chanh Dây", "Chanh dây chua ngọt, tươi mát", 25, "🍋", None, "y", 0, True, None, [("L",25)], None),
        ("sc10", "Sữa Chua Măng Cầu", "Măng cầu béo nhẹ, chua dịu", 25, "🫧", None, "y", 0, True, None, [("L",25)], None),
        ("sc11", "Sữa Chua Mật Ong", "Mật ong thơm, sữa chua mịn", 25, "🍯", None, "y", 0, True, None, [("L",25)], None),
    ],
    "sinhto": [
        ("st12", "Sinh Tố Bơ + Kem Dừa", "Bơ sáp phủ kem dừa, béo ngậy", 30, "🥑", None, "d", 0, True, None, [], None),
        ("st13", "Sinh Tố Đậu + Kem Đậu", "Đậu xanh mịn, kem đậu béo bùi", 30, "🫘", None, "d", 0, True, None, [], None),
        ("mk5", "Dưa Dầm Sữa Chua", "Dưa ngọt dầm sữa chua mát lạnh", 30, "🍈", None, "x", 0, True, None, [], None),
        ("mk6", "Bơ Dầm Sữa Chua", "Bơ sáp béo, sữa chua chua ngọt", 30, "🥑", None, "x", 0, True, None, [], None),
        ("mk9", "Măng Cầu Dầm Sữa Chua", "Măng cầu ngọt, sữa chua thanh", 30, "🍈", None, "x", 0, True, None, [], None),
        ("mk10", "Sầu Riêng Dầm Sữa Chua", "Sầu riêng béo ngậy, chua mát", 30, "🍈", None, "x", 0, True, None, [], None),
        ("mk11", "Trái Cây Dầm Thập Cẩm", "Nhiều loại trái cây, sữa chua mát", 30, "🍈", None, "x", 0, True, None, [], None),
        ("st1", "Sinh Tố Bơ", "Bơ sáp béo mịn, đá xay mát lạnh", 25, "🥑", "best", "d", 0, True, None, [], None),
        ("st2", "Sinh Tố Đậu", "Đậu xanh bùi béo, mịn như kem", 25, "🫘", None, "d", 0, True, None, [], None),
        ("st3", "Sinh Tố Sapoche", "Sapoche ngọt thanh, thơm đặc trưng", 25, "🥤", None, "d", 0, True, None, [], None),
        ("st4", "Sinh Tố Măng Cầu", "Măng cầu ngọt béo, mát lạnh", 25, "🥤", None, "d", 0, True, None, [], None),
        ("st5", "Sinh Tố Sầu Riêng", "Sầu riêng đậm, béo ngậy quyến rũ", 25, "🥤", None, "d", 0, True, None, [], None),
        ("st11", "Sinh Tố Sapoche + Kem Socola", "Sapoche ngọt, kem socola béo", 25, "🍫", None, "d", 0, True, None, [], None),
        ("mk7", "Mít Dầm Sữa Chua", "Mít ngọt thơm, sữa chua mát", 25, "🍈", None, "x", 0, True, None, [], None),
        ("mk8", "Sapoche Dầm Sữa Chua", "Sapoche dầm, sữa chua thanh", 25, "🍈", None, "x", 0, True, None, [], None),
        ("ch1", "Chè Thái Sầu Riêng", "Chè Thái ngọt mát, sầu riêng béo", 20, "🍧", None, "w", 0, True, None, [], None),
        ("ch2", "Chè Thái Sầu Riêng Đậu Xanh", "Sầu riêng + đậu xanh bùi", 20, "🍧", None, "w", 0, True, None, [], None),
        ("ch3", "Chè Trái Cây", "Nhiều loại trái cây, nước cốt dừa", 20, "🍧", None, "w", 0, True, None, [], None),
        ("st6", "Sinh Tố Mít", "Mít ngọt thơm, xay mịn mát", 20, "🥤", None, "d", 0, True, None, [], None),
        ("st7", "Sinh Tố Đậu Xanh", "Đậu xanh mịn, vị bùi tự nhiên", 20, "🥤", None, "d", 0, True, None, [], None),
        ("st8", "Sinh Tố Dưa Gang", "Dưa gang thanh mát, nhẹ nhàng", 20, "🍈", None, "d", 0, True, None, [], None),
        ("st9", "Sinh Tố Dừa", "Dừa tươi béo mát, thơm lừng", 20, "🥥", None, "d", 0, True, None, [], None),
        ("st10", "Sinh Tố Thập Cẩm", "Nhiều loại trái cây xay chung", 20, "🥤", None, "d", 0, True, None, [], None),
        ("km4", "Kem 3 Màu", "Dừa + đậu + socola, 3 vị 1 ly", 20, "🍦", None, "w", 0, True, None, [], None),
        ("ch4", "Chè Đậu Thập Cẩm", "Nhiều loại đậu, nước đường mát", 15, "🍧", None, "w", 0, True, None, [], None),
        ("ch5", "Chè Đậu Nếp", "Nếp dẻo thơm, đậu bùi ngọt nhẹ", 15, "🍧", None, "w", 0, True, None, [], None),
        ("ch6", "Chè Đậu Xanh Hạt", "Đậu xanh nguyên hạt, thanh mát", 15, "🍧", None, "w", 0, True, None, [], None),
        ("ch7", "Chè Đậu Đen", "Đậu đen bùi, nước đường thanh", 15, "🍧", None, "w", 0, True, None, [], None),
        ("ch8", "Chè Đậu Đỏ", "Đậu đỏ ngọt bùi, mát lạnh", 15, "🍧", None, "w", 0, True, None, [], None),
        ("km1", "Kem Dừa", "Kem dừa mát lạnh, béo tự nhiên", 15, "🥥", None, "w", 0, True, None, [], None),
        ("km2", "Kem Đậu", "Kem đậu xanh mịn, vị bùi nhẹ", 15, "🫘", None, "w", 0, True, None, [], None),
        ("km3", "Kem Socola", "Kem socola đậm, ngọt mát", 15, "🍫", None, "w", 0, True, None, [], None),
    ],
    "anvat": [
        ("av1", "Chân Gà Sốt Thái", "Cay nồng sần sật, sốt Thái đậm đà", 60, "🍗", "hot", "s", 0, False, "images/chan-ga-sot-thai.jpg", [], None),
        ("av4", "Chân Gà Ngâm Sả Tắc", "Giòn dai, sả tắc thơm chua nhẹ", 40, "🍗", None, "s", 0, False, None, [], None),
        ("dc4", "Khoai Tây Chiên Lắc Phô Mai", "Giòn rụm phủ phô mai thơm béo", 20, "🍟", None, "s", 0, False, None, [], None),
        ("av6", "Bánh Đa Trộn Sốt Me", "Bánh đa giòn, sốt me chua ngọt", 20, "🥟", None, "s", 0, False, None, [], None),
        ("av2", "Bánh Tráng Trộn", "Bánh tráng giòn, đủ vị mặn ngọt", 15, "🥟", None, "s", 0, False, None, [], None),
        ("av3", "Xoài Lắc", "Xoài xanh giòn, muối ớt cay nhẹ", 15, "🥭", None, "s", 0, False, None, [], None),
        ("av5", "Bánh Tráng Cuốn", "Cuốn tươi mát, chấm mắm ngọt", 15, "🥟", None, "s", 0, False, None, [], None),
        ("dc2", "Bò Viên Chiên (9 viên)", "Bò viên giòn ngoài, mềm dai trong", 15, "🍡", None, "s", 0, False, None, [], None),
        ("dc3", "Cá Viên Chiên (12 viên)", "Cá viên giòn tan, nóng thơm", 15, "🍡", None, "s", 0, False, None, [], None),
        ("dc5", "Trứng Cút Chiên (10 viên)", "Trứng cút giòn vàng, chấm tương ớt", 15, "🥚", None, "s", 0, False, None, [], None),
        ("dc1", "Xúc Xích Đức Chiên", "Xúc xích nóng giòn, đậm vị", 12, "🌭", None, "s", 0, False, None, [], None),
    ],
    "khac": [
        ("mk4", "Cocktail Trái Cây", "Nhiều loại trái cây, thạch dừa mát", 20, "🍹", None, "x", 0, True, None, [], None),
        ("mk2", "Đá Me", "Me chua ngọt, đá bào mát lạnh", 17, "🍧", None, "x", 0, True, None, [], None),
        ("nn5", "Bò Húc", "Tăng lực, tỉnh táo nhanh", 17, "🐂", None, "n", 0, False, None, [], None),
        ("mk1", "Bánh Flan (2 cái)", "Flan mềm mịn, caramel thơm ngọt", 15, "🍮", None, "x", 0, False, None, [], None),
        ("mk3", "Sữa Chua Đá", "Sữa chua đá bào, chua ngọt mát", 15, "🥛", None, "x", 0, True, None, [], None),
        ("nn1", "Sting", "Dâu tây sảng khoái", 15, "🥤", None, "n", 0, False, None, [], None),
        ("nn2", "C2", "Trà xanh nhẹ nhàng", 15, "🥤", None, "n", 0, False, None, [], None),
        ("nn3", "Pepsi", "Cola mát lạnh", 15, "🥤", None, "n", 0, False, None, [], None),
        ("nn4", "Ô Long", "Trà Ô Long thanh mát", 15, "🍵", None, "n", 0, False, None, [], None),
        ("nn6", "Cà Phê 247", "Cà phê đóng lon tiện lợi", 15, "☕", None, "n", 0, False, None, [], None),
        ("nn7", "7 Up Vị Chanh", "Chanh ga mát lạnh", 15, "🍋", None, "n", 0, False, None, [], None),
        ("tp1", "+ Trân Châu Đen", "Dẻo dai, ngọt đường đen", 5, "⚫", None, "x", 0, False, None, [], None),
        ("tp2", "+ Trân Châu Trắng", "Trắng mịn, dẻo thơm", 5, "⚪", None, "x", 0, False, None, [], None),
        ("tp3", "+ Pudding Socola", "Mềm mịn, ngọt socola", 5, "🍫", None, "x", 0, False, None, [], None),
        ("tp4", "+ Thạch Dừa", "Dai giòn, vị dừa nhẹ", 5, "🥥", None, "x", 0, False, None, [], None),
        ("tp5", "+ Thạch Cà Phê", "Thơm cà phê, giòn dai", 5, "☕", None, "x", 0, False, None, [], None),
        ("tp6", "+ Bánh Flan Trứng", "Flan mềm, caramel ngọt", 5, "🍮", None, "x", 0, False, None, [], None),
        ("tp7", "+ Kem Muối", "Mặn ngọt béo, phủ lên trên", 5, "🧂", None, "x", 0, False, None, [], None),
        ("tp8", "+ Khúc Bạch", "Dẻo thơm, ngọt nhẹ", 5, "⬜", None, "x", 0, False, None, [], None),
    ],
}

TOPPINGS_DATA = [
    ("tp1", "Trân Châu Đen", "⚫", 5),
    ("tp2", "Trân Châu Trắng", "⚪", 5),
    ("tp3", "Pudding Socola", "🍫", 5),
    ("tp4", "Thạch Dừa", "🥥", 5),
    ("tp5", "Thạch Cà Phê", "☕", 5),
    ("tp6", "Flan Trứng", "🍮", 5),
    ("tp7", "Kem Muối", "🧂", 5),
    ("tp8", "Khúc Bạch", "⬜", 5),
]

TIME_DEALS_DATA = [
    ("⚡ Deal buổi sáng", "Combo Sáng Tỉnh Táo — Giảm 10%", "Giao tận bàn • Pha chế tươi", 6, 10, 10),
    ("⚡ Deal buổi trưa", "Combo Trưa Tiết Kiệm — Giảm đến 20%", "Giao tận bàn • Pha chế tươi mỗi đơn", 10, 14, 20),
    ("⚡ Deal chiều", "Combo Xế Chiều — Mua 2 Giảm 15%", "Giải khát buổi chiều", 14, 17, 15),
]


# =============================================================================
# Seed Runner
# =============================================================================
async def seed_all(reset: bool = False):
    async with async_session() as db:
        # Check if already seeded
        existing = (await db.execute(select(Category))).scalars().first()
        if existing and not reset:
            logger.info("⏭️  Data already exists. Use --reset to re-seed.")
            return

        if reset:
            logger.info("🗑️  Clearing existing data...")
            await db.execute(ProductSize.__table__.delete())
            await db.execute(Product.__table__.delete())
            await db.execute(Category.__table__.delete())
            await db.execute(Topping.__table__.delete())
            await db.execute(TimeDeal.__table__.delete())
            await db.execute(AdminUser.__table__.delete())
            await db.commit()

        # --- Store (v3: SaaS foundation) ---
        logger.info("🏪 Seeding default store...")
        existing_store = (await db.execute(select(Store).where(Store.id == 1))).scalars().first()
        if not existing_store:
            db.add(Store(id=1, slug="default", name="Ngon-Ngon", phone="0378148148"))
            await db.flush()
            logger.info("   ✅ Default store created")
        else:
            logger.info("   ✅ Default store already exists")

        # --- Categories ---
        logger.info("📁 Seeding categories...")
        cat_map = {}  # slug → Category object
        for cat_data in CATEGORIES:
            cat = Category(
                slug=cat_data["slug"],
                name=cat_data["name"],
                emoji=cat_data["emoji"],
                layout=LayoutType(cat_data["layout"]),
                sort_order=cat_data["sort"],
            )
            db.add(cat)
            await db.flush()  # Get cat.id
            cat_map[cat_data["slug"]] = cat
        logger.info(f"   ✅ {len(cat_map)} categories")

        # --- Products ---
        logger.info("🍹 Seeding products...")
        total_products = 0
        total_sizes = 0
        for cat_slug, items in PRODUCTS.items():
            category = cat_map[cat_slug]
            for idx, item in enumerate(items):
                (lid, name, desc, price, emoji, badge, bg, sold, is_drink, img, sizes, combo) = item
                product = Product(
                    legacy_id=lid,
                    category_id=category.id,
                    name=name,
                    description=desc,
                    base_price=price,
                    emoji=emoji,
                    image_path=img,
                    badge=badge,
                    bg_class=bg,
                    sold_count=sold,
                    is_drink=is_drink,
                    sort_order=idx,
                    is_combo=combo is not None,
                    combo_description=combo[0] if combo else None,
                    original_price=combo[1] if combo else None,
                    save_amount=combo[2] if combo else None,
                )
                db.add(product)
                await db.flush()

                # Sizes
                for label, sz_price in sizes:
                    db.add(ProductSize(product_id=product.id, label=label, price=sz_price))
                    total_sizes += 1

                total_products += 1
        logger.info(f"   ✅ {total_products} products, {total_sizes} sizes")

        # --- Toppings ---
        logger.info("🧁 Seeding toppings...")
        for lid, name, emoji, price in TOPPINGS_DATA:
            db.add(Topping(legacy_id=lid, name=name, emoji=emoji, price=price))
        logger.info(f"   ✅ {len(TOPPINGS_DATA)} toppings")

        # --- Time Deals ---
        logger.info("⏰ Seeding time deals...")
        for label, title, subtitle, start, end, discount in TIME_DEALS_DATA:
            db.add(TimeDeal(
                label=label, title=title, subtitle=subtitle,
                start_hour=start, end_hour=end, discount_percent=discount,
            ))
        logger.info(f"   ✅ {len(TIME_DEALS_DATA)} time deals")

        # --- Admin User ---
        logger.info("🔐 Seeding admin user...")
        db.add(AdminUser(
            username=settings.ADMIN_USERNAME,
            hashed_password=hash_password(settings.ADMIN_PASSWORD),
        ))
        logger.info(f"   ✅ Admin: {settings.ADMIN_USERNAME}")

        await db.commit()
        logger.info("🎉 Seed complete!")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    asyncio.run(seed_all(reset=reset))
