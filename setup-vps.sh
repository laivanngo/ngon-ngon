#!/bin/bash
# =============================================================================
# Ngon-Ngon — Script cài đặt VPS production-grade
# =============================================================================
# Chạy 1 lần duy nhất trên VPS mới (với quyền root):
#   chmod +x setup-vps.sh && ./setup-vps.sh
#
# Flags:
#   --skip-ssh-hardening   Bỏ qua bước harden SSH (dùng khi chạy lại)
#   --skip-user-creation   Bỏ qua bước tạo user (dùng khi chạy lại)
# =============================================================================

set -euo pipefail

# ========================= CẤU HÌNH =========================
DEPLOY_USER="deploy"
SSH_PORT=2222
PROJECT_DIR="/opt/ngonngon"
TIMEZONE="Asia/Ho_Chi_Minh"
# =============================================================

# --- Parse flags ---
SKIP_SSH=false
SKIP_USER=false
for arg in "$@"; do
    case $arg in
        --skip-ssh-hardening) SKIP_SSH=true ;;
        --skip-user-creation) SKIP_USER=true ;;
        *) echo "Flag không hợp lệ: $arg"; exit 1 ;;
    esac
done

# --- Kiểm tra quyền root ---
if [ "$(id -u)" -ne 0 ]; then
    echo "Script này cần chạy với quyền root (sudo)."
    exit 1
fi

echo "=========================================="
echo " Ngon-Ngon — Cài đặt VPS Production"
echo "=========================================="
echo ""

# =============================================================================
# PHASE 1: BẢO MẬT
# =============================================================================

# --- 1. Cập nhật hệ thống ---
setup_system_update() {
    echo "[1/15] Cập nhật hệ thống..."
    apt-get update -qq
    apt-get upgrade -y -qq
    echo "  OK - Hệ thống đã cập nhật"
}

# --- 2. Tạo user deploy (không dùng root) ---
setup_user() {
    echo "[2/15] Tạo user deploy..."
    if $SKIP_USER; then
        echo "  SKIP - Bỏ qua (--skip-user-creation)"
        return 0
    fi

    if id "$DEPLOY_USER" &>/dev/null; then
        echo "  OK - User '$DEPLOY_USER' đã tồn tại"
    else
        useradd -m -s /bin/bash -G sudo "$DEPLOY_USER"
        echo "  OK - User '$DEPLOY_USER' đã tạo"
    fi

    # Copy SSH key từ root sang deploy user
    local deploy_home="/home/$DEPLOY_USER"
    if [ -f /root/.ssh/authorized_keys ]; then
        mkdir -p "$deploy_home/.ssh"
        cp /root/.ssh/authorized_keys "$deploy_home/.ssh/authorized_keys"
        chown -R "$DEPLOY_USER:$DEPLOY_USER" "$deploy_home/.ssh"
        chmod 700 "$deploy_home/.ssh"
        chmod 600 "$deploy_home/.ssh/authorized_keys"
        echo "  OK - SSH key đã copy sang user '$DEPLOY_USER'"
    else
        echo "  CẢNH BÁO: Không tìm thấy /root/.ssh/authorized_keys"
        echo "  Bạn cần tự thêm SSH key cho user '$DEPLOY_USER' trước khi harden SSH!"
    fi
}

# --- 3. Harden SSH ---
setup_ssh_hardening() {
    echo "[3/15] Harden SSH..."
    if $SKIP_SSH; then
        echo "  SKIP - Bỏ qua (--skip-ssh-hardening)"
        return 0
    fi

    local sshd_config="/etc/ssh/sshd_config"

    # Backup config gốc (chỉ backup 1 lần)
    if [ ! -f "${sshd_config}.original" ]; then
        cp "$sshd_config" "${sshd_config}.original"
        echo "  OK - Đã backup sshd_config gốc"
    fi

    # Tạo drop-in config cho hardening (idempotent)
    mkdir -p /etc/ssh/sshd_config.d
    cat > /etc/ssh/sshd_config.d/99-ngonngon-hardening.conf << 'SSHEOF'
# Ngon-Ngon SSH Hardening
Port 2222
PermitRootLogin no
PasswordAuthentication no
PermitEmptyPasswords no
MaxAuthTries 3
LoginGraceTime 20
ClientAliveInterval 300
ClientAliveCountMax 2
X11Forwarding no
AllowAgentForwarding no
SSHEOF

    # (Đoạn này nằm ngay dưới dòng SSHEOF của bạn)

    # Đảm bảo Include directive tồn tại trong sshd_config
    # THAY ĐỔI 1: Comment lại 3 dòng dưới đây
    # if ! grep -q "^Include /etc/ssh/sshd_config.d/\*.conf" "$sshd_config"; then
    #     echo "Include /etc/ssh/sshd_config.d/*.conf" >> "$sshd_config"
    # fi

    # Validate config trước khi restart
    if sshd -t 2>/dev/null; then
        systemctl restart ssh
        echo "  OK - SSH đã harden (port $SSH_PORT, no root, no password)"
    else
        echo "  LỖI: sshd config không hợp lệ! Kiểm tra lại."
        echo "  Khôi phục từ: ${sshd_config}.original"
        cp "${sshd_config}.original" "$sshd_config"  # THAY ĐỔI 2: THÊM DÒNG NÀY VÀO ĐÂY
        exit 1
    fi

    echo ""
    echo "  ╔══════════════════════════════════════════════════════════╗"
    echo "  ║  QUAN TRỌNG: Mở terminal MỚI và thử SSH trước khi     ║"
    echo "  ║  đóng terminal này!                                     ║"
    echo "  ║                                                          ║"
    echo "  ║  ssh -p $SSH_PORT $DEPLOY_USER@<IP_VPS>                 ║"
    echo "  ╚══════════════════════════════════════════════════════════╝"
    echo ""
}

# --- 4. Cài fail2ban ---
setup_fail2ban() {
    echo "[4/15] Cài đặt fail2ban..."
    if command -v fail2ban-client &>/dev/null; then
        echo "  OK - fail2ban đã có sẵn"
    else
        apt-get install -y -qq fail2ban
        echo "  OK - fail2ban đã cài"
    fi

    # Cấu hình jail (idempotent - ghi đè file)
    cat > /etc/fail2ban/jail.local << JAILEOF
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 3
backend  = systemd

[sshd]
enabled = true
port    = $SSH_PORT
filter  = sshd
logpath = /var/log/auth.log
JAILEOF

    systemctl enable fail2ban
    systemctl restart fail2ban
    echo "  OK - fail2ban đã cấu hình (ban 1h sau 3 lần sai, port $SSH_PORT)"
}

# --- 5. Cấu hình firewall ---
setup_firewall() {
    echo "[5/15] Cấu hình firewall..."
    if ! command -v ufw &>/dev/null; then
        apt-get install -y -qq ufw
    fi

    ufw default deny incoming
    ufw default allow outgoing
    ufw limit "$SSH_PORT/tcp"    # Rate limit SSH
    ufw allow 80/tcp             # HTTP (Let's Encrypt ACME)
    ufw allow 443/tcp            # HTTPS
    ufw --force enable
    echo "  OK - Firewall: deny all, allow SSH(rate-limited)/$SSH_PORT + HTTP/80 + HTTPS/443"
}

# --- 6. Bật auto security updates ---
setup_auto_updates() {
    echo "[6/15] Bật auto security updates..."
    apt-get install -y -qq unattended-upgrades apt-listchanges

    # Cấu hình chỉ update security patches (idempotent - ghi đè file)
    cat > /etc/apt/apt.conf.d/20auto-upgrades << 'AUTOEOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
AUTOEOF

    cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'UAEOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
UAEOF

    systemctl enable unattended-upgrades
    echo "  OK - Auto security updates (reboot lúc 4:00 AM nếu cần)"
}

# =============================================================================
# PHASE 2: CẤU HÌNH HỆ THỐNG
# =============================================================================

# --- 7. Timezone & locale ---
setup_timezone() {
    echo "[7/15] Cấu hình timezone & locale..."
    timedatectl set-timezone "$TIMEZONE"
    # Đảm bảo locale UTF-8
    if ! locale -a 2>/dev/null | grep -q "en_US.utf8"; then
        apt-get install -y -qq locales
        locale-gen en_US.UTF-8
    fi
    update-locale LANG=en_US.UTF-8
    echo "  OK - Timezone: $TIMEZONE, Locale: en_US.UTF-8"
}

# --- 8. Swap + Kernel hardening ---
setup_swap_and_sysctl() {
    echo "[8/15] Cấu hình swap & kernel hardening..."

    # Swap 1GB (cho VPS 1GB RAM)
    if [ ! -f /swapfile ]; then
        fallocate -l 1G /swapfile
        chmod 600 /swapfile
        mkswap /swapfile
        swapon /swapfile
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
        echo "  OK - Swap 1GB đã tạo"
    else
        echo "  OK - Swap đã có sẵn"
    fi

    # Kernel hardening qua drop-in file (idempotent - ghi đè, không append)
    cat > /etc/sysctl.d/99-ngonngon.conf << 'SYSEOF'
# === Swap optimization ===
vm.swappiness=10
vm.vfs_cache_pressure=50

# === Network hardening ===
# Chống SYN flood
net.ipv4.tcp_syncookies=1
# Reverse path filtering (chống IP spoofing)
net.ipv4.conf.all.rp_filter=1
net.ipv4.conf.default.rp_filter=1
# Không nhận ICMP redirects (chống MITM)
net.ipv4.conf.all.accept_redirects=0
net.ipv4.conf.default.accept_redirects=0
net.ipv4.conf.all.send_redirects=0
net.ipv4.conf.default.send_redirects=0
# Ignore broadcast ICMP (chống smurf attack)
net.ipv4.icmp_echo_ignore_broadcasts=1
SYSEOF

    sysctl --system > /dev/null 2>&1
    echo "  OK - Kernel hardening đã áp dụng"
}

# --- 9. Giới hạn journald ---
setup_journald() {
    echo "[9/15] Giới hạn journald log..."
    mkdir -p /etc/systemd/journald.conf.d
    cat > /etc/systemd/journald.conf.d/size.conf << 'JEOF'
[Journal]
SystemMaxUse=50M
JEOF
    systemctl restart systemd-journald 2>/dev/null || true
    echo "  OK - Journald giới hạn 50MB"
}

# =============================================================================
# PHASE 3: CÀI ĐẶT ỨNG DỤNG
# =============================================================================

# --- 10. Docker qua official apt repo ---
install_docker() {
    echo "[10/15] Cài đặt Docker..."
    if command -v docker &>/dev/null; then
        echo "  OK - Docker đã có sẵn ($(docker --version | cut -d' ' -f3 | tr -d ','))"
    else
        # Cài prerequisites
        apt-get install -y -qq ca-certificates curl gnupg

        # Thêm Docker GPG key
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
            gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg

        # Thêm Docker apt repo
        echo \
            "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
            https://download.docker.com/linux/ubuntu \
            $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
            tee /etc/apt/sources.list.d/docker.list > /dev/null

        # Cài Docker
        apt-get update -qq
        apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
            docker-buildx-plugin docker-compose-plugin

        systemctl enable docker
        systemctl start docker
        echo "  OK - Docker đã cài (official apt repo)"
    fi

    # Thêm deploy user vào docker group
    if id "$DEPLOY_USER" &>/dev/null; then
        usermod -aG docker "$DEPLOY_USER"
        echo "  OK - User '$DEPLOY_USER' đã thêm vào group docker"
    fi
}

# --- 11. Cài Git ---
install_git() {
    echo "[11/15] Cài đặt Git..."
    if command -v git &>/dev/null; then
        echo "  OK - Git đã có sẵn"
    else
        apt-get install -y -qq git
        echo "  OK - Git đã cài"
    fi
}

# --- 12. Tạo project structure ---
setup_project_structure() {
    echo "[12/15] Tạo project structure..."
    mkdir -p "$PROJECT_DIR"/{backups,logs,scripts}

    # Ownership cho deploy user
    if id "$DEPLOY_USER" &>/dev/null; then
        chown -R "$DEPLOY_USER:$DEPLOY_USER" "$PROJECT_DIR"
        chmod 750 "$PROJECT_DIR"
        chmod 700 "$PROJECT_DIR/backups"
    fi
    echo "  OK - $PROJECT_DIR (owned by $DEPLOY_USER)"
}

# =============================================================================
# PHASE 4: DEPLOYMENT & OPERATIONS
# =============================================================================

# --- 13. Deploy script với rollback + health check ---
setup_deploy_script() {
    echo "[13/15] Tạo deploy script..."
    cat > "$PROJECT_DIR/scripts/deploy.sh" << 'DPEOF'
#!/bin/bash
# =============================================================================
# Auto-deploy với rollback và health check
# =============================================================================
set -euo pipefail

PROJECT_DIR="/opt/ngonngon"
LOG_FILE="$PROJECT_DIR/logs/deploy.log"
HEALTH_URL="http://localhost/api/v1/health"
HEALTH_TIMEOUT=60

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"; }

cd "$PROJECT_DIR"

# Lưu commit hiện tại để rollback
PREV_COMMIT=$(git rev-parse HEAD)
log "=== BẮT ĐẦU DEPLOY ==="
log "Commit hiện tại: $PREV_COMMIT"

# Pull code mới
if ! git pull origin main; then
    log "LỖI: git pull thất bại"
    exit 1
fi

NEW_COMMIT=$(git rev-parse HEAD)
log "Commit mới: $NEW_COMMIT"

if [ "$PREV_COMMIT" = "$NEW_COMMIT" ]; then
    log "Không có thay đổi. Bỏ qua deploy."
    exit 0
fi

# Build trước (không stop containers cũ)
log "Building images..."
if ! docker compose build; then
    log "LỖI: Build thất bại. Rollback code..."
    git checkout "$PREV_COMMIT"
    exit 1
fi

# Restart containers
log "Khởi động lại containers..."
docker compose up -d --remove-orphans

# Health check
log "Kiểm tra health (tối đa ${HEALTH_TIMEOUT}s)..."
for i in $(seq 1 $((HEALTH_TIMEOUT / 2))); do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        log "THÀNH CÔNG: Deploy hoàn tất (health check OK sau $((i * 2))s)"
        exit 0
    fi
    sleep 2
done

# Health check thất bại -> rollback
log "LỖI: Health check thất bại sau ${HEALTH_TIMEOUT}s"
log "Rollback về commit: $PREV_COMMIT"
git checkout "$PREV_COMMIT"
docker compose up -d --build
log "Rollback hoàn tất"
exit 1
DPEOF
    chmod +x "$PROJECT_DIR/scripts/deploy.sh"

    # Symlink cho tiện dùng
    ln -sf "$PROJECT_DIR/scripts/deploy.sh" "$PROJECT_DIR/deploy.sh"
    echo "  OK - deploy.sh với rollback + health check"
}

# --- 14. Backup script với verification ---
setup_backup_script() {
    echo "[14/15] Tạo backup script..."
    cat > "$PROJECT_DIR/scripts/backup-db.sh" << 'BKEOF'
#!/bin/bash
# =============================================================================
# Backup PostgreSQL với verification
# =============================================================================
set -uo pipefail

PROJECT_DIR="/opt/ngonngon"
BACKUP_DIR="$PROJECT_DIR/backups"
LOG_FILE="$PROJECT_DIR/logs/backup.log"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DAY_OF_WEEK=$(date +%u)
DAY_OF_MONTH=$(date +%d)
BACKUP_FILE="$BACKUP_DIR/ngonngon_${TIMESTAMP}.sql.gz"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"; }

cd "$PROJECT_DIR"

log "=== BẮT ĐẦU BACKUP ==="

# Thực hiện backup
if ! docker compose exec -T db pg_dump -U ngonngon ngonngon | gzip > "$BACKUP_FILE"; then
    log "LỖI: pg_dump thất bại"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Verify: file không rỗng
if [ ! -s "$BACKUP_FILE" ]; then
    log "LỖI: File backup rỗng"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Verify: gzip integrity
if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
    log "LỖI: File backup bị corrupt"
    rm -f "$BACKUP_FILE"
    exit 1
fi

FILESIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "THÀNH CÔNG: $BACKUP_FILE ($FILESIZE)"

# === Rotation ===
# Giữ weekly backup (mỗi Chủ nhật) - giữ 4 tuần
if [ "$DAY_OF_WEEK" = "7" ]; then
    cp "$BACKUP_FILE" "$BACKUP_DIR/weekly_ngonngon_${TIMESTAMP}.sql.gz"
    log "  + Weekly backup đã tạo"
fi

# Giữ monthly backup (ngày 1 mỗi tháng) - giữ 2 tháng
if [ "$DAY_OF_MONTH" = "01" ]; then
    cp "$BACKUP_FILE" "$BACKUP_DIR/monthly_ngonngon_${TIMESTAMP}.sql.gz"
    log "  + Monthly backup đã tạo"
fi

# Xóa daily cũ hơn 7 ngày (không xóa weekly/monthly)
find "$BACKUP_DIR" -name "ngonngon_*.sql.gz" -mtime +7 -delete
# Xóa weekly cũ hơn 28 ngày
find "$BACKUP_DIR" -name "weekly_*.sql.gz" -mtime +28 -delete
# Xóa monthly cũ hơn 60 ngày
find "$BACKUP_DIR" -name "monthly_*.sql.gz" -mtime +60 -delete

log "=== BACKUP HOÀN TẤT ==="
BKEOF
    chmod +x "$PROJECT_DIR/scripts/backup-db.sh"

    # Symlink cho tiện dùng
    ln -sf "$PROJECT_DIR/scripts/backup-db.sh" "$PROJECT_DIR/backup-db.sh"
    echo "  OK - backup-db.sh với verification + rotation (7 daily, 4 weekly, 2 monthly)"
}

# --- 15. Cron jobs (file-based, idempotent) ---
setup_cron() {
    echo "[15/15] Cấu hình cron jobs..."
    cat > /etc/cron.d/ngonngon << CRONEOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Backup database lúc 3:00 AM mỗi ngày
0 3 * * * $DEPLOY_USER $PROJECT_DIR/scripts/backup-db.sh >> $PROJECT_DIR/logs/backup.log 2>&1
CRONEOF
    chmod 644 /etc/cron.d/ngonngon
    echo "  OK - Cron: backup lúc 3:00 AM (file-based, idempotent)"
}

# =============================================================================
# MAIN: Chạy từng phase theo thứ tự
# =============================================================================

setup_system_update
setup_user
setup_ssh_hardening
setup_fail2ban
setup_firewall
setup_auto_updates
setup_timezone
setup_swap_and_sysctl
setup_journald
install_docker
install_git
setup_project_structure
setup_deploy_script
setup_backup_script
setup_cron

# Đảm bảo ownership sau tất cả
if id "$DEPLOY_USER" &>/dev/null; then
    chown -R "$DEPLOY_USER:$DEPLOY_USER" "$PROJECT_DIR"
fi

echo ""
echo "=============================================="
echo " CÀI ĐẶT VPS HOÀN TẤT!"
echo "=============================================="
echo ""
echo "Thông tin quan trọng:"
echo "  - SSH port:  $SSH_PORT"
echo "  - User:      $DEPLOY_USER"
echo "  - Project:   $PROJECT_DIR"
echo "  - Timezone:  $TIMEZONE"
echo ""
echo "Bước tiếp theo (đăng nhập bằng user $DEPLOY_USER):"
echo "  1. ssh -p $SSH_PORT $DEPLOY_USER@<IP_VPS>"
echo "  2. cd $PROJECT_DIR && git clone <GITHUB_URL> ."
echo "  3. ./create-env.sh"
echo "  4. docker compose up -d"
echo "  5. ./init-ssl.sh"
echo ""
echo "Scripts có sẵn:"
echo "  - $PROJECT_DIR/scripts/deploy.sh     # Deploy với rollback"
echo "  - $PROJECT_DIR/scripts/backup-db.sh  # Backup thủ công"
echo ""
echo "RAM:"
free -h
echo ""
echo "Disk:"
df -h /
