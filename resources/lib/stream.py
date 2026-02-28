# -*- coding: utf-8 -*-
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from datetime import datetime
import json
import time
import ssl
from xml.dom import minidom
from urllib.request import urlopen, Request

from resources.lib.session import Session
from resources.lib.api import API
from resources.lib.epg import get_channel_epg
from resources.lib.utils import api_version

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
    from urllib.parse import urlencode
    headers = {'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0', 'Accept-Encoding' : 'gzip, deflate, br, zstd', 'Accept' : '*/*'}
    addon = xbmcaddon.Addon()
    list_item = xbmcgui.ListItem(path = url)
    list_item.setProperty('inputstream', 'inputstream.adaptive')
    list_item.setProperty('inputstream.adaptive.manifest_type', type)
    list_item.setProperty('inputstream.adaptive.stream_headers', urlencode(headers))
    list_item.setProperty('inputstream.adaptive.manifest_headers', urlencode(headers))
    if drm is not None:
        from inputstreamhelper import Helper # type: ignore
        is_helper = Helper('mpd', drm = 'com.widevine.alpha')
        if addon.getSetting('inputstream_helper') == 'false' or is_helper.check_inputstream():            
            list_item.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
            list_item.setProperty('inputstream.adaptive.license_key', drm['licenceUrl'] + '|' + urlencode({'x-axdrm-message' : drm['token']}) + '|R{SSM}|')                
    if type == 'mpd':
        list_item.setMimeType('application/dash+xml')
    list_item.setContentLookup(False)       
    if next_url is not None:
        next_list_item = xbmcgui.ListItem(path = next_url)
        next_list_item.setProperty('inputstream', 'inputstream.adaptive')
        next_list_item.setProperty('inputstream.adaptive.manifest_type', type)
        next_list_item.setProperty('inputstream.adaptive.stream_headers', urlencode(headers))
        next_list_item.setProperty('inputstream.adaptive.manifest_headers', urlencode(headers))
        if next_drm is not None:
            from inputstreamhelper import Helper # type: ignore
            is_helper = Helper('mpd', drm = 'com.widevine.alpha')
            if addon.getSetting('inputstream_helper') == 'false' or is_helper.check_inputstream():            
                list_item.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
                from urllib.parse import urlencode
                list_item.setProperty('inputstream.adaptive.license_key', drm['licenceUrl'] + '|' + urlencode({'x-axdrm-message' : drm['token']}) + '|R{SSM}|')                
        if type == 'mpd':
            next_list_item.setMimeType('application/dash+xml')
        next_list_item.setContentLookup(False)       
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.add(next_url, next_list_item)
    xbmcplugin.setResolvedUrl(_handle, True, list_item)

def get_stream_url(post, mode, reload_profile = False):
    api = API()
    session = Session()
    if reload_profile == True:
        xbmcgui.Dialog().notification('Oneplay','Znovunačtení profilu', xbmcgui.NOTIFICATION_INFO, 3000)
        session.reload_profile()
    url_dash = None
    url_dash_drm = None
    url_hls = None
    drm = None
    next_url_dash = None
    next_url_dash_drm = None
    next_url_hls = None
    next_drm = None    
    skip_error = False
    if 'startMode' in post['payload'] and post['payload']['startMode'] == 'live':
        post['payload']['startMode'] = 'start'
    data = api.call_api(url = 'https://http.cms.jyxo.cz/api/' + api_version + '/content.play', data = post, session = session)
    if 'err' in data and reload_profile == False:
        if len(data['err']) > 0 and data['err'] == 'Kdo se dívá?':
            return get_stream_url(post, mode, True)
        elif len(data['err']) > 0 and data['err'] == 'Potvrďte spuštění dalšího videa':
            response = xbmcgui.Dialog().yesno('Potvrzení spuštění', 'Máte limitovaný počet přehrání. Opravdu chcete pořad přehrát?', nolabel = 'Ne', yeslabel = 'Ano')
            if response:
                post['authorization'] = [{"schema":"UserConfirmAuthorization","type":"tasting"}]
                data = api.call_api(url = 'https://http.cms.jyxo.cz/api/' + api_version + '/content.play', data = post, session = session)
                if 'err' not in data:
                    skip_error = True
        elif len(data['err']) > 0 and data['err'] == 'Zadejte kód rodičovského zámku':
                addon = xbmcaddon.Addon()
                if str(addon.getSetting('pin')) == '1621' or len(str(addon.getSetting('pin'))) == 0:
                    pin = xbmcgui.Dialog().numeric(type = 0, heading = 'Zadejte PIN', bHiddenInput = True)
                    if len(str(pin)) != 4:
                        xbmcgui.Dialog().notification('Oneplay','Nezadaný-nesprávný PIN', xbmcgui.NOTIFICATION_ERROR, 5000)
                        pin = '1621'
                else:
                    pin = str(addon.getSetting('pin'))
                post['authorization'] = [{"schema":"PinRequestAuthorization","pin":pin,"type":"parental"}]
                data = api.call_api(url = 'https://http.cms.jyxo.cz/api/' + api_version + '/content.play', data = post, session = session)
                if 'err' in data:
                    if len(data['err']) > 0:
                        xbmcgui.Dialog().notification('Oneplay', data['err'], xbmcgui.NOTIFICATION_ERROR, 5000)
                    else:
                        xbmcgui.Dialog().notification('Oneplay', 'Problém při přehrání', xbmcgui.NOTIFICATION_ERROR, 5000)                    
                else:
                    skip_error = True
        elif len(data['err']) > 0:
            xbmcgui.Dialog().notification('Oneplay', data['err'], xbmcgui.NOTIFICATION_ERROR, 5000)
        if skip_error == False:
            return None, None, None, None, None, None, None, None
    else:
        if 'liveControl' in data['playerControl'] and 'timeShift' in data['playerControl']['liveControl']['timeline'] and data['playerControl']['liveControl']['timeline']['timeShift']['available'] == False:
            post.update({'payload' : {'criteria' : post['payload']['criteria'], 'startMode' : 'live'}})
            data = api.call_api(url = 'https://http.cms.jyxo.cz/api/' + api_version + '/content.play', data = post, session = session)
        if 'liveControl' in data['playerControl'] and 'mosaic' in data['playerControl']['liveControl']:
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
            data = api.call_api(url = 'https://http.cms.jyxo.cz/api/' + api_version + '/content.play', data = post, session = session)
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
    if mode != 'start' and data['media']['stream']['type'] == 'catchup' and 'playerControl' in data and 'nextVideo' in data['playerControl'] and 'playNextAction' in data['playerControl']['nextVideo'] and data['playerControl']['nextVideo']['playNextAction']['call'] == 'content.playnext':
        post = {"payload":data['playerControl']['nextVideo']['playNextAction']['params']['payload'],"playbackCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","subtitle":{"formats":["vtt"],"locations":["InstreamTrackLocation","ExternalTrackLocation"]},"liveSpecificCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","multipleAudio":False}}}
        data = api.call_api(url = 'https://http.cms.jyxo.cz/api/' + api_version + '/content.playnext', data = post, session = session)
        if 'err' in data or 'offer' not in data or 'channelUpdate' not in data['offer']:
            if 'err' in data and len(data['err']) > 0:
                if data['err'] == 'Kdo se dívá?' and reload_profile == False:
                    return get_stream_url(post, mode, True)
                elif data['err'] == 'Potvrďte spuštění dalšího videa':
                    pass
                else:
                    xbmcgui.Dialog().notification('Oneplay', data['err'], xbmcgui.NOTIFICATION_ERROR, 5000)
            return url_hls, url_dash, url_dash_drm, drm, None, None, None, None
        data = data['offer']['channelUpdate']        
        if 'media' in data:
            for asset in data['media']['stream']['assets']:
                if asset['protocol'] == 'dash':
                    if 'drm' in asset:
                        next_url_dash_drm = asset['src']
                        next_drm = {'token' : asset['drm'][0]['drmAuthorization']['value'], 'licenceUrl' : asset['drm'][0]['licenseAcquisitionURL']}
                    else:
                        next_url_dash = asset['src']
                if asset['protocol'] == 'hls':
                    if 'drm' not in asset:
                        next_url_hls = asset['src']     
    return url_hls, url_dash, url_dash_drm, drm, next_url_hls, next_url_dash, next_url_dash_drm, next_drm

def play_stream(id, mode, direct = False):
    addon = xbmcaddon.Addon()
    api = API()
    session = Session()
    keepalive = None

    id = json.loads(id)
    if direct == False or direct == 'False':
        post = {"payload":id}
        data = api.call_api(url = 'https://http.cms.jyxo.cz/api/' + api_version + '/page.content.display', data = post, session = session)
        if 'err' not in data:
            for block in data['layout']['blocks']:            
                if block['schema'] == 'ContentHeaderBlock':
                    if 'mainAction' in block and 'action' in block['mainAction'] and block['mainAction']['action']['call'] == 'content.play':
                        payload = block['mainAction']['action']['params']['payload']
    else:
        payload = id
    post = {"payload":payload,"playbackCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","subtitle":{"formats":["vtt"],"locations":["InstreamTrackLocation","ExternalTrackLocation"]},"liveSpecificCapabilities":{"protocols":["dash","hls"],"drm":["widevine","fairplay"],"altTransfer":"Unicast","multipleAudio":False}}}
    url_hls, url_dash, url_dash_drm, drm, next_url_hls, next_url_dash, next_url_dash_drm, next_drm = get_stream_url(post, mode)

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
