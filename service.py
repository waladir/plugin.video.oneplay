# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon
import time
from resources.lib.iptvsc import generate_epg

monitor = xbmc.Monitor()
addon = xbmcaddon.Addon()

# čekání minutu po startu Kodi, kvůli dokončení inicializace
if monitor.waitForAbort(60):
    exit()

def get_interval():
    """Vrací interval v sekundách"""
    setting = addon.getSetting('epg_interval')
    hours = int(setting) if setting else 12
    return hours * 3600

# iniciální hodnota pro další spuštění
offset_seconds = int(addon.getSetting('epg_offset') or 0) * 60
next_run = time.time() + 10 + offset_seconds

while not monitor.abortRequested():
    current_time = time.time()
    if next_run < current_time:
        if monitor.waitForAbort(3):
            break
        user = addon.getSetting('username')
        pwd = addon.getSetting('password')
        autogen = addon.getSetting('autogen') == 'true'
        if user and pwd and autogen:
            try:
                generate_epg(show_progress=False)
            except Exception as e:
                xbmc.log(f"Oneplay (service)> {e}")
        next_run = time.time() + get_interval()
    if monitor.waitForAbort(5):
        break

addon = None
