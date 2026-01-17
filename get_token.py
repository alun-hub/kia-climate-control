#!/usr/bin/env python3
"""
Skript för att hämta Kia refresh token via manuell inloggning
Kräver: pip install hyundai-kia-connect-api
"""

from hyundai_kia_connect_api import VehicleManager
import sys

def get_token():
    print("=" * 60)
    print("Kia Refresh Token Generator")
    print("=" * 60)
    
    # Get credentials
    username = input("\nAnge din Kia e-postadress: ").strip()
    password = input("Ange ditt Kia-lösenord: ").strip()
    pin = input("Ange din PIN (4 siffror): ").strip()
    
    try:
        print("\n🔄 Försöker logga in till Kia...")
        print("OBS: Detta kan ta upp till 60 sekunder...")
        
        # Create vehicle manager
        vm = VehicleManager(
            region=1,  # 1 = Europe
            brand=1,   # 1 = Kia  
            username=username,
            password=password,
            pin=pin
        )
        
        # Force login
        vm.check_and_refresh_token()
        
        # Get refresh token
        if hasattr(vm, 'token') and vm.token:
            refresh_token = vm.token.get('refresh_token')
            
            if refresh_token:
                print("\n✅ SUCCESS! Här är din refresh token:\n")
                print("=" * 60)
                print(refresh_token)
                print("=" * 60)
                print("\nKopiera denna token till din .env fil:")
                print(f"KIA_REFRESH_TOKEN={refresh_token}")
                print(f"KIA_USERNAME={username}")
                print(f"KIA_PIN={pin}")
                return True
            else:
                print("\n❌ Kunde inte hitta refresh token i svaret")
                return False
        else:
            print("\n❌ Ingen token returnerad från Kia")
            return False
            
    except Exception as e:
        print(f"\n❌ FEL: {e}")
        print("\nVanliga problem:")
        print("- Felaktigt användarnamn eller lösenord")
        print("- CAPTCHA krävs (prova igen om några minuter)")
        print("- Kia Connect inte aktiverat på ditt konto")
        print("- Nätverksproblem")
        return False

if __name__ == "__main__":
    success = get_token()
    sys.exit(0 if success else 1)
