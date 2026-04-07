#!/bin/bash
# =============================================================================
# Ngon-Ngon — Cài SSL Certificate (chạy 1 lần sau khi hệ thống đã chạy HTTP)
# =============================================================================
# Yêu cầu: docker compose up -d đã chạy thành công trên HTTP
# Chạy:    chmod +x init-ssl.sh && ./init-ssl.sh
#
# Tùy chọn:
#   --force    Ép gia hạn cert (dùng khi cert sắp hết hạn)
# =============================================================================

set -euo pipefail

# Cấu hình — có thể override qua biến môi trường
DOMAIN="${SSL_DOMAIN:-ngon-ngon.com}"
EMAIL="${SSL_EMAIL:-laivanngo@gmail.com}"

# Parse flags
FORCE_FLAG=""
for arg in "$@"; do
    case $arg in
        --force) FORCE_FLAG="--force-renewal" ;;
        *) echo "Flag không hợp lệ: $arg"; exit 1 ;;
    esac
done

echo "=============================================="
echo " Cài đặt SSL cho ${DOMAIN}"
echo "=============================================="
echo ""

# --- 1. Kiểm tra nginx đã chạy ---
echo "[1/4] Kiểm tra nginx..."
if ! docker compose ps nginx 2>/dev/null | grep -q "running"; then
    echo "  LỖI: Nginx chưa chạy."
    echo "  Hãy chạy 'docker compose up -d' trước."
    exit 1
fi
echo "  OK - Nginx đang chạy"

# --- 2. Kiểm tra domain trỏ đúng IP ---
echo "[2/4] Kiểm tra DNS..."
SERVER_IP=$(curl -sf https://ifconfig.me || curl -sf https://ipinfo.io/ip || echo "unknown")
DOMAIN_IP=$(dig +short "$DOMAIN" 2>/dev/null | tail -1)

if [ "$SERVER_IP" != "unknown" ] && [ -n "$DOMAIN_IP" ] && [ "$SERVER_IP" != "$DOMAIN_IP" ]; then
    echo "  CẢNH BÁO: Domain $DOMAIN trỏ đến $DOMAIN_IP"
    echo "             nhưng IP server là $SERVER_IP"
    echo "  Let's Encrypt sẽ thất bại nếu DNS chưa trỏ đúng!"
    echo ""
    read -rp "  Tiếp tục? (y/n): " answer
    if [ "$answer" != "y" ]; then
        echo "  Đã hủy."
        exit 0
    fi
else
    echo "  OK - DNS đã kiểm tra (Server IP: $SERVER_IP)"
fi

# --- 3. Lấy SSL cert ---
echo "[3/4] Lấy SSL certificate từ Let's Encrypt..."
if docker compose run --rm certbot certonly \
    --webroot \
    -w /var/www/certbot \
    -d "$DOMAIN" \
    -d "www.$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive \
    $FORCE_FLAG; then
    echo "  OK - Certificate đã lấy thành công"
else
    echo "  LỖI: Không lấy được certificate!"
    echo ""
    echo "  Kiểm tra:"
    echo "    1. Domain $DOMAIN đã trỏ đúng IP server chưa?"
    echo "    2. Port 80 đã mở trong firewall chưa?"
    echo "    3. Nginx đã serve /.well-known/acme-challenge/ chưa?"
    echo ""
    echo "  Thử debug: curl -I http://$DOMAIN/.well-known/acme-challenge/test"
    exit 1
fi

# --- 4. Verify cert + restart nginx ---
echo "[4/4] Verify và khởi động lại nginx..."

# Kiểm tra cert file tồn tại
CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
if ! docker compose run --rm certbot sh -c "test -f $CERT_PATH"; then
    echo "  LỖI: Cert file không tồn tại tại $CERT_PATH"
    exit 1
fi

# Restart nginx để load cert mới
docker compose restart nginx

# Verify HTTPS hoạt động (đợi nginx khởi động)
sleep 3
if curl -sf "https://$DOMAIN" > /dev/null 2>&1; then
    echo "  OK - HTTPS đã hoạt động"
else
    echo "  CẢNH BÁO: Không thể verify HTTPS (có thể do DNS propagation)"
    echo "  Thử thủ công: curl -I https://$DOMAIN"
fi

# Bật certbot auto-renewal
echo ""
echo "Bật auto-renewal SSL..."
docker compose --profile ssl up -d certbot
echo "  OK - Certbot sẽ tự gia hạn mỗi 12 giờ"

echo ""
echo "=============================================="
echo " SSL ĐÃ CÀI ĐẶT THÀNH CÔNG!"
echo "=============================================="
echo ""
echo "  https://$DOMAIN      — sẵn sàng"
echo "  https://www.$DOMAIN  — sẵn sàng"
echo ""
echo "  Cert sẽ tự động gia hạn qua certbot container."
echo "  Gia hạn thủ công: ./init-ssl.sh --force"
