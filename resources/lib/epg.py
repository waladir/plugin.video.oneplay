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
import time
from datetime import datetime, timezone

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

def format_ts(ts):
    """Převede timestamp na ISO formát s UTC nulou, který API vyžaduje"""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}.000Z"

def get_live_epg():
    """Získá aktuální a následující pořady pro všechny kanály"""
    now_ts = int(time.time())
    post = {"payload": {"criteria": {"channelSetId": "channel_list.1", "viewport": {"channelRange": {"from": 0, "to": 200}, "timeRange": {"from": format_ts(now_ts - 7200), "to": format_ts(now_ts + 21600)}, "schema": "EpgViewportAbsolute"}}, "requestedOutput": {"channelList": "none", "datePicker": False, "channelSets": False}}}
    epg_data = get_epg_data(post, None)
    epg_now, epg_next = {}, {}
    for item in sorted(epg_data.values(), key=lambda x: x['startts']):
        channel = item['channel_id']
        start, end = item['startts'], item['endts']
        if start <= now_ts < end:
            epg_now[channel] = item
        elif start >= now_ts and channel not in epg_next:
            epg_next[channel] = item
    return epg_now, epg_next

def get_channel_epg(channel_id, from_ts, to_ts):
    """Vrací EPG pro kanál a časový rozsah"""
    channels_list = Channels().get_channels_list('id')
    oneplay_number = channels_list.get(channel_id, {}).get('channel_number', 0)
    time_range = {"from": format_ts(from_ts), "to": format_ts(to_ts)}
    post = {"payload": {"criteria": {"channelSetId": "channel_list.1", "viewport": {"channelRange": {"from": max(0, oneplay_number - 1), "to": oneplay_number}, "timeRange": time_range, "schema": "EpgViewportAbsolute"}},"requestedOutput": {"channelList": "none", "datePicker": False, "channelSets": False}}}
    epg = get_epg_data(post, channel_id)
    if not epg: # pokud se nenajde EPG pro kanal, protoze obcas muze dojit k posunu cislovani kanalu na strane Oneplay a po odfiltrovani podle channel_id se nic nevrati, provede se nove volani, ktere nacte EPG pro vsechny kanaly
        post['payload']['criteria']['viewport']['channelRange']['from'] = 0
        post['payload']['criteria']['viewport']['channelRange']['to'] = 200
        epg = get_epg_data(post, channel_id)
    return epg

def get_day_epg(from_ts, to_ts):
    """Stažení EPG dat pro všechny kanály za daný časový rozsah"""
    post = {"payload":{"criteria":{"channelSetId":"channel_list.1","viewport":{"channelRange":{"from":0,"to":200},"timeRange":{"from":datetime.fromtimestamp(from_ts).strftime('%Y-%m-%dT%H:%M:%S') + '.000Z',"to":datetime.fromtimestamp(to_ts).strftime('%Y-%m-%dT%H:%M:%S') + '.000Z'},"schema":"EpgViewportAbsolute"}},"requestedOutput":{"channelList":"none","datePicker":False,"channelSets":False}}}
    return get_epg_data(post, None)

def get_epg_data(post, filter_channel_id):
    """Stažení EPG dat z API s možností filtrování na konkrétní kanál"""
    api = API()
    channels_list = Channels().get_channels_list('id')
    epg = {}
    response = api.call_api('epg.display', data=post, session=Session())
    if response.get('result', {}).get('status') != 'Ok':
        return {}
    data = response['result'].get('data', {})
    for channel in data.get('schedule', []):
        channel_id = channel['channelId']
        if channel_id not in channels_list or (filter_channel_id and channel_id != filter_channel_id):
            continue
        for item in channel.get('items', []):
            try:
                startts = int(datetime.fromisoformat(item['startAt'].replace('Z', '+00:00')).timestamp())
                endts = int(datetime.fromisoformat(item['endAt'].replace('Z', '+00:00')).timestamp())
                params = item.get('actions', [{}])[0].get('params', {})
                img = item.get('image', '').replace('{WIDTH}', '480').replace('{HEIGHT}', '320')
                epg_item = {'payload': params.get('payload', {}), 'type': params.get('contentType'), 'referenceid': item.get('referenceId'), 'title': item.get('title'), 'channel_id': channel_id, 'description': item.get('description', ''), 'startts': startts, 'endts': endts, 'cover': img, 'poster': img}
                key = f"{channel_id}_{startts}" if filter_channel_id is None else startts
                epg[key] = epg_item
            except (ValueError, KeyError, IndexError):
                continue
    return epg

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
#        try:
        if 1==1:
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
        # except Exception as e:
        #     xbmc.log(f"Oneplay > Chyba get_item_detail: {str(e)}")
        # finally:
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

