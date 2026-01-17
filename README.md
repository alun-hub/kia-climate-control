# 🚗 Kia EV6 Climate Control

En modern webbapplikation för att styra klimatanläggningen i din Kia EV6 via Kia UVO API. Schemalägg uppvärmning, starta/stoppa klimat på distans och övervaka fordonsstatus.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![Podman](https://img.shields.io/badge/Podman-Ready-orange)

---

## ✨ Funktioner

### 🌡️ Klimatkontroll
- ✅ Starta/stoppa klimatanläggning på distans
- ✅ Ställ in måltemperatur (16-30°C)
- ✅ Avfrostningsfunktion
- ✅ Se aktuell klimatstatus

### 📅 Schemaläggning
- ✅ Skapa schemalagda klimatstarter
- ✅ Välj specifika veckodagar
- ✅ Aktivera/inaktivera scheman med en knapptryckning
- ✅ Redigera och ta bort befintliga scheman

### 📊 Fordonsstatus
- ✅ Batterinivå med cirkulär gauge
- ✅ Räckvidd
- ✅ Laddningsstatus
- ✅ Dörr- och fönsterstatus
- ✅ Lås-status

### 🔧 Token-hantering (Nytt!)
- ✅ **Inbyggd token-hantering** - Ingen separat script behövs!
- ✅ Visuell steg-för-steg guide för att hämta tokens
- ✅ Automatisk token-utbyte direkt i webbgränssnittet
- ✅ Kopiera User Agent och login-URL med en knapptryckning
- ✅ Real-time anslutningsstatus
- ✅ Uppdatera credentials utan att editera filer manuellt

### 🎨 Användargränssnitt
- ✅ Modernt gradient-baserat UI
- ✅ Responsiv design
- ✅ Mörkt tema
- ✅ Animerad batterimätare
- ✅ Visuell feedback för alla åtgärder

---

## 🚀 Snabbstart

### Utveckling (lokalt)

1. **Klona repositoryt**
   ```bash
   git clone <repo-url>
   cd kia-climate-control
   ```

2. **Skapa virtuell miljö**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Installera dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Starta servern**
   ```bash
   python kia_backend.py
   ```

5. **Konfigurera tokens via webbgränssnittet**

   **Nytt sätt (Rekommenderat):**
   1. Öppna `http://localhost:5000`
   2. Klicka på "🔧 Token-hantering" i övre högra hörnet
   3. Följ den visuella guiden för att hämta dina tokens
   4. Spara direkt i webbgränssnittet - klart!

   **Gammalt sätt (Fortfarande fungerar):**
   - Kör `python get_kia_token.py` och skapa en `.env` fil manuellt

---

## 🐳 Produktion (Podman Container)

**Flask-appen servar både frontend och API** - ingen separat webbserver behövs!

Se [DEPLOYMENT.md](DEPLOYMENT.md) för detaljerad deploymentguide.
För Cloudflare Tunnel deployment, se [CLOUDFLARE-TUNNEL.md](CLOUDFLARE-TUNNEL.md).

### Snabbversion:

```bash
# Bygg container
podman build -t kia-climate-control:latest .

# Skapa data-mapp
mkdir data

# Kör container
podman run -d \
  --name kia-climate-control \
  -p 5000:5000 \
  --env-file .env \
  -v ./data:/app/data:Z \
  --restart unless-stopped \
  kia-climate-control:latest
```

---

## 📋 Förutsättningar

### Kia UVO Credentials
Du behöver:
- **E-postadress** för Kia Connect-appen
- **Refresh Token** från Kia UVO API

#### Hur får jag refresh token?
1. Använd verktyg som [mitmproxy](https://mitmproxy.org/) eller [Fiddler](https://www.telerik.com/fiddler)
2. Logga in i Kia Connect-appen via proxy
3. Fånga upp JWT-tokens från API-anrop
4. Kopiera refresh token

Alternativt, använd existerande skript som `get_kia_token.py`.

---

## 🏗️ Teknisk Stack

### Backend
- **Python 3.12**
- **Flask** - Webbserver
- **hyundai-kia-connect-api** - Kia UVO API integration
- **python-dotenv** - Environment variables

### Frontend
- **Vanilla JavaScript** - Ingen frameworks
- **Modern CSS** - Gradient design
- **SVG** - Cirkulär batterimätare

### Containerization
- **Podman** - Container runtime
- **Alpine/Slim** - Liten image-storlek

---

## 📁 Projektstruktur

```
kia-climate-control/
├── kia_backend.py          # Flask backend
├── public/
│   └── index.html          # Single-page frontend
├── data/                   # Persistent storage (volumes)
│   └── schedules.json      # Schemaläggningar
├── Dockerfile              # Container definition
├── docker-compose.yml      # Compose configuration
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (not in git)
├── .dockerignore          # Docker ignore patterns
├── .gitignore             # Git ignore patterns
├── DEPLOYMENT.md          # Deployment guide
└── README.md              # This file
```

---

## 🔐 Säkerhet

### För Cloudflare Tunnel (Rekommenderat):

Se [CLOUDFLARE-SECURITY.md](CLOUDFLARE-SECURITY.md) för fullständig guide om:
- ✅ **Automatisk HTTPS** och SSL-certifikat
- ✅ **Cloudflare Access** - Autentisering (gratis upp till 50 användare)
- ✅ **Rate limiting** och DDoS-skydd
- ✅ **Ingen öppen port** på din router

### Allmänna rekommendationer:

1. **Secrets Management**
   - Använd Podman secrets istället för .env i produktion
   - Rotera Kia UVO tokens regelbundet

2. **Backups**
   - Säkerhetskopiera `data/schedules.json`
   - Spara credentials säkert

3. **Monitoring**
   - Granska loggar regelbundet
   - Aktivera Cloudflare email-notifieringar

---

## 🤝 Bidra

Bidrag är välkomna! Skapa gärna en pull request eller öppna en issue.

### Utvecklingsriktlinjer:
1. Fork projektet
2. Skapa en feature branch (`git checkout -b feature/amazing-feature`)
3. Commit dina ändringar (`git commit -m 'Add some amazing feature'`)
4. Push till branchen (`git push origin feature/amazing-feature`)
5. Öppna en Pull Request

---

## 📝 License

Detta projekt är licensierat under MIT License - se LICENSE-filen för detaljer.

---

## 🙏 Acknowledgments

- [hyundai-kia-connect-api](https://github.com/Hyundai-Kia-Connect/hyundai_kia_connect_api) - För Kia UVO API-integrationen
- Kia Community - För dokumentation och reverse engineering av Kia UVO API

---

## ⚠️ Disclaimer

Detta projekt är inte officiellt godkänt av Kia. Använd på egen risk. Kia kan när som helst ändra sitt API vilket kan göra denna applikation icke-funktionell.

---

## 📞 Support

För frågor och support:
1. Kontrollera [DEPLOYMENT.md](DEPLOYMENT.md)
2. Öppna en issue på GitHub
3. Kontrollera loggar: `podman logs kia-climate-control`

---

**Utvecklad med ❤️ för Kia EV6-ägare**
