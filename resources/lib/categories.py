# -*- coding: utf-8 -*-
import sys
import os
import xbmcplugin
import xbmcgui
import xbmcaddon

from resources.lib.session import Session
from resources.lib.api import API
from resources.lib.epg import get_item_detail, epg_listitem
from resources.lib.utils import get_url, encode

_handle = int(sys.argv[1])

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
            if block['schema'] == 'CarouselBlock':
                if carouselId is None and criteria is None:
                    list_item = xbmcgui.ListItem(label = block['header']['title'])
                    url = get_url(action='list_category', id = id, carouselId = block['id'], criteria = encode(criteria), label = label + ' / ' + block['header']['title'])  
                    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
                elif block['id'] == carouselId or criteria is not None:
                    for carousel in block['carousels']:
                        for item in carousel['tiles']:
                            if item['action']['params']['schema'] == 'PageContentDisplayApiAction':
                                item_detail = get_item_detail(item['action']['params']['payload']['contentId'])
                                list_item = xbmcgui.ListItem(label = item['title'])
                                image = item['image'].replace('{WIDTH}', '320').replace('{HEIGHT}', '480')
                                list_item.setArt({'thumb': image, 'icon': image})    
                                list_item.setInfo('video', {'mediatype':'movie', 'title': item['title']}) 
                                list_item = epg_listitem(list_item, item_detail, None)
                                if item['action']['params']['contentType'] == 'show':
                                    url = get_url(action = 'list_show', id = item['action']['params']['payload']['contentId'], label = label + ' / ' + item['title'] )
                                    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
                                elif item['action']['params']['contentType']  in ['movie','epgitem']:
                                    list_item.setContentLookup(False)          
                                    list_item.setProperty('IsPlayable', 'true')
                                    url = get_url(action = 'play_archive', id = item['action']['params']['payload']['contentId'])
                                    xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
                                else:
                                    xbmcgui.Dialog().notification('Oneplay','Neznámý typ: ' + item['action']['params']['contentType'], xbmcgui.NOTIFICATION_INFO, 2000)                                    
                            elif item['action']['params']['schema'] == 'PageCategoryDisplayApiAction':
                                list_item = xbmcgui.ListItem(label = item['title'])
                                image = item['image'].replace('{WIDTH}', '540').replace('{HEIGHT}', '320')
                                list_item.setArt({'thumb': image, 'icon': image})    
                                url = get_url(action='list_category', id = item['action']['params']['payload']['categoryId'], criteria = encode(criteria), label = label + ' / ' + item['title'])  
                                xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
                            elif item['action']['params']['schema'] == 'ContentPlayApiAction':
                                list_item = xbmcgui.ListItem(label = item['title'])
                                image = item['image'].replace('{WIDTH}', '320').replace('{HEIGHT}', '480')
                                list_item.setArt({'thumb': image, 'icon': image})    
                                list_item.setInfo('video', {'mediatype':'movie', 'title': item['title']}) 
                                list_item.setContentLookup(False)          
                                list_item.setProperty('IsPlayable', 'true')
                                url = get_url(action = 'play_archive', id = item['action']['params']['payload']['criteria']['contentId'])
                                xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
                            else:
                                xbmcgui.Dialog().notification('Oneplay','Neznámá položka: ' + item['action']['params']['schema'], xbmcgui.NOTIFICATION_INFO, 2000)                                    
                        if carousel['paging']['next'] == True:
                            list_item = xbmcgui.ListItem(label='Následující strana')
                            url = get_url(action='list_carousel', id = carousel['id'], criteria = encode(criteria), page = 2, label = label)  
                            list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'next_arrow.png'), 'icon' : os.path.join(icons_dir , 'next_arrow.png') })
                            xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)              

def list_season(carouselId, id, page, label):
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'episodes')
    addon = xbmcaddon.Addon()
    session = Session()
    api = API()
    list_season_internal(addon, api, session, carouselId, id, page, label)

def list_season_internal(addon, api, session, carouselId, id, page, label):
    page = int(page)
    icons_dir = os.path.join(addon.getAddonInfo('path'), 'resources','images')
    episodes_paging = addon.getSetting('episodes_paging') == 'true'
    post = {"payload":{"carouselId":carouselId,"paging":{"count":12,"position":12*(page-1)+1},"criteria":{"filterCriterias":id,"sortOption":"DESC"}}}
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/carousel.display', data = post, session = session)
    if page > 1 and episodes_paging:
        list_item = xbmcgui.ListItem(label='Přechozí strana')
        url = get_url(action = 'list_season', carouselId = carouselId, id = id, page = page-1, label = label)       
        list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'previous_arrow.png'), 'icon' : os.path.join(icons_dir , 'previous_arrow.png') })
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    for item in data['carousel']['tiles']:
        if 'params' in item['action'] and 'contentId' in item['action']['params']['payload']['criteria']:
            if 'subTitle' in item:
                item['title'] = item['title'] + ' ' + item['subTitle']
            list_item = xbmcgui.ListItem(label = item['title'])
            image = item['image'].replace('{WIDTH}', '480').replace('{HEIGHT}', '320')
            list_item.setArt({'thumb': image, 'icon': image})    
            list_item.setInfo('video', {'mediatype':'movie', 'title': item['title']}) 
            list_item.setContentLookup(False)          
            list_item.setProperty('IsPlayable', 'true')
            url = get_url(action = 'play_archive', id = item['action']['params']['payload']['criteria']['contentId'])
            xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    if data['carousel']['paging']['next'] == True:
        if episodes_paging:
            list_item = xbmcgui.ListItem(label='Následující strana')
            url = get_url(action = 'list_season', carouselId = carouselId, id = id, page = page+1, label = label)       
            list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'next_arrow.png'), 'icon' : os.path.join(icons_dir , 'next_arrow.png') })
            xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
        else:
            list_season_internal(addon, api, session, carouselId, id, page+1, label)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)  

def list_show(id, label):
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'episodes')
    session = Session()
    api = API()
    post = {"payload":{"contentId":id}}
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
                season_select = False
                if 'criteria' in carousel:
                    for criteria in carousel['criteria']:
                        if criteria['schema'] == 'CarouselGenericFilter' and criteria['template'] == 'showSeason':
                            for item in criteria['items']:           
                                season_select = True
                                list_item = xbmcgui.ListItem(label = item['label'])
                                url = get_url(action = 'list_season', carouselId = carousel['id'], id = item['criteria'], page = 1, label = label + ' / ' + item['label'])
                                xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
                if season_select == False:
                    for item in carousel['tiles']:
                        if 'params' in item['action'] and 'contentId' in item['action']['params']['payload']['criteria']:
                            if 'subTitle' in item:
                                item['title'] = item['title'] + ' ' + item['subTitle']
                            list_item = xbmcgui.ListItem(label = item['title'])
                            image = item['image'].replace('{WIDTH}', '480').replace('{HEIGHT}', '320')
                            list_item.setArt({'thumb': image, 'icon': image})    
                            list_item.setInfo('video', {'mediatype':'movie', 'title': item['title']}) 
                            list_item.setContentLookup(False)          
                            list_item.setProperty('IsPlayable', 'true')
                            url = get_url(action = 'play_archive', id = item['action']['params']['payload']['criteria']['contentId'])
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
            list_item.setArt({'thumb': image, 'icon': image})    
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
                            url = get_url(action='list_category', id = filter['action']['params']['payload']['categoryId'], criteria = encode(criteria), label = label + ' / ' + filter['title'])  
                            xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)              


