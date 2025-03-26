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

from resources.lib.session import Session
from resources.lib.channels import Channels
from resources.lib.api import API
from resources.lib.utils import get_kodi_version

from datetime import datetime

current_version = 1

def open_db():
    global db, version
    addon = xbmcaddon.Addon()
    addon_userdata_dir = translatePath(addon.getAddonInfo('profile')) 
    if not os.path.isdir(addon_userdata_dir):
        os.mkdir(addon_userdata_dir)
    db = sqlite3.connect(addon_userdata_dir + 'items_data.db', timeout = 10)
    db.execute('CREATE TABLE IF NOT EXISTS version (version INTEGER PRIMARY KEY)')
    db.execute('CREATE TABLE IF NOT EXISTS items (id VARCHAR(255), description TEXT, original VARCHAR(255), cast VARCHAR(255), directors VARCHAR(255), year VARCHAR(255), country VARCHAR(255), genres VARCHAR(255))')
    row = None
    for row in db.execute('SELECT version FROM version'):
        version = row[0]
    if not row:
        db.execute('INSERT INTO version VALUES (?)', [current_version])
        db.commit()     
        version = current_version
    if version != current_version:
        version = migrate_db(version)

def close_db():
    global db
    db.close()    

def migrate_db(version):
    global db
    return version

def remove_db():
    addon = xbmcaddon.Addon()
    addon_userdata_dir = translatePath(addon.getAddonInfo('profile'))
    filename = os.path.join(addon_userdata_dir, 'items_data.db')
    if os.path.exists(filename):
        try:
            os.remove(filename) 
            xbmcgui.Dialog().notification('Oneplay', 'Keš dat pořadů byla vymazána', xbmcgui.NOTIFICATION_INFO, 5000)    
        except IOError:
            xbmcgui.Dialog().notification('Oneplay', 'Chyba při mazání keše!', xbmcgui.NOTIFICATION_ERROR, 5000)  

def load_epg_data(timestamp):
    from resources.lib.settings import Settings
    settings = Settings()
    data = settings.load_json_data({'filename' : 'epg_data.txt', 'description' : 'EPG'})
    if data is not None:
        data = json.loads(data)
        if 'timestamp' in data and 'epg' in data:
            if int(data['timestamp']) != timestamp:
                return []
            else:
                return data['epg']
        else:
            return []
    else:
        return []

def save_epg_data(epg, timestamp):
    from resources.lib.settings import Settings
    settings = Settings()
    data = json.dumps({'epg' : epg, 'timestamp' : timestamp})        
    settings.save_json_data({'filename' : 'epg_data.txt', 'description' : 'EPG'}, data)

def get_live_epg():
    session = Session()
    api = API()
    today_date = datetime.today() 
    from_ts = int(time.mktime(datetime(today_date.year, today_date.month, today_date.day).timetuple()))
    to_ts = from_ts + 60*60*24 - 1
    # epg_data = load_epg_data(from_ts)
    epg_data = []
    epg = {}
    if len(epg_data) == 0:
        # post = {"payload":{"criteria":{"channelSetId":"channel_list.1","viewport":{"channelRange":{"from":0,"to":200},"timeRange":{"from":datetime.fromtimestamp(from_ts).strftime('%Y-%m-%dT%H:%M:%S') + '.000Z',"to":datetime.fromtimestamp(to_ts).strftime('%Y-%m-%dT%H:%M:%S') + '.000Z'},"schema":"EpgViewportAbsolute"}},"requestedOutput":{"channelList":"none","datePicker":False,"channelSets":False}}}
        post = {"payload":{"criteria":{"channelSetId":"channel_list.1","viewport":{"channelRange":{"from":0,"to":200},"timeRange":{"from":datetime.fromtimestamp(datetime.now().timestamp()-3600).strftime('%Y-%m-%dT%H:%M:%S') + '.000Z',"to":datetime.fromtimestamp(datetime.now().timestamp()).strftime('%Y-%m-%dT%H:%M:%S') + '.000Z'},"schema":"EpgViewportAbsolute"}},"requestedOutput":{"channelList":"none","datePicker":False,"channelSets":False}}}
        data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/epg.display', data = post, session = session, nolog = True)
        if 'err' not in data:
            for channel in data['schedule']:
                for item in channel['items']:
                    startts = int(datetime.fromisoformat(item['startAt']).timestamp())
                    endts = int(datetime.fromisoformat(item['endAt']).timestamp())
                    epg_item = {'id' : item['id'], 'title' : item['title'], 'channel_id' : channel['channelId'], 'description' : item['description'], 'startts' : startts, 'endts' : endts, 'cover' : item['image'].replace('{WIDTH}', '480').replace('{HEIGHT}', '320'), 'poster' : item['image'].replace('{WIDTH}', '480').replace('{HEIGHT}', '320')}
                    epg_data.append(epg_item)
            # save_epg_data(epg_data, from_ts)
    for item in epg_data:
        currentts = datetime.now().timestamp()
        if item['startts'] < currentts and item['endts'] > currentts:
            epg.update({item['channel_id'] : item})
    return epg

def get_channel_epg(channel_id, from_ts, to_ts):
    session = Session()
    api = API()
    channels = Channels()
    channels_list = channels.get_channels_list('id')
    oneplay_number = channels_list[channel_id]['oneplay_number']
    epg = {}
    post = {"payload":{"criteria":{"channelSetId":"channel_list.1","viewport":{"channelRange":{"from":oneplay_number-1,"to":oneplay_number},"timeRange":{"from":datetime.fromtimestamp(from_ts-3600).strftime('%Y-%m-%dT%H:%M:%S') + '.000Z',"to":datetime.fromtimestamp(to_ts-3600).strftime('%Y-%m-%dT%H:%M:%S') + '.000Z'},"schema":"EpgViewportAbsolute"}},"requestedOutput":{"channelList":"none","datePicker":False,"channelSets":False}}}
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/epg.display', data = post, session = session, nolog = True)
    if 'err' not in data:
        for channel in data['schedule']:
            if channel['channelId'] == channel_id:
                for item in channel['items']:
                    startts = int(datetime.fromisoformat(item['startAt']).timestamp())
                    endts = int(datetime.fromisoformat(item['endAt']).timestamp())
                    if 'contentType' in item['actions'][0]['params']:
                        if item['actions'][0]['params']['contentType'] in ['show','movie']:
                            id = item['actions'][0]['params']['payload']['deeplink']['epgItem']
                        else:
                            id = item['actions'][0]['params']['payload']['contentId']
                        epg_item = {'id' : id, 'title' : item['title'], 'channel_id' : channel_id, 'description' : item['description'], 'startts' : startts, 'endts' : endts, 'cover' : item['image'].replace('{WIDTH}', '480').replace('{HEIGHT}', '320'), 'poster' : item['image'].replace('{WIDTH}', '480').replace('{HEIGHT}', '320')}
                        epg.update({startts : epg_item})
    return epg

def get_day_epg(from_ts, to_ts):
    session = Session()
    api = API()
    epg = {}
    post = {"payload":{"criteria":{"channelSetId":"channel_list.1","viewport":{"channelRange":{"from":0,"to":200},"timeRange":{"from":datetime.fromtimestamp(from_ts).strftime('%Y-%m-%dT%H:%M:%S') + '.000Z',"to":datetime.fromtimestamp(to_ts).strftime('%Y-%m-%dT%H:%M:%S') + '.000Z'},"schema":"EpgViewportAbsolute"}},"requestedOutput":{"channelList":"none","datePicker":False,"channelSets":False}}}
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/epg.display', data = post, session = session, nolog = True)
    if 'err' not in data:
        for channel in data['schedule']:
            for item in channel['items']:
                startts = int(datetime.fromisoformat(item['startAt']).timestamp())
                endts = int(datetime.fromisoformat(item['endAt']).timestamp())
                if 'contentType' in item['actions'][0]['params'] or 'contentId' in item['actions'][0]['params']['payload']:
                    if item['actions'][0]['params']['contentType'] == 'show':
                        id = item['actions'][0]['params']['payload']['deeplink']['epgItem']
                    else:
                        id = item['actions'][0]['params']['payload']['contentId']
                    epg_item = {'id' : id, 'title' : item['title'], 'channel_id' : channel['channelId'], 'description' : item['description'], 'startts' : startts, 'endts' : endts, 'cover' : item['image'].replace('{WIDTH}', '480').replace('{HEIGHT}', '320'), 'poster' : item['image'].replace('{WIDTH}', '480').replace('{HEIGHT}', '320')}
                    epg.update({channel['channelId'] + str(startts) : epg_item})
    return epg

def get_data_from_api(id):
    session = Session()
    api = API()
    item_detail = {}
    post = {"payload":{"contentId":id}}
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/page.content.display', data = post, session = session)
    if 'err' not in data:
        for block in data['layout']['blocks']:
            if block['schema'] == 'OnAirContentInfoBlock' and block['template'] == 'fullInfo' and 'additionalContentData' in block and 'lists' in block['additionalContentData']:
                description = ''
                cast = []
                directors = []
                genres = []
                original = ''
                year = ''
                country = ''
                if 'description' in block:
                    description = block['description']
                for item in block['additionalContentData']['lists']:
                    name = item['label']['name'].replace(':','')
                    if name == 'Hrají':
                        for value in item['valueList']:
                            cast.append(value['name'])
                    elif name == 'Režie':
                        for value in item['valueList']:
                            directors.append(value['name'])
                    elif name == 'Žánr':
                        for value in item['valueList']:
                            genres.append(value['name'])
                    elif name == 'Původní název':
                        for value in item['valueList']:
                            original = value['name']
                    elif name == 'Rok':
                        for value in item['valueList']:
                            year = value['name']
                    elif name == 'Země původu':
                        for value in item['valueList']:
                            country = value['name']
                    # else:
                    #     print(name)
                    #     print(item['valueList'])     
                item_detail = {'description' : description, 'original' : original, 'year' : year, 'genres' : genres, 'cast' : cast, 'directors' : directors, 'country' : country}
    return item_detail

def get_item_detail(id):
    global db
    item_detail = {}
    addon = xbmcaddon.Addon()
    if addon.getSetting('item_details') == 'true':
        open_db()
        row = None
        for row in db.execute('SELECT description, original, "cast", directors, year, country, genres FROM items WHERE id = ?', [id]):
            description = row[0]
            original = row[1]
            cast = json.loads(row[2])
            directors = json.loads(row[3])
            year = row[4]
            country = row[5]
            genres = json.loads(row[6])
        if not row:
            item_detail = get_data_from_api(id)
            if len(item_detail) > 0:
                db.execute('INSERT INTO items VALUES(?, ?, ?, ?, ?, ?, ?, ?)', (id, item_detail['description'], item_detail['original'], json.dumps(item_detail['cast']), json.dumps(item_detail['directors']), item_detail['year'], item_detail['country'], json.dumps(item_detail['genres'])))      
                db.commit()            
        else:
            item_detail = {'description' : description, 'original' : original, 'year' : year, 'genres' : genres, 'cast' : cast, 'directors' : directors, 'country' : country}
        close_db()            
    else:
        item_detail = get_data_from_api(id)
    return item_detail    

def epg_listitem(list_item, epg, icon):
    cast = []
    directors = []
    genres = []
    kodi_version = get_kodi_version()
    if kodi_version >= 20:
        infotag = list_item.getVideoInfoTag()
        infotag.setMediaType('movie')
    else:
        list_item.setInfo('video', {'mediatype' : 'movie'})
    if 'cover' in epg and len(epg['cover']) > 0:
        if 'poster' in epg and len(epg['poster']) > 0:
            if icon == '':
                icon = epg['poster']
            list_item.setArt({'poster': epg['poster'], 'icon': icon})
        else:
            if icon == '':
                icon = epg['cover']
            list_item.setArt({'thumb': epg['cover'], 'icon': icon})
    elif icon is not None:
        list_item.setArt({'thumb': icon, 'icon': icon})    
    if 'description' in epg and len(epg['description']) > 0:
        if kodi_version >= 20:
            infotag.setPlot(epg['description'])
        else:
            list_item.setInfo('video', {'plot': epg['description']})
    if 'year' in epg and len(str(epg['year'])) > 0 and epg['year'].isdigit():
        if kodi_version >= 20:
            infotag.setYear(int(epg['year']))
        else:
            list_item.setInfo('video', {'year': int(epg['year'])})
    if 'original' in epg and len(epg['original']) > 0:
        if kodi_version >= 20:
            infotag.setOriginalTitle(epg['original'])
        else:
            list_item.setInfo('video', {'originaltitle': epg['original']})
    if 'country' in epg and len(epg['country']) > 0:
        if kodi_version >= 20:
            infotag.setCountries([epg['country']])
        else:
            list_item.setInfo('video', {'country': epg['country']})
    if 'genres' in epg and len(epg['genres']) > 0:
        for genre in epg['genres']:      
          genres.append(genre)
        if kodi_version >= 20:
            infotag.setGenres(genres)
        else:
            list_item.setInfo('video', {'genre' : genres})    
    if 'cast' in epg and len(epg['cast']) > 0:
        for person in epg['cast']: 
            if len(person) > 0:
                if kodi_version >= 20:
                    cast.append(xbmc.Actor(person))
                else:
                    cast.append(person)
        if kodi_version >= 20:
            infotag.setCast(cast)
        else:
            list_item.setInfo('video', {'castandrole' : cast})  
    if 'directors' in epg and len(epg['directors']) > 0:
        for person in epg['directors']:      
            directors.append(person)
        if kodi_version >= 20:
            infotag.setDirectors(directors)
        else:
            list_item.setInfo('video', {'director' : directors})  
    return list_item

