# -*- coding: utf-8 -*-
import sys
import os
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
try:
    from xbmcvfs import translatePath
except ImportError:
    from xbmc import translatePath
    
from urllib.parse import quote  

from resources.lib.utils import get_url, plugin_id
from resources.lib.categories import page_search_display

_handle = int(sys.argv[1])

def list_search(label):
    """Vypíše menu pro vyhledávání včetně historie"""
    xbmcplugin.setPluginCategory(_handle, label)
    list_item = xbmcgui.ListItem(label='Nové hledání')
    url = get_url(action='program_search', query='-----', label=f"{label} / Nové hledání")
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    for item in load_search_history():
        list_item = xbmcgui.ListItem(label=item)
        url = get_url(action='program_search', query=item, label=f"{label} / {item}")
        list_item.addContextMenuItems([('Smazat', f"RunPlugin(plugin://{plugin_id}?action=delete_search&query={quote(item)})")])
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)

def program_search(query, label):
    """Samotné vyhledávání"""
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'movies')
    if query == '-----':
        kb = xbmc.Keyboard('', 'Hledat')
        kb.doModal()
        if not kb.isConfirmed() or not kb.getText():
            if kb.isConfirmed(): 
                xbmcgui.Dialog().notification('Oneplay', 'Je potřeba zadat vyhledávaný řetězec', xbmcgui.NOTIFICATION_ERROR, 3000)
            return
        query = kb.getText()
        save_search_history(query)
    page_search_display(query)    

def load_search_history():
    """Načtení historie"""
    filename = _get_history_file()
    if not os.path.exists(filename): return []
    history = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            history = [line.strip() for line in f if line.strip()]
    except (UnicodeDecodeError, Exception): # osetreni spatneho enkodovani
        try:
            with open(filename, 'r') as f:
                history = [line.strip() for line in f if line.strip()]
            with open(filename, 'w', encoding='utf-8') as f:
                for item in history: f.write(f"{item}\n")
        except Exception: history = []
    return history    

def save_search_history(query):
    """Uloření historie"""
    history = load_search_history()
    if query in history: history.remove(query)
    history.insert(0, query)
    max_h = int(xbmcaddon.Addon().getSetting('search_history') or 10)
    with open(_get_history_file(), 'w', encoding='utf-8') as f:
        for item in history[:max_h]: f.write(f"{item}\n")

def delete_search(query):
    """Odstranění stringu z historie"""
    history = [item for item in load_search_history() if item != query]
    with open(_get_history_file(), 'w', encoding='utf-8') as f:
        for item in history: f.write(f"{item}\n")
    xbmc.executebuiltin('Container.Refresh')

def _get_history_file():
    """Vrací jméno souboru s historií vyhledávání"""
    addon = xbmcaddon.Addon()
    path = translatePath(addon.getAddonInfo('profile'))
    if not os.path.exists(path): os.makedirs(path)
    return os.path.join(path, 'search_history.txt')