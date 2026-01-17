# Kia EV6 Climate Control - Deployment Guide

## 📦 Produktionsdriftsättning med Podman

Denna guide visar hur du bygger och kör applikationen i en Podman container.

**Flask-appen servar både frontend och API:**
- Frontend: `http://localhost:5000/` → `public/index.html`
- API: `http://localhost:5000/api/*` → Backend endpoints

För Cloudflare Tunnel deployment, se [CLOUDFLARE-TUNNEL.md](CLOUDFLARE-TUNNEL.md).

---

## ✅ Förutsättningar

1. **Podman installerat**
   ```bash
   # Verifiera installation
   podman --version
   ```

2. **Podman Compose (valfritt, för docker-compose.yml)**
   ```bash
   pip install podman-compose
   ```

3. **Dina Kia UVO credentials**
   - E-postadress
   - Refresh token
   - Access token (valfritt)

---

## 🚀 Steg 1: Förbered miljön

### Skapa data-mapp för persistent storage
```bash
mkdir data
```

### Konfigurera .env-filen
Skapa eller uppdatera `.env`:
```env
KIA_USERNAME=din@email.com
KIA_REFRESH_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
KIA_ACCESS_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
PORT=5000
```

---

## 🏗️ Steg 2: Bygg containern

### Med Podman
```bash
# Bygg imagen
podman build -t kia-climate-control:latest .

# Verifiera att imagen skapades
podman images | grep kia-climate-control
```

---

## ▶️ Steg 3: Kör containern

### Alternativ A: Med Podman direkt
```bash
# Kör container med environment variables från .env
podman run -d \
  --name kia-climate-control \
  -p 5000:5000 \
  --env-file .env \
  -v ./data:/app/data:Z \
  --restart unless-stopped \
  kia-climate-control:latest
```

### Alternativ B: Med Podman Compose
```bash
# Starta tjänsten
podman-compose up -d

# Se loggar
podman-compose logs -f

# Stoppa tjänsten
podman-compose down
```

---

## 🔍 Steg 4: Verifiera deployment

### Kontrollera att containern körs
```bash
podman ps
```

### Testa health check
```bash
curl http://localhost:5000/api/health
```

### Se loggar
```bash
podman logs -f kia-climate-control
```

### Öppna webbappen
Navigera till: **http://localhost:5000**

---

## 📊 Hantera containern

### Stoppa container
```bash
podman stop kia-climate-control
```

### Starta container
```bash
podman start kia-climate-control
```

### Starta om container
```bash
podman restart kia-climate-control
```

### Ta bort container
```bash
podman stop kia-climate-control
podman rm kia-climate-control
```

### Uppdatera till ny version
```bash
# Stoppa och ta bort gammal container
podman stop kia-climate-control
podman rm kia-climate-control

# Bygg ny image
podman build -t kia-climate-control:latest .

# Kör ny container
podman run -d \
  --name kia-climate-control \
  -p 5000:5000 \
  --env-file .env \
  -v ./data:/app/data:Z \
  --restart unless-stopped \
  kia-climate-control:latest
```

---

## 🔐 Säkerhet - Produktionsmiljö

### 1. Använd secrets för känslig data (rekommenderat)
```bash
# Skapa secrets för credentials
echo "din@email.com" | podman secret create kia_username -
echo "eyJ..." | podman secret create kia_refresh_token -

# Kör med secrets
podman run -d \
  --name kia-climate-control \
  -p 5000:5000 \
  --secret kia_username \
  --secret kia_refresh_token \
  -v ./data:/app/data:Z \
  --restart unless-stopped \
  kia-climate-control:latest
```

### 2. Reverse Proxy med HTTPS (rekommenderat för produktion)
Använd Nginx eller Caddy som reverse proxy:

**Exempel med Caddy:**
```caddy
kia.dindomän.se {
    reverse_proxy localhost:5000
}
```

### 3. Brandväggsregler
```bash
# Öppna endast port 5000 för localhost (om du använder reverse proxy)
firewall-cmd --add-port=5000/tcp --permanent
firewall-cmd --reload
```

---

## 🔄 Automatisk start vid systemboot

### Med Podman systemd
```bash
# Generera systemd unit file
podman generate systemd --name kia-climate-control --files --new

# Flytta till systemd directory
sudo mv container-kia-climate-control.service /etc/systemd/system/

# Aktivera och starta
sudo systemctl enable container-kia-climate-control
sudo systemctl start container-kia-climate-control

# Kontrollera status
sudo systemctl status container-kia-climate-control
```

---

## 📁 Datavolym och backup

### Schemaläggningar sparas i
```
./data/schedules.json
```

### Backup
```bash
# Backup av scheman
cp ./data/schedules.json ./data/schedules.json.backup

# Återställ från backup
cp ./data/schedules.json.backup ./data/schedules.json
```

---

## 🐛 Felsökning

### Se detaljerade loggar
```bash
podman logs kia-climate-control
```

### Inspektera container
```bash
podman inspect kia-climate-control
```

### Kör interaktivt shell i containern
```bash
podman exec -it kia-climate-control /bin/bash
```

### Testa anslutning till Kia API
```bash
podman exec kia-climate-control curl http://localhost:5000/api/health
```

### Container startar inte?
- Kontrollera att port 5000 inte används: `netstat -tulpn | grep 5000`
- Verifiera .env-filen: `cat .env`
- Kontrollera loggar: `podman logs kia-climate-control`

---

## 🌐 Nätverksinställningar

### Exponera på alla nätverksgränssnitt
```bash
podman run -d \
  --name kia-climate-control \
  -p 0.0.0.0:5000:5000 \
  --env-file .env \
  -v ./data:/app/data:Z \
  --restart unless-stopped \
  kia-climate-control:latest
```

### Använd specifik IP
```bash
podman run -d \
  --name kia-climate-control \
  -p 192.168.1.100:5000:5000 \
  --env-file .env \
  -v ./data:/app/data:Z \
  --restart unless-stopped \
  kia-climate-control:latest
```

---

## 📝 Miljövariabler

| Variabel | Beskrivning | Obligatorisk |
|----------|-------------|--------------|
| `KIA_USERNAME` | E-postadress för Kia Connect | Ja |
| `KIA_REFRESH_TOKEN` | Refresh token från Kia | Ja |
| `KIA_ACCESS_TOKEN` | Access token (fallback) | Nej |
| `PORT` | Port för webbservern | Nej (default: 5000) |

---

## 🔧 Prestandaoptimering

### Begränsa resurser
```bash
podman run -d \
  --name kia-climate-control \
  -p 5000:5000 \
  --env-file .env \
  -v ./data:/app/data:Z \
  --memory="512m" \
  --cpus="1.0" \
  --restart unless-stopped \
  kia-climate-control:latest
```

---

## ✅ Checklista för produktion

- [ ] .env-filen är konfigurerad med korrekta credentials
- [ ] data/-mappen är skapad
- [ ] Container är byggd framgångsrikt
- [ ] Health check returnerar OK
- [ ] Webbgränssnittet är tillgängligt
- [ ] Schemaläggningar fungerar
- [ ] Automatisk omstart är konfigurerad
- [ ] Backup-rutin är på plats
- [ ] HTTPS/Reverse proxy är konfigurerad (för extern åtkomst)
- [ ] Brandväggsregler är satta

---

## 📞 Support

Om du stöter på problem:
1. Kontrollera loggarna: `podman logs kia-climate-control`
2. Verifiera credentials i .env-filen
3. Testa API-anslutning: `curl http://localhost:5000/api/health`
4. Kontrollera att Kia UVO API är tillgängligt

---

**🎉 Lycka till med din deployment!**
