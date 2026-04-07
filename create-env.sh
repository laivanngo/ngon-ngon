#!/bin/bash
# =============================================================================
# Tạo file .env trên VPS (chạy 1 lần sau khi git clone)
# =============================================================================
set -e

if [ -f .env ]; then
    echo "⚠️  File .env đã tồn tại. Xóa và tạo lại? (y/n)"
    read -r answer
    if [ "$answer" != "y" ]; then
        echo "Đã hủy."
        exit 0
    fi
fi

# Generate secure secrets
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))" 2>/dev/null || openssl rand -base64 48)
DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))" 2>/dev/null || openssl rand -base64 24)
ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))" 2>/dev/null || openssl rand -base64 16)

cat > .env << ENVFILE
# Ngon-Ngon Production Environment
# Tạo bởi create-env.sh lúc $(date)

DB_NAME=ngonngon
DB_USER=ngonngon
DB_PASSWORD=${DB_PASSWORD}

JWT_SECRET=${JWT_SECRET}

ALLOWED_ORIGINS=https://ngon-ngon.com,https://www.ngon-ngon.com

ENV=production

ADMIN_USERNAME=admin
ADMIN_PASSWORD=${ADMIN_PASSWORD}

KDS_PIN=2026

DEFAULT_STORE_ID=1
ENVFILE

echo "✅ File .env đã tạo thành công!"
echo "   Admin password:    ${ADMIN_PASSWORD}"
echo "   Database password: ${DB_PASSWORD}"
echo "   JWT Secret:        ${JWT_SECRET}"
echo ""
echo "⚠️  LƯU LẠI thông tin trên ở nơi an toàn!"
echo "   Tiếp theo chạy: docker compose up -d"
