# Raspberry Pi Zero 2W Installation Guide

## Förberedelser

### Hårdvara som behövs
- Raspberry Pi Zero 2W
- microSD-kort (minst 8 GB, rekommenderat 16 GB Class 10)
- Strömadapter (5V 2A rekommenderat)
- Nätverksanslutning (WiFi eller USB-Ethernet adapter)

### Installera Raspberry Pi OS

1. Ladda ner [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Välj **Raspberry Pi OS Lite (64-bit)** för minimal installation
3. Konfigurera WiFi och SSH via Imager innan du skriver
4. Skriv till microSD-kort och starta Pi:n

## Metod 1: Direkt Python-installation (REKOMMENDERAT för Pi Zero 2W)

### Steg 1: Anslut till Pi:n

```bash
ssh pi@raspberry-pi-ip-address
# Standard lösenord är det du satte i Imager
```

### Steg 2: Uppdatera systemet

```bash
sudo apt update
sudo apt upgrade -y
```

### Steg 3: Installera Python och dependencies

```bash
# Installera Python 3 och pip
sudo apt install -y python3-pip python3-venv git

# Installera systembibliotek som kan behövas
sudo apt install -y gcc python3-dev
```

### Steg 4: Ladda ner din app

```bash
# Skapa katalog för appen
mkdir -p ~/kia-climate-control
cd ~/kia-climate-control

# Kopiera filer från din dator (kör på din dator, inte Pi:n):
# scp -r kia_backend.py public/ requirements.txt .env pi@raspberry-pi-ip:~/kia-climate-control/
```

Eller använd git:
```bash
# Om du har koden på GitHub
git clone https://github.com/ditt-användarnamn/kia-climate-control.git
cd kia-climate-control
```

### Steg 5: Skapa virtual environment och installera

```bash
cd ~/kia-climate-control

# Skapa virtual environment
python3 -m venv venv

# Aktivera virtual environment
source venv/bin/activate

# Installera dependencies
pip install -r requirements.txt
```

### Steg 6: Konfigurera .env-fil

```bash
nano .env
```

Lägg till:
```
KIA_USERNAME=din@email.com
KIA_REFRESH_TOKEN=din_refresh_token
KIA_ACCESS_TOKEN=din_access_token
PORT=5000
```

Spara med `Ctrl+X`, `Y`, `Enter`

### Steg 7: Testa appen

```bash
# Kör appen
python kia_backend.py
```

Öppna i webbläsare: `http://raspberry-pi-ip:5000`

### Steg 8: Konfigurera autostart med systemd

Skapa service-fil:
```bash
sudo nano /etc/systemd/system/kia-climate.service
```

Innehåll:
```ini
[Unit]
Description=Kia EV6 Climate Control
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/kia-climate-control
Environment="PATH=/home/pi/kia-climate-control/venv/bin"
ExecStart=/home/pi/kia-climate-control/venv/bin/python kia_backend.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Aktivera och starta:
```bash
sudo systemctl daemon-reload
sudo systemctl enable kia-climate.service
sudo systemctl start kia-climate.service

# Kontrollera status
sudo systemctl status kia-climate.service

# Visa loggar
sudo journalctl -u kia-climate.service -f
```

## Metod 2: Docker (Kräver mer RAM)

⚠️ **VARNING**: Docker + container kan använda 300-400 MB RAM på Pi Zero 2W!

### Installera Docker

```bash
# Installera Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Lägg till pi-användaren i docker-gruppen
sudo usermod -aG docker pi

# Logga ut och in igen för att gruppändringen ska träda i kraft
```

### Bygg och kör med Alpine (lättare)

```bash
cd ~/kia-climate-control

# Bygg med Alpine-version
docker build -f Dockerfile.pi -t kia-climate:latest .

# Kör container
docker run -d \
  --name kia-climate \
  --restart unless-stopped \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -e KIA_USERNAME=din@email.com \
  -e KIA_REFRESH_TOKEN=din_refresh_token \
  -e KIA_ACCESS_TOKEN=din_access_token \
  kia-climate:latest

# Visa loggar
docker logs -f kia-climate
```

## Prestandaoptimering för Pi Zero 2W

### 1. Minska swap-användning (förlänger SD-kortets livslängd)

```bash
sudo nano /etc/dphys-swapfile
# Ändra CONF_SWAPSIZE från 100 till 512
```

### 2. Övervaka resursanvändning

```bash
# Installera htop
sudo apt install htop

# Kör htop för att se RAM/CPU-användning
htop
```

### 3. Logrotation (förhindra att loggar fyller SD-kortet)

```bash
sudo nano /etc/logrotate.d/kia-climate
```

Innehåll:
```
/home/pi/kia-climate-control/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

## Felsökning

### Appen startar inte
```bash
# Kontrollera loggar
sudo journalctl -u kia-climate.service -n 50

# Testa manuellt
cd ~/kia-climate-control
source venv/bin/activate
python kia_backend.py
```

### Out of Memory (OOM)
```bash
# Kontrollera minnesanvändning
free -h

# Om Docker används, överväg att byta till direkt Python-installation
```

### Långsam prestanda
- Detta är normalt för Pi Zero 2W
- Överväg uppgradering till Raspberry Pi 3/4 för bättre prestanda
- Minska antalet samtidiga API-anrop

## Säkerhet

### 1. Ändra standard-lösenord
```bash
passwd
```

### 2. Konfigurera brandvägg
```bash
sudo apt install ufw
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 5000/tcp  # Flask app
sudo ufw enable
```

### 3. Håll systemet uppdaterat
```bash
# Skapa cron-jobb för automatiska uppdateringar
sudo apt install unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades
```

## Prestandajämförelse

| Enhet | RAM | CPU | Rekommendation |
|-------|-----|-----|----------------|
| Pi Zero 2W | 512 MB | 4x1 GHz | OK för 1-2 användare, direkt Python |
| Pi 3B+ | 1 GB | 4x1.4 GHz | Bra, Docker OK |
| Pi 4 (2GB) | 2 GB | 4x1.5 GHz | Utmärkt, flera containers |
| Pi 4 (4GB+) | 4-8 GB | 4x1.5 GHz | Perfekt, många services |

## Strömförbrukning

- Pi Zero 2W: ~1-2W idle, ~3-4W under last
- Med WiFi + USB-Ethernet: ~5W
- Rekommenderad adapter: 5V 2A (10W)

## Nästa steg

- Konfigurera statisk IP-adress
- Sätt upp Cloudflare Tunnel (se CLOUDFLARE-TUNNEL.md)
- Backup av .env-fil regelbundet
- Överväg att köra från USB istället för SD-kort för bättre prestanda och livslängd
