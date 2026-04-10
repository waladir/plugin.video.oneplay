# -*- coding: utf-8 -*-
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

import json
from resources.lib.settings import Settings
from resources.lib.api import API
from resources.lib.epg import epg_listitem, get_item_detail
from resources.lib.session import Session
from resources.lib.utils import get_url, plugin_id, get_color, get_label_color

if len(sys.argv) > 1:
    _handle = int(sys.argv[1])

FAVOURITES_FILE = {'filename' : 'favourites.txt', 'description' : 'oblíbených'}    
EPISODES_BL_FILE = {'filename': 'favourites_episodes_bl.txt', 'description': 'skrytých epizod oblíbených'}

def save_favourites(favourites):
    """Uloží oblíbené"""
    try:
        json_data = json.dumps(favourites)
        Settings().save_json_data(FAVOURITES_FILE, json_data)
        return True
    except (TypeError, ValueError):
        return False

def add_favourite(type, id, image, title):
    """Přidá položku do oblíbených"""
    favourites = get_favourites()
    type_group = favourites.setdefault(type, {})
    if id in type_group:
        xbmcgui.Dialog().notification('Oneplay', 'Pořad je již v oblíbených', xbmcgui.NOTIFICATION_ERROR, 5000)
        return
    type_group[id] = {'image': image, 'title': title}
    if save_favourites(favourites):
        xbmcgui.Dialog().notification('Oneplay', 'Pořad byl přidaný do oblíbených', xbmcgui.NOTIFICATION_INFO, 5000)

def remove_favourite(type, id):
    """Odebere položku z oblíbených"""
    favourites = get_favourites()
    
    if type in favourites and id in favourites[type]:
        del favourites[type][id]
        if not favourites[type]:
            del favourites[type]
        if save_favourites(favourites):
            xbmc.executebuiltin('Container.Refresh')

def get_favourites():
    """Načte oblíbené ze souboru"""
    favourites = Settings().load_json_data(FAVOURITES_FILE)
    try:
        return json.loads(favourites) if favourites else {}
    except (json.JSONDecodeError, TypeError):
        return {}

def list_favourites(label):
    """V7pid obl9bených"""
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'movies')
    favourites = get_favourites()
    types = ['category', 'show', 'season', 'item']
    for type in types:
        if type not in favourites:
            continue
        for id, item in favourites[type].items():
            title = item.get('title', 'Bez názvu')
            image = item.get('image')
            list_item = xbmcgui.ListItem(label=title)
            list_item.setArt({'thumb': image, 'icon': image, 'poster': image})
            menu = [('Odstranit z oblíbených Oneplay',  f"RunPlugin(plugin://{plugin_id}?action=remove_favourite&type={type}&id={id})")]
            list_item.addContextMenuItems(menu)
            is_folder = True
            url = ""
            if type == 'show':
                payload = {'contentId': id}
                data = get_item_detail(payload, item={'title': title, 'image': {'image': image}})
                data['type'] = type
                list_item = epg_listitem(list_item, data, None)
                url = get_url(action='list_show', id=json.dumps(payload), label=title)
            elif type == 'item':
                if 'criteria' in id:
                    continue
                payload = {'contentId': id}
                data = get_item_detail(payload, item={'title': title, 'image': {'image': image}})
                data['type'] = 'movie'
                list_item.setContentLookup(False)          
                list_item.setProperty('IsPlayable', 'true')
                url = get_url(action='play_archive', id=json.dumps(payload), direct=False, mode='start', title=title)
                is_folder = False
            elif type == 'season':
                item_id, carusel_id = id.split('~')[:2]
                url = get_url(action='list_season', carouselId=carusel_id, criteria=item_id, label=title)
            elif type == 'category':
                parts = id.split('~')
                item_id, carusel_id = parts[0], parts[1]
                criteria = parts[2] if len(parts) > 2 else 'None'
                payload = {'categoryId': item_id}
                if criteria != 'None':
                    payload['criteria'] = {'filterCriterias': criteria}
                url = get_url(action='page.category.display', params=json.dumps({'payload': payload}), label=label)
            xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)
    xbmcplugin.endOfDirectory(_handle)

def list_favourites_new(label):
    """Načte nejnovější epizody oblíbených"""
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'movies')
    addon = xbmcaddon.Addon()
    color = get_color()
    limit = int(addon.getSetting('favourites_new_count'))
    sort_desc = addon.getSetting('episodes_order') == 'sestupně'
    api = API()
    session = Session()
    favourites = get_favourites()
    blacklist = get_favourites_episodes_bl()
    seasons = []
    
    # vygenerování seznamu sezón. Pokud je jedná o typ show, použije se první sezóna
    for type in ['show', 'season']:
        if type not in favourites:
            continue
        for f_id, item in favourites[type].items():
            if type == 'show':
                data = api.page_content_display(post={'payload': {'contentId': f_id}}, session=session)
                data_seasons = data.get('seasons', [])
                for s in data_seasons:
                    seasons.append({'title': f"{item['title']} / {s['label']}", 'id': s['criteria'], 'carouselId': s['carouselId'], 'show': f_id})
            elif type == 'season':
                parts = f_id.split('~')
                if len(parts) >= 2:
                    seasons.append({'title': item['title'], 'id': parts[0], 'carouselId': parts[1], 'show': parts[1].split(';')[0]})
    
    # pro seznony nacte prvnich x epizod
    episodes = {}
    show = ''
    for season in seasons:
        if show != season['show']:
            show = season['show']
            cnt = 0
        page = 0
        has_next = True
        while has_next and cnt < limit:
            page += 1
            payload = {'carouselId': season['carouselId'], 'criteria': {'filterCriterias': season['id'], 'sortOption': 'DESC'}, 'paging': {"count": 12, "position": 12 * (page - 1) + 1}}
            carousel = api.carousel_display({'payload': payload}, session, silent=True)
            tiles = carousel.get('tiles', [])
            has_next = carousel.get('paging', {}).get('next', False)
            if not tiles: break
            for tile in tiles:
                # přeskakují se nepřehratelné epizody
                if tile.get('action', {}).get('call') != 'content.play':
                    continue
                params = tile.get('action', {}).get('params', {})
                item_payload = params.get('payload', {})
                content_id = item_payload.get('criteria', {}).get('contentId') or tile.get('tracking', {}).get('id')
                if content_id and content_id not in blacklist:
                    cnt += 1
                    if cnt <= limit:
                        item_data = get_item_detail(item_payload, item=tile, download_data=False)
                        try:
                            season_num = season['title'].split('/')[-1].split()[0].strip('.').zfill(3) # cislo sezony
                            episode_num = item_data['title'].split('.')[0].zfill(5) # cislo epizody
                            sort_key = f"{season['id']}_{season_num}_{episode_num}"
                        except (IndexError, ValueError):
                            sort_key = len(episodes)
                        episodes[sort_key] = {'id': content_id, 'payload': item_payload, 'type': item_data['type'], 'showtitle': season['title'], 'title': item_data['title'], 'cover': item_data['cover'], 'description': item_data.get('description', '')}
                    else:
                        break
    
    for episode_id in sorted(episodes.keys(), reverse=sort_desc):
        item = episodes[episode_id]
        title = item['title']
        title = title.replace('Dříve než v TV', item['showtitle']) # pokud nazev obsahuje Driver nez v TV (vyplnuje se pri parsovani dat v get_item_detail), nahradi se obsahem showtitle, ktery obsahuje nazev poradu a sezony
        if '\n' not in title:
            title += '\n' + get_label_color(item['showtitle'], color)
        list_item = xbmcgui.ListItem(label=title)
        list_item = epg_listitem(list_item, item, None)
        list_item.setProperty('IsPlayable', 'true')
        list_item.setContentLookup(False)
        list_item.addContextMenuItems([('Skrýt epizodu', f"RunPlugin(plugin://{plugin_id}?action=add_favourites_episodes_bl&id={item['id']})")])
        url = get_url(action='play_archive', id=json.dumps(item['payload']), direct=True)
        xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)

def get_favourites_episodes_bl():
    """Načte blacklist epizod"""
    data = Settings().load_json_data(EPISODES_BL_FILE)
    try:
        return json.loads(data) if data else []
    except (json.JSONDecodeError, TypeError):
        return []

def add_favourites_episodes_bl(id):
    """Přidá id epizody na blacklist"""
    blacklist = get_favourites_episodes_bl()
    if id not in blacklist:
        blacklist.append(id)
        try:
            json_data = json.dumps(blacklist)
            Settings().save_json_data(EPISODES_BL_FILE, json_data)
            xbmc.executebuiltin('Container.Refresh')
        except (TypeError, ValueError):
            xbmcgui.Dialog().notification('Oneplay', 'Chyba při uložení skrytých epizod oblíbených pořadů', xbmcgui.NOTIFICATION_ERROR, 3000)

