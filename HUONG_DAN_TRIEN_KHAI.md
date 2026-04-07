# HƯỚNG DẪN TRIỂN KHAI NGON-NGON
## Dành cho chủ quán (không cần biết code)

---

## TỔNG QUAN

Hệ thống gồm 3 trang web:
- **ngon-ngon.com** → Menu khách hàng đặt hàng
- **ngon-ngon.com/admin.html** → Trang quản lý cho chủ quán
- **ngon-ngon.com/kds.html** → Màn hình bếp (KDS) cho nhân viên pha chế

Quy trình đặt hàng: Khách vào ngon-ngon.com → chọn món → đặt hàng → hệ thống BÁO NGAY lập tức về KDS → nhân viên pha chế → giao cho khách.

---

## BƯỚC 1: CÀI ĐẶT VPS (làm 1 lần)

Lần đầu tiên, SSH vào VPS bằng root (nhà cung cấp VPS sẽ gửi mật khẩu qua email):

```bash
ssh root@180.93.1.117
```

Upload file `setup-vps.sh` lên VPS và chạy:

```bash
chmod +x setup-vps.sh
./setup-vps.sh
```

Chờ khoảng 3-5 phút. Khi thấy dòng "CÀI ĐẶT VPS HOÀN TẤT!" là xong.

**QUAN TRỌNG — Ghi nhớ thông tin sau khi cài xong:**
- SSH port đã đổi thành: **2222** (không còn dùng port 22)
- User đã đổi thành: **deploy** (không còn dùng root)
- Đăng nhập root đã bị TẮT (để bảo mật)

**Từ bây giờ, mỗi khi SSH vào VPS đều dùng lệnh này:**
```bash
ssh -p 2222 deploy@180.93.1.117
```

Hoặc trong VS Code: kết nối SSH với host `180.93.1.117`, port `2222`, user `deploy`.

---

## BƯỚC 2: ĐƯA CODE LÊN GITHUB (làm 1 lần)

Trên máy tính Windows 10, mở VS Code:

2a. Cài Git cho Windows: tải từ https://git-scm.com/download/win và cài đặt.

2b. Tạo repository trên GitHub:
- Vào https://github.com → đăng nhập → New repository
- Tên repo: `ngonngon`
- Chọn Private → Create repository

2c. Đẩy code lên GitHub (chạy trong Terminal của VS Code, tại thư mục dự án):
```bash
git init
git add .
git commit -m "First deploy"
git branch -M main
git remote add origin https://github.com/TEN_GITHUB/ngonngon.git
git push -u origin main
```

(Thay TEN_GITHUB bằng username GitHub của anh)

---

## BƯỚC 3: KÉO CODE VỀ VPS (làm 1 lần)

SSH vào VPS bằng user deploy:

```bash
ssh -p 2222 deploy@180.93.1.117
cd /opt/ngonngon
git clone https://github.com/TEN_GITHUB/ngonngon.git .
```

(Lưu ý: có dấu chấm `.` cuối cùng, nghĩa là clone vào thư mục hiện tại)

---

## BƯỚC 4: TẠO FILE CẤU HÌNH (làm 1 lần)

File .env chứa mật khẩu và secret — được tạo trực tiếp trên VPS, KHÔNG lưu trên GitHub.

```bash
chmod +x create-env.sh && ./create-env.sh
```

Script sẽ tự tạo mật khẩu ngẫu nhiên và hiện lên màn hình:

```
   Admin password:    xxxxxxxxxxxxxxxx
   Database password: xxxxxxxxxxxxxxxx
   JWT Secret:        xxxxxxxxxxxxxxxx
```

**QUAN TRỌNG: Chụp màn hình hoặc copy LƯU LẠI thông tin này ở nơi an toàn!**
Đặc biệt Admin password — đây là mật khẩu đăng nhập trang quản lý.

---

## BƯỚC 5: KHỞI CHẠY HỆ THỐNG

```bash
docker compose up -d
```

Chờ khoảng 3-5 phút lần đầu (Docker tải image + build). Kiểm tra:

```bash
docker compose ps
```

Khi cả 3 container (db, api, nginx) đều hiện "healthy" hoặc "running" là thành công.

Thử truy cập: http://ngon-ngon.com — phải thấy trang menu.

---

## BƯỚC 6: CÀI SSL (HTTPS) — làm 1 lần

```bash
chmod +x init-ssl.sh
./init-ssl.sh
```

Script sẽ tự kiểm tra DNS, lấy cert SSL, và verify HTTPS.
Chờ khoảng 1-2 phút. Sau đó truy cập: https://ngon-ngon.com

Nếu lỗi, script sẽ hiện hướng dẫn cụ thể để sửa.

---

## BƯỚC 7: CÀI TỰ ĐỘNG DEPLOY (tùy chọn)

Để mỗi khi anh push code lên GitHub, VPS tự động cập nhật:

7a. SSH vào VPS và tạo SSH key:
```bash
ssh -p 2222 deploy@180.93.1.117
ssh-keygen -t ed25519 -C "deploy" -f ~/.ssh/deploy_key -N ""
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/deploy_key
```

7b. Copy toàn bộ nội dung hiện ra (bắt đầu bằng `-----BEGIN`).

7c. Vào GitHub repo → Settings → Secrets and variables → Actions → New repository secret:
- `VPS_HOST` = `180.93.1.117`
- `VPS_USER` = `deploy`
- `VPS_SSH_KEY` = (paste nội dung private key vừa copy)
- `VPS_SSH_PORT` = `2222`

Từ nay, mỗi khi anh push code lên GitHub:
1. GitHub Actions sẽ kiểm tra chất lượng code trước
2. Nếu OK → tự SSH vào VPS và deploy
3. Deploy có tự kiểm tra health — nếu lỗi sẽ tự rollback về bản cũ

---

## SỬ DỤNG HÀNG NGÀY

**Đăng nhập Admin:** Vào https://ngon-ngon.com/admin.html
- Username: `admin`
- Password: (mật khẩu đã tạo ở Bước 4 — xem lại nơi anh đã lưu)

**Đăng nhập KDS (bếp):** Vào https://ngon-ngon.com/kds.html
- Nhập PIN: (xem trong file `.env` trên VPS, dòng `KDS_PIN`)

**Cập nhật code:** Trên máy Windows, sửa code → Terminal:
```bash
git add .
git commit -m "Mô tả thay đổi"
git push
```
VPS sẽ tự cập nhật (nếu đã cài Bước 7).

Hoặc deploy thủ công — SSH vào VPS:
```bash
ssh -p 2222 deploy@180.93.1.117
cd /opt/ngonngon && bash scripts/deploy.sh
```

---

## XỬ LÝ SỰ CỐ

**Hệ thống không truy cập được:**
```bash
ssh -p 2222 deploy@180.93.1.117
cd /opt/ngonngon
docker compose ps          # Xem container nào đang chạy
docker compose logs api    # Xem log lỗi backend
docker compose logs nginx  # Xem log lỗi nginx
docker compose restart     # Khởi động lại tất cả
```

**Muốn khởi động lại hoàn toàn:**
```bash
cd /opt/ngonngon
docker compose down
docker compose up -d
```

**Backup database thủ công:**
```bash
bash /opt/ngonngon/scripts/backup-db.sh
```
(Hệ thống đã tự backup lúc 3:00 sáng mỗi ngày)

**Xem dung lượng ổ cứng:**
```bash
df -h /
docker system prune -f    # Dọn dẹp Docker rác (tiết kiệm ổ cứng)
```

**Kiểm tra RAM:**
```bash
free -h
```

**Quên mật khẩu Admin?**
SSH vào VPS và xem file `.env`:
```bash
ssh -p 2222 deploy@180.93.1.117
cat /opt/ngonngon/.env | grep ADMIN_PASSWORD
```

---

## THÔNG TIN KỸ THUẬT

- VPS: 180.93.1.117 (1 vCPU, 1GB RAM, 10GB SSD)
- SSH: port 2222, user `deploy` (root đã tắt, password đã tắt)
- Domain: ngon-ngon.com + www.ngon-ngon.com
- SSL: Let's Encrypt (tự động gia hạn mỗi 12 giờ)
- Database: PostgreSQL 16
- Backend: FastAPI (Python 3.12)
- Backup: tự động lúc 3:00 sáng (giữ 7 ngày + 4 tuần + 2 tháng)
- Bảo mật: fail2ban, firewall UFW, auto security updates
- SĐT quán: 0378148148
