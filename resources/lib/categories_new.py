# -*- coding: utf-8 -*-
import sys
import os
import xbmcplugin
import xbmcgui
import xbmc
import xbmcaddon

import json 
import time
from urllib.request import urlopen, Request

from resources.lib.session import Session
from resources.lib.api import API
from resources.lib.epg import get_item_detail, epg_listitem
from resources.lib.utils import get_url
from resources.lib.stream import get_manifest_redirect, get_stream_url, get_list_item

if len(sys.argv) > 1:
    _handle = int(sys.argv[1])

class Item:
    def __init__(self, label, schema, call, params, route, tracking, data):
        self.label = label
        self.schema = schema
        self.call = call
        self.params = params
        self.route = route
        self.tracking = tracking
        self.data = data
        func = getattr(self, self.schema)
        func()

    def ApiAppAction(self):
        self.call = self.call.replace('.', '_')
        if 'payload' in self.params and self.params and 'contentId' in self.params['payload']:
            item = get_item_detail(self.params['payload']['contentId'], True, self.data)
        else:
            item = {}
        item['title'] = self.route['title']
        list_item = xbmcgui.ListItem(label = item['title'])
        if 'schema' in self.params and (self.params['schema'] == 'ContentPlayApiAction' or (self.params['schema'] == 'PageContentDisplayApiAction' and self.params['contentType'] == 'movie')):
            list_item = epg_listitem(list_item, item, None)
            url = get_url(action = self.call, params = json.dumps(self.params), label = item['title'])
            list_item.setContentLookup(False)          
            list_item.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
        else:
            list_item = epg_listitem(list_item, item, None)
            url = get_url(action = self.call, params = json.dumps(self.params), label = self.label + ' / ' + item['title'])
            xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

    def CarouselBlock(self):
        item = {'title' : self.tracking['title']}
        list_item = xbmcgui.ListItem(label = item['title'])
        url = get_url(action = 'page_category_display', params = json.dumps(self.params), id = self.tracking['id'], show_filter = False, label = self.label + ' / ' + item['title'])
        # menus = [('Přidat do oblíbených Oneplay', 'RunPlugin(plugin://' + plugin_id + '?action=add_favourite&type=category&id=' + id + '~' + block['id'] + '~' + str(criteria) + '&image=None&title=' + (label + ' / ' + block['header']['title']).replace('Kategorie / ','') + ')')]
        # list_item.addContextMenuItems(menus)       
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    
    def CarouselGenericFilter(self):
        list_item = xbmcgui.ListItem(label = self.data['label'])
        url = get_url(action = self.call, params = json.dumps(self.params), label = self.label)
        if self.data is not None and 'image' in self.data:
            list_item.setArt({ 'thumb' : self.data['image'], 'icon' : self.data['image'] })

        # menus = [('Přidat do oblíbených Oneplay', 'RunPlugin(plugin://' + plugin_id + '?action=add_favourite&type=category&id=' + id + '~' + block['id'] + '~' + str(criteria) + '&image=None&title=' + (label + ' / ' + block['header']['title']).replace('Kategorie / ','') + ')')]
        # list_item.addContextMenuItems(menus)       
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

    def SubMenu(self):
        list_item = xbmcgui.ListItem(label = self.data['label'])
        url = get_url(action = self.call, params = json.dumps(self.params), id = self.data['id'], show_filter = True, label = self.label)
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

def CarouselBlock(label, block, params, id):
    if id is None and block['template'] != 'contentFilter':
        if 'showMore' in block['carousels'][0]:
            item = block['carousels'][0]['showMore']
            item['action']['route']['title'] = block['carousels'][0]['tracking']['title']
            Item(label = label, schema = item['action']['schema'], call = item['action']['call'], params = item['action']['params'], route = item['action']['route'], tracking = block['carousels'][0]['tracking'], data = None)
        else:
            if params['schema'] == 'PageCategoryDisplayApiAction':
                Item(label = label, schema = block['schema'], call = None, params = params, route = None, tracking = block['carousels'][0]['tracking'], data = None)
            else:
                if block['header']['title'] in ['Celé díly']:
                    if 'criteria' in block['carousels'][0]:
                        carouselId = block['carousels'][0]['id']
                        for item in block['carousels'][0]['criteria'][0]['items']:
                            if 'additionalText' in item:
                                label = item['label'] + ' (' + item['additionalText'] + ')'
                            else:
                                label = item['label']
                            Item(label = label + ' / ' + item['label'], schema = block['carousels'][0]['criteria'][0]['schema'], call = 'carousel_display', params = {'payload' : {'carouselId' : carouselId, 'criteria' : {'filterCriterias' : item['criteria'], 'sortOption' : 'DESC'}}}, route = None, tracking = None, data = {'label' : label})
                    else:
                        for tile in block['carousels'][0]['tiles']:
                            print(tile)
    else:
        if block['carousels'][0]['tracking']['id'] == id or block['template'] == 'contentFilter':
            for tile in block['carousels'][0]['tiles']:
                title = tile['title']
                image = tile['image'].replace('{WIDTH}', '320').replace('{HEIGHT}', '480')
                Item(label = label, schema = tile['action']['schema'], call = tile['action']['call'], params = tile['action']['params'], route = tile['action']['route'], tracking = None, data = {'title' : title, 'cover' : image})
            if block['carousels'][0]['paging']['next'] == True:
                addon = xbmcaddon.Addon()
                icons_dir = os.path.join(addon.getAddonInfo('path'), 'resources','images')
                pageCount = block['carousels'][0]['paging']['pageCount']
                count = len(block['carousels'][0]['tiles'])
                page = 2
                carouselId = block['carousels'][0]['id']
                image = os.path.join(icons_dir , 'next_arrow.png')
                Item(label = 'Následující strana', schema = block['carousels'][0]['criteria'][0]['schema'], call = 'carousel_display', params = {'payload' : {'carouselId' : carouselId, 'criteria' : block['carousels'][0]['paging']['criteria'], 'paging' : {'count' : count, 'position' : count * (page - 1) + 1}}}, route = None, tracking = None, data = {'label' : 'Následující strana (' + str(page) + '/' + str(pageCount) + ')', 'image' : image})

def TabBlock(label, block):
    for block in block['layout']['blocks']:
        pass


    # for tile in block['layout']['blocks'][0]['carousels'][0]['tiles']:
    #     title = tile['title']
    #     image = tile['image'].replace('{WIDTH}', '320').replace('{HEIGHT}', '480')
    #     Item(label = label, schema = tile['action']['schema'], call = tile['action']['call'], params = tile['action']['params'], route = tile['action']['route'], tracking = None, data = {'title' : title, 'cover' : image})
    # for select in block['layout']['blocks'][0]['carousels'][0]['criteria']:
    #     if select['schema'] == 'CarouselGenericFilter' and select['title'] == 'Vybrat sérii':
    #         for item in select['items']:
    #             label = item['label'] + ' (' + item['additionalText'] + ')'
    #             carouselId = block['layout']['blocks'][0]['carousels'][0]['id']
    #             Item(label = label + ' / ' + item['label'], schema = select['schema'], call = 'carousel_display', params = {'payload' : {'carouselId' : carouselId, 'criteria' : {'filterCriterias' : item['criteria'], 'sortOption' : 'DESC'}}}, route = None, tracking = None, data = {'label' : label})

def BreadcrumbBlock(label, block, params, id, show_filter):
    for item in block['menu']['groups'][0]['items']:
        if item['schema'] == 'SubMenu':
            if show_filter == False or show_filter == 'False':
                Item(label = label, schema = item['schema'], call = 'page_category_display', params = params, route = None, tracking = None, data = {'label' : item['title'], 'id' : id})
            else:
                for filter in item['groups'][0]['items']:
                    Item(label = label, schema = filter['action']['schema'], call = filter['action']['call'], params = filter['action']['params'], route = {'title' : filter['title']}, tracking = None, data = None)

        
def page_category_display(label, params, id, show_filter):
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'movies')
    params = json.loads(params)
    session = Session()
    api = API()
    post = {'payload' : params['payload']}
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/page.category.display', data = post, session = session) 
    if 'err' not in data:
        for block in data['layout']['blocks']:
            if block['schema'] == 'BreadcrumbBlock':
                BreadcrumbBlock(label, block, params, id, show_filter)
            if block['schema'] == 'TabBlock':                
                TabBlock(label, block)
            if block['schema'] == 'CarouselBlock' and (show_filter == False or show_filter == 'False'):
                CarouselBlock(label, block, params, id)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)    

def page_content_display(label, params):
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'movies')
    params = json.loads(params)
    session = Session()
    api = API()
    post = {'payload' : params['payload']}
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/page.content.display', data = post, session = session)
    if 'err' not in data:
        # for block in data['layout']['blocks']:
        #     if block['schema'] == 'TabBlock':
        #         for tab in block['tabs']:
        #             if tab['label']['name'] == 'Celé díly' and tab['isActive'] == False:
        #                 post = {"payload":{"tabId":tab['id']}}
        #                 data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/tab.display', data = post, session = session)

        
        if data['tracking']['type'] == 'movie':
            params = {'payload' : {'criteria' : {'schema' : 'ContentCriteria', 'contentId' : data['tracking']['id']}}}
            content_play(json.dumps(params))
        else:
            for block in data['layout']['blocks']:
                if block['schema'] in 'CarouselBlock' and block['header']['title'] == 'Celé díly':
                    CarouselBlock(label, block, params, None)
                if block['schema'] in 'TabBlock':
                    TabBlock(label, block)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)    

def carousel_display(label, params):
    xbmcplugin.setPluginCategory(_handle, label)
    xbmcplugin.setContent(_handle, 'movies')
    params = json.loads(params)
    get_page = True
    page = 1
    session = Session()
    api = API()
    post = {'payload' : params['payload']}
    while get_page == True:
        data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/carousel.display', data = post, session = session)
        if 'err' not in data:
            if data['carousel']['paging']['next'] == True:
                pageCount = data['carousel']['paging']['pageCount']
                count = len(data['carousel']['tiles'])
                if 'paging' in post['payload']:
                    position = post['payload']['paging']['position']
                    page = int((position - 1) / count + 1 - 1)
                else:
                    page = 0
                if 'criteria' in data['carousel']['paging'] and page > 0:
                    carouselId = data['carousel']['id']
                    Item(label = 'Předchozí strana', schema = 'CarouselGenericFilter', call = 'carousel_display', params = {'payload' : {'carouselId' : carouselId, 'criteria' : data['carousel']['paging']['criteria'], 'paging' : {'count' : count, 'position' : count * (page - 1) + 1}}}, route = None, tracking = None, data = {'label' : 'Předchozí strana (' + str(page) + '/' + str(pageCount) + ')'})                    

            for item in data['carousel']['tiles']:
                Item(label = label, schema = item['action']['schema'], call = item['action']['call'], params = item['action']['params'], route = item['action']['route'], tracking = None, data = None)
            if data['carousel']['paging']['next'] == True:
                if 'paging' in post['payload']:
                    position = post['payload']['paging']['position']
                    page = int((position - 1) / count + 1 + 1)
                else:
                    page = 2
                if 'criteria' in data['carousel']['paging'] and page < pageCount:
                    carouselId = data['carousel']['id']
                    Item(label = 'Následující strana', schema = 'CarouselGenericFilter', call = 'carousel_display', params = {'payload' : {'carouselId' : carouselId, 'criteria' : data['carousel']['paging']['criteria'], 'paging' : {'count' : count, 'position' : count * (page - 1) + 1}}}, route = None, tracking = None, data = {'label' : 'Následující strana (' + str(page) + '/' + str(pageCount) + ')'})                    
                    get_page = False
                else:
                    count = len(data['carousel']['tiles'])
                    page = page + 1
                    post['payload']['paging'] = {'count' : count, 'position' : count * (page - 1) + 1}
            else:
                get_page = False
        else:
            get_page = False                
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)       

def content_play(params):
    addon = xbmcaddon.Addon()
    params = json.loads(params)
    post = {'payload' : params['payload'], "playbackCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","subtitle":{"formats":["vtt"],"locations":["InstreamTrackLocation","ExternalTrackLocation"]},"liveSpecificCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","multipleAudio":False}}}
    url_hls, url_dash, url_dash_drm, drm = get_stream_url(post, 'archive')

    if addon.getSetting('prefer_hls') == 'true' and url_hls is not None:
        url, keepalive = get_manifest_redirect(url_hls)
        get_list_item('hls', url, None, None, None)
    elif url_dash is not None:
        url, keepalive = get_manifest_redirect(url_dash)
        get_list_item('mpd', url, None, None, None)
    elif url_dash_drm is not None:
        url, keepalive = get_manifest_redirect(url_dash_drm)
        get_list_item('mpd', url, drm, None, None)
    elif url_hls is not None:
        url, keepalive = get_manifest_redirect(url_hls)
        get_list_item('hls', url, None, None, None)
    else:
        xbmcgui.Dialog().notification('Oneplay','Problém při přehrání', xbmcgui.NOTIFICATION_ERROR, 5000)
    if keepalive is not None:
        time.sleep(3)
        while(xbmc.Player().isPlaying()):
            request = Request(url = keepalive , data = None)
            if addon.getSetting('log_request_url') == 'true':
                xbmc.log('Oneplay > ' + str(keepalive))
            response = urlopen(request)
            if addon.getSetting('log_response') == 'true':
                xbmc.log('Oneplay > ' + str(response.status))
            time.sleep(20)        

def list_categories_new(label):
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
                        Item(label = label, schema = item['action']['schema'], call = item['action']['call'], params = item['action']['params'], route = item['action']['route'], tracking = None, data = None)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)    
