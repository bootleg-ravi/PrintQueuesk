import json, os, sys
import firebase_admin
from firebase_admin import credentials, db

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        # Running as bundled exe
        return os.path.join(sys._MEIPASS, relative_path)
    # Running in development
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative_path)

try:
    firebase_config = json.loads(os.environ["FIREBASE_CONFIG"])
except KeyError:
    config_path = get_resource_path("config/firebase_service_account.json")
    with open(config_path) as f:
        firebase_config = json.load(f)

cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred, {
    'databaseURL': "https://printqueuesk-f2c93-default-rtdb.asia-southeast1.firebasedatabase.app/"
})