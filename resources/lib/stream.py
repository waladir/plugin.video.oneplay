# -*- coding: utf-8 -*-
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from datetime import datetime
import time
import ssl
from xml.dom import minidom
from urllib.request import urlopen, Request

from resources.lib.session import Session
from resources.lib.api import API
from resources.lib.channels import Channels
from resources.lib.epg import get_channel_epg

if len(sys.argv) > 1:
    _handle = int(sys.argv[1])

def play_catchup(id, start_ts, end_ts):
    start_ts = int(start_ts)
    end_ts = int(end_ts)    
    epg = get_channel_epg(channel_id = id, from_ts = start_ts - 7200, to_ts = end_ts + 60*60*12)
    if start_ts in epg:
        if epg[start_ts]['endts'] > int(time.mktime(datetime.now().timetuple()))-10:
            play_stream(id, 'start')
        else:
            play_stream(epg[start_ts]['id'], 'archive')
    else:
        play_stream(id, 'start')

def get_manifest_redirect(url):
    try:
        context=ssl.create_default_context()
        context.set_ciphers('DEFAULT')
        request = Request(url = url , data = None)
        response = urlopen(request)
        manifest = response.geturl()
        keepalive = get_keepalive_url(manifest, response)
        return manifest, keepalive
    except:
        return url, None

def get_keepalive_url(manifest, response):
    keepalive = None
    if 'manifest.mpd' in manifest:
        dom = minidom.parseString(response.read())
        adaptationSets = dom.getElementsByTagName('AdaptationSet')
        for adaptationSet in adaptationSets:
            if adaptationSet.getAttribute('contentType') == 'video':
                minBandwidth = adaptationSet.getAttribute('minBandwidth')
                segmentTemplates = adaptationSet.getElementsByTagName('SegmentTemplate')
                for segmentTemplate in segmentTemplates:
                    timelines = segmentTemplate.getElementsByTagName('S')
                    for timeline in timelines:
                        if len(timeline.getAttribute('t')) > 0:
                            ts = timeline.getAttribute('t')
                    uri = 'dash/' + segmentTemplate.getAttribute('media').replace('&amp;', '&').replace('$RepresentationID$', 'video=' + minBandwidth).replace('$Time$', ts)
                    keepalive = manifest.replace('manifest.mpd?bkm-query', uri)
    elif 'index.m3u8' in manifest:
        streams = str(response.read()).split('#EXT-X-STREAM-INF:BANDWIDTH=')
        if len(streams) > 0:
            uri = streams[1].split('\\n')[1]
            keepalive = manifest.replace('index.m3u8?bkm-query', uri)
    return keepalive

def get_list_item(type, url, drm, next_url, next_drm):
    list_item = xbmcgui.ListItem(path = url)
    list_item.setProperty('inputstream', 'inputstream.adaptive')
    list_item.setProperty('inputstream.adaptive.manifest_type', type)
    if drm is not None:
        from inputstreamhelper import Helper # type: ignore
        is_helper = Helper('mpd', drm = 'com.widevine.alpha')
        if is_helper.check_inputstream():            
            list_item.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
            from urllib.parse import urlencode
            list_item.setProperty('inputstream.adaptive.license_key', drm['licenceUrl'] + '|' + urlencode({'x-axdrm-message' : drm['token']}) + '|R{SSM}|')                
    if type == 'mpd':
        list_item.setMimeType('application/dash+xml')
    list_item.setContentLookup(False)       
    if next_url is not None:
        next_list_item = xbmcgui.ListItem(path = next_url)
        next_list_item.setProperty('inputstream', 'inputstream.adaptive')
        next_list_item.setProperty('inputstream.adaptive.manifest_type', type)
        if next_drm is not None:
            from inputstreamhelper import Helper # type: ignore
            is_helper = Helper('mpd', drm = 'com.widevine.alpha')
            if is_helper.check_inputstream():            
                list_item.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
                from urllib.parse import urlencode
                list_item.setProperty('inputstream.adaptive.license_key', drm['licenceUrl'] + '|' + urlencode({'x-axdrm-message' : drm['token']}) + '|R{SSM}|')                
        if type == 'mpd':
            next_list_item.setMimeType('application/dash+xml')
        next_list_item.setContentLookup(False)       
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.add(next_url, next_list_item)
    xbmcplugin.setResolvedUrl(_handle, True, list_item)

def get_stream_url(post, mode, next = False):
    api = API()
    session = Session()
    url_dash = None
    url_dash_drm = None
    url_hls = None
    drm = None
    if next == False:
        data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/content.play', data = post, session = session)
        if 'err' in data:
            return None, None, None, None
    else:
        data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/content.playnext', data = post, session = session)
        if 'err' in data or 'offer' not in data or 'channelUpdate' not in data['offer']:
            return None, None, None, None
        data = data['offer']['channelUpdate']
    if 'err' in data:
        if data['err'] == 'Zadejte kód rodičovského zámku' and next == False:
            addon = xbmcaddon.Addon()
            if str(addon.getSetting('pin')) == '1621' or len(str(addon.getSetting('pin'))) == 0:
                pin = xbmcgui.Dialog().numeric(type = 0, heading = 'Zadejte PIN', bHiddenInput = True)
                if len(str(pin)) != 4:
                    xbmcgui.Dialog().notification('Oneplay','Nezadaný-nesprávný PIN', xbmcgui.NOTIFICATION_ERROR, 5000)
                    pin = '1621'
            else:
                pin = str(addon.getSetting('pin'))
            post['authorization'] = [{"schema":"PinRequestAuthorization","pin":pin,"type":"parental"}]
            data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/content.play', data = post, session = session)
            if 'err' in data:
                if len(data['err']) > 0:
                    xbmcgui.Dialog().notification('Oneplay', data['err'], xbmcgui.NOTIFICATION_ERROR, 5000)
                else:
                    xbmcgui.Dialog().notification('Oneplay', 'Problém při přehrání', xbmcgui.NOTIFICATION_ERROR, 5000)                    

        else:            
            if len(data['err']) > 0:
                xbmcgui.Dialog().notification('Oneplay', data['err'], xbmcgui.NOTIFICATION_ERROR, 5000)
            else:
                xbmcgui.Dialog().notification('Oneplay', 'Problém při přehrání', xbmcgui.NOTIFICATION_ERROR, 5000)                    
    else:
        if mode == 'start' and 'liveControl' in data['playerControl'] and 'timeShift' in data['playerControl']['liveControl']['timeline'] and data['playerControl']['liveControl']['timeline']['timeShift']['available'] == False:
            post.update({'payload' : {'criteria' : post['payload']['criteria'], 'startMode' : 'live'}})
            if next == False:
                data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/content.play', data = post, session = session)
            else:
                data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/content.playnext', data = post, session = session)

        if 'liveControl' in data['playerControl'] and 'mosaic' in data['playerControl']['liveControl'] and next == False:
            md_titles = []
            md_ids = []
            for item in data['playerControl']['liveControl']['mosaic']['items']:
                md_titles.append(item['title'])
                md_ids.append(item['play']['params']['payload']['criteria']['contentId'])            
            response = xbmcgui.Dialog().select(heading = 'Multidimenze - výběr streamu', list = md_titles, preselect = 0)
            if response < 0:
                return
            id = md_ids[response]
            if mode == 'archive':
                post = {"payload":{"criteria":{"schema":"MDPlaybackCriteria","contentId":id,"position":0}},"playbackCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","subtitle":{"formats":["vtt"],"locations":["InstreamTrackLocation","ExternalTrackLocation"]},"liveSpecificCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","multipleAudio":False}}}
            else:
                post = {"payload":{"criteria":{"schema":"MDPlaybackCriteria","contentId":id,"position":0},"startMode":mode},"playbackCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","subtitle":{"formats":["vtt"],"locations":["InstreamTrackLocation","ExternalTrackLocation"]},"liveSpecificCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","multipleAudio":False}}}
            data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/content.play', data = post, session = session)
            if 'err' in data or 'media' not in data:
                if len(data['err']) > 0:
                    xbmcgui.Dialog().notification('Oneplay', data['err'], xbmcgui.NOTIFICATION_ERROR, 5000)
                else:
                    xbmcgui.Dialog().notification('Oneplay', 'Problém při přehrání', xbmcgui.NOTIFICATION_ERROR, 5000)                    
    if 'media' in data:
        for asset in data['media']['stream']['assets']:
            if asset['protocol'] == 'dash':
                if 'drm' in asset:
                    url_dash_drm = asset['src']
                    drm = {'token' : asset['drm'][0]['drmAuthorization']['value'], 'licenceUrl' : asset['drm'][0]['licenseAcquisitionURL']}
                else:
                    url_dash = asset['src']
            if asset['protocol'] == 'hls':
                if 'drm' not in asset:
                    url_hls = asset['src']
    return url_hls, url_dash, url_dash_drm, drm

def play_stream(id, mode):
    addon = xbmcaddon.Addon()
    api = API()
    session = Session()
    keepalive = None
    next_url_dash = None
    next_url_dash_drm = None
    next_url_hls = None
    next_drm = None

    if mode == 'start':
        channels = Channels()
        channels_list = channels.get_channels_list('id')
        channel = channels_list[id]
        if channel['adult'] == True:
            if str(addon.getSetting('pin')) == '1621' or len(str(addon.getSetting('pin'))) == 0:
                pin = xbmcgui.Dialog().numeric(type = 0, heading = 'Zadejte PIN', bHiddenInput = True)
                if len(str(pin)) != 4:
                    xbmcgui.Dialog().notification('Oneplay','Nezadaný-nesprávný PIN', xbmcgui.NOTIFICATION_ERROR, 5000)
                    pin = '1621'
            else:
                pin = str(addon.getSetting('pin'))
            post = {"authorization":[{"schema":"PinRequestAuthorization","pin":pin,"type":"parental"}],"payload":{"criteria":{"schema":"ContentCriteria","contentId":"channel." + id},"startMode":"live"},"playbackCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","subtitle":{"formats":["vtt"],"locations":["InstreamTrackLocation","ExternalTrackLocation"]},"liveSpecificCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","multipleAudio":False}}}
        else:
            post = {"payload":{"criteria":{"schema":"ContentCriteria","contentId":"channel." + id},"startMode":mode},"playbackCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","subtitle":{"formats":["vtt"],"locations":["InstreamTrackLocation","ExternalTrackLocation"]},"liveSpecificCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","multipleAudio":False}}}
    else:
        post = {"payload":{"contentId":id}}
        data = api.call_api(url = 'https://http.cms.jyxo.cz/api/v3/page.content.display', data = post, session = session)
        if 'err' not in data:
            for block in data['layout']['blocks']:            
                if block['schema'] == 'ContentHeaderBlock':
                    if 'mainAction' in block and 'action' in block['mainAction'] and 'criteria' in block['mainAction']['action']['params']['payload'] and 'contentId' in block['mainAction']['action']['params']['payload']['criteria']:
                        id = block['mainAction']['action']['params']['payload']['criteria']['contentId']
        if 'epgitem' in id:
            post = {"payload":{"criteria":{"schema":"ContentCriteria","contentId":id},"startMode":"start","timelineMode":"epg"},"playbackCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","subtitle":{"formats":["vtt"],"locations":["InstreamTrackLocation","ExternalTrackLocation"]},"liveSpecificCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","multipleAudio":False}}}
            next_url_hls, next_url_dash, next_url_dash_drm, next_drm = get_stream_url(post, mode, True)
        post = {"payload":{"criteria":{"schema":"ContentCriteria","contentId":id}},"playbackCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","subtitle":{"formats":["vtt"],"locations":["InstreamTrackLocation","ExternalTrackLocation"]},"liveSpecificCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","multipleAudio":False}}}

    url_hls, url_dash, url_dash_drm, drm = get_stream_url(post, mode)

    if addon.getSetting('prefer_hls') == 'true' and url_hls is not None:
        url, keepalive = get_manifest_redirect(url_hls)
        get_list_item('hls', url, None, next_url_hls, None)
    elif url_dash is not None:
        url, keepalive = get_manifest_redirect(url_dash)
        get_list_item('mpd', url, None, next_url_dash, None)
    elif url_dash_drm is not None:
        url, keepalive = get_manifest_redirect(url_dash_drm)
        get_list_item('mpd', url, drm, next_url_dash_drm, next_drm)
    elif url_hls is not None:
        url, keepalive = get_manifest_redirect(url_hls)
        get_list_item('hls', url, None, next_url_hls, None)
    else:
        xbmcgui.Dialog().notification('Oneplay','Pořad nelze přehrát', xbmcgui.NOTIFICATION_ERROR, 3000)
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
