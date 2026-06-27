# Oracle Free Tier Deployment

This is the simple free setup for sharing the app by Oracle VM public IP.

## 1. Create Oracle VM

- Use Oracle Cloud Free Tier.
- Create an Ubuntu VM.
- Open inbound ports `22` and `80` in the VM security list.
- SSH into the VM.

## 2. Install server packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx git
```

## 3. Clone the repo

```bash
sudo mkdir -p /opt/abconstruction
sudo chown "$USER":"$USER" /opt/abconstruction
cd /opt/abconstruction
git clone https://github.com/kunal358/Construction-Management.git
cd Construction-Management
```

Copy your current `instance/construction.db`, `instance/expense_categories.txt`, and uploaded files if you want existing data on the server.

## 4. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Configure environment

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))"
```

Edit `.env`:

```bash
nano .env
```

Set:

- `SECRET_KEY`
- `AB_AUTH_USERNAME`
- `AB_AUTH_PASSWORD_HASH`

## 6. Test gunicorn

```bash
set -a
source .env
set +a
gunicorn --bind 127.0.0.1:8000 wsgi:application
```

Open another SSH session and test:

```bash
curl -I http://127.0.0.1:8000/
```

Stop gunicorn with `Ctrl+C`.

## 7. Create systemd service

```bash
sudo nano /etc/systemd/system/abconstruction.service
```

Paste:

```ini
[Unit]
Description=AB Construction Flask App
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/opt/abconstruction/Construction-Management
EnvironmentFile=/opt/abconstruction/Construction-Management/.env
ExecStart=/opt/abconstruction/Construction-Management/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

If your VM user is not `ubuntu`, change `User=ubuntu`.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now abconstruction
sudo systemctl status abconstruction
```

## 8. Configure nginx

```bash
sudo nano /etc/nginx/sites-available/abconstruction
```

Paste:

```nginx
server {
    listen 80;
    server_name _;

    client_max_body_size 25M;

    location /static/ {
        alias /opt/abconstruction/Construction-Management/static/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/abconstruction /etc/nginx/sites-enabled/abconstruction
sudo nginx -t
sudo systemctl reload nginx
```

Open:

```text
http://ORACLE_PUBLIC_IP
```

## 9. Backups

Run manually:

```bash
chmod +x scripts/backup.sh
./scripts/backup.sh
```

Optional daily cron:

```bash
crontab -e
```

Add:

```cron
0 2 * * * APP_DIR=/opt/abconstruction/Construction-Management /opt/abconstruction/Construction-Management/scripts/backup.sh >/tmp/abconstruction-backup.log 2>&1
```

## Notes

- Without a domain, the app uses plain HTTP on the public IP.
- Login still protects the app, but passwords travel over HTTP. Use a domain and HTTPS later if this becomes important.
- Keep regular DB backups because SQLite lives on the VM disk.
