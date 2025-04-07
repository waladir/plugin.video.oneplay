# -*- coding: utf-8 -*-
import sys
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
from resources.lib.session import Session
from resources.lib.api import API
from resources.lib.epg import get_item_detail, epg_listitem

_handle = int(sys.argv[1])

def list_search(label):
    xbmcplugin.setPluginCategory(_handle, label)
    list_item = xbmcgui.ListItem(label='Nové hledání')
    url = get_url(action='program_search', query = '-----', label = label + ' / ' + 'Nové hledání')  
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    history = load_search_history()
    for item in history:
        list_item = xbmcgui.ListItem(label=item)
        url = get_url(action='program_search', query = item, label = label + ' / ' + item)  
        list_item.addContextMenuItems([('Smazat', 'RunPlugin(plugin://' + plugin_id + '?action=delete_search&query=' + quote(item) + ')')])
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle,cacheToDisc = False)

def program_search(query, label):
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'movies')
    if query == '-----':
        input = xbmc.Keyboard('', 'Hledat')
        input.doModal()
        if not input.isConfirmed(): 
            return
        query = input.getText()
        if len(query) == 0:
            xbmcgui.Dialog().notification('Oneplay', 'Je potřeba zadat vyhledávaný řetězec', xbmcgui.NOTIFICATION_ERROR, 5000)
            return   
        else:
            save_search_history(query)
    session = Session()
    api = API()

    post = {"payload":{"query":query}}
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/page.search.display', data = post, session = session)    
    if 'err' not in data:
        if 'blocks' in data['layout']:
            for block in data['layout']['blocks']:
                if block['schema'] == 'CarouselBlock':
                    if block['template'] == 'searchPortrait':
                        for carousel in block['carousels']:
                            for item in carousel['tiles']:
                                if item['action']['params']['schema'] == 'PageContentDisplayApiAction':
                                    item_detail = get_item_detail(item['action']['params']['payload']['contentId'], False)
                                    list_item = xbmcgui.ListItem(label = item['title'])
                                    image = item['image'].replace('{WIDTH}', '320').replace('{HEIGHT}', '480')
                                    list_item.setArt({'poster': image})    
                                    list_item.setInfo('video', {'mediatype':'movie', 'title': item['title']}) 
                                    list_item = epg_listitem(list_item, item_detail, None)
                                    if item['action']['params']['contentType'] == 'show':
                                        menus = [('Přidat do oblíbených Oneplay', 'RunPlugin(plugin://' + plugin_id + '?action=add_favourite&type=show&id=' + item['action']['params']['payload']['contentId'] + '&image=' + image + '&title=' + item['title'] + ')')]
                                        list_item.addContextMenuItems(menus)       
                                        url = get_url(action = 'list_show', id = item['action']['params']['payload']['contentId'], label = label + ' / ' + item['title'] )
                                        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
                                    elif item['action']['params']['contentType'] == 'movie':
                                        list_item.setContentLookup(False)          
                                        list_item.setProperty('IsPlayable', 'true')
                                        menus = [('Přidat do oblíbených Oneplay', 'RunPlugin(plugin://' + plugin_id + '?action=add_favourite&type=item&id=' + item['action']['params']['payload']['contentId'] + '&image=' + image + '&title=' + item['title'] + ')')]
                                        list_item.addContextMenuItems(menus)       
                                        url = get_url(action = 'play_archive', id = item['action']['params']['payload']['contentId'])
                                        xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
                                    else:
                                        xbmcgui.Dialog().notification('Oneplay','Neznámý typ: ' + item['action']['params']['contentType'], xbmcgui.NOTIFICATION_INFO, 2000)                                    
        else:
            xbmcgui.Dialog().notification('Oneplay','Nic nenalezeno', xbmcgui.NOTIFICATION_INFO, 3000)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)              

def save_search_history(query):
    addon = xbmcaddon.Addon()
    addon_userdata_dir = translatePath(addon.getAddonInfo('profile')) 
    max_history = int(addon.getSetting('search_history'))
    cnt = 0
    history = []
    filename = addon_userdata_dir + 'search_history.txt'
    try:
        with open(filename, 'r') as file:
            for line in file:
                item = line[:-1]
                history.append(item)
    except IOError:
        history = []
    history.insert(0,query)
    with open(filename, 'w') as file:
        for item  in history:
            cnt = cnt + 1
            if cnt <= max_history:
                file.write('%s\n' % item)

def load_search_history():
    history = []
    addon = xbmcaddon.Addon()
    addon_userdata_dir = translatePath(addon.getAddonInfo('profile')) 
    filename = addon_userdata_dir + 'search_history.txt'
    try:
        with open(filename, 'r') as file:
            for line in file:
                item = line[:-1]
                history.append(item)
    except IOError:
        history = []
    return history

def delete_search(query):
    addon = xbmcaddon.Addon()
    addon_userdata_dir = translatePath(addon.getAddonInfo('profile')) 
    filename = addon_userdata_dir + 'search_history.txt'
    history = load_search_history()
    for item in history:
        if item == query:
            history.remove(item)
    try:
        with open(filename, 'w') as file:
            for item in history:
                file.write('%s\n' % item)
    except IOError:
        pass
    xbmc.executebuiltin('Container.Refresh')

