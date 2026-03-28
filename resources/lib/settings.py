# -*- coding: utf-8 -*-
import os
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin
try:
    from xbmcvfs import translatePath
except ImportError:
    from xbmc import translatePath

from resources.lib.utils import get_url

def list_settings(label):
    """Menu Nastavení Oneplay"""
    handle = int(sys.argv[1])
    xbmcplugin.setPluginCategory(handle, label)
    menu_items = [
        ('Kanály', 'manage_channels', True),
        ('Profily', 'list_profiles', True),
        ('Účty', 'list_accounts', True),
        ('Nastavení doplňku', 'addon_settings', False)
    ]
    for item_label, action, is_folder in menu_items:
        list_item = xbmcgui.ListItem(label=item_label)
        url = get_url(action=action, label=item_label)
        xbmcplugin.addDirectoryItem(handle, url, list_item, is_folder)
    xbmcplugin.endOfDirectory(handle)

class Settings:
    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.addon_userdata_dir = translatePath(path = self.addon.getAddonInfo('profile'))
        if not os.path.exists(self.addon_userdata_dir):
            os.makedirs(self.addon_userdata_dir)

    @property
    def is_settings_ok(self):
        """Kontroluje nastavení doplňku"""
        if not self.addon.getSetting('username') or not self.addon.getSetting('password'):
            xbmcgui.Dialog().notification('Oneplay', 'V nastavení je nutné mít vyplněné přihlašovací údaje', xbmcgui.NOTIFICATION_ERROR, 3000)
            return False
        return True

    def _get_path(self, filename):
        """Sestaví cestu k souboru"""
        return os.path.join(self.addon_userdata_dir, filename)

    def save_json_data(self, file_info, data):
        """Uloží json data do souboru"""
        if not self.is_settings_ok:
            return
        filename = self._get_path(file_info['filename'])
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write('%s\n' % data)
        except (IOError, OSError) as e:
            xbmcgui.Dialog().notification('Oneplay', f"Chyba uložení {file_info.get('description', '')}", xbmcgui.NOTIFICATION_ERROR, 3000)

    def load_json_data(self, file_info):
        """Načte data ze souboru. Vrací None, pokud soubor neexistuje nebo nejde načíst"""
        if not self.is_settings_ok:
            return None
        filename = self._get_path(file_info['filename'])
        if not os.path.exists(filename):
            return None
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except (IOError, OSError):
            return None

    def reset_json_data(self, file_info):
        """Smaže soubor s json daty"""
        filename = self._get_path(file_info['filename'])
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except (IOError, OSError):
            pass
