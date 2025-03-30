# -*- coding: utf-8 -*-
import sys
import xbmcgui
import xbmcplugin
import xbmcaddon

from datetime import datetime

from resources.lib.channels import Channels 
from resources.lib.epg import get_live_epg, epg_listitem
from resources.lib.utils import get_url, get_color, plugin_id

if len(sys.argv) > 1:
    _handle = int(sys.argv[1])

def list_live(label):
    addon = xbmcaddon.Addon()
    xbmcplugin.setPluginCategory(_handle, label)
    if addon.getSetting('default_tv_view') == 'false':
        xbmcplugin.setContent(_handle, 'tvshows')
    channels = Channels()
    channels_list = channels.get_channels_list('channel_number')
    epg = get_live_epg()
    cnt = 0
    for num in sorted(channels_list.keys()):
        cnt += 1
        if addon.getSetting('channel_numbers') == 'číslo kanálu':
            channel_number = str(num) + '. '
        elif addon.getSetting('channel_numbers') == 'pořadové číslo':
            channel_number = str(cnt) + '. '
        else:
            channel_number = ''
        if channels_list[num]['id'] in epg:
            epg_item = epg[channels_list[num]['id']]
            list_item = xbmcgui.ListItem(label = channel_number + channels_list[num]['name'] + '[COLOR ' + get_color(addon.getSetting('label_color_live')) + '] | ' + epg_item['title'] + ' | ' + datetime.fromtimestamp(epg_item['startts']).strftime('%H:%M') + ' - ' + datetime.fromtimestamp(epg_item['endts']).strftime('%H:%M') + '[/COLOR]')
            list_item = epg_listitem(list_item = list_item, epg = epg_item, icon = channels_list[num]['logo'])
            menus = [('Přidat nahrávku', 'RunPlugin(plugin://' + plugin_id + '?action=add_recording&id=' + str(epg_item['id']) + ')')]
            list_item.addContextMenuItems(menus)       
        else:
            epg_item = {}
            list_item = xbmcgui.ListItem(label = channel_number + channels_list[num]['name'])
            list_item.setArt({'thumb': channels_list[num]['logo'], 'icon': channels_list[num]['logo']})    
            list_item.setInfo('video', {'mediatype':'movie', 'title': channels_list[num]['name']}) 
        list_item.setContentLookup(False)          
        list_item.setProperty('IsPlayable', 'true')
        url = get_url(action = 'play_live', id = channels_list[num]['id'], mode = 'start', title = channels_list[num]['name'])
        xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)


