# -*- coding: utf-8 -*-
import os
import sys
import xbmcgui
import xbmcplugin
import xbmcaddon

from datetime import date, datetime, timedelta
import json

from resources.lib.utils import get_url, day_translation, day_translation_short, plugin_id
from resources.lib.channels import Channels 
from resources.lib.epg import get_channel_epg, epg_listitem

if len(sys.argv) > 1:
    _handle = int(sys.argv[1])

def list_archive(label):
    """Seznam kanálů v archivu"""    
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
            url = get_url(action='list_archive_days', id=channel['id'], label=f"{label} / {channel['name']}")
            xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)

def list_archive_days(id, label):
    """Výběr dne v archivu"""      
    xbmcplugin.setPluginCategory(_handle, label)
    today = date.today()
    for i in range(8):
        day = today - timedelta(days=i)
        day_idx = day.strftime('%w')
        if i == 0:
            den_label, den = 'Dnes', 'Dnes'
        elif i == 1:
            den_label, den = 'Včera', 'Včera'
        else:
            formatted_date = day.strftime('%d.%m.')
            den_label = f"{day_translation_short[day_idx]} {formatted_date}"
            den = f"{day_translation[day_idx]} {day.strftime('%d.%m.%Y')}"
        list_item = xbmcgui.ListItem(label=den)
        url = get_url(action='list_program', id=id, day_min=i, label=f"{label} / {den_label}")
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)

def list_program(id, day_min, label):
    """Výpis pořadů pro konkrétní kanál a den"""  
    addon = xbmcaddon.Addon()
    icons_dir = os.path.join(addon.getAddonInfo('path'), 'resources', 'images')
    label = label.replace('Archiv /', '')
    xbmcplugin.setPluginCategory(_handle, label)
    if addon.getSetting('default_tv_view') == 'false':
        xbmcplugin.setContent(_handle, 'tvshows')
    day_min = int(day_min)
    now_ts = int(datetime.now().timestamp())
    dt_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_ts = int(dt_today.timestamp())
    from_ts = today_start_ts - (day_min * 86400)
    to_ts = now_ts if day_min == 0 else from_ts + 60*60*24
    limit_ts = now_ts - 60*60*24*7
    epg = get_channel_epg(id, from_ts, to_ts)

    if day_min < 7:
        day = date.today() - timedelta(days=day_min + 1)
        den_label = f"{day_translation_short[day.strftime('%w')]} {day.strftime('%d.%m.')}"
        url = get_url(action='list_program', id=id, day_min=day_min + 1, label=f"{label.rsplit(' / ')[0]} / {den_label}")
        item = xbmcgui.ListItem(label='Předchozí den')
        arrow = os.path.join(icons_dir, 'previous_arrow.png')
        item.setArt({'thumb': arrow, 'icon': arrow})
        xbmcplugin.addDirectoryItem(_handle, url, item, True)

    for start_ts in sorted(epg.keys()):
        item_data = epg[start_ts]
        if item_data['endts'] > limit_ts:
            dt_start = datetime.fromtimestamp(item_data['startts'])
            dt_end = datetime.fromtimestamp(item_data['endts'])
            item_label = (f"{day_translation_short[dt_start.strftime('%w')]} {dt_start.strftime('%d.%m. %H:%M')} - {dt_end.strftime('%H:%M')} | {item_data['title']}")
            list_item = xbmcgui.ListItem(label=item_label)
            list_item = epg_listitem(list_item=list_item, epg=item_data, icon=None)
            payload = item_data['payload']
            contentId = payload.get('contentId', '')
            menus = [('Přidat nahrávku', f'RunPlugin(plugin://{plugin_id}?action=add_recording&id={contentId})')]
            list_item.addContextMenuItems(menus)
            list_item.setContentLookup(False)
            list_item.setProperty('IsPlayable', 'true')
            action = 'play_live' if item_data['endts'] > (now_ts - 10) else 'play_archive' # pokud porad jeste neskoncil, pusti se live
            url = get_url(action=action, id=json.dumps(payload), direct=False, mode='start')
            xbmcplugin.addDirectoryItem(_handle, url, list_item, False)

    if day_min > 0:
        day = date.today() - timedelta(days=day_min - 1)
        den_label = f"{day_translation_short[day.strftime('%w')]} {day.strftime('%d.%m.')}"
        url = get_url(action='list_program', id=id, day_min=day_min - 1, label=f"{label.rsplit(' / ')[0]} / {den_label}")
        item = xbmcgui.ListItem(label='Následující den')
        arrow = os.path.join(icons_dir, 'next_arrow.png')
        item.setArt({'thumb': arrow, 'icon': arrow})
        xbmcplugin.addDirectoryItem(_handle, url, item, True)
    xbmcplugin.endOfDirectory(_handle, updateListing=True, cacheToDisc=False)
