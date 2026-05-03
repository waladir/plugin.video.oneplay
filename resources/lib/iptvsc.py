# -*- coding: utf-8 -*-
import os

import xbmcgui
import xbmcaddon
import xbmcvfs

from datetime import datetime, timezone, timedelta
import time

from resources.lib.channels import Channels
from resources.lib.utils import plugin_id, replace_by_html_entity
from resources.lib.epg import get_epg
from resources.lib.recordings import add_recording

def save_file_test():
    """Otestuje uložení souboru do output_dir"""
    addon = xbmcaddon.Addon()
    output_dir = addon.getSetting('output_dir')
    if not output_dir:
        return 0
    test_file = os.path.join(output_dir, 'test.fil')
    try:
        file = xbmcvfs.File(test_file, 'w')
        try:
            file.write('test') # xbmcvfs v K19+ bere string přímo
        finally:
            file.close()
        file = xbmcvfs.File(test_file, 'r')
        try:
            content = file.read()
            success = (content == 'test')
        finally:
            file.close()
        xbmcvfs.delete(test_file)
        return 1 if success else 0
    except Exception:
        if xbmcvfs.exists(test_file):
            xbmcvfs.delete(test_file)
        return 0

def generate_playlist(output_file=''):
    """Generování playlistu"""
    addon = xbmcaddon.Addon()
    output_dir = addon.getSetting('output_dir')
    if not output_dir:
        xbmcgui.Dialog().notification('Oneplay', 'Nastav adresář pro playlist a EPG!', xbmcgui.NOTIFICATION_ERROR, 3000)
        return
    if save_file_test() == 0:
        xbmcgui.Dialog().notification('Oneplay', 'Chyba při uložení playlistu (test zápisu selhal)', xbmcgui.NOTIFICATION_ERROR, 3000)
        return
    if not output_file:
        ext = 'm3u' if addon.getSetting('playlist_filename') == 'playlist.m3u' else 'txt'
        output_file = os.path.join(output_dir, f'playlist.{ext}')
    channels = Channels()
    channels_list = channels.get_channels_list('channel_number')
    catchup_mode = addon.getSetting('catchup_mode')
    playlist_lines = ['#EXTM3U']
    for number in sorted(channels_list.keys()):
        ch = channels_list[number]
        name = ch['name']
        logo = ch.get('logo') or ''
        ch_id = ch['id']
        catchup_str = ""
        if not ch.get('liveOnly'):
            if catchup_mode == 'default':
                catchup_str = (f'catchup="default" catchup-days="7" '
                               f'catchup-source="plugin://{plugin_id}/?action=iptsc_play_stream&id={ch_id}'
                               '&catchup_start_ts={utc}&catchup_end_ts={utcend}" ')
            else:
                catchup_str = 'catchup="append" catchup-days="7" catchup-source="&catchup_start_ts={utc}&catchup_end_ts={utcend}" '
        playlist_lines.append(f'#EXTINF:-1 {catchup_str}tvg-chno="{number}" tvg-id="{name}" tvh-epg="0" tvg-logo="{logo}",{name}')
        if not ch.get('liveOnly'):
            playlist_lines.append('#KODIPROP:inputstream=inputstream.ffmpegdirect')
            playlist_lines.append('#KODIPROP:inputstream.ffmpegdirect.stream_mode=timeshift')
            playlist_lines.append('#KODIPROP:inputstream.ffmpegdirect.is_realtime_stream=true')
        
        playlist_lines.append('#KODIPROP:mimetype=video/mp2t')
        playlist_lines.append(f'plugin://{plugin_id}/?action=iptsc_play_stream&id={ch_id}')
    try:
        f = xbmcvfs.File(output_file, 'w')
        content = '\n'.join(playlist_lines) + '\n'
        if f.write(content):
            f.close()
            xbmcgui.Dialog().notification('Oneplay', 'Playlist byl uložený', xbmcgui.NOTIFICATION_INFO, 3000)
        else:
            raise IOError("Zápis do souboru selhal")
    except Exception:
        xbmcgui.Dialog().notification('Oneplay', 'Chyba při uložení playlistu', xbmcgui.NOTIFICATION_ERROR, 3000)

def generate_epg(output_file='', show_progress=True):
    """Generování EPG"""
    tz_offset = int(datetime.now(timezone.utc).astimezone().utcoffset().total_seconds() / 3600)    
    addon = xbmcaddon.Addon()
    channels = Channels()
    channels_list = channels.get_channels_list('channel_number')
    channels_list_by_id = channels.get_channels_list('id')
    if not channels_list:
        xbmcgui.Dialog().notification('Oneplay', 'Nevrácena žádná data!', xbmcgui.NOTIFICATION_ERROR, 3000)
        return
    if save_file_test() == 0:
        xbmcgui.Dialog().notification('Oneplay', 'Chyba při uložení EPG (test zápisu selhal)', xbmcgui.NOTIFICATION_ERROR, 3000)
        return
    if not output_file:
        output_dir = addon.getSetting('output_dir')
        output_file = os.path.join(output_dir, 'oneplay_epg.xml')
    dialog = None
    f = None
    def safe_write(handle, text):
        try:
            handle.write(text.encode('utf-8'))
        except (TypeError, AttributeError):
            handle.write(text)
    try:
        f = xbmcvfs.File(output_file, 'w')
        safe_write(f, '<?xml version="1.0" encoding="UTF-8"?>\n')
        safe_write(f, '<tv generator-info-name="EPG grabber">\n')
        for number in sorted(channels_list.keys()):
            ch = channels_list[number]
            name = replace_by_html_entity(ch['name'])
            logo = ch.get('logo') or ''
            safe_write(f, f'  <channel id="{name}">\n')
            safe_write(f, f'    <display-name lang="cs">{name}</display-name>\n')
            safe_write(f, f'    <icon src="{logo}" />\n')
            safe_write(f, f'  </channel>\n')
        now = datetime.now()
        today_start_dt = datetime(now.year, now.month, now.day)
        epg_from = int(addon.getSetting('epg_from') or 1)
        epg_to = int(addon.getSetting('epg_to') or 7)
        days_range = range(-epg_from, epg_to)
        total_days = len(days_range)
        if show_progress:
            dialog = xbmcgui.DialogProgressBG()
            dialog.create('Stahování EPG dat', 'Probíhá generování XML...')
        formatted_tz = f"+{str(tz_offset).zfill(2)}00"
        for idx, day_offset in enumerate(days_range):
            current_day_dt = today_start_dt + timedelta(days=day_offset)
            date_str = current_day_dt.strftime('%d.%m.%Y')
            if show_progress and dialog:
                percent = int((idx / max(1, total_days)) * 100)
                dialog.update(percent, message=f"Zpracovávám den: {date_str}")
            day_ts = int(time.mktime(current_day_dt.timetuple()))
            epg_data = get_epg(ts=day_ts, filter_channel_id=None, reset_cache=True)
            for channel_id in epg_data:
                day_buffer = []
                for ts in sorted(epg_data[channel_id].keys()):
                    item = epg_data[channel_id][ts]
                    ch_info = channels_list_by_id.get(item['channel_id'])
                    if ch_info:
                        ch_name = replace_by_html_entity(ch_info['name'])
                        start = datetime.fromtimestamp(item['startts']).strftime('%Y%m%d%H%M%S')
                        stop = datetime.fromtimestamp(item['endts']).strftime('%Y%m%d%H%M%S')
                        title = replace_by_html_entity(item['title'])
                        desc = replace_by_html_entity(item.get('description', ''))
                        icon = item.get('poster') or ''
                        day_buffer.append(f'  <programme start="{start} {formatted_tz}" stop="{stop} {formatted_tz}" channel="{ch_name}">\n')
                        day_buffer.append(f'    <title lang="cs">{title}</title>\n')
                        if desc:
                            day_buffer.append(f'    <desc lang="cs">{desc}</desc>\n')
                        if icon:
                            day_buffer.append(f'    <icon src="{icon}"/>\n')
                        day_buffer.append('  </programme>\n')
                        if len(day_buffer) > 250:
                            safe_write(f, "".join(day_buffer))
                            day_buffer = []
                if day_buffer:
                    safe_write(f, "".join(day_buffer))
        safe_write(f, '</tv>\n')
        f.close()
        if show_progress:
            dialog.close()
            xbmcgui.Dialog().notification('Oneplay', 'EPG bylo uložené', xbmcgui.NOTIFICATION_INFO, 3000)
        elif addon.getSetting('epg_info') == 'true':
            xbmcgui.Dialog().notification('Oneplay', 'EPG bylo uložené', xbmcgui.NOTIFICATION_INFO, 3000)
    except Exception:
        if f: f.close()
        if dialog: dialog.close()
        xbmcgui.Dialog().notification('Oneplay', 'Chyba při generování EPG!', xbmcgui.NOTIFICATION_ERROR, 3000)

def iptv_sc_rec(channelName, startdatetime):
    """Zpracování nahrávek z IPTV SC"""
    channels = Channels()
    channels_list = channels.get_channels_list('name', visible_filter = False)
    from_ts = int(time.mktime(time.strptime(startdatetime, '%d.%m.%Y %H:%M')))
    epg = get_epg(from_ts, channels_list[channelName]['id'])
    if len(epg) > 0 and str(from_ts) in epg:
        payload = epg[str(from_ts)]['payload']
        contentId = payload.get('contentId', '')
        add_recording(contentId)
    else:
        xbmcgui.Dialog().notification('Oneplay', 'Pořad v Oneplay nenalezen! Používáte EPG z doplňku Oneplay?', xbmcgui.NOTIFICATION_ERROR, 5000)
