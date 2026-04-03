# -*- coding: utf-8 -*-
import sys
import os
import xbmcplugin
import xbmcgui
import xbmcaddon

import json 
from datetime import datetime

from resources.lib.session import Session
from resources.lib.api import API
from resources.lib.epg import get_item_detail, epg_listitem, get_epg, get_live_epg
from resources.lib.utils import get_url, plugin_id

if len(sys.argv) > 1:
    _handle = int(sys.argv[1])

def parse_tiles(label, carousel, page):
    """Parsování dlaždic"""
    epg = None
    addon = xbmcaddon.Addon()
    icons_dir = os.path.join(addon.getAddonInfo('path'), 'resources', 'images')
    is_recording = 'page:8' in carousel['id'] # pokud je nactane kategorie s nahravkami
    if page > 1:
        page_count = carousel['paging']['pageCount']
        payload = {'criteria': carousel['paging']['criteria'], 'carouselId': carousel['id'], 'paging': {'count': 24, 'position' : (page-2)*24+1}}
        image = os.path.join(icons_dir , 'previous_arrow.png')    
        list_item = xbmcgui.ListItem(label=f"Předchozí strana ({page-1}/{page_count})")
        list_item.setArt({'thumb': image, 'icon': image})            
        url = get_url(action='carousel.display', payload=json.dumps(payload), page=page-1, label=label)
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    for tile in carousel.get('tiles', []):
        print(json.dumps(tile,indent=4))
        params = tile.get('action', {}).get('params', {})
        if params.get('schema') in ['ContentPlayApiAction', 'PageContentDisplayApiAction'] and tile.get('tracking', {}).get('upsell', False) == False and params.get('action', {}).get('call') not in ['user.upsell.preview']: # prehratelna polozka
            contentType = params.get('contentType')
            id = params.get('payload')            
            if not contentType: # osetreni pripadu bez contentType
                contentId = params.get('payload', {}).get('criteria', {}).get('contentId')
                if not contentId:
                    contentId = params.get('payload', {}).get('criteria', {}).get('channel')
                # link na zive vysilani, pouzije se channel
                if 'channel.' in contentId: 
                    channel_id = contentId.replace('channel.', '')
                    time = params.get('payload', {}).get('criteria', {}).get('time')
                    if time:
                        contentType = 'episode'
                        timets = int(datetime.fromisoformat(time).timestamp())                        
                        epg = get_epg(timets, channel_id)
                        if timets in epg:
                            tile['action']['params']['payload'] = {"contentId": epg[timets].get('payload', {}).get('contentId')}
                    else:
                        contentType = 'channel'
                        if not epg:
                            epg, _ = get_live_epg()
                        # zmena payloadu z kanalu na epgitem
                        if channel_id in epg:
                            id = {"contentId": epg[channel_id]['payload']['contentId']}
                            tile['action']['params']['payload'] = {"contentId": epg.get(channel_id).get('payload').get('contentId')}         
                # epizoda
                elif 'episode.' in contentId:
                    contentType = 'episode'
            # pro epizodu používáme přímo id (v sezóně nemá payload z API), direct=True
            data = get_item_detail(id, item=tile, download_data=(contentType not in ['episode']))
            list_item = xbmcgui.ListItem(label=data.get('title', tile.get('title')))
            list_item = epg_listitem(list_item, data, None)
            payload = params.get('payload', {})
            contentId = payload.get('contentId') or payload.get('deeplink', {}).get('epgItem')
            menu = []
            if contentId:
                menu_label = 'Smazat nahrávku' if is_recording else 'Přidat nahrávku'
                action = 'delete_recording' if is_recording else 'add_recording'
                menu.append([menu_label, f"RunPlugin(plugin://{plugin_id}?action={action}&id={contentId})"])
            if contentType in ['show']:
                url = get_url(action='list_show', id=json.dumps(data.get('payload') or id), label=f"{label} / {tile['title']}" if label else tile['title'])
                menu.append(['Přidat do oblíbených Oneplay', f"RunPlugin(plugin://{plugin_id}?action=add_favourite&type=show&id={contentId}&image={data.get('cover')}&title={tile.get('title')})"])
                list_item.addContextMenuItems(menu)
                xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
            elif contentType in ['movie', 'epgitem', 'channel', 'episode']:
                id = id if contentType == 'episode' else (data.get('payload') or id)            
                is_direct = True if contentType == 'episode' else ('payload' in data)
                list_item.setContentLookup(False)          
                list_item.setProperty('IsPlayable', 'true')
                # direct se pouzije, pokud payload je vraceny z API page_content_display (pri prehrani se uz nebude zbytecne volat nebo se jedna o epizodu
                url = get_url(action='play_archive', id=json.dumps(id), direct=is_direct, mode='start', title=tile['title'])
                menu.append(['Přidat do oblíbených Oneplay', f"RunPlugin(plugin://{plugin_id}?action=add_favourite&type=item&id={contentId}&image={data.get('cover')}&title={tile.get('title')})"])
                list_item.addContextMenuItems(menu)
                xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
            elif contentType in ['competition', 'team', 'collection']:
                continue
            else:
                xbmcgui.Dialog().notification('Oneplay',f"Neznámý contentType: {contentType}", xbmcgui.NOTIFICATION_INFO, 3000)
    if carousel.get('paging', {}).get('next', False) and carousel.get('paging').get('pageCount'): # pokud je v datech priznak, ze existuje dalsi strana, zobrazi se polozka pro prechod na nasledujici stranu
        page_count = carousel.get('paging').get('pageCount')
        payload = {'criteria': carousel['paging']['criteria'], 'carouselId': carousel['id'], 'paging': {'count': 24, 'position' : (page)*24+1}}
        image = os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources','images', 'next_arrow.png')    
        list_item = xbmcgui.ListItem(label=f"Následující strana ({page+1}/{page_count})")
        list_item.setArt({'thumb': image, 'icon': image})            
        url = get_url(action='carousel.display', payload=json.dumps(payload), page=page+1, label=label)
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

def carousel_display(label, payload, page):
    """Načte karusel s podporou stránkování. S page=-1 projde všechny strany"""
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'movies')    
    page = int(page)
    payload = json.loads(payload) 
    session, api = Session(), API()
    cnt = 0
    if page > 0:
        carousel = api.carousel_display({'payload': payload}, session)
        parse_tiles(label, carousel, page)
    else:
        while cnt == 0 or carousel.get('paging', {}).get('next') == True:
            cnt += 1
            payload['paging'] = {"count":12,"position":12*(cnt-1)+1}
            carousel = api.carousel_display({'payload': payload}, session)
            parse_tiles(label, carousel, page)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False) 

def parse_carousel(label, params, carousel_id):
    """Parsování konkretního karuselu"""
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'movies')    
    params = json.loads(params)
    session, api = Session(), API()
    data = api.page_category_display({'payload' : params['payload']}, session)
    for block in data:
        if block.get('schema') == 'CarouselBlock':
            carousel = block['carousels'][0]
            if carousel_id in [carousel['id'], 'showMore']: # hleda se shoda podle id karuselu, pokud je showMore, v params uz je filtr
                parse_tiles(label, carousel, 1)
                xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)    
                return

def parse_page_block(block, params, label):
    """Parsování bloku kategorií podle typu"""
    schema = block.get('schema')
    if schema == 'BreadcrumbBlock': # filtry
        for breadcrumb in block['menu']['groups'][0]['items']:
            if breadcrumb['schema'] == 'SubMenu':
                for item in breadcrumb['groups'][0]['items']:
                    get_item(label=breadcrumb['title'], title=breadcrumb['title'], schema='ApiAppAction', call='list_filters', params=params)
                    return
    elif schema == 'CarouselBlock': # karusel
        carousel = block['carousels'][0]
        if block.get('template') in ['contentFilter', 'myListPortraitContinueWatching', 'myListLandscape']: # templates, kde se nacitaji dlazdice primo
            parse_tiles(label, carousel, 1)
        else:
            title = block.get('header', {}).get('title', 'Kategorie')
            list_item = xbmcgui.ListItem(label=title)
            carousel_id = carousel['id']
            if 'showMore' in carousel: # pokud ma priznak showMore, pouzije se filtr, ktery vrati uz konkretni karusel
                params = carousel['showMore']['action']['params']        
                carousel_id = 'showMore'
            url = get_url(action='parse_carousel', params=json.dumps(params), carousel_id=carousel_id, label=f"{label} / {title}")
            menu = []
            menu.append(['Přidat do oblíbených Oneplay', f"RunPlugin(plugin://{plugin_id}?action=add_favourite&type=category&id={params.get('payload', {}).get('categoryId')}~None~{params.get('payload', {}).get('criteria', {}).get('filterCriterias')}&image=None&title={title.replace('Kategorie / ','')})"])
            list_item.addContextMenuItems(menu)
            xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    elif schema == 'TabBlock':
        for layout_block in block['layout']['blocks']:
            parse_page_block(layout_block , params, label)
    elif schema == 'HeroBlock': # ignoruje se
        pass
    elif schema == 'SinglePromoBlock': # ignoruje se
        pass        
    elif schema == 'PromoCarouselBlock': # ignoruje se
        pass
    else:    
        xbmcgui.Dialog().notification('Oneplay',f"Neznámé block schema: {schema}", xbmcgui.NOTIFICATION_INFO, 3000)

def page_category_display(label, params):
    """Načtení kategorie"""
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'movies')
    params = json.loads(params)
    session, api = Session(), API()
    data = api.page_category_display({'payload' : params['payload']}, session)
    for block in data:
        parse_page_block(block, params, label)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)  

def page_search_display(query):
    """Vyhledávání"""
    session = Session()
    api = API()    
    data = api.page_search_display(query, session)
    if 'blocks' in data['layout']:
        for block in data['layout']['blocks']:
            if block['schema'] == 'CarouselBlock':
                carousel = block['carousels'][0]
                parse_tiles(None, carousel, 1)
        xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)              
    else:                
        xbmcgui.Dialog().notification('Oneplay','Nic nenalezeno', xbmcgui.NOTIFICATION_INFO, 3000)

def get_item(label, title, schema, call, params):
    """Generuje položky hlavního menu"""
    if schema == 'ApiAppAction':
        if call in ['page.category.display', 'list_filters']:
            list_item = xbmcgui.ListItem(label=title)
            url = get_url(action=call, params=json.dumps(params), label=label)
            menu = []
            menu.append(['Přidat do oblíbených Oneplay', f"RunPlugin(plugin://{plugin_id}?action=add_favourite&type=category&id={params.get('payload', {}).get('categoryId')}~None~{params.get('payload', {}).get('criteria', {}).get('filterCriterias')}&image=None&title={title.replace('Kategorie / ','')})"])
            list_item.addContextMenuItems(menu)
            xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
            return
    xbmcgui.Dialog().notification('Oneplay',f"Neznámé schema: {schema} {call}", xbmcgui.NOTIFICATION_INFO, 3000)

def list_filters(label, params):
    """Zobrazí filtrz (žánry)"""
    xbmcplugin.setPluginCategory(_handle, label); 
    xbmcplugin.setContent(_handle, 'movies')
    params = json.loads(params)
    session, api = Session(), API()
    data = api.page_category_display({'payload': params.get('payload')}, session)
    for block in data:
        schema = block.get('schema')
        if schema == 'BreadcrumbBlock':
            groups = block.get('menu', {}).get('groups', [{}])[0].get('items', [])
            for breadcrumb in groups:
                if breadcrumb.get('schema') == 'SubMenu':
                    items = breadcrumb.get('groups', [{}])[0].get('items', [])
                    for item in items:
                        action = item.get('action', {})
                        get_item(label=item.get('title', ''), title=item.get('title', ''), schema=action.get('schema'), call=action.get('call'), params=action.get('params'))
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)

def list_show(label, id):
    """Vypíše seznam sezón"""
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'movies')    
    addon = xbmcaddon.Addon()
    is_episodes_count = addon.getSetting('episodes_count')
    id = json.loads(id)
    api = API()
    session = Session()
    data = api.page_content_display(post={"payload": id}, session=session)
    if not data.get('seasons', []) and data.get('episodes', []): # osetreni, pokud se vraci primo epizody bez sezon
        for episode in data.get('episodes', []):
            if episode.get('action',{}).get('call') == 'content.play':
                params = episode.get('action', {}).get('params', {})
                data = get_item_detail(id, item=episode, download_data=False)
                list_item = xbmcgui.ListItem(label=episode.get('title'))
                list_item = epg_listitem(list_item, data, None)
                list_item.setContentLookup(False)          
                list_item.setProperty('IsPlayable', 'true')
                url = get_url(action='play_archive', id=json.dumps(params.get('payload', {})), direct=True, mode='start', title=episode['title'])
                xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    else:
        for season in data.get('seasons', []):
            if is_episodes_count == 'true':
                episodes_count = get_episodes_count(season['carouselId'], season['criteria'])
            else:
                episodes_count = -1
            if episodes_count > 0:
                season_label = season['label'] 
                if episodes_count == 1:
                    title = f"{season_label} ({episodes_count} díl)"
                elif episodes_count > 1 and episodes_count < 5:
                    title = f"{season_label} ({episodes_count} díly)"
                elif episodes_count == 9999:
                    title = f"{season_label} (20+ dílů)"
                else:
                    title = f"{season_label} ({episodes_count} dílů)"
            else:
                title = season['label']
            if episodes_count != 0:            
                list_item = xbmcgui.ListItem(label=title)
                url = get_url(action='list_season', carouselId=season['carouselId'], criteria=season['criteria'], label=f"{label} / {season['label']}")
                menu = []
                menu.append(['Přidat do oblíbených Oneplay', f"RunPlugin(plugin://{plugin_id}?action=add_favourite&type=season&id={season['criteria']}~{season['carouselId']}&image=None&title={label} / {season['label']})"])
                list_item.addContextMenuItems(menu)
                xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False) 

def list_season(label, carouselId, criteria):
    """Vypíše epizody"""
    order = 'DESC' if xbmcaddon.Addon().getSetting('episodes_order') == 'sestupně' else 'ASC'
    # page = -1 nacte vsechny epizody
    carousel_display(label, json.dumps({'carouselId' : carouselId, 'criteria': {'filterCriterias': criteria, 'sortOption': order}}), page=-1)

def list_categories(label):
    """Výpis hlavního menu kategorií"""
    xbmcplugin.setPluginCategory(_handle, label)
    api = API()
    data = api.app_init(session=Session())
    for group in data.get('menu', {}).get('groups', []):
        if group.get('position') == 'top':
            for item in group.get('items', []):
                action = item.get('action', {})
                if action.get('call') == 'page.category.display':
                    get_item(label=item.get('title', ''), title=item.get('title', ''), schema=action.get('schema'), call=action['call'], params=action.get('params'))
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)

def get_episodes_count(carouselId, criteria):
    """Načte karusel s podporou stránkování. S page=-1 projde všechny strany"""
    payload = {'carouselId' : carouselId, 'criteria': {'filterCriterias': criteria, 'sortOption': 'DESC'}}
    session, api = Session(), API()
    page = 0
    cnt = 0
    while page == 0 or carousel.get('paging', {}).get('next') == True:
        page += 1
        payload['paging'] = {"count":12,"position":12*(page-1)+1}
        carousel = api.carousel_display({'payload': payload}, session)
        for tile in carousel.get('tiles', []):
            if tile.get('action',{}).get('call') == 'content.play':
                cnt += 1
                if cnt == 20:
                    return 9999
    return cnt
