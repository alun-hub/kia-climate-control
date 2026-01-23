# Kia Climate Control - Raspberry Pi Deployment med Podman

Komplett guide för att köra Kia Climate Control-appen i en Podman-container på Raspberry Pi.

## 📋 Innehåll

- [Hårdvarukrav](#hårdvarukrav)
- [Installation av Raspberry Pi OS](#installation-av-raspberry-pi-os)
- [Installera Podman](#installera-podman)
- [Hämta projektet](#hämta-projektet)
- [Bygg Docker-imagen](#bygg-docker-imagen)
- [Konfigurera autostart](#konfigurera-autostart)
- [Verifiera installation](#verifiera-installation)
- [Hantera appen](#hantera-appen)
- [Felsökning](#felsökning)

---

## 🔧 Hårdvarukrav

### Rekommenderat
- **Raspberry Pi 3B eller nyare** (1 GB+ RAM)
- microSD-kort (minst 16 GB, Class 10)
- Strömadapter (5V 2.5A)
- Nätverksanslutning (Ethernet eller WiFi)

### Fungerar men begränsat
- Raspberry Pi Zero 2W (512 MB RAM) - endast för lätt användning

---

## 💿 Installation av Raspberry Pi OS

### 1. Ladda ner Raspberry Pi Imager
- Windows/Mac/Linux: https://www.raspberrypi.com/software/

### 2. Installera OS
1. Öppna Raspberry Pi Imager
2. Välj OS: **Raspberry Pi OS Lite (64-bit)**
3. Välj ditt SD-kort
4. Klicka på kugghjulet ⚙️ för avancerade inställningar:
   - **Hostname**: `kia-pi` (eller valfritt)
   - **✓ Enable SSH** (lösenordsautentisering)
   - **Username**: `pi` eller ditt användarnamn
   - **Password**: Välj ett säkert lösenord
   - **✓ Configure WiFi** (om du inte använder Ethernet)
   - **Time zone**: `Europe/Stockholm`
   - **Keyboard layout**: `se`
5. Klicka "Write" och vänta

### 3. Första uppstart
1. Sätt i SD-kortet i Raspberry Pi
2. Anslut nätverkskabel (om Ethernet)
3. Anslut ström
4. Vänta ~60 sekunder

### 4. Hitta Pi:ns IP-adress

**Från router:**
- Logga in på din router (oftast http://192.168.1.1)
- Leta efter enhet med namnet `kia-pi`

**Med ping:**
```bash
ping kia-pi.local
```

### 5. SSH-anslutning
```bash
# Från Windows PowerShell, macOS Terminal eller Linux
ssh pi@192.168.1.XXX
# eller
ssh pi@kia-pi.local

# Första gången: svara "yes" på fingerprint-frågan
# Ange ditt lösenord
```

---

## 🐋 Installera Podman

```bash
# Uppdatera systemet
sudo apt update && sudo apt upgrade -y

# Installera Podman
sudo apt install -y podman

# Verifiera installation
podman --version
# Bör visa: podman version 3.x.x eller nyare
```

---

## 📥 Hämta projektet

### Alternativ 1: Klona från GitHub (Rekommenderat)

```bash
# Installera Git om det inte finns
sudo apt install -y git

# Konfigurera Git credentials (för att slippa logga in varje gång)
git config --global credential.helper store

# Klona projektet
cd ~
git clone https://github.com/ditt-användarnamn/kia-climate-control.git
cd kia-climate-control
```

**För GitHub: Använd Personal Access Token**
1. Skapa token: https://github.com/settings/tokens
2. Välj scope: `repo`
3. Vid `git clone` eller `git pull`, använd token som lösenord

### Alternativ 2: Kopiera filer från Windows

**På din Windows-dator:**
```powershell
cd C:\Users\alun\kia-climate-control

# Kopiera alla filer till Pi:n
scp -r * pi@192.168.1.XXX:~/kia-climate-control/
```

### Alternativ 3: SSH-nycklar (Bäst för säkerhet)

**På Raspberry Pi:**
```bash
# Generera SSH-nyckel
ssh-keygen -t ed25519 -C "din@email.com"
# Tryck Enter för default location

# Visa din publika nyckel
cat ~/.ssh/id_ed25519.pub
# Kopiera utskriften
```

**På GitHub:**
1. Gå till: https://github.com/settings/ssh/new
2. Klistra in din publika nyckel
3. Klona med SSH:
```bash
git clone git@github.com:ditt-användarnamn/kia-climate-control.git
```

---

## 🏗️ Bygg Docker-imagen

```bash
# Navigera till projektkatalogen
cd ~/kia-climate-control

# Skapa .env-fil (om den inte finns)
nano .env
```

**Lägg till i .env:**
```env
KIA_USERNAME=din@email.com
KIA_REFRESH_TOKEN=din_refresh_token
KIA_ACCESS_TOKEN=din_access_token
PORT=5000
```

**Spara:** `Ctrl+X`, `Y`, `Enter`

**Skapa data-katalog:**
```bash
mkdir -p ~/kia-climate-control/data
```

**Bygg imagen:**
```bash
# Bygg imagen för ARM64 (tar ~5-10 minuter första gången)
podman build -f Dockerfile.pi -t localhost/kia-climate-control:latest .

# Verifiera att imagen finns
podman images | grep kia-climate
```

**Förväntad output:**
```
localhost/kia-climate-control  latest  abc123def456  2 minutes ago  150 MB
```

---

## 🚀 Konfigurera autostart

### Skapa systemd service-fil

```bash
sudo nano /etc/systemd/system/kia-climate-podman.service
```

**Klistra in följande konfiguration:**

```ini
[Unit]
Description=Kia EV6 Climate Control (Podman)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/kia-climate-control

# Stoppa och ta bort gammal container (ignorera fel)
ExecStartPre=-/usr/bin/podman stop kia-climate
ExecStartPre=-/usr/bin/podman rm kia-climate

# Starta container i attached mode
ExecStart=/usr/bin/podman run --rm \
  --name kia-climate \
  -p 5000:5000 \
  -v /home/pi/kia-climate-control/data:/app/data:Z \
  -v /home/pi/kia-climate-control/.env:/app/.env:Z \
  -v /etc/localtime:/etc/localtime:ro \
  localhost/kia-climate-control:latest

# Stoppa container när service stoppas
ExecStop=/usr/bin/podman stop kia-climate

# Automatisk omstart om container kraschar
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**OBS!** Ändra `/home/pi` till `/home/ditt-användarnamn` om du använder ett annat användarnamn.

**Spara:** `Ctrl+X`, `Y`, `Enter`

### Aktivera och starta servicen

```bash
# Reload systemd för att läsa in nya service-filen
sudo systemctl daemon-reload

# Aktivera autostart vid boot
sudo systemctl enable kia-climate-podman.service

# Starta servicen
sudo systemctl start kia-climate-podman.service

# Kontrollera status
sudo systemctl status kia-climate-podman.service
```

**Förväntad status:**
```
● kia-climate-podman.service - Kia EV6 Climate Control (Podman)
   Loaded: loaded (/etc/systemd/system/kia-climate-podman.service; enabled)
   Active: active (running) since ...
```

---

## ✅ Verifiera installation

### 1. Kontrollera loggar

```bash
# Visa live-loggar
sudo journalctl -u kia-climate-podman.service -f

# Visa senaste 50 raderna
sudo journalctl -u kia-climate-podman.service -n 50
```

**Du bör se:**
```
╔═══════════════════════════════════════╗
║  Kia EV6 Climate Control Server       ║
║  Port: 5000                            ║
║  Python Backend with KiaUvoApiEU      ║
║  Schemaläggning: Aktiv                ║
╚═══════════════════════════════════════╝

Schemaläggnings-tråd startad
Initierar Kia API...
Loggar in som din@email.com...
✓ Ansluten till fordon: ...
 * Running on http://192.168.1.XXX:5000
```

### 2. Testa i webbläsare

Öppna: `http://192.168.1.XXX:5000` (ersätt XXX med Pi:ns IP)

Du bör se Kia Climate Control-gränssnittet.

### 3. Testa credentials-persistens

```bash
# Gå till admin-sidan i webbläsaren
# http://192.168.1.XXX:5000/admin

# Spara nya credentials

# Kontrollera att de sparades till .env
cat ~/kia-climate-control/.env

# Starta om containern
sudo systemctl restart kia-climate-podman.service

# Credentials bör finnas kvar efter omstart
```

### 4. Testa schemaläggning

1. Skapa ett schema som körs om 2-3 minuter via webgränssnittet
2. Följ loggarna:
```bash
sudo journalctl -u kia-climate-podman.service -f
```
3. När tiden kommer bör du se:
```
Kollar scheman: 19:45, Dag: 2
✓ Kör schemalagd klimatstart: Mitt Test
✓ Klimat startad från schema 'Mitt Test'
```

---

## 🔧 Hantera appen

### Visa status
```bash
sudo systemctl status kia-climate-podman.service
```

### Starta
```bash
sudo systemctl start kia-climate-podman.service
```

### Stoppa
```bash
sudo systemctl stop kia-climate-podman.service
```

### Starta om
```bash
sudo systemctl restart kia-climate-podman.service
```

### Visa loggar
```bash
# Live-loggar
sudo journalctl -u kia-climate-podman.service -f

# Senaste 100 raderna
sudo journalctl -u kia-climate-podman.service -n 100

# Loggar från senaste 24h
sudo journalctl -u kia-climate-podman.service --since "24 hours ago"
```

### Inaktivera autostart
```bash
sudo systemctl disable kia-climate-podman.service
```

### Aktivera autostart igen
```bash
sudo systemctl enable kia-climate-podman.service
```

---

## 🔄 Uppdatera appen

### Med Git

```bash
# Navigera till projektkatalogen
cd ~/kia-climate-control

# Hämta senaste koden
git pull origin main

# Bygg om imagen
podman build -f Dockerfile.pi -t localhost/kia-climate-control:latest .

# Starta om servicen (den kommer automatiskt använda nya imagen)
sudo systemctl restart kia-climate-podman.service

# Kontrollera loggar
sudo journalctl -u kia-climate-podman.service -f
```

### Manuell uppdatering

```bash
# Kopiera nya filer från Windows
scp kia_backend.py pi@192.168.1.XXX:~/kia-climate-control/
scp -r public pi@192.168.1.XXX:~/kia-climate-control/

# På Raspberry Pi: Bygg om och starta om
cd ~/kia-climate-control
podman build -f Dockerfile.pi -t localhost/kia-climate-control:latest .
sudo systemctl restart kia-climate-podman.service
```

---

## 🐛 Felsökning

### Containern startar inte

**Kontrollera loggar:**
```bash
sudo journalctl -u kia-climate-podman.service -n 50
```

**Vanliga problem:**

1. **"exec format error"**
   - Imagen är byggd för fel arkitektur
   - Lösning: Bygg imagen direkt på Raspberry Pi
   ```bash
   podman rmi localhost/kia-climate-control:latest
   podman build -f Dockerfile.pi -t localhost/kia-climate-control:latest .
   ```

2. **"Permission denied" på volumes**
   - SELinux-problem
   - Lösning: Lägg till `:Z` på volume-mounts (redan inkluderat i service-filen)

3. **"Cannot connect to Kia API"**
   - Felaktiga credentials
   - Lösning: Gå till `/admin` och generera nya tokens

### Appen når inte Kia API

```bash
# Testa internetanslutning
ping -c 4 google.com

# Testa från containern
podman exec kia-climate ping -c 4 google.com
```

### Schemaläggning fungerar inte

**Kontrollera tidszon:**
```bash
# På Pi:n
date

# I containern
podman exec kia-climate date

# Båda bör visa samma tid
```

**Kontrollera schema-fil:**
```bash
cat ~/kia-climate-control/data/schedules.json
```

Verifiera:
- `"enabled": true`
- `"days"`: Rätt veckodagar (0=Måndag, 6=Söndag)
- `"time"`: Format "HH:MM" (t.ex. "07:30")

**Följ schemaläggnings-tråden:**
```bash
sudo journalctl -u kia-climate-podman.service -f | grep -i "schema"
```

### Credentials försvinner vid omstart

**Kontrollera att .env är mountad som volume:**
```bash
podman inspect kia-climate | grep -A 5 "Mounts"
```

Du bör se:
```json
"Mounts": [
  {
    "Source": "/home/pi/kia-climate-control/.env",
    "Destination": "/app/.env",
    ...
  }
]
```

**Om inte, kontrollera service-filen:**
```bash
sudo nano /etc/systemd/system/kia-climate-podman.service
```

Verifiera att denna rad finns:
```
-v /home/pi/kia-climate-control/.env:/app/.env:Z \
```

### Hög CPU/RAM-användning

**Kontrollera resurser:**
```bash
# Installera htop
sudo apt install htop

# Kör htop
htop
```

**Kontrollera container-statistik:**
```bash
podman stats kia-climate
```

**Lösningar:**
- Raspberry Pi Zero 2W: Överväg uppgradering till Pi 3B+
- Minska poll-intervall i appen
- Använd Alpine-versionen (Dockerfile.pi) som är lättare

### Out of Memory

**Kontrollera minne:**
```bash
free -h
```

**Öka swap (om nödvändigt):**
```bash
sudo nano /etc/dphys-swapfile
# Ändra CONF_SWAPSIZE från 100 till 512

sudo systemctl restart dphys-swapfile
```

### Imagen tar för mycket plats

**Kontrollera storlek:**
```bash
podman images
```

**Rensa gamla images:**
```bash
podman image prune -a
```

**Kontrollera diskutrymme:**
```bash
df -h
```

### Podman-kommandon fungerar inte

**Kontrollera att Podman är installerat:**
```bash
which podman
podman --version
```

**Om Podman saknas:**
```bash
sudo apt update
sudo apt install -y podman
```

---

## 📊 Övervaka prestanda

### Realtidsövervakning med htop
```bash
sudo apt install htop
htop
```

### Container-statistik
```bash
podman stats kia-climate
```

### Minnesanvändning
```bash
free -h
```

### Diskutrymme
```bash
df -h
```

### CPU-temperatur
```bash
vcgencmd measure_temp
```

### Nätverksanslutningar
```bash
sudo netstat -tlnp | grep 5000
```

---

## 🔒 Säkerhet

### 1. Ändra SSH-port (Valfritt)
```bash
sudo nano /etc/ssh/sshd_config
# Ändra Port 22 till Port 2222
sudo systemctl restart ssh
```

### 2. Konfigurera brandvägg
```bash
sudo apt install ufw

# Tillåt SSH
sudo ufw allow 22/tcp

# Tillåt Flask-app endast från lokalt nätverk
sudo ufw allow from 192.168.1.0/24 to any port 5000

# Aktivera
sudo ufw enable

# Status
sudo ufw status
```

### 3. Automatiska säkerhetsuppdateringar
```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades
# Välj "Yes"
```

### 4. Backup av .env
```bash
# Skapa backup
cp ~/kia-climate-control/.env ~/kia-climate-control/.env.backup

# Automatisk backup (cron)
crontab -e
# Lägg till:
0 2 * * * cp ~/kia-climate-control/.env ~/kia-climate-control/.env.backup.$(date +\%Y\%m\%d)
```

---

## 💡 Tips och tricks

### Statisk IP-adress
```bash
sudo nano /etc/dhcpcd.conf

# Lägg till i slutet:
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8

# Spara och starta om
sudo reboot
```

### Alias för vanliga kommandon
```bash
nano ~/.bashrc

# Lägg till:
alias kia-logs='sudo journalctl -u kia-climate-podman.service -f'
alias kia-status='sudo systemctl status kia-climate-podman.service'
alias kia-restart='sudo systemctl restart kia-climate-podman.service'

# Aktivera
source ~/.bashrc
```

### Backup hela projektet
```bash
# Skapa backup
tar -czf kia-backup-$(date +%Y%m%d).tar.gz ~/kia-climate-control/

# Kopiera till Windows-dator
scp kia-backup-*.tar.gz användarnamn@windows-dator-ip:C:/Backups/
```

### Övervaka disk-IO
```bash
sudo apt install iotop
sudo iotop
```

### Kör från USB istället för SD-kort
För bättre prestanda och livslängd, överväg att köra OS från USB:
- Guide: https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#usb-mass-storage-boot

---

## 📞 Support och mer information

### Relaterade guider
- [PI3B-QUICKSTART.md](PI3B-QUICKSTART.md) - Steg-för-steg guide för Pi 3B
- [CLOUDFLARE-TUNNEL.md](CLOUDFLARE-TUNNEL.md) - Extern åtkomst via Cloudflare
- [README.md](README.md) - Allmän projektinformation

### Loggar för support
Om du behöver hjälp, inkludera följande information:

```bash
# Systeminfo
uname -a
cat /etc/os-release

# Podman-version
podman --version

# Service-status
sudo systemctl status kia-climate-podman.service

# Senaste loggar
sudo journalctl -u kia-climate-podman.service -n 100 --no-pager

# Container-info
podman inspect kia-climate

# Minnesanvändning
free -h
```

---

## 🎉 Lycka till!

Din Kia Climate Control-app körs nu i en Podman-container på Raspberry Pi med:
- ✅ Automatisk start vid boot
- ✅ Automatisk omstart vid krasch
- ✅ Persistent credential-lagring
- ✅ Schemaläggning med rätt tidszon
- ✅ Enkel uppdatering och underhåll

Enjoy! 🚗💨
