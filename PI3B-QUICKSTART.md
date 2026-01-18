# Raspberry Pi 3B - Snabbstart Guide

## 🎯 Översikt

Du kommer att installera Kia Climate Control-appen på din Raspberry Pi 3B v1.2 från 2015.

**Hårdvara:**
- Raspberry Pi 3B (1 GB RAM, 4x 1.2 GHz)
- microSD-kort (minst 8 GB)
- Strömadapter (5V 2.5A rekommenderat)
- Ethernet-kabel (rekommenderat) eller WiFi

**Val att göra:**
- **Metod 1**: Direkt Python (Enklast, minst minneskrävande) ← REKOMMENDERAT
- **Metod 2**: Docker (Mer isolerat, enklare uppdateringar)

---

## 📋 Steg 1: Förbered Raspberry Pi

### A. Installera Raspberry Pi OS

1. **Ladda ner Raspberry Pi Imager**
   - Windows: https://www.raspberrypi.com/software/
   - Installera och öppna programmet

2. **Välj OS**
   - Klicka "Choose OS"
   - Välj: **Raspberry Pi OS (other)**
   - Välj: **Raspberry Pi OS Lite (64-bit)**

   ℹ️ _Lite-versionen är perfekt för server-användning (ingen desktop GUI)_

3. **Konfigurera inställningar**
   - Klicka på kugghjulet ⚙️ (Settings)
   - **Hostname**: `kia-pi` (eller valfritt namn)
   - **✓ Enable SSH** (Använd lösenordsautentisering)
   - **Username**: `pi` (eller eget namn)
   - **Password**: Välj ett säkert lösenord
   - **✓ Configure WiFi** (om du inte använder Ethernet)
     - SSID: Ditt WiFi-namn
     - Password: Ditt WiFi-lösenord
     - Country: SE
   - **Locale**:
     - Time zone: Europe/Stockholm
     - Keyboard layout: se

4. **Skriv till SD-kort**
   - Välj ditt SD-kort
   - Klicka "Write"
   - Vänta tills färdig (~5-10 minuter)

5. **Sätt i SD-kort och starta Pi:n**
   - Ta ut SD-kort och sätt i Pi:n
   - Anslut Ethernet-kabel (om du använder det)
   - Anslut ström
   - Vänta ~60 sekunder för första uppstarten

---

## 🔌 Steg 2: Anslut till Pi:n

### Hitta Pi:ns IP-adress

**Alternativ A: Från din router**
- Logga in på din router (oftast http://192.168.1.1)
- Leta efter enhet med namnet `kia-pi`

**Alternativ B: Använd nmap (Windows)**
```bash
# Installera nmap: https://nmap.org/download.html
# Kör sedan:
nmap -sn 192.168.1.0/24
# Leta efter "kia-pi" eller "Raspberry Pi"
```

**Alternativ C: Från din dator (om på samma nätverk)**
```bash
ping kia-pi.local
```

### SSH-anslutning

**Windows (PowerShell eller CMD):**
```bash
ssh pi@192.168.1.XXX
# Byt ut XXX med Pi:ns IP-adress
# Eller:
ssh pi@kia-pi.local

# Första gången får du frågan om fingerprint - svara "yes"
# Ange lösenordet du skapade tidigare
```

**Tips för Windows-användare:**
- Använd [Windows Terminal](https://apps.microsoft.com/store/detail/windows-terminal/9N0DX20HK701) för bästa upplevelse
- Eller [PuTTY](https://www.putty.org/) som alternativ

---

## 🚀 Steg 3A: Installation med direkt Python (REKOMMENDERAT)

### 1. Uppdatera systemet

```bash
# Efter SSH-anslutning:
sudo apt update && sudo apt upgrade -y
# Detta kan ta 5-10 minuter första gången
```

### 2. Installera nödvändiga paket

```bash
sudo apt install -y python3-pip python3-venv git
```

### 3. Skapa arbetskatalog

```bash
mkdir -p ~/kia-climate-control
cd ~/kia-climate-control
```

### 4. Kopiera filer från din Windows-dator

**På din Windows-dator (öppna ny PowerShell/terminal):**

```powershell
# Navigera till din projektkatalog
cd C:\Users\alun\kia-climate-control

# Kopiera filer till Pi:n
# Byt ut "pi@192.168.1.XXX" med dina uppgifter
scp kia_backend.py requirements.txt pi@192.168.1.XXX:~/kia-climate-control/
scp -r public pi@192.168.1.XXX:~/kia-climate-control/

# Kopiera .env om du har den (INTE git-versionerad):
scp .env pi@192.168.1.XXX:~/kia-climate-control/
```

**Alternativt: Använd Git**
```bash
# På Pi:n, om du har projektet på GitHub:
cd ~/kia-climate-control
git clone https://github.com/ditt-användarnamn/kia-climate-control.git .
```

### 5. Skapa virtual environment och installera

```bash
# På Pi:n:
cd ~/kia-climate-control

# Skapa virtual environment
python3 -m venv venv

# Aktivera
source venv/bin/activate

# Uppgradera pip
pip install --upgrade pip

# Installera dependencies
pip install -r requirements.txt
# Detta kan ta 3-5 minuter på Pi 3B
```

### 6. Konfigurera credentials

```bash
# Om du inte kopierade .env, skapa den:
nano .env
```

Lägg till (använd dina egna värden):
```env
KIA_USERNAME=din@email.com
KIA_REFRESH_TOKEN=din_refresh_token_här
KIA_ACCESS_TOKEN=din_access_token_här
PORT=5000
```

**Spara:** `Ctrl+X`, `Y`, `Enter`

ℹ️ _Om du inte har tokens än, kör appen och besök http://raspberry-pi-ip:5000/admin_

### 7. Testa appen

```bash
# Kör appen
python kia_backend.py
```

Du bör se:
```
╔═══════════════════════════════════════╗
║  Kia EV6 Climate Control Server       ║
║  Port: 5000                            ║
║  Python Backend with KiaUvoApiEU      ║
║  Schemaläggning: Aktiv                ║
╚═══════════════════════════════════════╝
```

**Testa i webbläsare:**
- Öppna: `http://192.168.1.XXX:5000`
- Eller: `http://kia-pi.local:5000`

**Stoppa appen:** `Ctrl+C`

### 8. Konfigurera autostart med systemd

```bash
# Skapa service-fil
sudo nano /etc/systemd/system/kia-climate.service
```

Klistra in:
```ini
[Unit]
Description=Kia EV6 Climate Control
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/kia-climate-control
Environment="PATH=/home/pi/kia-climate-control/venv/bin"
ExecStart=/home/pi/kia-climate-control/venv/bin/python kia_backend.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Spara:** `Ctrl+X`, `Y`, `Enter`

```bash
# Aktivera och starta service
sudo systemctl daemon-reload
sudo systemctl enable kia-climate.service
sudo systemctl start kia-climate.service

# Kontrollera status
sudo systemctl status kia-climate.service
# Du bör se "active (running)"

# Visa loggar live
sudo journalctl -u kia-climate.service -f
# Avsluta med Ctrl+C
```

**Klart!** 🎉 Appen startar nu automatiskt vid omstart.

---

## 🚀 Steg 3B: Installation med Docker (ALTERNATIV)

### 1. Installera Docker

```bash
# Installera Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Lägg till pi-användaren i docker-gruppen
sudo usermod -aG docker pi

# Logga ut och in igen för att gruppändringen ska träda i kraft
exit
# SSH:a in igen
```

### 2. Kopiera projektet

```bash
mkdir -p ~/kia-climate-control
cd ~/kia-climate-control

# Kopiera från Windows (se steg 3A, punkt 4)
# Eller använd git
```

### 3. Skapa .env-fil

```bash
nano .env
```

Lägg till:
```env
KIA_USERNAME=din@email.com
KIA_REFRESH_TOKEN=din_refresh_token
KIA_ACCESS_TOKEN=din_access_token
PORT=5000
```

### 4. Bygg och kör

```bash
# Bygg image (tar ~10-15 minuter första gången)
docker build -t kia-climate:latest .

# Kör container
docker run -d \
  --name kia-climate \
  --restart unless-stopped \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  kia-climate:latest

# Visa loggar
docker logs -f kia-climate

# Stoppa container
docker stop kia-climate

# Starta igen
docker start kia-climate
```

---

## 🌐 Steg 4: Extern åtkomst med Cloudflare Tunnel

### Installera cloudflared

```bash
# Ladda ner för ARM64
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb

# Installera
sudo dpkg -i cloudflared-linux-arm64.deb

# Verifiera
cloudflared --version
```

### Snabbtest (tillfällig tunnel)

```bash
cloudflared tunnel --url http://localhost:5000
```

Du får en URL som: `https://random-words.trycloudflare.com`

### Permanent tunnel

Se [CLOUDFLARE-TUNNEL.md](CLOUDFLARE-TUNNEL.md) för fullständig guide.

---

## 🔧 Hantera appen

### Direkt Python-installation

```bash
# Visa status
sudo systemctl status kia-climate.service

# Starta
sudo systemctl start kia-climate.service

# Stoppa
sudo systemctl stop kia-climate.service

# Starta om
sudo systemctl restart kia-climate.service

# Visa loggar
sudo journalctl -u kia-climate.service -f

# Uppdatera appen
cd ~/kia-climate-control
source venv/bin/activate
git pull  # Om du använder git
pip install -r requirements.txt --upgrade
sudo systemctl restart kia-climate.service
```

### Docker-installation

```bash
# Visa status
docker ps -a

# Loggar
docker logs -f kia-climate

# Starta om
docker restart kia-climate

# Stoppa
docker stop kia-climate

# Uppdatera
cd ~/kia-climate-control
git pull
docker build -t kia-climate:latest .
docker stop kia-climate
docker rm kia-climate
# Kör "docker run" kommandot igen från steg 3B
```

---

## 📊 Övervaka prestanda

### htop (Realtidsövervakning)

```bash
# Installera
sudo apt install htop

# Kör
htop
# Tryck F10 för att avsluta
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

---

## 🔒 Säkerhet

### 1. Ändra standard SSH-port (Valfritt men rekommenderat)

```bash
sudo nano /etc/ssh/sshd_config
# Ändra Port 22 till Port 2222
# Spara och starta om SSH:
sudo systemctl restart ssh
```

### 2. Konfigurera brandvägg

```bash
sudo apt install ufw

# Tillåt SSH (använd din port)
sudo ufw allow 22/tcp

# Tillåt Flask-appen (endast från lokalt nätverk)
sudo ufw allow from 192.168.1.0/24 to any port 5000

# Aktivera
sudo ufw enable

# Status
sudo ufw status
```

### 3. Automatiska uppdateringar

```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades
# Välj "Yes"
```

---

## 🆘 Felsökning

### Appen startar inte

```bash
# Kontrollera loggar
sudo journalctl -u kia-climate.service -n 50

# Testa manuellt
cd ~/kia-climate-control
source venv/bin/activate
python kia_backend.py
# Titta på felmeddelanden
```

### Kan inte nå appen från annan dator

```bash
# Kontrollera att appen lyssnar på 0.0.0.0:5000
sudo netstat -tlnp | grep 5000

# Kontrollera brandvägg
sudo ufw status

# Testa från Pi:n själv
curl http://localhost:5000
```

### Python-paket kan inte installeras

```bash
# Installera build-dependencies
sudo apt install python3-dev build-essential

# Försök igen
pip install -r requirements.txt
```

### Out of memory

```bash
# Kontrollera minne
free -h

# Öka swap (om nödvändigt)
sudo nano /etc/dphys-swapfile
# Ändra CONF_SWAPSIZE=100 till CONF_SWAPSIZE=512
sudo systemctl restart dphys-swapfile
```

---

## 📝 Nästa steg

1. ✅ **Testa alla funktioner** i webgränssnittet
2. ✅ **Sätt upp scheman** för klimatkontroll
3. ✅ **Konfigurera Cloudflare Tunnel** för extern åtkomst
4. ✅ **Sätt upp automatiska backups** av .env och data/
5. ✅ **Lägg till övervakningsverktyg** (t.ex. monitoring dashboard)

---

## 💡 Tips

### Statisk IP-adress

```bash
# Redigera dhcpcd.conf
sudo nano /etc/dhcpcd.conf

# Lägg till i slutet (anpassa till ditt nätverk):
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8

# Spara och starta om
sudo reboot
```

### Kör från USB istället för SD-kort

För bättre prestanda och livslängd kan du köra OS från USB:
1. Kopiera SD-kort till USB-disk
2. Uppdatera firmware för USB-boot
3. Boota från USB

Guide: https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#usb-mass-storage-boot

### Backup

```bash
# Backup av viktiga filer
tar -czf kia-backup-$(date +%Y%m%d).tar.gz ~/kia-climate-control/.env ~/kia-climate-control/data/

# Kopiera till Windows-dator
scp pi@192.168.1.XXX:~/kia-backup-*.tar.gz C:\Backups\
```

---

## 📞 Support

Om du stöter på problem:
1. Kontrollera loggarna: `sudo journalctl -u kia-climate.service -f`
2. Testa manuellt: `python kia_backend.py`
3. Kontrollera .env-filen har rätt credentials
4. Besök `/admin` för att hämta nya tokens om nödvändigt

**Lycka till!** 🚗💨
