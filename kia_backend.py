#!/usr/bin/env python3
"""
Kia EV6 Climate Control Backend (Python)
Använder hyundai_kia_connect_api för att kommunicera med Kia
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from hyundai_kia_connect_api.KiaUvoApiEU import KiaUvoApiEU
from hyundai_kia_connect_api.const import BRANDS
from hyundai_kia_connect_api.ApiImplType1 import ClimateRequestOptions
import os
from dotenv import load_dotenv
import logging
from datetime import datetime
import json
import threading
import time

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

# Global variables
api = None
token = None
vehicle = None


def initialize_kia():
    """Initialize the Kia API connection"""
    global api, token, vehicle

    try:
        logger.info("Initierar Kia API...")

        # Create API client
        REGION = 1  # Europe
        BRAND = 1   # Kia
        LANGUAGE = "sv"

        api = KiaUvoApiEU(REGION, BRAND, LANGUAGE)

        # Login with refresh token as password
        username = os.getenv('KIA_USERNAME')
        refresh_token = os.getenv('KIA_REFRESH_TOKEN')

        logger.info(f"Loggar in som {username}...")
        token = api.login(username, refresh_token)

        # Get vehicles
        logger.info("Hämtar fordon...")
        vehicles = api.get_vehicles(token)

        if not vehicles or len(vehicles) == 0:
            raise Exception("Inga fordon hittades på kontot")

        vehicle = vehicles[0]
        logger.info(
            f"✓ Ansluten till fordon: {vehicle.id if hasattr(vehicle, 'id') else 'Kia EV6'}")

        return True

    except Exception as e:
        logger.error(f"✗ Fel vid initiering: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# Initialize on startup
initialize_kia()


@app.route('/')
def index():
    """Serve the frontend"""
    return send_from_directory('public', 'index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'connected': token is not None and vehicle is not None,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/credentials', methods=['GET'])
def get_credentials():
    """Get current credentials (username only, not the full tokens for security)"""
    try:
        username = os.getenv('KIA_USERNAME', '')
        # Don't send the full tokens, just indicate if they exist
        has_refresh_token = bool(os.getenv('KIA_REFRESH_TOKEN'))
        has_access_token = bool(os.getenv('KIA_ACCESS_TOKEN'))

        return jsonify({
            'success': True,
            'username': username,
            'refresh_token': '***' if has_refresh_token else '',
            'access_token': '***' if has_access_token else '',
            'has_credentials': bool(username and has_refresh_token)
        })
    except Exception as e:
        logger.error(f"Get credentials error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/credentials', methods=['POST'])
def update_credentials():
    """Update credentials and reinitialize connection"""
    global api, token, vehicle

    try:
        data = request.get_json()
        new_username = data.get('username')
        new_refresh_token = data.get('refresh_token')
        new_access_token = data.get('access_token', '')

        if not new_username or not new_refresh_token:
            return jsonify({
                'success': False,
                'message': 'Både e-post och refresh token krävs'
            }), 400

        # Update environment variables (in-memory)
        os.environ['KIA_USERNAME'] = new_username
        os.environ['KIA_REFRESH_TOKEN'] = new_refresh_token
        if new_access_token:
            os.environ['KIA_ACCESS_TOKEN'] = new_access_token

        # Save to .env file for persistence
        env_path = '.env'
        if os.path.exists(env_path):
            # Read existing .env
            with open(env_path, 'r') as f:
                lines = f.readlines()

            # Update credentials in .env
            updated_username = False
            updated_refresh = False
            updated_access = False
            with open(env_path, 'w') as f:
                for line in lines:
                    if line.startswith('KIA_USERNAME='):
                        f.write(f'KIA_USERNAME={new_username}\n')
                        updated_username = True
                    elif line.startswith('KIA_REFRESH_TOKEN='):
                        f.write(f'KIA_REFRESH_TOKEN={new_refresh_token}\n')
                        updated_refresh = True
                    elif line.startswith('KIA_ACCESS_TOKEN='):
                        if new_access_token:
                            f.write(f'KIA_ACCESS_TOKEN={new_access_token}\n')
                            updated_access = True
                        # Skip if no access token provided
                    else:
                        f.write(line)

                # Add if not found
                if not updated_username:
                    f.write(f'\nKIA_USERNAME={new_username}\n')
                if not updated_refresh:
                    f.write(f'KIA_REFRESH_TOKEN={new_refresh_token}\n')
                if not updated_access and new_access_token:
                    f.write(f'KIA_ACCESS_TOKEN={new_access_token}\n')

            logger.info("Credentials updated in .env file")

        # Reinitialize connection
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
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'Fel vid uppdatering: {str(e)}'
        }), 500


def ensure_token():
    """Ensure we have a valid token, refresh if needed"""
    global api, token, vehicle

    if api is None or token is None or vehicle is None:
        logger.warning("Token/API saknas, försöker återansluta...")
        if not initialize_kia():
            return False
    return True


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get vehicle status"""
    try:
        if not ensure_token():
            return jsonify({
                'success': False,
                'message': 'Inte ansluten till fordon'
            }), 401

        logger.info("Hämtar fordonsstatus...")

        # Update vehicle with cached state
        try:
            api.update_vehicle_with_cached_state(token, vehicle)
        except Exception as e:
            # If token expired, try to reinitialize
            logger.warning(f"Fel vid uppdatering, försöker återansluta: {str(e)}")
            if initialize_kia():
                api.update_vehicle_with_cached_state(token, vehicle)
            else:
                raise e

        # Get door status
        door_status = {
            'driver': False,
            'passenger': False,
            'backLeft': False,
            'backRight': False,
            'hood': False,
            'trunk': False
        }

        if hasattr(vehicle, 'data') and vehicle.data:
            status = vehicle.data.get('vehicleStatus', {})
            door_status = {
                'driver': status.get('doorOpen', {}).get('frontLeft') == 1,
                'passenger': status.get('doorOpen', {}).get('frontRight') == 1,
                'backLeft': status.get('doorOpen', {}).get('backLeft') == 1,
                'backRight': status.get('doorOpen', {}).get('backRight') == 1,
                'hood': status.get('hoodOpen') == 1,
                'trunk': status.get('trunkOpen') == 1
            }

        # Get window status
        window_status = {
            'driver': False,
            'passenger': False,
            'backLeft': False,
            'backRight': False
        }

        if hasattr(vehicle, 'data') and vehicle.data:
            status = vehicle.data.get('vehicleStatus', {})
            window_status = {
                'driver': status.get('windowOpen', {}).get('frontLeft') == 1,
                'passenger': status.get('windowOpen', {}).get('frontRight') == 1,
                'backLeft': status.get('windowOpen', {}).get('backLeft') == 1,
                'backRight': status.get('windowOpen', {}).get('backRight') == 1
            }

        vehicle_data = {
            'model': 'Kia EV6',
            'vin': vehicle.id if hasattr(vehicle, 'id') else 'N/A',
            'battery': vehicle.ev_battery_percentage if hasattr(vehicle, 'ev_battery_percentage') else 0,
            'range': vehicle.ev_driving_range if hasattr(vehicle, 'ev_driving_range') else 0,
            'charging': vehicle.ev_battery_is_charging if hasattr(vehicle, 'ev_battery_is_charging') else False,
            'pluggedIn': vehicle.ev_battery_is_plugged_in if hasattr(vehicle, 'ev_battery_is_plugged_in') else False,
            'locked': vehicle.is_locked if hasattr(vehicle, 'is_locked') else False,
            'climateActive': vehicle.air_control_is_on if hasattr(vehicle, 'air_control_is_on') else False,
            'doors': door_status,
            'windows': window_status,
            'location': {
                'lat': vehicle.location_latitude if hasattr(vehicle, 'location_latitude') else None,
                'lon': vehicle.location_longitude if hasattr(vehicle, 'location_longitude') else None
            },
            'lastUpdated': datetime.now().isoformat()
        }

        return jsonify({
            'success': True,
            'data': vehicle_data
        })

    except Exception as e:
        logger.error(f"Status error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/climate/start', methods=['POST'])
def start_climate():
    """Start climate control"""
    try:
        if not ensure_token():
            return jsonify({
                'success': False,
                'message': 'Inte ansluten till fordon'
            }), 401

        data = request.get_json()
        temperature = data.get('temperature', 21)
        defrost = data.get('defrost', False)

        logger.info(f"Startar klimat: {temperature}°C, defrost: {defrost}")

        # Create climate options
        options = ClimateRequestOptions()
        options.set_temp = temperature
        options.defrost = defrost
        options.climate = True
        options.heating = 1

        # Start climate
        response = api.start_climate(token, vehicle, options)

        logger.info(f"Klimat startad: {response}")

        return jsonify({
            'success': True,
            'message': f'Klimat startad på {temperature}°C'
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Climate start error: {error_msg}")

        # Handle duplicate request error
        if "Duplicate request" in error_msg:
            return jsonify({
                'success': False,
                'message': 'Vänta några sekunder innan nästa kommando'
            }), 429

        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500


@app.route('/api/climate/stop', methods=['POST'])
def stop_climate():
    """Stop climate control"""
    try:
        if not ensure_token():
            return jsonify({
                'success': False,
                'message': 'Inte ansluten till fordon'
            }), 401

        logger.info("Stoppar klimat...")

        # Stop climate
        response = api.stop_climate(token, vehicle)

        logger.info(f"Klimat stoppad: {response}")

        return jsonify({
            'success': True,
            'message': 'Klimat stoppad'
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Climate stop error: {error_msg}")

        # Handle duplicate request error
        if "Duplicate request" in error_msg:
            return jsonify({
                'success': False,
                'message': 'Vänta några sekunder innan nästa kommando'
            }), 429

        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500


@app.route('/api/lock', methods=['POST'])
def lock_vehicle():
    """Lock vehicle - Not available in KiaUvoApiEU"""
    return jsonify({
        'success': False,
        'message': 'Lås-funktion ej tillgänglig via Kia API. Använd appen eller bilens nycklar.'
    }), 501


@app.route('/api/unlock', methods=['POST'])
def unlock_vehicle():
    """Unlock vehicle - Not available in KiaUvoApiEU"""
    return jsonify({
        'success': False,
        'message': 'Upplås-funktion ej tillgänglig via Kia API. Använd appen eller bilens nycklar.'
    }), 501

# Schedule management endpoints


def get_schedules_path():
    """Get the path to schedules file (supports containerized deployment)"""
    # Check if running in container with data volume
    if os.path.exists('/app/data'):
        return '/app/data/schedules.json'
    # Fall back to local directory
    return 'schedules.json'


@app.route('/api/schedules', methods=['GET'])
def get_schedules():
    """Get all climate schedules"""
    try:
        schedules_path = get_schedules_path()
        schedules = []
        if os.path.exists(schedules_path):
            with open(schedules_path, 'r') as f:
                schedules = json.load(f)

        return jsonify({
            'success': True,
            'schedules': schedules
        })
    except Exception as e:
        logger.error(f"Get schedules error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/schedules', methods=['POST'])
def save_schedule():
    """Save a climate schedule"""
    try:
        data = request.get_json()
        schedules_path = get_schedules_path()

        # Load existing schedules
        schedules = []
        if os.path.exists(schedules_path):
            with open(schedules_path, 'r') as f:
                schedules = json.load(f)

        # Add new schedule
        schedule = {
            'id': data.get('id', str(datetime.now().timestamp())),
            'name': data.get('name', 'Ny schemaläggning'),
            'time': data.get('time'),
            'temperature': data.get('temperature', 21),
            'defrost': data.get('defrost', False),
            'days': data.get('days', []),  # [0-6] where 0=Monday
            'enabled': data.get('enabled', True)
        }

        # Update existing or add new
        schedule_exists = False
        for i, s in enumerate(schedules):
            if s.get('id') == schedule['id']:
                schedules[i] = schedule
                schedule_exists = True
                break

        if not schedule_exists:
            schedules.append(schedule)

        # Save to file
        with open(schedules_path, 'w') as f:
            json.dump(schedules, f, indent=2)

        return jsonify({
            'success': True,
            'message': 'Schemaläggning sparad',
            'schedule': schedule
        })

    except Exception as e:
        logger.error(f"Save schedule error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/schedules/<schedule_id>/toggle', methods=['PATCH'])
def toggle_schedule(schedule_id):
    """Toggle a climate schedule enabled/disabled"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        schedules_path = get_schedules_path()

        schedules = []
        if os.path.exists(schedules_path):
            with open(schedules_path, 'r') as f:
                schedules = json.load(f)

        # Update schedule enabled status
        for s in schedules:
            if s.get('id') == schedule_id:
                s['enabled'] = enabled
                break

        # Save to file
        with open(schedules_path, 'w') as f:
            json.dump(schedules, f, indent=2)

        return jsonify({
            'success': True,
            'message': f'Schema {"aktiverat" if enabled else "inaktiverat"}'
        })

    except Exception as e:
        logger.error(f"Toggle schedule error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/schedules/<schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    """Delete a climate schedule"""
    try:
        schedules_path = get_schedules_path()
        schedules = []
        if os.path.exists(schedules_path):
            with open(schedules_path, 'r') as f:
                schedules = json.load(f)

        # Remove schedule
        schedules = [s for s in schedules if s.get('id') != schedule_id]

        # Save to file
        with open(schedules_path, 'w') as f:
            json.dump(schedules, f, indent=2)

        return jsonify({
            'success': True,
            'message': 'Schemaläggning borttagen'
        })

    except Exception as e:
        logger.error(f"Delete schedule error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/charging/start', methods=['POST'])
def start_charging():
    """Start charging"""
    try:
        if api is None or token is None or vehicle is None:
            return jsonify({
                'success': False,
                'message': 'Inte ansluten till fordon'
            }), 401

        logger.info("Startar laddning...")
        response = api.start_charge(token, vehicle)

        return jsonify({
            'success': True,
            'message': 'Laddning startad'
        })

    except Exception as e:
        logger.error(f"Start charging error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/charging/stop', methods=['POST'])
def stop_charging():
    """Stop charging"""
    try:
        if api is None or token is None or vehicle is None:
            return jsonify({
                'success': False,
                'message': 'Inte ansluten till fordon'
            }), 401

        logger.info("Stoppar laddning...")
        response = api.stop_charge(token, vehicle)

        return jsonify({
            'success': True,
            'message': 'Laddning stoppad'
        })

    except Exception as e:
        logger.error(f"Stop charging error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))

    # Start schedule checker thread
    def check_schedules():
        """Background thread to check and execute schedules"""
        logger.info("Schemaläggnings-tråd startad")

        while True:
            try:
                # Wait a bit for initialization
                if api is None or token is None or vehicle is None:
                    logger.debug("Väntar på API-initiering...")
                    time.sleep(10)
                    continue

                schedules_path = get_schedules_path()
                if not os.path.exists(schedules_path):
                    time.sleep(60)
                    continue

                with open(schedules_path, 'r') as f:
                    schedules = json.load(f)

                now = datetime.now()
                current_time = now.strftime('%H:%M')
                current_day = now.weekday()  # 0=Monday, 6=Sunday

                logger.debug(
                    f"Kollar scheman: {current_time}, Dag: {current_day}")

                for schedule in schedules:
                    if not schedule.get('enabled', True):
                        continue

                    # Check if current day is in schedule
                    if current_day not in schedule.get('days', []):
                        continue

                    # Check if time matches
                    if schedule.get('time') == current_time:
                        logger.info(
                            f"✓ Kör schemalagd klimatstart: {schedule.get('name')}")

                        try:
                            # Create climate options
                            options = ClimateRequestOptions()
                            options.set_temp = schedule.get('temperature', 21)
                            options.defrost = schedule.get('defrost', False)
                            options.climate = True
                            options.heating = 1

                            # Start climate
                            result = api.start_climate(token, vehicle, options)
                            logger.info(
                                f"✓ Klimat startad från schema '{schedule.get('name')}': {result}")
                        except Exception as e:
                            logger.error(
                                f"✗ Fel vid schemalagd klimatstart: {str(e)}")
                            import traceback
                            logger.error(traceback.format_exc())

                # Sleep for 60 seconds before next check
                time.sleep(60)

            except Exception as e:
                logger.error(f"Schedule checker error: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(60)

    # Start background thread
    schedule_thread = threading.Thread(target=check_schedules, daemon=True)
    schedule_thread.start()

    print(f"""
╔═══════════════════════════════════════╗
║  Kia EV6 Climate Control Server       ║
║  Port: {port}                            ║
║  Python Backend with KiaUvoApiEU      ║
║  Schemaläggning: Aktiv                ║
╚═══════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=port, debug=False)
