# Cloudflare Tunnel - Säkerhetskonfiguration

## Översikt

Denna guide visar hur du konfigurerar:
1. **Tvinga HTTPS** - Endast säkra anslutningar
2. **SSL/TLS-certifikat** - Automatiskt via Cloudflare
3. **Autentisering** - Cloudflare Access (Zero Trust)

---

## Del 1: Tvinga HTTPS

Cloudflare Tunnel använder **automatiskt HTTPS** för all extern trafik, men vi ska säkerställa att HTTP omdirigeras till HTTPS.

### Steg 1: Aktivera "Always Use HTTPS"

1. Logga in på [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Välj din domän
3. Gå till **SSL/TLS** → **Edge Certificates**
4. Scrolla ner till **Always Use HTTPS**
5. Aktivera "Always Use HTTPS"

✅ Nu kommer alla HTTP-förfrågningar automatiskt att omdirigeras till HTTPS

### Steg 2: Sätt SSL/TLS-läge

1. I Cloudflare Dashboard, gå till **SSL/TLS** → **Overview**
2. Välj SSL/TLS-krypteringsläge:

**Rekommenderat: Full (strict)**
```
Browser ←[HTTPS]→ Cloudflare ←[HTTP]→ Flask App (localhost:5000)
```

Välj **"Full"** eller **"Full (strict)"**:
- **Full**: Cloudflare krypterar till din server, men validerar inte certifikatet
- **Full (strict)**: Validerar certifikat (kräver eget cert på servern)

För Cloudflare Tunnel, använd **"Full"** - tunneln hanterar kryptering automatiskt.

✅ SSL/TLS-certifikat skapas automatiskt av Cloudflare (gratis, förnyar sig automatiskt)

---

## Del 2: Cloudflare Access (Autentisering)

Cloudflare Access är en Zero Trust-lösning som lägger autentisering framför din app. Gratis för upp till 50 användare!

### Steg 1: Aktivera Zero Trust

1. Gå till [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Klicka på **Zero Trust** i vänstermenyn
3. Om du inte har det aktiverat, klicka **Get started**
4. Välj en subdomain för ditt Zero Trust team (t.ex. `mittteam.cloudflareaccess.com`)

### Steg 2: Skapa en Access Application

1. I Zero Trust Dashboard, gå till **Access** → **Applications**
2. Klicka **Add an application**
3. Välj **Self-hosted**

#### Application Details:
```
Application name: Kia EV6 Climate Control
Session Duration: 24 hours
Application domain:
  - kia.dindomän.se
```

#### Identity Providers (IdP):

Välj hur användare ska logga in. Alternativ:

**A) One-time PIN (Enklast)**
- Användare får en PIN-kod via email
- Konfiguration:
  1. Välj **One-time PIN**
  2. Lägg till godkända email-adresser

**B) Google OAuth**
- Logga in med Google-konto
- Konfiguration:
  1. Välj **Google**
  2. Ingen extra konfiguration krävs för grundläggande användning

**C) Microsoft/GitHub/etc.**
- Stöd för många identity providers
- Kräver OAuth-konfiguration

### Steg 3: Skapa Access Policy

Efter att ha skapat applikationen, lägg till en policy:

#### Policy 1: Tillåt specifika email-adresser

```
Policy name: Godkända användare
Action: Allow
Session duration: 24 hours

Include:
  - Selector: Emails
  - Value: din@email.com, annan@email.com
```

#### Policy 2: Tillåt specifik domän (om alla på företaget ska ha åtkomst)

```
Policy name: Företagsanvändare
Action: Allow
Session duration: 24 hours

Include:
  - Selector: Email ending in
  - Value: @dindomän.se
```

### Steg 4: Applicera och testa

1. Klicka **Save application**
2. Besök din URL: `https://kia.dindomän.se`
3. Du ska nu mötas av Cloudflare Access login-sida
4. Logga in med din valda metod (email PIN, Google, etc.)
5. Efter lyckad inloggning kommer du åt appen

---

## Del 3: Avancerade säkerhetsinställningar

### HSTS (HTTP Strict Transport Security)

Tvingar webbläsare att alltid använda HTTPS.

1. Gå till **SSL/TLS** → **Edge Certificates**
2. Scrolla ner till **HTTP Strict Transport Security (HSTS)**
3. Klicka **Enable HSTS**
4. Rekommenderade inställningar:
   ```
   Max Age Header: 6 months
   Apply HSTS to subdomains: No (om du bara har kia.dindomän.se)
   Preload: No (inte nödvändigt för privat app)
   No-Sniff Header: Yes
   ```

### Authenticated Origin Pulls (Extra säkerhet)

Säkerställer att endast Cloudflare kan ansluta till din server.

**OBS:** Inte nödvändigt för Cloudflare Tunnel då tunneln redan är säker.

### Rate Limiting

Begränsa antal requests per IP för att förhindra missbruk.

1. Gå till **Security** → **WAF**
2. Klicka **Rate limiting rules**
3. Skapa regel:
   ```
   Rule name: API Rate Limit
   When incoming requests match:
     - Hostname equals kia.dindomän.se
     - URI Path starts with /api/
   Then:
     - Action: Block
     - For: 1 minute
     - When rate exceeds: 100 requests per 1 minute
   ```

---

## Del 4: Komplett Cloudflare Tunnel Config med säkerhet

Uppdatera din `~/.cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL_ID>
credentials-file: /home/user/.cloudflared/<TUNNEL_ID>.json

ingress:
  # Kia Climate Control app med säkerhet
  - hostname: kia.dindomän.se
    service: http://localhost:5000
    # Origin server name för TLS-verifiering (valfritt)
    originRequest:
      noTLSVerify: true  # Eftersom vi använder HTTP lokalt

  # Catch-all
  - service: http_status:404
```

---

## Del 5: Verifiera säkerhetskonfigurationen

### Test 1: Tvingad HTTPS
```bash
curl -I http://kia.dindomän.se
# Ska returnera 301/302 redirect till https://
```

### Test 2: SSL-certifikat
```bash
# Kontrollera certifikat
openssl s_client -connect kia.dindomän.se:443 -servername kia.dindomän.se

# Eller i webbläsare: Klicka på hänglåset → "Connection is secure"
```

### Test 3: Access-autentisering
```bash
# Besök i inkognito/privat läge
https://kia.dindomän.se

# Ska omdirigera till Cloudflare Access login
```

---

## Exempel: Komplett säkerhetskonfiguration

### Scenario: Hemmabruk, endast du och partner

**Identity Provider:** One-time PIN via email

**Access Policy:**
```
Policy name: Familjemedlemmar
Action: Allow
Include:
  - Selector: Emails
  - Values:
      - din@email.com
      - partner@email.com
```

**SSL/TLS:** Full
**Always Use HTTPS:** Aktiverad
**HSTS:** Aktiverad (6 månader)

### Scenario: Dela med vänner (begränsat)

**Identity Provider:** Google OAuth

**Access Policy:**
```
Policy name: Godkända Google-konton
Action: Allow
Include:
  - Selector: Emails
  - Values:
      - din@gmail.com
      - van1@gmail.com
      - van2@gmail.com
```

**Rate Limiting:** 100 requests/minut per IP

---

## Felsökning

### Problem: "Too many redirects"
**Lösning:** Ändra SSL/TLS-läge till "Full" eller "Flexible"

### Problem: Kan inte logga in via Access
**Lösning:**
- Kontrollera att din email finns i Access Policy
- Kolla spam-mapp för PIN-kod
- Verifiera att Identity Provider är korrekt konfigurerad

### Problem: Certifikatvarning i webbläsare
**Lösning:**
- Vänta några minuter (Cloudflare genererar certifikat)
- Kontrollera att DNS pekar korrekt till Cloudflare
- Verifiera att tunneln körs

---

## Kostnad

| Funktion | Kostnad |
|----------|---------|
| Cloudflare Tunnel | Gratis |
| SSL/TLS-certifikat | Gratis |
| DDoS-skydd | Gratis |
| Cloudflare Access | Gratis (upp till 50 användare) |
| Rate Limiting | Gratis (grundläggande) |
| WAF Rules | Gratis (5 regler) |

---

## Sammanfattning

Med denna konfiguration har du:

✅ **HTTPS** - Automatisk kryptering via Cloudflare
✅ **SSL-certifikat** - Gratis, automatiskt förnyade
✅ **Autentisering** - Endast godkända användare kommer åt appen
✅ **DDoS-skydd** - Cloudflare skyddar automatiskt
✅ **Rate limiting** - Förhindrar missbruk
✅ **Ingen öppen port** - Allt går genom säker tunnel
✅ **Global CDN** - Snabb åtkomst från hela världen

**Din Kia EV6 Climate Control är nu säkert tillgänglig via internet! 🔒🚗**

---

## Nästa steg

1. Aktivera email-notifieringar för säkerhetsvarningar
2. Sätt upp 2FA på ditt Cloudflare-konto
3. Överväg att lägga till IP-whitelist för extra säkerhet
4. Granska Access-loggar regelbundet

---

**Frågor?** Kolla [Cloudflare Docs](https://developers.cloudflare.com/cloudflare-one/) för mer information.
