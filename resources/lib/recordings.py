# -*- coding: utf-8 -*-
import os
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from datetime import date, datetime, timedelta
import json

from resources.lib.session import Session
from resources.lib.channels import Channels
from resources.lib.categories import page_category_display
from resources.lib.epg import epg_listitem, get_epg
from resources.lib.api import API
from resources.lib.utils import get_url, plugin_id, day_translation, day_translation_short

if len(sys.argv) > 1:
    _handle = int(sys.argv[1])

def list_recordings(label):
    """Menu s nahrávkami"""
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'tvshows')
    list_item = xbmcgui.ListItem(label='Plánování nahrávek')
    url = get_url(action='list_planning_recordings', label = label + ' / ' + 'Plánování')  
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    page_category_display(label = 'Nahrávky', params = json.dumps({'schema' : 'PageCategoryDisplayApiAction', 'payload' : {'categoryId' : '8'}}))

def list_planning_recordings(label):
    """Seznam kanálů"""    
    addon = xbmcaddon.Addon()
    xbmcplugin.setPluginCategory(_handle, label)
    channels_list = Channels().get_channels_list('channel_number')
    channel_numbers = addon.getSetting('channel_numbers')
    cnt = 0
    for number in sorted(channels_list.keys()):  
        channel = channels_list[number]
        if not channel.get('liveOnly', False):
            cnt += 1
            if channel_numbers == 'číslo kanálu':
                channel_number = f"{number}. "
            elif channel_numbers == 'pořadové číslo':
                channel_number = f"{cnt}. "
            else:
                channel_number = ""
            list_item = xbmcgui.ListItem(label=f"{channel_number}{channel['name']}")
            list_item.setArt({'thumb': channel['logo'], 'icon': channel['logo']})
            url = get_url(action='list_rec_days', id=channel['id'], label=f"{label} / {channel['name']}")
            xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle)

def list_rec_days(id, label):
    """Výběr dne"""      
    xbmcplugin.setPluginCategory(_handle, label)
    today = date.today()
    labels = ['Dnes', 'Zítra']

    for i in range(8):
        day = today + timedelta(days=i)
        w_day = day.strftime('%w')
        if i < 2:
            den_label, den = labels[i], labels[i]
        else:
            den_label = f"{day_translation_short[w_day]} {day.strftime('%d.%m.')}"
            den = f"{day_translation[w_day]} {day.strftime('%d.%m.%Y')}"
        list_item = xbmcgui.ListItem(label=den)
        url = get_url(action='future_program', id=id, day=i, label=f"{label} / {den_label}")
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle)

def future_program(id, day, label):
    """Program s nastavením nahrávek"""
    addon = xbmcaddon.Addon(); day = int(day)
    icons_dir = os.path.join(addon.getAddonInfo('path'), 'resources', 'images')
    label = label.replace('Nahrávky / Plánování /', '')
    xbmcplugin.setPluginCategory(_handle, label); xbmcplugin.setContent(_handle, 'episodes')
    now_ts = int(datetime.now().timestamp())
    ts = now_ts + (day * 86400)
    epg = get_epg(ts, id)
    den = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
    base_label = label.rsplit(' / ', 1)[0]
    if day > 0:
        dt = date.today() + timedelta(days=day - 1)
        d_lbl = f"{day_translation_short[dt.strftime('%w')]} {dt.strftime('%d.%m.')}"
        list_item = xbmcgui.ListItem(label='Předchozí den')
        list_item.setArt({'thumb': os.path.join(icons_dir, 'previous_arrow.png'), 'icon': os.path.join(icons_dir, 'previous_arrow.png')})
        xbmcplugin.addDirectoryItem(_handle, get_url(action='future_program', id=id, day=day-1, label=f"{base_label} / {d_lbl}"), list_item, True)
    for key in sorted(epg.keys()):
        item = epg[key]
        start, end = item['startts'], item['endts']
        if (datetime.fromtimestamp(start).strftime('%Y-%m-%d') == den or datetime.fromtimestamp(end).strftime('%Y-%m-%d') == den):
            st_dt = datetime.fromtimestamp(start)
            t_str = f"{day_translation_short[st_dt.strftime('%w')]} {st_dt.strftime('%d.%m. %H:%M')} - {datetime.fromtimestamp(end).strftime('%H:%M')}"
            list_item = xbmcgui.ListItem(label=f"{t_str} | {item['title']}")
            list_item = epg_listitem(list_item, item, '')
            list_item.setProperty('IsPlayable', 'false')
            list_item.addContextMenuItems([('Přidat nahrávku', f"RunPlugin(plugin://{plugin_id}?action=add_recording&id={item['payload']['contentId']})")])
            xbmcplugin.addDirectoryItem(_handle, get_url(action='add_recording', id=item['payload']['contentId']), list_item, False)
    if day < 7:
        dt = date.today() + timedelta(days=day + 1)
        d_lbl = f"{day_translation_short[dt.strftime('%w')]} {dt.strftime('%d.%m.')}"
        list_item = xbmcgui.ListItem(label='Následující den')
        list_item.setArt({'thumb': os.path.join(icons_dir, 'next_arrow.png'), 'icon': os.path.join(icons_dir, 'next_arrow.png')})
        xbmcplugin.addDirectoryItem(_handle, get_url(action='future_program', id=id, day=day+1, label=f"{base_label} / {d_lbl}"), list_item, True)
    xbmcplugin.endOfDirectory(_handle, updateListing=True)

def add_recording(id):
    """Přidání nahrávky"""
    session = Session()
    api = API()
    data = api.user_list_change(id, 'add', session)
    if data:
        xbmcgui.Dialog().notification('Oneplay', 'Nahrávka přidána', xbmcgui.NOTIFICATION_INFO, 3000)
    else:
        xbmcgui.Dialog().notification('Oneplay', 'Chyba při přidání nahrávky', xbmcgui.NOTIFICATION_INFO, 3000)
    xbmc.executebuiltin('Container.Refresh')
    
def delete_recording(id):
    """Odstranění nahrávky"""
    session = Session()
    api = API()
    data = api.user_list_change(id, 'remove', session)
    if data:
        xbmcgui.Dialog().notification('Oneplay', 'Nahrávka odstraněna', xbmcgui.NOTIFICATION_INFO, 3000)
    else:
        xbmcgui.Dialog().notification('Oneplay', 'Chyba při mazání nahrávky', xbmcgui.NOTIFICATION_INFO, 3000)
    xbmc.executebuiltin('Container.Refresh')
