# -*- coding: utf-8 -*-
import sys
import os
import xbmcplugin
import xbmcgui
import xbmcaddon

import time 
from datetime import datetime

from resources.lib.session import Session
from resources.lib.api import API
from resources.lib.epg import get_item_detail, epg_listitem
from resources.lib.utils import get_url, plugin_id, get_kodi_version

if len(sys.argv) > 1:
    _handle = int(sys.argv[1])

def get_episodes(carouselId, id, season_title, limit = 1000):
    session = Session()
    api = API()
    get_page = True
    page = 1
    cnt = 0
    episodes = {}
    filterCriterias = id
    while get_page == True:
        post = {"payload":{"carouselId":carouselId,"paging":{"count":12,"position":12*(page-1)+1},"criteria":{"filterCriterias":filterCriterias,"sortOption":"DESC"}}}
        data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/carousel.display', data = post, session = session)
        if not 'err' in data and 'carousel' in data:
            for item in data['carousel']['tiles']:
                if 'params' in item['action'] and ('contentId' in item['action']['params']['payload'] or 'contentId' in item['action']['params']['payload']['criteria']):
                    cnt += 1
                    if 'subTitle' in item:
                        item['title'] = item['title'] + ' ' + item['subTitle']
                    title = item['title']
                    subtitle = ''
                    if 'additionalFragments' in item and len(item['additionalFragments']) > 0 and 'labels' in item['additionalFragments'][0]:
                        for label in item['labels']:
                            if 'Vyprší' not in label['name']:
                                subtitle = label['name']
                        for label in item['additionalFragments'][0]['labels']:
                            if ':' in label['name']:
                                if len(subtitle) > 0:
                                    subtitle += ' | ' + label['name']
                                else:
                                    subtitle = label['name']
                            if 'Díl' in label['name']:
                                if len(subtitle) > 0:
                                    subtitle += ' | ' + label['name']
                                else:
                                    subtitle = label['name']

                    image = item['image'].replace('{WIDTH}', '480').replace('{HEIGHT}', '320')
                    if 'contentId' in item['action']['params']['payload']:
                        id = item['action']['params']['payload']['contentId']
                    else:
                        id = item['action']['params']['payload']['criteria']['contentId']
                    episodeId = int(id.split('.')[1])
                    if id not in episodes:
                        episodes.update({episodeId : {'id' : id, 'season_title' : season_title, 'title' : title, 'subtitle' : subtitle, 'image' : image}})
                    if cnt >= limit:
                        get_page = False
                        break
            if data['carousel']['paging']['next'] == True:
                page = page + 1
            else:
                get_page = False
        else:
            get_page = False
    return episodes

def get_shows(id, last_season = False):
    session = Session()
    api = API()
    post = {"payload":{"contentId":id}}
    seasons = []
    shows = []
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/page.content.display', data = post, session = session)
    for block in data['layout']['blocks']:
        if block['schema'] == 'TabBlock' and block['template'] == 'tabs':
            for tab in block['tabs']:
                if tab['label']['name'] == 'Celé díly':
                    if tab['isActive'] == True:
                        data = block
                    else:
                        post = {"payload":{"tabId":tab['id']}}
                        data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/tab.display', data = post, session = session)
    for block in data['layout']['blocks']:
        if block['schema'] == 'CarouselBlock' and block['template'] in ['list','grid']:
            for carousel in block['carousels']:
                if 'criteria' in carousel:
                    for criteria in carousel['criteria']:
                        if criteria['schema'] == 'CarouselGenericFilter' and criteria['template'] == 'showSeason':
                            first = True
                            season_item = None
                            for season in criteria['items']:   
                                season_item = {'title' : season['label'], 'id' : season['criteria'], 'carouselId' : carousel['id']}
                                if last_season == False and season_item not in seasons:
                                    seasons.append(season_item)
                                if last_season == True and first == True and '.' in season['label'] and season['label'].split('.')[0] != '1':
                                    break
                                first = False
                            if last_season == True:
                                seasons.append(season_item)
                if len(seasons) == 0:
                    for item in carousel['tiles']:
                        if 'params' in item['action'] and 'contentId' in item['action']['params']['payload']['criteria']:
                            if 'subTitle' in item:
                                item['title'] = item['title'] + ' ' + item['subTitle']
                            image = item['image'].replace('{WIDTH}', '480').replace('{HEIGHT}', '320')
                            show_item = {'title' : item['title'], 'id' : item['action']['params']['payload']['criteria']['contentId'], 'image' : image}
                            shows.append(show_item)
    return {'seasons' : seasons, 'shows' : shows}

def list_categories(label):
    xbmcplugin.setPluginCategory(_handle, label)
    session = Session()
    api = API()
    post = {"payload":{"reason":"start"}}
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/app.init', data = post, session = session) 
    if 'err' in data or not 'menu' in data:
        xbmcgui.Dialog().notification('Oneplay','Problém při načtení kategorií', xbmcgui.NOTIFICATION_ERROR, 5000)
    else:
        for group in data['menu']['groups']:
            if group['position'] == 'top':
                for item in group['items']:
                    if item['action']['call'] == 'page.category.display':
                        list_item = xbmcgui.ListItem(label = item['title'])
                        url = get_url(action='list_category', id = item['action']['params']['payload']['categoryId'], label = label + ' / ' + item['title'])  
                        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)    

def list_category(id, carouselId, criteria, label):
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'movies')
    addon = xbmcaddon.Addon()
    icons_dir = os.path.join(addon.getAddonInfo('path'), 'resources','images')
    session = Session()
    api = API()
    if criteria is not None:
        post = {"payload":{"categoryId":id,"criteria":{"filterCriterias":criteria}}}
    else:
        post = {"payload":{"categoryId":id}}
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/page.category.display', data = post, session = session) 
    if 'err' not in data:
        for block in data['layout']['blocks']:
            if block['schema'] == 'BreadcrumbBlock':
                for item in block['menu']['groups'][0]['items']:
                    if item['schema'] == 'SubMenu':
                        list_item = xbmcgui.ListItem(label = item['title'])
                        url = get_url(action='list_filters', id = id, filters = item['id'], label = label)  
                        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
            if block['schema'] in ['CarouselBlock', 'TabBlock']:
                if carouselId is None and criteria is None and block['schema'] != 'TabBlock':
                    list_item = xbmcgui.ListItem(label = block['header']['title'])
                    url = get_url(action='list_category', id = id, carouselId = block['id'], criteria = criteria, label = label + ' / ' + block['header']['title'])  
                    menus = [('Přidat do oblíbených Oneplay', 'RunPlugin(plugin://' + plugin_id + '?action=add_favourite&type=category&id=' + id + '~' + block['id'] + '~' + str(criteria) + '&image=None&title=' + (label + ' / ' + block['header']['title']).replace('Kategorie / ','') + ')')]
                    list_item.addContextMenuItems(menus)       
                    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
                elif block['id'] == carouselId or criteria is not None or block['schema'] == 'TabBlock':
                    if block['schema'] == 'TabBlock':
                        blocks =  block['layout']['blocks']
                    else:
                        blocks = [block]
                    for block in blocks:
                        for carousel in block['carousels']:
                            for item in carousel['tiles']:
                                if item['action']['params']['schema'] == 'PageContentDisplayApiAction':
                                    item_detail = get_item_detail(item['action']['params']['payload']['contentId'])
                                    if id == '8' and 'additionalFragments' in item:
                                        year = datetime.now().year
                                        expiration = int(time.mktime(time.strptime(item['additionalFragments'][0]['labels'][0]['name'] + str(year) + ' ' + item['additionalFragments'][0]['labels'][1]['name'], '%d.%m.%Y %H:%M'))) + 30*24*60*60
                                        item['title'] = item['title'] + '\n[COLOR=gray]' + item['labels'][0]['name'] + ' | ' + item['additionalFragments'][0]['labels'][0]['name'] + ' ' + item['additionalFragments'][0]['labels'][1]['name'] + ' (do ' + datetime.fromtimestamp(expiration).strftime('%d.%m').lstrip("0").replace(" 0", " ") +')[/COLOR]'
                                    list_item = xbmcgui.ListItem(label = item['title'])
                                    image = item['image'].replace('{WIDTH}', '320').replace('{HEIGHT}', '480')
                                    list_item.setArt({'poster': image})    
                                    list_item.setInfo('video', {'mediatype':'movie', 'title': item['title']}) 
                                    list_item = epg_listitem(list_item, item_detail, None)
                                    if item['action']['params']['contentType'] == 'show':
                                        url = get_url(action = 'list_show', id = item['action']['params']['payload']['contentId'], label = label + ' / ' + item['title'] )
                                        menus = [('Přidat do oblíbených Oneplay', 'RunPlugin(plugin://' + plugin_id + '?action=add_favourite&type=show&id=' + item['action']['params']['payload']['contentId'] + '&image=' + image + '&title=' + item['title'] + ')')]
                                        if id == '8':
                                            menus.append(('Smazat nahrávku', 'RunPlugin(plugin://' + plugin_id + '?action=delete_recording&id=' + item['action']['params']['payload']['contentId'] + ')'))
                                        list_item.addContextMenuItems(menus)       
                                        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
                                    elif item['action']['params']['contentType']  in ['movie','epgitem','match']:
                                        list_item.setContentLookup(False)          
                                        list_item.setProperty('IsPlayable', 'true')
                                        if 'startMode' in item['action']['params']['payload']:
                                            url = get_url(action = 'play_live', id = item['action']['params']['payload']['contentId'].replace('channel.'), mode = 'start')
                                        else:
                                            url = get_url(action = 'play_archive', id = item['action']['params']['payload']['contentId'])
                                        menus = [('Přidat do oblíbených Oneplay', 'RunPlugin(plugin://' + plugin_id + '?action=add_favourite&type=item&id=' + item['action']['params']['payload']['contentId'] + '&image=' + image + '&title=' + item['title'] + ')')]
                                        if id == '8':
                                            menus.append(('Smazat nahrávku', 'RunPlugin(plugin://' + plugin_id + '?action=delete_recording&id=' + item['action']['params']['payload']['contentId'] + ')'))
                                        list_item.addContextMenuItems(menus)       
                                        xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
                                    else:
                                        xbmcgui.Dialog().notification('Oneplay','Neznámý typ: ' + item['action']['params']['contentType'], xbmcgui.NOTIFICATION_INFO, 2000)                                    
                                elif item['action']['params']['schema'] == 'PageCategoryDisplayApiAction':
                                    list_item = xbmcgui.ListItem(label = item['title'])
                                    image = item['image'].replace('{WIDTH}', '540').replace('{HEIGHT}', '320')
                                    list_item.setArt({'poster': image})    
                                    url = get_url(action='list_category', id = item['action']['params']['payload']['categoryId'], criteria = criteria, label = label + ' / ' + item['title'])  
                                    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
                                elif item['action']['params']['schema'] == 'ContentPlayApiAction':
                                    list_item = xbmcgui.ListItem(label = item['title'])
                                    image = item['image'].replace('{WIDTH}', '320').replace('{HEIGHT}', '480')
                                    list_item.setArt({'poster': image})    
                                    list_item.setInfo('video', {'mediatype':'movie', 'title': item['title']}) 
                                    list_item.setContentLookup(False)          
                                    list_item.setProperty('IsPlayable', 'true')
                                    if 'startMode' in item['action']['params']['payload']:
                                        url = get_url(action = 'play_live', id = item['action']['params']['payload']['criteria']['contentId'].replace('channel.',''), mode = 'start')
                                    else:
                                        url = get_url(action = 'play_archive', id = item['action']['params']['payload']['criteria']['contentId'])
                                    menus = [('Přidat do oblíbených Oneplay', 'RunPlugin(plugin://' + plugin_id + '?action=add_favourite&type=item&id=' + item['action']['params']['payload']['criteria']['contentId'] + '&image=' + image + '&title=' + item['title'] + ')')]
                                    list_item.addContextMenuItems(menus)       
                                    xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
                                else:
                                    xbmcgui.Dialog().notification('Oneplay','Neznámá položka: ' + item['action']['params']['schema'], xbmcgui.NOTIFICATION_INFO, 2000)                                    
                            if 'pagein' in carousel and carousel['paging']['next'] == True:
                                list_item = xbmcgui.ListItem(label='Následující strana')
                                url = get_url(action='list_carousel', id = carousel['id'], criteria = criteria, page = 2, label = label)  
                                list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'next_arrow.png'), 'icon' : os.path.join(icons_dir , 'next_arrow.png') })
                                xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)              

def list_season(carouselId, id, label):
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'episodes')
    season_title = label.split(' / ')[-2] + ' / ' + label.split(' / ')[-1]
    kodi_version = get_kodi_version()
    episodes = get_episodes(carouselId, id, season_title)
    for episodeId in episodes:
        item = episodes[episodeId]
        list_item = xbmcgui.ListItem(label = item['title'])
        list_item.setArt({'poster': item['image']})    
        if kodi_version >= 20:
            infotag = list_item.getVideoInfoTag()
            infotag.setMediaType('episode')
        else:
            list_item.setInfo('video', {'mediatype' : 'episode'})
        if kodi_version >= 20:
            infotag.setTitle(item['title'])
        else:
            list_item.setInfo('video', {'title' : item['title']})
        if kodi_version >= 20:
            infotag.setTvShowTitle(item['season_title'])
        else:
            list_item.setInfo('video', {'tvshowtitle' : item['season_title']})   
        list_item.setContentLookup(False)          
        list_item.setProperty('IsPlayable', 'true')
        url = get_url(action = 'play_archive', id = item['id'])
        xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)  

def list_show(id, label):
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'episodes')
    data = get_shows(id)
    if len(data['seasons']) > 0:
        for season in data['seasons']:
            list_item = xbmcgui.ListItem(label = season['title'])
            url = get_url(action = 'list_season', carouselId = season['carouselId'], id = season['id'], label = label + ' / ' + season['title'])
            menus = [('Přidat do oblíbených Oneplay', 'RunPlugin(plugin://' + plugin_id + '?action=add_favourite&type=season&id=' + season['id'] + '~' + season['carouselId'] + '&image=None&title=' + label.split(' / ')[-1] + ' / ' + season['title'] + ')')]
            list_item.addContextMenuItems(menus)       
            xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    else:
        for show in data['shows']:
            list_item = xbmcgui.ListItem(label = show['title'])
            list_item.setArt({'poster': show['image']})    
            list_item.setInfo('video', {'mediatype':'movie', 'title': show['title']}) 
            list_item.setContentLookup(False)          
            list_item.setProperty('IsPlayable', 'true')
            url = get_url(action = 'play_archive', id = show['id'])
            xbmcplugin.addDirectoryItem(_handle, url, list_item, False)                            
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)  

def list_tv_episodes(id, label):
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'episodes')
    session = Session()
    api = API()
    post = {"payload":{"contentId":id}}
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/page.content.display', data = post, session = session)
    for block in data['layout']['blocks']:
        if block['schema'] == 'CarouselBlock' and 'header' in block and block['header']['title'] == 'Vysílané v TV':
            carouselId = block['carousels'][0]['id']
            kodi_version = get_kodi_version()
            episodes = get_episodes(carouselId, id, '')
            for episodeId in episodes:
                item = episodes[episodeId]
                if len(item['subtitle']) > 0:
                    list_item = xbmcgui.ListItem(label = item['title'] + '\n[COLOR=gray]' + item['subtitle'] + '[/COLOR]')
                else:
                    list_item = xbmcgui.ListItem(label = item['title'])
                list_item.setArt({'poster': item['image']})    
                if kodi_version >= 20:
                    infotag = list_item.getVideoInfoTag()
                    infotag.setMediaType('episode')
                else:
                    list_item.setInfo('video', {'mediatype' : 'episode'})
                if kodi_version >= 20:
                    infotag.setTitle(item['title'])
                else:
                    list_item.setInfo('video', {'title' : item['title']})
                if kodi_version >= 20:
                    infotag.setTvShowTitle(item['subtitle'])
                else:
                    list_item.setInfo('video', {'tvshowtitle' : item['season_title']})   
                list_item.setContentLookup(False)          
                list_item.setProperty('IsPlayable', 'true')
                url = get_url(action = 'play_archive', id = item['id'])
                xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)  

def list_carousel(id, criteria, page, label):
    page = int(page)
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'movies')    
    addon = xbmcaddon.Addon()
    icons_dir = os.path.join(addon.getAddonInfo('path'), 'resources','images')
    session = Session()
    api = API()
    post = {"payload":{"carouselId":id,"paging":{"count":24,"position":24*(page-1)+1},"criteria":{"filterCriterias":criteria,"sortOption":"sorting-date-desc"}}}
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/carousel.display', data = post, session = session) 
    if page > 1:
        list_item = xbmcgui.ListItem(label='Přechozí strana (' + str(page-1) + '/' + str(data['carousel']['paging']['pageCount']) + ')')
        url = get_url(action='list_carousel', id = id, criteria = filter, page = page-1, label = label)  
        list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'previous_arrow.png'), 'icon' : os.path.join(icons_dir , 'previous_arrow.png') })
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    for item in data['carousel']['tiles']:
        if 'contentId' in item['action']['params']['payload']:
            item_detail = get_item_detail(item['action']['params']['payload']['contentId'])
            list_item = xbmcgui.ListItem(label = item['title'])
            image = item['image'].replace('{WIDTH}', '320').replace('{HEIGHT}', '480')
            list_item.setArt({'poster': image})    
            list_item.setInfo('video', {'mediatype':'movie', 'title': item['title']}) 
            list_item = epg_listitem(list_item, item_detail, None)        
            if item['action']['params']['contentType'] == 'show':
                url = get_url(action = 'list_show', id = item['action']['params']['payload']['contentId'], label = label + ' / ' + item['title'] )
                xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
            else:
                list_item.setContentLookup(False)          
                list_item.setProperty('IsPlayable', 'true')
                url = get_url(action = 'play_archive', id = item['action']['params']['payload']['contentId'])
                xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    if data['carousel']['paging']['next'] == True:
        list_item = xbmcgui.ListItem(label='Následující strana (' + str(page+1) + '/' + str(data['carousel']['paging']['pageCount']) + ')')
        url = get_url(action='list_carousel', id = id, criteria = filter, page = page+1, label = label)  
        list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'next_arrow.png'), 'icon' : os.path.join(icons_dir , 'next_arrow.png') })
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)              

def list_filters(id, filters, label):
    xbmcplugin.setPluginCategory(_handle, label)
    session = Session()
    api = API()
    post = {"payload":{"categoryId":id}}
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/page.category.display', data = post, session = session) 
    for block in data['layout']['blocks']:
        if block['schema'] == 'BreadcrumbBlock':
            for item in block['menu']['groups'][0]['items']:
                if item['schema'] == 'SubMenu' and item['id'] == filters:
                    for filter in item['groups'][0]['items']:
                        if 'categoryId' in filter['action']['params']['payload']:
                            list_item = xbmcgui.ListItem(label = filter['title'])
                            if 'criteria' in filter['action']['params']['payload']:
                                criteria = filter['action']['params']['payload']['criteria']['filterCriterias']
                            else:
                                criteria = ''
                            url = get_url(action='list_category', id = filter['action']['params']['payload']['categoryId'], criteria = criteria, label = label + ' / ' + filter['title'])  
                            menus = [('Přidat do oblíbených Oneplay', 'RunPlugin(plugin://' + plugin_id + '?action=add_favourite&type=category&id=' + filter['action']['params']['payload']['categoryId'] + '~None~' + str(criteria) + '&image=None&title=' + (label + ' / ' + filter['title']).replace('Kategorie / ','') + ')')]
                            list_item.addContextMenuItems(menus)       
                            xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)              


