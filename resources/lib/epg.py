# -*- coding: utf-8 -*-
import os

import xbmc
import xbmcgui
import xbmcaddon
try:
    from xbmcvfs import translatePath
except ImportError:
    from xbmc import translatePath

import sqlite3
import json
from datetime import datetime, timedelta
import time

from resources.lib.session import Session
from resources.lib.channels import Channels
from resources.lib.api import API
from resources.lib.utils import get_kodi_version, get_color, get_label_color

CURRENT_VERSION = 1
DB_NAME = 'items_data.db'

def get_db_path():
    """Vrací absolutní cestu k databázi v profilu doplňku"""
    addon = xbmcaddon.Addon()
    profile_dir = translatePath(addon.getAddonInfo('profile'))
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)
    return os.path.join(profile_dir, DB_NAME)

def open_db():
    """Otevře databázi, inicializuje tabulky a provede migraci"""
    db_path = get_db_path()
    db = sqlite3.connect(db_path, timeout=10)
    with db:
        db.execute('CREATE TABLE IF NOT EXISTS version (version INTEGER PRIMARY KEY)')
        db.execute('CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, description TEXT, original TEXT, cast TEXT, directors TEXT, year TEXT, country TEXT, genres TEXT)')
        cursor = db.execute('SELECT version FROM version LIMIT 1')
        row = cursor.fetchone()
        if not row:
            db.execute('INSERT INTO version (version) VALUES (?)', (CURRENT_VERSION,))
            db.commit()
            db_version = CURRENT_VERSION
        else:
            db_version = row[0]
            
        if db_version != CURRENT_VERSION:
            db_version = migrate_db(db, db_version)
    return db

def migrate_db(db, version):
    """Případná migrace struktury DB"""
    return version

def remove_db():
    """Smaže soubor databáze a informuje uživatele"""
    db_path = get_db_path()
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            xbmcgui.Dialog().notification('Oneplay', 'Keš dat pořadů byla vymazána', xbmcgui.NOTIFICATION_INFO, 3000)
        except OSError:
            xbmcgui.Dialog().notification('Oneplay', 'Chyba při mazání keše!', xbmcgui.NOTIFICATION_ERROR, 3000)

def close_db(db):
    """Zavření DB"""
    if db:
        db.close()

def clean_epg_cache(days):
    """Čístí EPG keš"""
    addon = xbmcaddon.Addon()
    profile_dir = translatePath(addon.getAddonInfo('profile'))
    cache_dir = os.path.join(profile_dir, 'epg_cache')
    os.makedirs(cache_dir, exist_ok=True)
    limit_date = (datetime.now() - timedelta(days=days)).date()
    for filename in os.listdir(cache_dir):
        if filename.startswith("epg_cache_") and filename.endswith(".txt"):
            try:
                parts = filename[:-4].split('_')
                date_str = parts[-1]
                file_date = datetime.fromtimestamp(time.mktime(time.strptime(date_str, "%Y-%m-%d"))).date()
                if file_date < limit_date:
                    os.remove(os.path.join(cache_dir, filename))
            except (ValueError, IndexError):
                continue

def get_live_epg():
    """Z EPG dat vrací aktualní a následující pořad pro všechny kanály"""
    ts = int(time.time())    
    epg_now, epg_next = {}, {}
    epg_data = get_epg(ts)
    for channel_id in epg_data.keys():
        for item in sorted(epg_data[channel_id].values(), key=lambda x: x['startts']):
            start, end = item['startts'], item['endts']
            if start <= ts < end:
                epg_now[channel_id] = item
            elif start >= ts and channel_id not in epg_next:
                epg_next[channel_id] = item
    return epg_now, epg_next    

def get_epg(ts, filter_channel_id=None):
    """Vrací EPG data s podporou kešování"""
    dt = datetime.fromtimestamp(ts)
    day = dt.strftime('%Y-%m-%d')
    prev_day = (dt - timedelta(days=1)).strftime('%Y-%m-%d')
    next_day = (dt + timedelta(days=1)).strftime('%Y-%m-%d')

    addon = xbmcaddon.Addon()
    profile_dir = translatePath(addon.getAddonInfo('profile'))
    cache_dir = os.path.join(profile_dir, 'epg_cache')
    os.makedirs(cache_dir, exist_ok=True)

    channels_list = Channels().get_channels_list('id')
    channel_ids = [filter_channel_id] if filter_channel_id else channels_list.keys()
    epg = {}
    reload_data = False
    
    for channel_id in channel_ids:
        filename = os.path.join(cache_dir, f"epg_cache_{channel_id}_{day}.txt")
        if not os.path.exists(filename): # pokud soubor pro kanal a den neexistuje, provede se nacteni dat z API
            reload_data = True
            break
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                epg[channel_id] = data
        except (IOError, json.JSONDecodeError):
            reload_data = True
            break

    # pokud se podarilo nacist nakesovana data, vrati EPG data, pokud je fitrovani na kanal, tak pak EPG kanalu
    if not reload_data:
        return epg.get(filter_channel_id, epg) if filter_channel_id else epg
    
    clean_epg_cache(days=31) # procisteni starsich EPG dat 
    api = API()
    post = {"payload":{"criteria":{"channelSetId":"channel_list.1","viewport":{"channelRange":{"from":0,"to":200},"timeRange":{"from": f"{prev_day}T23:00:00.000Z","to": f"{next_day}T02:00:00.000Z"},"schema":"EpgViewportAbsolute"}},"requestedOutput":{"channelList":"none","datePicker":False,"channelSets":False}}}
    response = api.call_api('epg.display', data=post, session=Session())
    if response.get('result', {}).get('status') != 'Ok':
        return {}
    epg = {}
    channel_ids = set(channels_list.keys())
    schedule = response.get('result', {}).get('data', {}).get('schedule', [])
    for channel in schedule:
        channel_id = channel['channelId']
        if channel_id not in channel_ids: # pokud neni kanal s EPG v seznamu kanalu, EPG se pro nej ukladat nebude
            continue
        channel_ids.remove(channel_id)
        epg_data = {}
        for item in channel.get('items', []):
            try:
                startts = int(datetime.fromisoformat(item['startAt'].replace('Z', '+00:00')).timestamp())
                endts = int(datetime.fromisoformat(item['endAt'].replace('Z', '+00:00')).timestamp())
                img = item.get('image', '').replace('{WIDTH}', '480').replace('{HEIGHT}', '320')
                actions = item.get('actions', [{}])[0]
                params = actions.get('params', {})
                epg_item = {'payload': params.get('payload', {}), 'type': params.get('contentType'), 'referenceid': item.get('referenceId'), 'title': item.get('title'), 'channel_id': channel_id, 'description': item.get('description', ''), 'startts': startts, 'endts': endts, 'cover': img, 'poster': img}
                epg_data[startts] = epg_item
            except (ValueError, KeyError, IndexError):
                continue
        epg[channel_id] = epg_data
        cache_path = os.path.join(cache_dir, f"epg_cache_{channel_id}_{day}.txt")
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(epg_data, f)

    # Ošetření kanálů, které v API chyběly (vytvoření prázdné cache)
    for channel_id in channel_ids:
        cache_path = os.path.join(cache_dir, f"epg_cache_{channel_id}_{day}.txt")
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump({}, f)

    return epg.get(filter_channel_id, {}) if filter_channel_id else epg

def get_item_detail(id, item, download_data=True):
    """formátuje titulek pořadu s dotažením a doplňuje metadata"""
    item_detail = {}
    color = get_color()
    if item:
        title = item.get('title', '')
        type_item = item.get('tracking', {}).get('type', 'item')
        subtitle_parts = [] 
        if 'subTitle' in item:
            subtitle_parts.append(item['subTitle'])
            
        img_labels = item.get('image', {}).get('labels', [])
        if img_labels:
            subtitle_parts.append(img_labels[0]['name'])
            
        for label in item.get('labels', []): # data nahravek
            if all(x not in label['name'] for x in ['Vyprší', 'Můj seznam']):
                subtitle_parts.append(label['name'])
        fragments = item.get('additionalFragments', [])
        if fragments and len(fragments) > 0 and 'labels' in fragments[0]:
            has_date = False
            for label in fragments[0]['labels']:
                name = label['name']
                if name.count('.') == 2: # Datum
                    subtitle_parts.append(name)
                    has_date = True
                elif ':' in name: # Čas
                    if has_date and subtitle_parts:
                        subtitle_parts[-1] += f" {name}"
                    else:
                        subtitle_parts.append(name)
                elif 'Díl' in name:
                    subtitle_parts.append(name)
        subtitle = " | ".join([s for s in subtitle_parts if s]) # slozeni druheho radku
        if len(subtitle) > 1:
            title = f"{title}\n{get_label_color(subtitle, color)}"
        image = item.get('image', {}).get('image', '').replace('{WIDTH}', '320').replace('{HEIGHT}', '480')
        item_detail = {
            'title': title,
            'type': type_item,
            'cover': image,
            'poster': image,
            'description': item.get('description', '')
        }
        tracking = item_detail.get('tracking', {}) # udaje o sezone
        if 'show' in tracking:
            item_detail['showtitle'] = f"{tracking['show'].get('title', '')} / {tracking.get('season', '')}"

    addon = xbmcaddon.Addon()
    if download_data == True and addon.getSetting('item_details') == 'true':
        db = None
        try:
            contentId = id.get('contentId')
            db = open_db()
            cursor = db.execute('SELECT description, original, "cast", directors, year, country, genres FROM items WHERE id = ?', (contentId,))
            row = cursor.fetchone()
            if row:
                # Data nalezena v DB
                item_detail.update({
                    'description': row[0] or item_detail.get('description', ''),
                    'original': row[1],
                    'cast': json.loads(row[2]),
                    'directors': json.loads(row[3]),
                    'year': row[4],
                    'country': row[5],
                    'genres': json.loads(row[6])
                })
            else: # data nejsou v DB, stáhneme z API
                api = API()
                session = Session()
                data = api.page_content_display(post={"payload": id}, session=session)
                item_data = data.get('info')
                payload = data.get('payload')
                if item_data:
                    # uložení do cache
                    db.execute('INSERT OR REPLACE INTO items (id, description, original, "cast", directors, year, country, genres) VALUES(?, ?, ?, ?, ?, ?, ?, ?)',(contentId, item_data['plot'], item_data['original_title'], json.dumps(item_data['cast']),json.dumps(item_data['director']), item_data['year'], item_data['country'], json.dumps(item_data['genre'])))
                    db.commit()
                    item_detail.update({'payload': payload, 'description': item_data['plot'] or item_detail.get('description', ''), 'original': item_data['original_title'], 'cast': item_data['cast'], 'directors': item_data['director'], 'year': item_data['year'], 'country': item_data['country'], 'genres': item_data['genre']})
        except Exception as e:
            xbmc.log(f"Oneplay > Chyba get_item_detail: {str(e)}")
        finally:
            if db: close_db(db)
    return item_detail

def epg_listitem(list_item, epg, icon):
    """Vyplní metadata"""
    cast = []
    directors = []
    genres = []
    kodi_version = get_kodi_version()
    media_type = epg.get('type', 'movie')
    if media_type == 'episode':
        media_type = 'tvshow'
    elif media_type not in ['tvshow', 'movie']:
        media_type = 'movie'    

    if kodi_version >= 20:
        infotag = list_item.getVideoInfoTag()
        infotag.setMediaType(epg['type'])
        infotag.setTitle(epg['title'])
    else:
        list_item.setInfo('video', {'mediatype' : epg['type']})
        list_item.setInfo('video', {'title': epg['title']})

    if epg.get('cover'):
        if epg.get('poster'):
            if icon == '':
                icon = epg['poster']
            list_item.setArt({'poster': epg['poster'], 'icon': icon})
        else:
            if icon == '':
                icon = epg['cover']
            list_item.setArt({'thumb': epg['cover'], 'icon': icon})
    elif icon is not None:
        list_item.setArt({'thumb': icon, 'icon': icon})    

    if epg.get('description'):
        if kodi_version >= 20:
            infotag.setPlot(epg['description'])
        else:
            list_item.setInfo('video', {'plot': epg['description']})

    if epg.get('year') and epg['year'].isdigit():
        if kodi_version >= 20:
            infotag.setYear(int(epg['year']))
        else:
            list_item.setInfo('video', {'year': int(epg['year'])})

    if epg.get('original'):
        if kodi_version >= 20:
            infotag.setOriginalTitle(epg['original'])
        else:
            list_item.setInfo('video', {'originaltitle': epg['original']})

    if epg.get('country'):
        if kodi_version >= 20: 
            infotag.setCountries([epg['country']])
        else: 
            list_item.setInfo('video', {'country': epg['country']})

    genres_data = epg.get('genres', [])             
    if genres_data:
        for genre in genres_data:      
          genres.append(genre)
        if kodi_version >= 20:
            infotag.setGenres(genres)
        else:
            list_item.setInfo('video', {'genre' : genres})  

    cast_data = epg.get('cast', [])             
    if cast_data:
        for person in cast_data: 
            if len(person) > 0:
                if kodi_version >= 20:
                    cast.append(xbmc.Actor(person))
                else:
                    cast.append(person)
        if kodi_version >= 20:
            infotag.setCast(cast)
        else:
            list_item.setInfo('video', {'castandrole' : cast})  
            
    directors_data = epg.get('directors', [])             
    if directors_data:
        for person in directors_data:      
            directors.append(person)
        if kodi_version >= 20:
            infotag.setDirectors(directors)
        else:
            list_item.setInfo('video', {'director' : directors})  
    return list_item

