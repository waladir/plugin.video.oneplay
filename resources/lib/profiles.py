# -*- coding: utf-8 -*-
import sys
import os
import xbmc
import xbmcgui
import xbmcplugin

import json

from resources.lib.api import API
from resources.lib.utils import get_url
from resources.lib.settings import Settings

PROFILES_FILE = {'filename' : 'profiles.txt', 'description' : 'profilů'}
ACCOUNTS_FILE = {'filename' : 'accounts.txt', 'description' : 'účtů'}

if len(sys.argv) > 1:
    _handle = int(sys.argv[1])

def list_profiles(label):
    """Vypíše seznam profilů se zvýrazněným aktivním profilem"""  
    xbmcplugin.setPluginCategory(_handle, label)
    for profile in get_profiles():
        name = f"[B]{profile['name']}[/B]" if profile.get('active') else profile['name']
        list_item = xbmcgui.ListItem(label=name)
        list_item.setArt({'thumb': profile['image'], 'icon': profile['image']})
        url = get_url(action='set_active_profile', id=profile['id'])
        xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    xbmcplugin.addDirectoryItem(_handle, get_url(action='reset_profiles'), xbmcgui.ListItem(label='Načtení profilů'), False)
    xbmcplugin.endOfDirectory(_handle)

def set_active_profile(profile_id):
    """Nastavení profilu jako aktivního"""  
    profiles = get_profiles()
    for profile in profiles:
        profile['active'] = (profile['id'] == profile_id)
    Settings.save_json_data(file_info=PROFILES_FILE, data=profiles)
    xbmc.executebuiltin('Container.Refresh')

def get_profiles(active=False, session=None):
    """Načtení uložených profilů. Pokud soubor neexistuje, načtou se profily z API"""  
    settings = Settings()
    profiles = settings.load_json_data(file_info=PROFILES_FILE)
    try:
        profiles = json.loads(profiles) if profiles else []
    except (json.decoder.JSONDecodeError, json.JSONDecodeError, TypeError):
        profiles = []      
    if not profiles:
        data = API().user_profiles_display(session=session)
        profiles = []
        for i, profile in enumerate(data.get('availableProfiles', {}).get('profiles', [])):
            profiles.append({'id': profile['profile']['id'], 'name': profile['profile']['name'], 'image': profile['profile']['avatarUrl'], 'active': (i == 0)})
        settings.save_json_data(file_info=PROFILES_FILE, data=profiles)
    if active:
        return next((profile for profile in profiles if profile.get('active', False)), None)
    return profiles

def get_profile_id(session):
    """Vrátí aktuální profil"""
    profile = get_profiles(active=True, session=session)
    return profile['id']

def reset_profiles(load_profiles=True):
    """Odstraní uložené profilu a znovu je načte z API"""
    settings = Settings()
    settings.reset_json_data(file_info=PROFILES_FILE)
    if load_profiles:
        get_profiles()
        xbmcgui.Dialog().notification('Oneplay', 'Profily byly znovu načtené', xbmcgui.NOTIFICATION_INFO, 5000)
        xbmc.executebuiltin('Container.Refresh')

def list_accounts(label):
    """Zobrazí seznam účtů"""
    xbmcplugin.setPluginCategory(_handle, label)
    accounts = get_accounts()
    for account in accounts:
        name = account['name']
        display_name = f'[B]{name}[/B]' if account.get('active') else name
        list_item = xbmcgui.ListItem(label=display_name)
        url = get_url(action='set_active_account', name=name)  
        xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    xbmcplugin.addDirectoryItem(_handle, get_url(action='reset_accounts'), xbmcgui.ListItem(label='Načtení účtů'), False)
    xbmcplugin.endOfDirectory(_handle)

def set_active_account(name):
    """Nastaví aktivní účet"""
    from resources.lib.session import Session
    from resources.lib.channels import Channels
    settings = Settings()
    filename = settings._get_path('accounts.txt')
    accounts = get_accounts()
    for account in accounts:
        account['active'] = (account['name'] == name)
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(accounts, f)
    except IOError:
        xbmcgui.Dialog().notification('Oneplay', 'Chyba při uložení účtů', xbmcgui.NOTIFICATION_ERROR, 5000)
        return
    reset_profiles(load_profiles=False)
    Session().remove_session()
    channels = Channels()
    channels.reset_channels_full()
    xbmc.executebuiltin('Container.Refresh')

def get_accounts(active=False, accounts_data=None):
    """Načtení účtů"""
    settings = Settings()
    filename = settings._get_path('accounts.txt')
    accounts = []
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    accounts = json.loads(content)
        except (IOError, ValueError):
            xbmcgui.Dialog().notification('Oneplay', 'Chyba při načtení účtů', xbmcgui.NOTIFICATION_ERROR, 3000)
    if not accounts and accounts_data:
        for i, name in enumerate(accounts_data):
            accounts.append({'name': name, 'active': (i == 0)})
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(accounts, f)
        except IOError:
            xbmcgui.Dialog().notification('Oneplay', 'Chyba při uložení účtů', xbmcgui.NOTIFICATION_ERROR, 3000)
    if active:
        return next((acc for acc in accounts if acc.get('active')), None)
    return accounts

def get_account_id(accounts_data = None):
    """Vrací aktivní účet"""
    account = get_accounts(active=True, accounts_data=accounts_data)
    return account['name']

def reset_accounts():
    """Provede reset uložených účtů a jejich načtení z API. Zároveň se provede reset sessiony a kanálů"""
    from resources.lib.session import Session
    from resources.lib.channels import Channels
    settings = Settings()
    settings.reset_json_data(file_info=ACCOUNTS_FILE)
    reset_profiles(load_profiles = False)
    session = Session()
    session.remove_session()
    channels = Channels()
    channels.reset_channels_full()
    xbmcgui.Dialog().notification('Oneplay', 'Účty byly znovu načtené', xbmcgui.NOTIFICATION_INFO, 3000)    
  
