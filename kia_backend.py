#!/usr/bin/env python3
"""
Kia EV6 Climate Control Backend (Python)
Stabiliserad schemaläggning + token refresh
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from hyundai_kia_connect_api.KiaUvoApiEU import KiaUvoApiEU
from hyundai_kia_connect_api.ApiImplType1 import ClimateRequestOptions
from hyundai_kia_connect_api.exceptions import AuthenticationError
import os
from dotenv import load_dotenv
import logging
from datetime import datetime, timezone, timedelta
import json
import threading
import time
import errno

# ---------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

api = None
token = None
vehicle = None
api_lock = threading.RLock()
init_cooldown_until = 0
init_backoff_seconds = 0
last_vehicle_refresh_ts = 0
last_success_at = None
last_error = None
last_error_at = None
last_cooldown_log_ts = 0

# ---------------------------------------------------------------------
# Kia helpers
# ---------------------------------------------------------------------

def initialize_kia():
    """(Re)initialize Kia API connection"""
    global api, token, vehicle, init_cooldown_until, init_backoff_seconds
    global last_success_at, last_error, last_error_at

    try:
        with api_lock:
            now = time.time()
            if now < init_cooldown_until:
                wait = int(init_cooldown_until - now)
                logger.warning(f"Initierar ej Kia API (cooldown {wait}s kvar)")
                return False

            logger.info("Initierar Kia API...")

            api = KiaUvoApiEU(
                region=1,      # Europe
                brand=1,       # Kia
                language="sv"
            )

            username = os.getenv("KIA_USERNAME")
            refresh_token = os.getenv("KIA_REFRESH_TOKEN")

            token = api.login(username, refresh_token)

            vehicles = api.get_vehicles(token)
            if not vehicles:
                raise Exception("Inga fordon hittades")

            vehicle = vehicles[0]

            logger.info(f"✓ Ansluten till fordon: {getattr(vehicle, 'id', 'EV6')}")
            last_success_at = datetime.now().isoformat()
            last_error = None
            last_error_at = None
            init_cooldown_until = 0
            init_backoff_seconds = 0
            return True

    except Exception as e:
        last_error = str(e)
        last_error_at = datetime.now().isoformat()
        msg = str(e).lower()
        if "exceeds number of requests" in msg:
            init_backoff_seconds = max(init_backoff_seconds * 2, 120)
            init_backoff_seconds = min(init_backoff_seconds, 600)
            init_cooldown_until = time.time() + init_backoff_seconds
            logger.error(f"✗ Kia init misslyckades: {e} (cooldown {init_backoff_seconds}s)")
        else:
            init_cooldown_until = time.time() + 30
        logger.error(f"✗ Kia init misslyckades: {e}")
        return False

def get_cooldown_seconds():
    now = time.time()
    if now < init_cooldown_until:
        return int(init_cooldown_until - now)
    return 0


def _token_is_expired_or_near_expiry(margin_seconds=300):
    """Check if the current access token is expired or will expire soon."""
    if token is None:
        return True
    try:
        now = datetime.now(timezone.utc)
        expires_at = token.valid_until
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return now >= (expires_at - timedelta(seconds=margin_seconds))
    except Exception:
        return False


def _refresh_token_if_needed():
    """Attempt to refresh the access token. Returns True on success."""
    global token, last_success_at, last_error, last_error_at
    try:
        logger.info("Förnyar access token...")
        new_token = api.refresh_access_token(token)
        if isinstance(new_token, object) and hasattr(new_token, 'access_token'):
            token = new_token
            last_success_at = datetime.now().isoformat()
            last_error = None
            last_error_at = None
            logger.info("✓ Access token förnyad")
            return True
        else:
            logger.warning("refresh_access_token returnerade oväntat resultat, gör full re-init")
            return False
    except Exception as e:
        logger.warning(f"Token-förnyelse misslyckades: {e}")
        return False


def invalidate_session():
    """Mark the current session as invalid so next ensure_token triggers re-init."""
    global token
    token = None
    logger.info("Session ogiltigförklarad – nästa anrop gör re-login")


def ensure_token(force_reinit=False, allow_init=True):
    """Ensure we have a valid, non-expired token/session.

    If allow_init is False, never reinitialize (useful to avoid background retries).
    """
    global api, token, vehicle, last_vehicle_refresh_ts, last_cooldown_log_ts

    try:
        # Guard shared API/session state across threads
        with api_lock:
            needs_init = force_reinit or api is None or token is None or vehicle is None

            # Proactively refresh if token is about to expire (5 min margin)
            if not needs_init and _token_is_expired_or_near_expiry():
                logger.info("Access token utgången eller nära utgång")
                if _refresh_token_if_needed():
                    return True
                # Refresh failed, need full re-init
                needs_init = True

            if needs_init:
                cooldown = get_cooldown_seconds()
                if cooldown > 0 or not allow_init:
                    now = time.time()
                    if now - last_cooldown_log_ts > 60:
                        logger.warning("Initierar ej Kia API (cooldown/allow_init)")
                        last_cooldown_log_ts = now
                    return False

                logger.warning("Token/API saknas eller force_reinit – initierar om")
                return initialize_kia()

            return True

    except Exception as e:
        logger.error(f"ensure_token misslyckades: {e}")
        return False


def build_climate_options(temperature, defrost):
    """Correct & stable climate options for EV6 EU"""
    options = ClimateRequestOptions()
    options.climate = True
    options.heating = 1
    options.airCtrl = True
    options.defrost = bool(defrost)
    options.set_temp = int(temperature)
    return options


def _send_climate_start(options):
    """Send start_climate command, handling auth errors. Returns (ok, error_msg)."""
    try:
        with api_lock:
            api.start_climate(token, vehicle, options)
        return True, None
    except AuthenticationError as e:
        logger.warning(f"Token utgången vid klimatstart: {e}")
        invalidate_session()
        if not ensure_token():
            return False, "Token utgången, kunde inte förnya"
        try:
            with api_lock:
                api.start_climate(token, vehicle, options)
            return True, None
        except Exception as e2:
            return False, str(e2)
    except Exception as e:
        return False, str(e)


def _verify_climate_active():
    """Check if climate is actually running. Returns True/False, or None if check failed."""
    try:
        with api_lock:
            api.update_vehicle_with_cached_state(token, vehicle)
        return getattr(vehicle, 'air_control_is_on', False)
    except AuthenticationError:
        invalidate_session()
        if not ensure_token():
            return None
        try:
            with api_lock:
                api.update_vehicle_with_cached_state(token, vehicle)
            return getattr(vehicle, 'air_control_is_on', False)
        except Exception:
            return None
    except Exception as e:
        logger.warning(f"Kunde inte verifiera klimatstatus: {e}")
        return None


def start_climate_verified(options, max_attempts=2, verify_delay=25):
    """Start climate, verify it's running, retry if not.

    Returns (success: bool, message: str, verified: bool).
    """
    for attempt in range(1, max_attempts + 1):
        ok, err = _send_climate_start(options)
        if not ok:
            if attempt < max_attempts:
                logger.warning(f"Klimatstart misslyckades (försök {attempt}/{max_attempts}): {err} – väntar {verify_delay}s och gör re-login")
                time.sleep(verify_delay)
                invalidate_session()
                ensure_token()
                continue
            return False, f"Klimatstart misslyckades: {err}", False

        logger.info(f"Klimatstart-kommando skickat (försök {attempt}/{max_attempts}), väntar {verify_delay}s...")
        time.sleep(verify_delay)

        is_active = _verify_climate_active()

        if is_active is True:
            logger.info(f"✓ Klimat verifierad som aktiv (försök {attempt})")
            return True, "Klimat startad och verifierad", True

        if is_active is None:
            logger.warning(f"Kunde inte verifiera klimat (försök {attempt})")
            # Can't verify — assume the command went through
            return True, "Klimat startad (kunde inte verifiera status)", False

        # is_active is False
        if attempt < max_attempts:
            logger.warning(f"Klimat INTE aktiv efter försök {attempt} – försöker igen")
        else:
            logger.error(f"Klimat INTE aktiv efter {max_attempts} försök")

    return False, f"Klimat startades {max_attempts} gånger men verifiering visar att den inte är aktiv", False


# Init on startup
initialize_kia()

# ---------------------------------------------------------------------
# Basic routes
# ---------------------------------------------------------------------

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/admin')
def admin():
    return send_from_directory('public', 'admin.html')


@app.route('/api/health')
def health():
    return jsonify({
        "status": "ok",
        "connected": api is not None and token is not None and vehicle is not None,
        "cooldown_seconds": get_cooldown_seconds(),
        "last_success_at": last_success_at,
        "last_error": last_error,
        "last_error_at": last_error_at,
        "timestamp": datetime.now().isoformat()
    })

# ---------------------------------------------------------------------
# Token/credentials management
# ---------------------------------------------------------------------

@app.route('/api/credentials', methods=['GET'])
def get_credentials():
    """Get current credentials (username only, not full tokens)."""
    try:
        username = os.getenv('KIA_USERNAME', '')
        has_refresh_token = bool(os.getenv('KIA_REFRESH_TOKEN'))
        has_access_token = bool(os.getenv('KIA_ACCESS_TOKEN'))

        return jsonify({
            'success': True,
            'username': username,
            'refresh_token': '***' if has_refresh_token else '',
            'access_token': '***' if has_access_token else '',
            'has_credentials': bool(username and has_refresh_token),
            'connected': token is not None and vehicle is not None
        })
    except Exception as e:
        logger.error(f"Get credentials error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/token-urls', methods=['GET'])
def get_token_urls():
    """Get the URLs needed for token generation flow."""
    try:
        from urllib.parse import quote

        auth_domain = "https://idpconnect-eu.kia.com"
        url_authorize_redirect = "https://www.kia.com/api/bin/oneid/login"
        url_authorize_redirect_quoted = quote(url_authorize_redirect, safe='', encoding=None, errors=None)
        url_redirect = "https://prd.eu-ccapi.kia.com:8080/api/v1/user/oauth2/redirect"
        client_id = "fdc85c00-0a2f-4c64-bcb4-2cfb1500730a"

        url_login = (
            f"{auth_domain}/auth/api/v2/user/oauth2/authorize?"
            f"ui_locales=de&"
            f"scope=openid+profile+email+phone&"
            f"response_type=code&"
            f"client_id=peukiaidm-online-sales&"
            f"redirect_uri={url_authorize_redirect_quoted}&"
            f"state=aHR0cHM6Ly93d3cua2lhLmNvbS9kZS8"
        )

        user_agent = (
            "Mozilla/5.0 (Linux; Android 4.1.1; Galaxy Nexus Build/JRO03C) "
            "AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19_CCS_APP_AOS"
        )

        return jsonify({
            'success': True,
            'login_url': url_login,
            'user_agent': user_agent,
            'redirect_url': url_redirect,
            'auth_domain': auth_domain,
            'client_id': client_id
        })
    except Exception as e:
        logger.error(f"Get token URLs error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/get-auth-url', methods=['GET'])
def get_auth_url():
    """Generate the authorization URL after login."""
    try:
        import requests
        from urllib.parse import urlparse, parse_qs

        auth_domain = "https://idpconnect-eu.kia.com"
        url_redirect = "https://prd.eu-ccapi.kia.com:8080/api/v1/user/oauth2/redirect"
        client_id = "fdc85c00-0a2f-4c64-bcb4-2cfb1500730a"
        user_agent = (
            "Mozilla/5.0 (Linux; Android 4.1.1; Galaxy Nexus Build/JRO03C) "
            "AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.166 Mobile Safari/535.19_CCS_APP_AOS"
        )

        session = requests.Session()
        session.headers.update({
            "User-Agent": user_agent,
            "Accept-Language": "de-DE,de;q=0.9",
        })

        url = (
            f"{auth_domain}/auth/api/v2/user/oauth2/authorize?"
            f"response_type=code&"
            f"client_id={client_id}&"
            f"redirect_uri={url_redirect}&"
            f"lang=de&"
            f"state=ccsp"
        )

        response = session.get(url)

        try:
            url_parsed = urlparse(response.url)
            url_queries = parse_qs(url_parsed.query)
            next_uri = url_queries["next_uri"][0]
            next_uri_parsed = urlparse(next_uri)
            next_uri_queries = parse_qs(next_uri_parsed.query)
            connector_session_key = next_uri_queries["connector_session_key"][0]

            auth_url = (
                f"{auth_domain}/auth/api/v2/user/oauth2/authorize?"
                f"client_id={client_id}&"
                f"redirect_uri={url_redirect}&"
                f"response_type=code&"
                f"scope=&"
                f"state=ccsp&"
                f"connector_client_id=hmgid1.0-{client_id}&"
                f"ui_locales=&"
                f"connector_scope=&"
                f"connector_session_key={connector_session_key}"
            )

            return jsonify({
                'success': True,
                'auth_url': auth_url
            })
        except Exception as e:
            logger.error(f"Could not extract connector_session_key: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Kunde inte generera authorization URL: {str(e)}'
            }), 500

    except Exception as e:
        logger.error(f"Get auth URL error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/exchange-code', methods=['POST'])
def exchange_code():
    """Exchange authorization code for tokens."""
    try:
        import requests
        from urllib.parse import urlparse, parse_qs
        import base64

        data = request.get_json(silent=True) or {}
        redirect_url = data.get('redirect_url', '')

        if not redirect_url:
            return jsonify({
                'success': False,
                'message': 'Redirect URL krävs'
            }), 400

        try:
            url_parsed = urlparse(redirect_url)
            url_queries = parse_qs(url_parsed.query)
            authorization_code = url_queries["code"][0]
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Kunde inte extrahera authorization code från URL: {str(e)}'
            }), 400

        auth_domain = "https://idpconnect-eu.kia.com"
        url_redirect = "https://prd.eu-ccapi.kia.com:8080/api/v1/user/oauth2/redirect"
        client_id = "fdc85c00-0a2f-4c64-bcb4-2cfb1500730a"

        token_url = f"{auth_domain}/auth/api/v2/user/oauth2/token"
        token_data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": url_redirect,
            "client_id": client_id,
            "client_secret": "secret",
        }

        response = requests.post(token_url, data=token_data)

        if response.status_code == 200:
            tokens = response.json()

            expires_in_hours = 24
            try:
                access_token = tokens.get('access_token', '')
                parts = access_token.split('.')
                if len(parts) >= 2:
                    payload = parts[1]
                    padding = 4 - (len(payload) % 4)
                    if padding != 4:
                        payload += '=' * padding

                    decoded_bytes = base64.urlsafe_b64decode(payload)
                    decoded_str = decoded_bytes.decode('utf-8')

                    import json as json_module
                    payload_data = json_module.loads(decoded_str)

                    if 'exp' in payload_data:
                        from datetime import timezone
                        exp_timestamp = payload_data['exp']
                        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                        now = datetime.now(timezone.utc)
                        expires_in_seconds = (exp_datetime - now).total_seconds()
                        expires_in_hours = max(1, int(expires_in_seconds / 3600))
            except Exception as e:
                logger.warning(f"Could not decode token expiry: {str(e)}")

            return jsonify({
                'success': True,
                'refresh_token': tokens.get('refresh_token'),
                'access_token': tokens.get('access_token'),
                'expires_in_hours': expires_in_hours
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Fel vid hämtning av tokens: {response.text}'
            }), 500

    except Exception as e:
        logger.error(f"Exchange code error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/credentials', methods=['POST'])
def update_credentials():
    """Update credentials and reinitialize connection."""
    try:
        data = request.get_json(silent=True) or {}
        new_username = data.get('username')
        new_refresh_token = data.get('refresh_token')
        new_access_token = data.get('access_token', '')

        if not new_username or not new_refresh_token:
            return jsonify({
                'success': False,
                'message': 'Både e-post och refresh token krävs'
            }), 400

        os.environ['KIA_USERNAME'] = new_username
        os.environ['KIA_REFRESH_TOKEN'] = new_refresh_token
        if new_access_token:
            os.environ['KIA_ACCESS_TOKEN'] = new_access_token

        env_path = '/app/.env' if os.path.exists('/app/.env') or os.path.exists('/app') else '.env'

        env_vars = {}
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key] = value
            except Exception as e:
                logger.warning(f"Could not read existing .env: {str(e)}")

        env_vars['KIA_USERNAME'] = new_username
        env_vars['KIA_REFRESH_TOKEN'] = new_refresh_token
        if new_access_token:
            env_vars['KIA_ACCESS_TOKEN'] = new_access_token
        if 'PORT' not in env_vars:
            env_vars['PORT'] = '5000'

        try:
            with open(env_path, 'w') as f:
                for key, value in env_vars.items():
                    f.write(f'{key}={value}\n')
            logger.info(f"Credentials saved to {env_path}")
        except Exception as e:
            logger.error(f"Failed to save credentials to {env_path}: {str(e)}")
            raise

        logger.info("Återansluter med nya uppgifter...")
        if initialize_kia():
            return jsonify({
                'success': True,
                'message': 'Uppgifter sparade och anslutning upprättad'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Uppgifter sparade men anslutning misslyckades. Kontrollera dina uppgifter.'
            }), 500

    except Exception as e:
        logger.error(f"Update credentials error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Fel vid uppdatering: {str(e)}'
        }), 500


# ---------------------------------------------------------------------
# Vehicle status
# ---------------------------------------------------------------------

@app.route('/api/status')
def status():
    if not ensure_token():
        cooldown = get_cooldown_seconds()
        if cooldown > 0:
            return jsonify(success=False, code="rate_limit", message=f"Rate-limit – försök igen om {cooldown}s", retry_after=cooldown), 429
        return jsonify(success=False, code="not_connected", message="Ej ansluten"), 401

    try:
        with api_lock:
            api.update_vehicle_with_cached_state(token, vehicle)
    except AuthenticationError as e:
        logger.warning(f"Token utgången vid statushämtning: {e} – försöker förnya")
        invalidate_session()
        if not ensure_token():
            return jsonify(success=False, code="not_connected", message="Token utgången, kunde inte förnya"), 401
        try:
            with api_lock:
                api.update_vehicle_with_cached_state(token, vehicle)
        except Exception as e2:
            logger.exception(f"Status-fel efter token-förnyelse: {e2}")
            return jsonify(success=False, code="status_error", message="Kunde inte hämta status"), 502
    except Exception as e:
        logger.exception(f"Status-fel: {e}")
        return jsonify(success=False, code="status_error", message="Kunde inte hämta status"), 502

    # Default door/window status
    door_status = {
        "driver": False,
        "passenger": False,
        "backLeft": False,
        "backRight": False,
        "hood": False,
        "trunk": False
    }
    window_status = {
        "driver": False,
        "passenger": False,
        "backLeft": False,
        "backRight": False
    }

    if hasattr(vehicle, 'data') and vehicle.data:
        status_data = vehicle.data.get('vehicleStatus', {})
        door_status = {
            "driver": status_data.get('doorOpen', {}).get('frontLeft') == 1,
            "passenger": status_data.get('doorOpen', {}).get('frontRight') == 1,
            "backLeft": status_data.get('doorOpen', {}).get('backLeft') == 1,
            "backRight": status_data.get('doorOpen', {}).get('backRight') == 1,
            "hood": status_data.get('hoodOpen') == 1,
            "trunk": status_data.get('trunkOpen') == 1
        }
        window_status = {
            "driver": status_data.get('windowOpen', {}).get('frontLeft') == 1,
            "passenger": status_data.get('windowOpen', {}).get('frontRight') == 1,
            "backLeft": status_data.get('windowOpen', {}).get('backLeft') == 1,
            "backRight": status_data.get('windowOpen', {}).get('backRight') == 1
        }

    return jsonify(success=True, data={
        "battery": getattr(vehicle, "ev_battery_percentage", 0),
        "range": getattr(vehicle, "ev_driving_range", 0),
        "charging": getattr(vehicle, "ev_battery_is_charging", False),
        "pluggedIn": getattr(vehicle, "ev_battery_is_plugged_in", False),
        "locked": getattr(vehicle, "is_locked", False),
        "climateActive": getattr(vehicle, "air_control_is_on", False),
        "doors": door_status,
        "windows": window_status,
        "lastUpdated": datetime.now().isoformat()
    })


# ---------------------------------------------------------------------
# Climate control
# ---------------------------------------------------------------------

@app.route('/api/climate/start', methods=['POST'])
def start_climate():
    if not ensure_token():
        return jsonify(success=False, message="Ej ansluten"), 401

    data = request.get_json(silent=True) or {}
    options = build_climate_options(
        data.get("temperature", 21),
        data.get("defrost", False)
    )

    success, message, verified = start_climate_verified(options)
    status_code = 200 if success else 502
    return jsonify(success=success, message=message, verified=verified), status_code


@app.route('/api/climate/stop', methods=['POST'])
def stop_climate():
    if not ensure_token():
        return jsonify(success=False, message="Ej ansluten"), 401

    try:
        with api_lock:
            api.stop_climate(token, vehicle)
        return jsonify(success=True, message="Klimat stoppad")
    except AuthenticationError as e:
        logger.warning(f"Token utgången vid klimatstopp: {e} – försöker förnya")
        invalidate_session()
        if not ensure_token():
            return jsonify(success=False, message="Token utgången, kunde inte förnya"), 401
        try:
            with api_lock:
                api.stop_climate(token, vehicle)
            return jsonify(success=True, message="Klimat stoppad")
        except Exception as e2:
            logger.exception(f"Klimat stopp-fel efter token-förnyelse: {e2}")
            return jsonify(success=False, message="Kunde inte stoppa klimat"), 502
    except Exception as e:
        logger.exception(f"Klimat stopp-fel: {e}")
        return jsonify(success=False, message="Kunde inte stoppa klimat"), 502


# ---------------------------------------------------------------------
# Schedule storage
# ---------------------------------------------------------------------

def schedules_path():
    return "/app/data/schedules.json" if os.path.exists("/app/data") else "schedules.json"

def load_schedules_with_retry(path, retries=3, delay=0.2):
    """Read schedules with basic retry to avoid partial writes."""
    last_error = None
    for _ in range(retries):
        try:
            with open(path) as f:
                return json.load(f)
        except FileNotFoundError:
            return []
        except json.JSONDecodeError as e:
            last_error = e
            time.sleep(delay)
        except OSError as e:
            # Retry on transient read errors
            if e.errno in (errno.EAGAIN, errno.EACCES, errno.EINTR):
                last_error = e
                time.sleep(delay)
            else:
                raise
    if last_error:
        raise last_error
    return []

def save_schedules_atomic(path, schedules):
    """Write schedules atomically to avoid corrupt files."""
    directory = os.path.dirname(path) or "."
    tmp_path = os.path.join(directory, f".schedules.tmp.{os.getpid()}")
    with open(tmp_path, 'w') as f:
        json.dump(schedules, f, indent=2)
    os.replace(tmp_path, path)

@app.route('/api/schedules', methods=['GET'])
def get_schedules():
    try:
        schedules = load_schedules_with_retry(schedules_path())
        return jsonify(success=True, schedules=schedules)
    except Exception as e:
        logger.exception(f"Kunde inte läsa schema: {e}")
        return jsonify(success=False, message="Kunde inte läsa schema"), 500


@app.route('/api/schedules', methods=['POST'])
def save_schedule():
    """Save or update a climate schedule."""
    try:
        data = request.get_json(silent=True) or {}
        schedules = load_schedules_with_retry(schedules_path())

        schedule = {
            'id': data.get('id', str(datetime.now().timestamp())),
            'name': data.get('name', 'Ny schemaläggning'),
            'time': data.get('time'),
            'temperature': data.get('temperature', 21),
            'defrost': data.get('defrost', False),
            'days': data.get('days', []),
            'enabled': data.get('enabled', True)
        }

        schedule_exists = False
        for i, s in enumerate(schedules):
            if s.get('id') == schedule['id']:
                schedules[i] = schedule
                schedule_exists = True
                break

        if not schedule_exists:
            schedules.append(schedule)

        save_schedules_atomic(schedules_path(), schedules)

        return jsonify(success=True, message='Schemaläggning sparad', schedule=schedule)

    except Exception as e:
        logger.exception(f"Save schedule error: {e}")
        return jsonify(success=False, message=str(e)), 500


@app.route('/api/schedules/<schedule_id>/toggle', methods=['PATCH'])
def toggle_schedule(schedule_id):
    """Toggle a climate schedule enabled/disabled."""
    try:
        data = request.get_json(silent=True) or {}
        enabled = data.get('enabled', True)
        schedules = load_schedules_with_retry(schedules_path())

        for s in schedules:
            if s.get('id') == schedule_id:
                s['enabled'] = enabled
                break

        save_schedules_atomic(schedules_path(), schedules)

        return jsonify(success=True, message=f'Schema {"aktiverat" if enabled else "inaktiverat"}')

    except Exception as e:
        logger.exception(f"Toggle schedule error: {e}")
        return jsonify(success=False, message=str(e)), 500


@app.route('/api/schedules/<schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    """Delete a climate schedule."""
    try:
        schedules = load_schedules_with_retry(schedules_path())
        schedules = [s for s in schedules if s.get('id') != schedule_id]

        save_schedules_atomic(schedules_path(), schedules)

        return jsonify(success=True, message='Schemaläggning borttagen')

    except Exception as e:
        logger.exception(f"Delete schedule error: {e}")
        return jsonify(success=False, message=str(e)), 500


# ---------------------------------------------------------------------
# Schedule worker (FIXED)
# ---------------------------------------------------------------------


# ---------------------------------------------------------------------
# Charging control
# ---------------------------------------------------------------------

@app.route('/api/charging/start', methods=['POST'])
def start_charging():
    """Start charging."""
    try:
        if not ensure_token():
            return jsonify(success=False, message="Ej ansluten"), 401

        with api_lock:
            api.start_charge(token, vehicle)

        return jsonify(success=True, message="Laddning startad")
    except AuthenticationError as e:
        logger.warning(f"Token utgången vid laddningsstart: {e} – försöker förnya")
        invalidate_session()
        if not ensure_token():
            return jsonify(success=False, message="Token utgången, kunde inte förnya"), 401
        try:
            with api_lock:
                api.start_charge(token, vehicle)
            return jsonify(success=True, message="Laddning startad")
        except Exception as e2:
            logger.exception(f"Start charging error efter token-förnyelse: {e2}")
            return jsonify(success=False, message="Kunde inte starta laddning"), 502
    except Exception as e:
        logger.exception(f"Start charging error: {e}")
        return jsonify(success=False, message="Kunde inte starta laddning"), 502


@app.route('/api/charging/stop', methods=['POST'])
def stop_charging():
    """Stop charging."""
    try:
        if not ensure_token():
            return jsonify(success=False, message="Ej ansluten"), 401

        with api_lock:
            api.stop_charge(token, vehicle)

        return jsonify(success=True, message="Laddning stoppad")
    except AuthenticationError as e:
        logger.warning(f"Token utgången vid laddningsstopp: {e} – försöker förnya")
        invalidate_session()
        if not ensure_token():
            return jsonify(success=False, message="Token utgången, kunde inte förnya"), 401
        try:
            with api_lock:
                api.stop_charge(token, vehicle)
            return jsonify(success=True, message="Laddning stoppad")
        except Exception as e2:
            logger.exception(f"Stop charging error efter token-förnyelse: {e2}")
            return jsonify(success=False, message="Kunde inte stoppa laddning"), 502
    except Exception as e:
        logger.exception(f"Stop charging error: {e}")
        return jsonify(success=False, message="Kunde inte stoppa laddning"), 502

def schedule_worker():
    logger.info("Schemaläggnings-tråd startad")
    last_run = {}
    last_cleanup_day = None

    while True:
        try:
            try:
                schedules = load_schedules_with_retry(schedules_path())
            except Exception as e:
                logger.error(f"Kunde inte läsa schemafil: {e}")
                time.sleep(15)
                continue

            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            now_seconds = now.hour * 3600 + now.minute * 60 + now.second
            current_day = now.weekday()

            if last_cleanup_day != today:
                last_run = {}
                last_cleanup_day = today

            for idx, schedule in enumerate(schedules):
                if not schedule.get("enabled", True):
                    continue
                if current_day not in schedule.get("days", []):
                    continue
                schedule_time = schedule.get("time")
                if not schedule_time:
                    continue

                try:
                    hh, mm = schedule_time.split(":")
                    schedule_seconds = int(hh) * 3600 + int(mm) * 60
                except Exception:
                    logger.warning(f"Ogiltig tid i schema: {schedule_time}")
                    continue

                # Allow a small window to avoid missing the minute due to drift
                if not (schedule_seconds <= now_seconds < schedule_seconds + 90):
                    continue

                schedule_id = schedule.get("id") or f"idx{idx}"
                run_key = f"{schedule_id}-{schedule_time}"
                if run_key in last_run:
                    continue
                last_run[run_key] = True

                logger.info(f"✓ Kör schema: {schedule.get('name')}")

                if not ensure_token():
                    logger.error("Token ej giltig för schema")
                    continue

                options = build_climate_options(
                    schedule.get("temperature", 21),
                    schedule.get("defrost", False)
                )

                success, message, verified = start_climate_verified(options)
                if success:
                    logger.info(f"✓ Schema '{schedule.get('name')}': {message}")
                else:
                    logger.error(f"✗ Schema '{schedule.get('name')}': {message}")

            time.sleep(15)

        except Exception as e:
            logger.error(f"Schedule worker crash: {e}")
            time.sleep(60)


# ---------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))

    threading.Thread(target=schedule_worker, daemon=True).start()

    print(f"""
╔═══════════════════════════════════════╗
║  Kia EV6 Climate Control Server       ║
║  Port: {port}                            ║
║  Schemaläggning: Stabil               ║
╚═══════════════════════════════════════╝
""")

    app.run(host="0.0.0.0", port=port, debug=False)
