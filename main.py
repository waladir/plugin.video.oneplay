# -*- coding: utf-8 -*-
import os
import sys 
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from urllib.parse import parse_qsl

from resources.lib.utils import get_url, check_settings
from resources.lib.live import list_live
from resources.lib.epg import remove_db
from resources.lib.archive import list_archive, list_archive_days, list_program
from resources.lib.iptvsc import generate_playlist, generate_epg, iptv_sc_rec
from resources.lib.stream import play_stream, play_catchup
from resources.lib.channels import Channels, manage_channels, list_channels_list_backups, list_channels_edit, edit_channel, delete_channel, change_channels_numbers
from resources.lib.channels import list_channels_groups, add_channel_group, edit_channel_group, edit_channel_group_list_channels, edit_channel_group_add_channel, edit_channel_group_add_all_channels, edit_channel_group_delete_channel, select_channel_group, delete_channel_group
from resources.lib.recordings import list_recordings, delete_recording, list_planning_recordings, list_rec_days, future_program, add_recording
from resources.lib.categories import list_categories, page_category_display, page_content_display, carousel_display, content_play
from resources.lib.search import list_search, delete_search, program_search
from resources.lib.profiles import list_profiles, set_active_profile, reset_profiles
from resources.lib.profiles import list_accounts, set_active_account, reset_accounts
from resources.lib.favourites import list_favourites, list_favourites_new, add_favourite, remove_favourite, add_favourites_episodes_bl
from resources.lib.settings import list_settings
from resources.lib.session import Session

if len(sys.argv) > 1:
    _handle = int(sys.argv[1])

def main_menu():
    addon = xbmcaddon.Addon()
    icons_dir = os.path.join(addon.getAddonInfo('path'), 'resources','images')

    list_item = xbmcgui.ListItem(label='Živé vysílání')
    url = get_url(action='list_live', page = 1, label = 'Živé vysílání')  
    list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'livetv.png'), 'icon' : os.path.join(icons_dir , 'livetv.png') })
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

    list_item = xbmcgui.ListItem(label='Archiv')
    url = get_url(action='list_archive', label = 'Archiv')  
    list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'archive.png'), 'icon' : os.path.join(icons_dir , 'archive.png') })
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

    list_item = xbmcgui.ListItem(label='Kategorie')
    url = get_url(action='list_categories', label = 'Kategorie')  
    list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'categories.png'), 'icon' : os.path.join(icons_dir , 'categories.png') })
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)    

    list_item = xbmcgui.ListItem(label = 'Oblíbené')
    url = get_url(action='list_favourites', label = 'Oblíbené')  
    list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'favourites.png'), 'icon' : os.path.join(icons_dir , 'favourites.png') })
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

    list_item = xbmcgui.ListItem(label = 'Nejnovější epizody Oblíbených')
    url = get_url(action='list_favourites_new', label = 'Oblíbené')  
    list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'favourites.png'), 'icon' : os.path.join(icons_dir , 'favourites.png') })
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

    list_item = xbmcgui.ListItem(label='Nahrávky')
    url = get_url(action='list_recordings', label = 'Nahrávky')  
    list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'recordings.png'), 'icon' : os.path.join(icons_dir , 'recordings.png') })
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

    list_item = xbmcgui.ListItem(label='Vyhledávání')
    url = get_url(action='list_search', label = 'Vyhledávání')  
    list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'search.png'), 'icon' : os.path.join(icons_dir , 'search.png') })
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

    if addon.getSetting('hide_settings') != 'true':
        list_item = xbmcgui.ListItem(label='Nastavení Oneplay')
        url = get_url(action='list_settings', label = 'Nastavení Oneplay')  
        list_item.setArt({ 'thumb' : os.path.join(icons_dir , 'settings.png'), 'icon' : os.path.join(icons_dir , 'settings.png') })
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)

    xbmcplugin.endOfDirectory(_handle, cacheToDisc = False)

def router(paramstring):
    params = dict(parse_qsl(paramstring))
    check_settings() 
    if params:
        if params['action'] == 'list_live':
            list_live(params['label'])

        elif params['action'] == 'list_archive':
            list_archive(params['label'])
        elif params['action'] == 'list_archive_days':
            list_archive_days(params['id'], params['label'])
        elif params['action'] == 'list_program':
            list_program(params['id'], params['day_min'], params['label'])

        elif params['action'] == 'list_categories':
            list_categories(params['label'])
        elif params['action'] == 'page_category_display':
            if 'id' not in params:
                params['id'] = None
            if 'show_filter' not in params:
                params['show_filter'] = False
            page_category_display(params['label'], params['params'], params['id'], params['show_filter'])
        elif params['action'] == 'page_content_display':
            page_content_display(params['label'], params['params'])
        elif params['action'] == 'carousel_display':
            carousel_display(params['label'], params['params'])
        elif params['action'] == 'content_play':
            content_play(params['params'])            
        elif params['action'] == 'epg_display':
            list_live('Živé vysílání')
        elif params['action'] == 'list_tv_episodes':
            import json
            page_content_display(params['label'], params = json.dumps({'schema': 'PageContentDisplayApiAction', 'payload': {'contentId': params['id']}, 'contentType': 'show'}))

        elif params['action'] == 'list_recordings':
            list_recordings(params['label'])
        elif params['action'] == 'delete_recording':
            delete_recording(params['id'])
        elif params['action'] == 'list_planning_recordings':
            list_planning_recordings(params['label'])
        elif params['action'] == 'list_rec_days':
            list_rec_days(params['id'], params['label'])
        elif params['action'] == 'future_program':
            future_program(params['id'], params['day'], params['label'])
        elif params['action'] == 'add_recording':
            add_recording(params['id'])

        elif params['action'] == 'list_search':
            list_search(params['label'])
        elif params['action'] == 'program_search':
            program_search(params['query'], params['label'])
        elif params['action'] == 'delete_search':
            delete_search(params['query'])

        elif params['action'] == 'play_live':
            play_stream(params['id'], params['mode'])
        elif params['action'] == 'play_archive':
            play_stream(params['id'], 'archive')

        elif params['action'] == 'list_settings':
            list_settings(params['label'])
        elif params['action'] == 'addon_settings':
            xbmcaddon.Addon().openSettings()
        elif params['action'] == 'reset_session':
            session = Session()
            session.remove_session()
        elif params['action'] == 'list_profiles':
            list_profiles(params['label'])                      
        elif params['action'] == 'set_active_profile':
            set_active_profile(params['id'])                      
        elif params['action'] == 'reset_profiles':
            reset_profiles()    
        elif params['action'] == 'list_accounts':
            list_accounts(params['label'])                      
        elif params['action'] == 'set_active_account':
            set_active_account(params['name'])                      
        elif params['action'] == 'reset_accounts':
            reset_accounts()                         
            session = Session()
            session.remove_session()
            xbmc.executebuiltin('Container.Refresh')
        elif params['action'] == 'manage_channels':
            manage_channels(params['label'])
        elif params['action'] == 'reset_channels_list':
            channels = Channels()
            channels.reset_channels()   
        elif params['action'] == 'restore_channels':
            channels = Channels()
            channels.restore_channels(params['backup'])        
        elif params['action'] == 'list_channels_list_backups':
            list_channels_list_backups(params['label'])

        elif params['action'] == 'list_channels_edit':
            list_channels_edit(params['label'])
        elif params['action'] == 'edit_channel':
            edit_channel(params['id'])
        elif params['action'] == 'delete_channel':
            delete_channel(params['id'])
        elif params['action'] == 'change_channels_numbers':
            change_channels_numbers(params['from_number'], params['direction'])

        elif params['action'] == 'list_channels_groups':
            list_channels_groups(params['label'])
        elif params['action'] == 'add_channel_group':
            add_channel_group(params['label'])
        elif params['action'] == 'edit_channel_group':
            edit_channel_group(params['group'], params['label'])
        elif params['action'] == 'delete_channel_group':
            delete_channel_group(params['group'])
        elif params['action'] == 'select_channel_group':
            select_channel_group(params['group'])

        elif params['action'] == 'edit_channel_group_list_channels':
            edit_channel_group_list_channels(params['group'], params['label'])
        elif params['action'] == 'edit_channel_group_add_channel':
            edit_channel_group_add_channel(params['group'], params['channel'])
        elif params['action'] == 'edit_channel_group_add_all_channels':
            edit_channel_group_add_all_channels(params['group'])
        elif params['action'] == 'edit_channel_group_delete_channel':
            edit_channel_group_delete_channel(params['group'], params['channel'])

        elif params['action'] == 'list_favourites':
            list_favourites(params['label'])
        elif params['action'] == 'list_favourites_new':
            list_favourites_new(params['label'])
        elif params['action'] == 'add_favourite':
            add_favourite(params['type'], params['id'], params['image'], params['title'])
        elif params['action'] == 'remove_favourite':
            remove_favourite(params['type'], params['id'])
        elif params['action'] == 'add_favourites_episodes_bl':
            add_favourites_episodes_bl(params['id'])
            
        elif params['action'] == 'generate_playlist':
            if 'output_file' in params:
                generate_playlist(params['output_file'])
                xbmcplugin.addDirectoryItem(_handle, '1', xbmcgui.ListItem())
                xbmcplugin.endOfDirectory(_handle, succeeded = True)
            else:
                generate_playlist()
        elif params['action'] == 'generate_epg':
            if 'output_file' in params:
                generate_epg(params['output_file'], False)
                xbmcplugin.addDirectoryItem(_handle, '1', xbmcgui.ListItem())
                xbmcplugin.endOfDirectory(_handle, succeeded = True)
            else:
                generate_epg(show_progress = True)
        elif params['action'] == 'iptsc_play_stream':
            if 'catchup_start_ts' in params and 'catchup_end_ts' in params:
                play_catchup(id = params['id'], start_ts = params['catchup_start_ts'], end_ts = params['catchup_end_ts'])
            else:
                play_stream(params['id'], 'start')
        elif params['action'] == 'iptv_sc_rec':
            iptv_sc_rec(params['channel'], params['startdatetime'])

        elif params['action'] == 'remove_cache':
            remove_db()            
        else:
            raise ValueError('Neznámý parametr: {0}!'.format(paramstring))
    else:
        main_menu()

if __name__ == '__main__':
    router(sys.argv[2][1:])
