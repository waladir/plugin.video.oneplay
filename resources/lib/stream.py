# -*- coding: utf-8 -*-
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

import json
import time
import ssl
import xml.etree.ElementTree as ET
from urllib.request import urlopen, Request
from urllib.parse import urlencode

from resources.lib.session import Session
from resources.lib.api import API
from resources.lib.epg import get_epg
from resources.lib.utils import is_json_string

def play_catchup(id, start_ts, end_ts):
    """Ošetřuje spuštění catchupu"""
    start_ts, end_ts = int(start_ts), int(end_ts)
    epg = get_epg(start_ts, id)
    id = {"criteria": {"schema": "ContentCriteria", "contentId": "channel." + id}, "startMode": "start"}
    item = epg.get(str(start_ts))
    if not item: # pokud se nepodari najit jako string, zkusi se integer (asi neni potreba)
        item = epg.get(start_ts)
    if item: # pokud se najde pořad v EPG, pustí se catchup, jinak jako fallback živé vysílání
        if item['endts'] > (time.time() - 10):
            play_stream(id, 'start', True)
        else:
            play_stream(item['payload'], 'archive')
    else:
        play_stream(id, 'start', True)

def get_manifest_redirect(url):
    """Stáhne manifest a vrátí URL z redirektu"""
    try:
        context = ssl.create_default_context()
        context.set_ciphers('DEFAULT')
        with urlopen(Request(url), context=context, timeout=10) as response:
            manifest_url = response.geturl()
            content = response.read()
            keepalive = get_keepalive_url(manifest_url, content)
            return manifest_url, keepalive
    except Exception:
        return url, None

def get_keepalive_url(manifest, content):
    """Vrací URL pro volání v rámci keepalive volání"""
    if not content: return None
    try:
        if 'manifest.mpd' in manifest:
            root = ET.fromstring(content)
            # Namespace pro DASH (častý u MPD) - případně upravte dle API
            ns = {'dash': 'urn:mpeg:dash:schema:mpd:2011'}
            # Hledáme video set s nejnižším bandwidth
            for ad_set in root.findall('.//AdaptationSet[@contentType="video"]', ns) or root.findall('.//AdaptationSet'):
                if ad_set.get('contentType') == 'video':
                    min_bw = ad_set.get('minBandwidth', '0')
                    seg_temp = ad_set.find('.//SegmentTemplate', ns)
                    if seg_temp is not None:
                        # Najdeme poslední časový bod (T) v Timeline
                        timelines = seg_temp.findall('.//S', ns)
                        ts = timelines[-1].get('t') if timelines else "0"
                        media = seg_temp.get('media', '').replace('&amp;', '&')
                        media = media.replace('$RepresentationID$', f'video={min_bw}').replace('$Time$', ts)
                        return manifest.replace('manifest.mpd?bkm-query', f'dash/{media}')

        elif 'index.m3u8' in manifest:
            content_str = content.decode('utf-8', errors='ignore')
            if '#EXT-X-STREAM-INF' in content_str:
                parts = content_str.split('#EXT-X-STREAM-INF:')
                if len(parts) > 1:
                    uri = parts[1].split('\n')[1].strip()
                    return manifest.replace('index.m3u8?bkm-query', uri)
    except Exception:
        pass
    return None    

def get_list_item(manifest_type, url, drm, next_url, next_drm):
    """Vytvoření list_item a spuštění (v případě dalšího pořadu přidání do playlistu)"""
    addon = xbmcaddon.Addon()
    headers = urlencode({'User-Agent': API().UA, 'Accept-Encoding': 'gzip, deflate, br, zstd', 'Accept': '*/*'})
    def configure_item(item_url, item_drm):
        item = xbmcgui.ListItem(path=item_url)
        item.setContentLookup(False)
        prop = item.setProperty
        prop('inputstream', 'inputstream.adaptive')
        prop('inputstream.adaptive.manifest_type', manifest_type)
        prop('inputstream.adaptive.stream_headers', headers)
        prop('inputstream.adaptive.manifest_headers', headers)
        if manifest_type == 'mpd':
            item.setMimeType('application/dash+xml')
        if item_drm:
            from inputstreamhelper import Helper # type: ignore
            is_helper = Helper('mpd', drm='com.widevine.alpha')
            if addon.getSetting('inputstream_helper') == 'false' or is_helper.check_inputstream():
                lic_url = item_drm.get('licenceUrl', '')
                token = urlencode({'x-axdrm-message': item_drm.get('token', '')})
                
                prop('inputstream.adaptive.license_type', 'com.widevine.alpha')
                prop('inputstream.adaptive.license_key', f"{lic_url}|{token}|R{{SSM}}|")
        return item
    main_item = configure_item(url, drm)
    if next_url:
        next_item = configure_item(next_url, next_drm)
        xbmc.PlayList(xbmc.PLAYLIST_VIDEO).add(next_url, next_item)
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, main_item)

def get_stream_url(post, mode):
    """Zajištuje získání URL streamu, včetně ošetření multidimenze"""
    api = API()
    session = Session()
    url_dash = url_dash_drm = url_hls = drm = None
    next_url_dash = next_url_dash_drm = next_url_hls = next_drm = None

    def parse_media(media):
        hls, dash, dash_drm, drm_data =  None, None, None, None
        assets = media.get('media', {}).get('stream', {}).get('assets', [])
        for asset in assets:
            if asset['protocol'] == 'dash':
                if 'drm' in asset:
                    dash_drm = asset['src']
                    drm_data = {'token': asset['drm'][0]['drmAuthorization']['value'], 'licenceUrl': asset['drm'][0]['licenseAcquisitionURL']}
                else:
                    dash = asset['src']
            elif asset['protocol'] == 'hls' and 'drm' not in asset:
                hls = asset['src']
        return hls, dash, dash_drm, drm_data

    if post.get('payload', {}).get('startMode') == 'live':
        post['payload']['startMode'] = 'start'
    data = api.content_play(post=post, session=session)
    if not data:
        return (None,) * 8
    liveControl = data.get('playerControl', {}).get('liveControl', {})
    if liveControl.get('timeline', {}).get('timeShift', {}).get('available') is False:
        post['payload'].update({'startMode': 'live'})
        data = api.content_play(post=post, session=session)
    if 'mosaic' in liveControl:
        items = liveControl['mosaic'].get('items', [])
        md_titles = [item['title'] for item in items]
        response = xbmcgui.Dialog().select('Multidimenze - výběr streamu', md_titles)
        if response < 0:
            return (None,) * 8
        selected_id = items[response]['play']['params']['payload']['criteria']['contentId']
        md_criteria = {"schema": "MDPlaybackCriteria", "contentId": selected_id, "position": 0}
        if mode != 'archive':
            md_criteria["startMode"] = mode
        post = {"payload": {"criteria": md_criteria}, "playbackCapabilities": {"protocols": ["dash", "hls"], "drm": ["widevine", "fairplay"], "altTransfer": "Unicast", "multipleAudio": False}}
        data = api.content_play(post=post, session=session)
        if not data or 'media' not in data:
            if data:
                xbmcgui.Dialog().notification('Oneplay', 'Problém při přehrání', xbmcgui.NOTIFICATION_ERROR, 3000)
            return (None,) * 8
    if 'media' in data:
        url_hls, url_dash, url_dash_drm, drm = parse_media(data)

    play_next = data.get('playerControl', {}).get('nextVideo', {}).get('playNextAction', {})
    if mode != 'start' and data.get('media', {}).get('stream', {}).get('type') == 'catchup' and play_next.get('call') == 'content.playnext':
        next_post = {"payload": play_next['params']['payload'], "playbackCapabilities": post.get("playbackCapabilities")}
        next_data = api.content_play(post=next_post, session=session, is_next=True)
        offer_data = next_data.get('offer', {}).get('channelUpdate') if next_data else None
        if offer_data and 'media' in offer_data:
            next_url_hls, next_url_dash, next_url_dash_drm, next_drm = parse_media(offer_data)

    return url_hls, url_dash, url_dash_drm, drm, next_url_hls, next_url_dash, next_url_dash_drm, next_drm

def play_stream(id, mode, direct=False):
    """Zajišťuje přehrání streamu"""
    addon = xbmcaddon.Addon()
    api = API()
    session = Session()
    if isinstance(id, (str, bytes)) and is_json_string(id):
        id = json.loads(id)
    is_direct = str(direct).lower() == 'true'
    if not is_direct: # je nutné získat payload z page.content.display
        data = api.page_content_display(post={"payload": id}, session=session)
        payload = data.get('payload')
    else:
        payload = id
    if not payload:
        xbmcgui.Dialog().notification('Oneplay', 'Pořad nelze přehrát', xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    post = {"payload": payload, "playbackCapabilities": {"protocols": ["dash", "hls"], "drm": ["widevine", "fairplay"], "altTransfer": "Unicast", "subtitle": {"formats": ["vtt"], "locations": ["InstreamTrackLocation", "ExternalTrackLocation"]}, "liveSpecificCapabilities": {"protocols": ["dash", "hls"], "drm": ["widevine", "fairplay"], "altTransfer": "Unicast", "multipleAudio": False}}}
    url_hls, url_dash, url_dash_drm, drm, next_url_hls, next_url_dash, next_url_dash_drm, next_drm = get_stream_url(post, mode)

    stream = None
    if addon.getSetting('prefer_hls') == 'true' and url_hls:
        stream = ('hls', url_hls, None, next_url_hls, None)
    elif url_dash:
        stream = ('mpd', url_dash, None, next_url_dash, None)
    elif url_dash_drm:
        stream = ('mpd', url_dash_drm, drm, next_url_dash_drm, next_drm)
    elif url_hls:
        stream = ('hls', url_hls, None, next_url_hls, None)
    if not stream:
        xbmcgui.Dialog().notification('Oneplay', 'Pořad nelze přehrát', xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    stream_type, url, drm, next_url, next_drm = stream
    url, keepalive = get_manifest_redirect(url)
    get_list_item(stream_type, url, drm, next_url, next_drm)

    # zajišťuje posílání keepalive požadavků kvůli, aby nedošlo k přerušení streamu např. při pauze
    if keepalive: 
        xbmc.sleep(3000)
        monitor = xbmc.Monitor()
        while xbmc.Player().isPlaying() and not monitor.abortRequested():
            try:
                request = Request(url=keepalive)
                if addon.getSetting('log_request_url') == 'true':
                    xbmc.log(f'Oneplay > Keepalive: {keepalive}')
                with urlopen(request, timeout=10) as response:
                    if addon.getSetting('log_response') == 'true':
                        xbmc.log(f'Oneplay > Keepalive Status: {response.status}')
            except Exception as e:
                xbmc.log(f'Oneplay > Keepalive Error: {e}', xbmc.LOGERROR)
            for _ in range(20):
                if not xbmc.Player().isPlaying() or monitor.abortRequested():
                    break
                xbmc.sleep(1000)
