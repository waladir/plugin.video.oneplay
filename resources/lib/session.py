# -*- coding: utf-8 -*-
import xbmcaddon
import xbmcgui

import json
import time 

from resources.lib.api import API
from resources.lib.profiles import get_profile_id

class Session:
    TOKEN_VALIDITY = 4 * 60 * 60  # 4 hodiny
    SESSION_FILE = {'filename': 'session.txt', 'description': 'session'}

    def __init__(self):
        self.token = None
        self.load_session()

    def create_session(self):
        """Proces přihlášení"""
        addon = xbmcaddon.Addon()
        api = API()
        data = api.user_login_step(username=addon.getSetting('username'), password=addon.getSetting('password'))
        self.token = data['step']['bearerToken']
        self.manage_devices(deviceId=data['step']['currentUser']['currentDevice']['id'])
        self.reload_profile()

    def manage_devices(self, deviceId):
        """Přejmenuje aktuální zařízení a odstraní ostatní stejným jménem"""
        addon = xbmcaddon.Addon()
        api = API()
        device_name = addon.getSetting('deviceid')
        api.user_device_change(id=deviceId, name=device_name, session=self)
        data = api.setting_display(screen='devices', session=self)
        devices = data.get('screen', {}).get('userDevices', {}).get('devices', [])
        for device in devices:
            if device['id'] != deviceId and device['name'] == device_name:
                api.user_device_remove(id=device['id'], session=self)

    def reload_profile(self):
        """Znovu vybere profil"""
        addon = xbmcaddon.Addon()
        api = API()
        data = api.user_profile_select(profileId=get_profile_id(session=self), profile_pin=addon.getSetting('profile_pin'), session=self)
        self.token = data['bearerToken']
        self.save_session()

    def load_session(self):
        """Načte session, kontroluje integritu a expiraci"""
        from resources.lib.settings import Settings
        settings = Settings()
        data = settings.load_json_data(file_info=self.SESSION_FILE)
        if data:
            try:
                data = json.loads(data)
                token = data.get('token')
                valid_to = data.get('valid_to', 0)
                if token and int(valid_to) > int(time.time()):
                    self.token = token
                    return
            except (json.JSONDecodeError, ValueError):
                pass
        self.create_session()

    def save_session(self):
        """Uloží aktuální token"""
        from resources.lib.settings import Settings
        settings = Settings()
        valid_to = int(time.time() + self.TOKEN_VALIDITY)
        data = json.dumps({'token': self.token, 'valid_to': valid_to})
        settings.save_json_data(file_info=self.SESSION_FILE, data=data)

    def remove_session(self):
        """Smaže session a vytvoří novou session"""
        from resources.lib.settings import Settings
        settings = Settings()
        settings.reset_json_data(file_info=self.SESSION_FILE)
        self.create_session()
        xbmcgui.Dialog().notification('Oneplay', 'Byla vytvořena nová session', xbmcgui.NOTIFICATION_INFO, 3000)





