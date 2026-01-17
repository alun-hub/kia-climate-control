# Kia EV6 Climate Control - Cloudflare Tunnel Deployment

## Översikt

Flask-applikationen servar både frontend (HTML/CSS/JS) och backend API. Detta fungerar perfekt med Cloudflare Tunnel.

## Arkitektur

```
Internet → Cloudflare Tunnel → Flask App (Port 5000)
                                    ├── / (index.html)
                                    └── /api/* (REST API)
```

Flask servar:
- **Frontend**: `http://localhost:5000/` → `public/index.html`
- **API**: `http://localhost:5000/api/*` → Backend endpoints

## Steg 1: Bygg och kör containern

```bash
# Använd build.sh eller manuellt:
podman build -t kia-climate-control:latest .

# Kör containern
podman run -d \
  --name kia-climate-control \
  -p 5000:5000 \
  --env-file .env \
  -v ./data:/app/data:Z \
  --restart unless-stopped \
  kia-climate-control:latest
```

## Steg 2: Verifiera att appen fungerar lokalt

```bash
# Testa frontend
curl http://localhost:5000/

# Testa API health check
curl http://localhost:5000/api/health

# Öppna i webbläsare
http://localhost:5000
```

## Steg 3: Installera Cloudflare Tunnel (cloudflared)

### Windows
```powershell
# Ladda ner från: https://github.com/cloudflare/cloudflared/releases
# Eller med winget:
winget install --id Cloudflare.cloudflared
```

### Linux
```bash
# Debian/Ubuntu
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Eller via package manager
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-archive-keyring.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-archive-keyring.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install cloudflared
```

## Steg 4: Autentisera med Cloudflare

```bash
cloudflared tunnel login
```

Detta öppnar en webbläsare där du loggar in på Cloudflare och väljer din domän.

## Steg 5: Skapa en tunnel

```bash
# Skapa tunnel
cloudflared tunnel create kia-climate

# Detta skapar en tunnel och ger dig ett tunnel ID
# Spara tunnel ID:t som visas
```

## Steg 6: Konfigurera tunneln

Skapa `config.yml` i Cloudflare Tunnel config-mappen:

**Windows**: `%USERPROFILE%\.cloudflared\config.yml`
**Linux**: `~/.cloudflared/config.yml`

```yaml
tunnel: <TUNNEL_ID>
credentials-file: /home/user/.cloudflared/<TUNNEL_ID>.json

ingress:
  # Route till din Kia app
  - hostname: kia.dindomän.se
    service: http://localhost:5000

  # Catch-all rule (obligatorisk)
  - service: http_status:404
```

**Om du kör i container**, ändra service till:
```yaml
  - hostname: kia.dindomän.se
    service: http://host.containers.internal:5000  # För Podman/Docker på Windows/Mac
    # ELLER
    service: http://172.17.0.1:5000  # För Linux (Docker bridge IP)
```

## Steg 7: Konfigurera DNS

```bash
# Skapa DNS-record som pekar till tunneln
cloudflared tunnel route dns kia-climate kia.dindomän.se
```

## Steg 8: Kör tunneln

### Testa först (interaktivt)
```bash
cloudflared tunnel run kia-climate
```

### Kör som tjänst (produktion)

**Windows (Service)**
```powershell
# Installera som service
cloudflared service install

# Starta service
sc start cloudflared
```

**Linux (systemd)**
```bash
# Installera som systemd service
sudo cloudflared service install

# Starta service
sudo systemctl start cloudflared
sudo systemctl enable cloudflared

# Kontrollera status
sudo systemctl status cloudflared
```

## Steg 9: Testa din deployment

Besök: `https://kia.dindomän.se`

Du bör nu kunna:
- Se webbgränssnittet
- Kontrollera fordonsstatus
- Starta/stoppa klimat
- Hantera schemaläggningar

## Alternativ: Snabb tunnel (utan custom domain)

För snabb test utan DNS-konfiguration:

```bash
cloudflared tunnel --url http://localhost:5000
```

Detta ger dig en tillfällig URL som: `https://random-words.trycloudflare.com`

## Säkerhet

⚠️ **VIKTIGT:** Din app är nu tillgänglig via internet. Se [CLOUDFLARE-SECURITY.md](CLOUDFLARE-SECURITY.md) för omfattande säkerhetsguide!

### Snabbstart säkerhet:

1. **Tvinga HTTPS** (Obligatoriskt)
   - Cloudflare Dashboard → SSL/TLS → Edge Certificates → "Always Use HTTPS"

2. **Lägg till autentisering** (Starkt rekommenderat)
   - Cloudflare Dashboard → Zero Trust → Access → Applications
   - Skapa application för `kia.dindomän.se`
   - Lägg till email-baserad autentisering

3. **Rate Limiting** (Rekommenderat)
   - Begränsa antal requests för att förhindra missbruk

**För fullständig säkerhetsguide, se [CLOUDFLARE-SECURITY.md](CLOUDFLARE-SECURITY.md)**

## Felsökning

### Tunnel ansluter inte
```bash
# Kontrollera tunnel-status
cloudflared tunnel info kia-climate

# Visa loggar
# Windows
Get-EventLog -LogName Application -Source cloudflared

# Linux
sudo journalctl -u cloudflared -f
```

### 502 Bad Gateway
- Kontrollera att Flask-appen körs: `curl http://localhost:5000/api/health`
- Kontrollera att porten är korrekt i config.yml
- Kontrollera firewall-regler

### Frontend laddas inte
- Verifiera att `public/` mappen finns i containern
- Testa lokalt först: `http://localhost:5000/`
- Kontrollera Flask-loggar: `podman logs kia-climate-control`

## Monitoring

```bash
# Podman container status
podman ps
podman stats kia-climate-control

# Cloudflare Tunnel status
cloudflared tunnel info kia-climate

# Loggar
podman logs -f kia-climate-control
```

## Backup

```bash
# Backup av schemaläggningar
podman exec kia-climate-control cat /app/data/schedules.json > schedules-backup.json

# Backup av .env
cp .env .env.backup
```

## Kostnader

- **Cloudflare Tunnel**: Gratis
- **Cloudflare DNS**: Gratis
- **Cloudflare Access** (Zero Trust): Gratis upp till 50 användare
- **Server/VPS**: Varierar (kan köra hemma, VPS, eller cloud)

## Fördelar med denna setup

✅ Ingen öppen port på din router
✅ Automatisk HTTPS via Cloudflare
✅ DDoS-skydd via Cloudflare
✅ Snabb global åtkomst via Cloudflare CDN
✅ Enkel att sätta upp
✅ Gratis (för grundläggande användning)

---

**Lycka till med din Cloudflare Tunnel deployment! 🚀**
