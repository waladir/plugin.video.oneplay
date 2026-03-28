# -*- coding: utf-8 -*-
import os
import sys
import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

from urllib.parse import quote

import glob
import json
import codecs
import time 
import shutil
from datetime import datetime

from resources.lib.settings import Settings
from resources.lib.api import API
from resources.lib.session import Session
from resources.lib.profiles import get_profile_id
from resources.lib.utils import get_url, plugin_id

if len(sys.argv) > 1:
    _handle = int(sys.argv[1])

def manage_channels(label):
    """Menu správy kanálů"""
    xbmcplugin.setPluginCategory(_handle, label)
    menu_items = [
        ('Ruční editace', 'list_channels_edit', True),
        ('Vlastní skupiny kanálů', 'list_channels_groups', True),
        ('Aktualizovat kanály', 'reset_channels_list', False),
        ('Obnovit seznam kanálů', 'list_channels_list_backups', True)
    ]
    for item_label, action, is_folder in menu_items:
        list_item = xbmcgui.ListItem(label=item_label)
        new_label = f"{label} / {item_label}" if is_folder else label
        url = get_url(action=action, label=new_label)
        xbmcplugin.addDirectoryItem(_handle, url, list_item, is_folder)
    xbmcplugin.endOfDirectory(_handle)

def list_channels_edit(label):
    """Editace kanálů"""
    xbmcplugin.setPluginCategory(_handle, label)
    channels = Channels()
    channels_list = channels.get_channels_list('channel_number', visible_filter=False)
    for number, channel in sorted(channels_list.items()):
        channel_id = channel['id']
        display_label = f"{number} {channel['name']}"
        if not channel.get('visible', True):
            display_label = f"[COLOR gray]{display_label}[/COLOR]"
        list_item = xbmcgui.ListItem(label=display_label)
        list_item.setArt({'thumb': channel['logo'], 'icon': channel['logo']})
        base_cmd = f"RunPlugin(plugin://{plugin_id}?action=change_channels_numbers&from_number={number}"
        list_item.addContextMenuItems([
            ('Zvýšit čísla odsud', f"{base_cmd}&direction=increase)"),
            ('Snížit čísla odsud', f"{base_cmd}&direction=decrease)"),
            ('Odstranit kanál', f"RunPlugin(plugin://{plugin_id}?action=delete_channel&id={channel_id})")
        ])
        url = get_url(action='edit_channel', id=channel_id)
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)

def edit_channel(channel_id):
    """Editace kanálu"""
    channels = Channels()
    channel = channels.channels.get(channel_id)
    if not channel:
        return
    new_num = xbmcgui.Dialog().numeric(0, 'Číslo kanálu', str(channel['channel_number']))
    if new_num and int(new_num) > 0:
        new_num = int(new_num)
        channels_nums = channels.get_channels_list('channel_number', visible_filter=False)
        if new_num in channels_nums:
            name = channels_nums[new_num]['name']
            xbmcgui.Dialog().notification('Oneplay', f'Číslo {new_num} už má {name}', xbmcgui.NOTIFICATION_ERROR, 3000)
        else:
            channels.set_number(channel_id, new_num)
            xbmc.executebuiltin('Container.Refresh')

def delete_channel(id):
    """Smaže kanál"""
    channels = Channels()
    channels.delete_channel(id)
    xbmc.executebuiltin('Container.Refresh')

def change_channels_numbers(from_number, direction):
    """Posun čísel kanálů"""
    channels = Channels()
    title = 'Zvětšit' if direction == 'increase' else 'Zmenšit'
    change = xbmcgui.Dialog().numeric(0, f'{title} čísla od {from_number} o:', '1')
    if change and int(change) > 0:
        change = int(change)
        if direction == 'decrease':
            change *= -1
        channels.change_channels_numbers(from_number, change)
        xbmc.executebuiltin('Container.Refresh')
    else:
        xbmcgui.Dialog().notification('Oneplay', 'Zadejte platné číslo!', xbmcgui.NOTIFICATION_ERROR, 3000)

def list_channels_list_backups(label):
    """Vypíše seznam záloh kanálů"""
    xbmcplugin.setPluginCategory(_handle, label)
    channels = Channels() 
    backups = channels.get_backups()
    if not backups:
        xbmcgui.Dialog().notification('Oneplay', 'Neexistuje žádná záloha', xbmcgui.NOTIFICATION_INFO, 3000)
        return
    for path in sorted(backups, reverse=True): # Nejnovější nahoře
        filename = os.path.basename(path)
        parts = filename.replace('channels_backup_', '').replace('.txt', '').split('-')
        if len(parts) == 6:
            Y, M, D, h, m, s = parts
            display_date = f"Záloha z {D}.{M}.{Y} v {h}:{m}:{s}"
            list_item = xbmcgui.ListItem(label=display_date)
            url = get_url(action='restore_channels', backup=path)
            xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)

def list_channels_groups(label):
    """Menu seznamu kanálů"""
    xbmcplugin.setPluginCategory(_handle, label)    
    channels_groups = Channels_groups()
    xbmcplugin.addDirectoryItem(_handle, get_url(action='add_channel_group'), xbmcgui.ListItem(label='Nová skupina'), False)
    if channels_groups.selected == None:
        list_item = xbmcgui.ListItem(label='[B]Všechny kanály[/B]')
    else:  
        list_item = xbmcgui.ListItem(label='Všechny kanály')
    url = get_url(action='list_channels_groups', label = 'Seznam kanálů / Skupiny kanálů')  
    list_item.addContextMenuItems([('Vybrat skupinu', 'RunPlugin(plugin://' + plugin_id + '?action=select_channel_group&group=all)' ,)])       
    xbmcplugin.addDirectoryItem(_handle, url, list_item, True)    
    for group in channels_groups.groups:
        is_selected = channels_groups.selected == group
        display_label = f"[B]{group}[/B]" if is_selected else group
        list_item = xbmcgui.ListItem(label=display_label)
        list_item.addContextMenuItems([
            ('Vybrat skupinu', f'RunPlugin(plugin://{plugin_id}?action=select_channel_group&group={quote(group)})'),
            ('Smazat skupinu', f'RunPlugin(plugin://{plugin_id}?action=delete_channel_group&group={quote(group)})')
        ])
        url = get_url(action='edit_channel_group', group=group, label=f"Skupiny kanálů/ {group}")
        xbmcplugin.addDirectoryItem(_handle, url, list_item, True)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)

def add_channel_group():
    """Vytvoření nového seznamu kanálů"""
    input = xbmc.Keyboard('', 'Název skupiny')
    input.doModal()
    if not input.isConfirmed(): 
        return
    group = input.getText().strip()
    if len(group) == 0:
        xbmcgui.Dialog().notification('Oneplay', 'Je nutné zadat název skupiny', xbmcgui.NOTIFICATION_ERROR, 5000)
        sys.exit()          
    channels_groups = Channels_groups()
    if group in channels_groups.groups:
        xbmcgui.Dialog().notification('Oneplay', 'Název skupiny je už použitý', xbmcgui.NOTIFICATION_ERROR, 5000)
        sys.exit()          
    channels_groups.add_channels_group(group)    
    xbmc.executebuiltin('Container.Refresh')

def edit_channel_group(group, label):
    """Úprava seznamu kanálů"""
    xbmcplugin.setPluginCategory(_handle, label)    
    channels_groups = Channels_groups()
    channels_list = Channels().get_channels_list('name', visible_filter=False)
    menu_items = [
        (' Přidat kanál', 'edit_channel_group_list_channels'),
        (' Přidat všechny kanály', 'edit_channel_group_add_all_channels')
    ]
    for text, act in menu_items:
        url = get_url(action=act, group=group, label=f"{group} / {text.strip()}")
        xbmcplugin.addDirectoryItem(_handle, url, xbmcgui.ListItem(label=text), True)
    group_channels = channels_groups.channels.get(group, [])
    for channel_name in group_channels:
        if channel_name in channels_list:
            channel = channels_list[channel_name]
            list_item = xbmcgui.ListItem(label=channel_name)
            list_item.setArt({'thumb': channel['logo'], 'icon': channel['logo']})
            list_item.addContextMenuItems([('Odstranit ze skupiny', f'RunPlugin(plugin://{plugin_id}?action=edit_channel_group_delete_channel&group={quote(group)}&channel={quote(channel_name)})')])
            xbmcplugin.addDirectoryItem(_handle, label, list_item, False)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)

def delete_channel_group(group):
    """Smazání seznamu kanálů"""
    response = xbmcgui.Dialog().yesno('Smazání skupiny kanálů', 'Opravdu smazat skupinu kanálů ' + group + '?', nolabel = 'Ne', yeslabel = 'Ano')
    if response:
        channels_groups = Channels_groups()
        channels_groups.delete_channels_group(group)
        xbmc.executebuiltin('Container.Refresh')

def select_channel_group(group):
    """Výběr seznamu kanálů"""
    channels_groups = Channels_groups()
    channels_groups.select_group(group)
    xbmc.executebuiltin('Container.Refresh')
    if group != 'all' and not channels_groups.channels.get(group):
        xbmcgui.Dialog().notification('Oneplay', 'Skupina je prázdná', xbmcgui.NOTIFICATION_WARNING, 3000)

def edit_channel_group_list_channels(group, label):
    """Seznam kanálů pro editaci seznamu kanálů"""
    xbmcplugin.setPluginCategory(_handle, label)  
    channels_groups = Channels_groups()
    channels_list = Channels().get_channels_list('channel_number', visible_filter=False)
    channels_in_group = set(channels_groups.channels.get(group, []))
    for number, channel in sorted(channels_list.items()):
        if channel['name'] not in channels_in_group:
            list_item = xbmcgui.ListItem(label=f"{number} {channel['name']}")
            list_item.setArt({'thumb': channel['logo'], 'icon': channel['logo']})
            url = get_url(action='edit_channel_group_add_channel', group=group, channel=channel['name'])
            xbmcplugin.addDirectoryItem(_handle, url, list_item, False)
    xbmcplugin.endOfDirectory(_handle, cacheToDisc=False)

def edit_channel_group_add_channel(group, channel):
    """Přidání kanálu do seznamu kanálů"""
    channels_groups = Channels_groups()
    channels_groups.add_channel_to_group(channel, group)
    xbmc.executebuiltin('Container.Refresh')

def edit_channel_group_add_all_channels(group):
    """Přidání všech kanálu do seznamu kanálů"""
    channels_groups = Channels_groups()
    channels_groups.add_all_channels_to_group(group)
    xbmc.executebuiltin('Container.Refresh')

def edit_channel_group_delete_channel(group, channel):
    """Odstranění kanálu ze seznamu kanálů"""
    channels_groups = Channels_groups()
    channels_groups.delete_channel_from_group(channel, group)
    xbmc.executebuiltin('Container.Refresh')

class Channels:
    CHANNELS_FILE = {'filename' : 'channels.txt', 'description' : 'kanálů'}

    def __init__(self):
        self.channels = {}    
        self.valid_to = -1
        self.favorites = 0
        self.load_channels()

    def set_visibility(self, id, visibility):
        """Nastaví u kanálů jeho viditelnost"""
        if id in self.channels:
            self.channels[id]['visible'] = visibility
            self.save_channels()

    def set_number(self, id, number):
        """Nastaví číslo kanálu"""
        if id in self.channels:
            self.channels[id]['channel_number'] = int(number)
            self.save_channels()

    def delete_channel(self, id):
        """Odstranění kanálu"""
        if self.channels.pop(id, None):
            self.save_channels()

    def change_channels_numbers(self, from_number, change):
        """Hromadně posune číslování kanálů od určitého čísla"""
        from_number, change = int(from_number), int(change)
        for channel in self.channels.values():
            if channel['channel_number'] >= from_number:
                channel['channel_number'] += change
        self.save_channels()  

    def get_channels_list(self, bykey = None, visible_filter = True):
        """Vrátí kanály s volitelným klíčem a možností omezení na viditelné kanály"""
        if visible_filter:
            filtered = {channel_id: channel for channel_id, channel in self.channels.items() if channel.get('visible', True)}
        else:
            filtered = self.channels
        if bykey is None:
            return filtered
        return {channel[bykey]: channel for channel in filtered.values()}

    def get_channels(self):
        """Načte kanály z Oneplay"""
        addon = xbmcaddon.Addon()
        if addon.getSetting('use_picons_server') == 'true':
            use_picons_server = True
            picons_server_ip = addon.getSetting('picons_server_ip')
            picons_server_port = addon.getSetting('picons_server_port')
        else:
            use_picons_server = False
        channels = {}
        api = API()
        session = Session()
        data = api.epg_channels_display(profileId=get_profile_id(session), session=session)
        for channel in data.get('channelList', []):
            if (channel.get('upsell', False) is False) and ('upsell' not in channel.get('flags', {})):
                logo_url = channel.get('logo', '')
                image = None
                imagesq = None
                if len(channel['logo']) > 1:
                    if image is None:  
                        image = logo_url.replace('{WIDTH}', '480').replace('{HEIGHT}', '320')
                    if imagesq is None:  
                        imagesq = logo_url.replace('{WIDTH}', '256').replace('{HEIGHT}', '256')
                if use_picons_server is True:
                    image = f"http://{picons_server_ip}:{picons_server_port}/picons/{quote(channel['name'])}"
                flags = channel.get('flags', {})
                channels[channel['id']] = {'channel_number': int(channel['order']), 'oneplay_number': int(channel['order']), 'name': channel['name'], 'id': channel['id'], 'logo': image, 'logosq': imagesq, 'adult': 'adult' in flags, 'liveOnly': 'liveOnly' in flags, 'visible': True}
        favorites = 1 if data.get('userFavorites', {}).get('channels') else 0
        return channels, favorites

    def load_channels(self):
        """Načte data kanálů, ošetření expirace"""
        settings = Settings()
        data = settings.load_json_data(file_info=self.CHANNELS_FILE)
        try:
            data = json.loads(data) if data else {}
        except (json.JSONDecodeError, TypeError):
            data = {}        
        loaded_channels = data.get('channels', {})
        self.valid_to = int(data.get('valid_to', -1))
        self.favorites = data.get('favorites', 0)
        if loaded_channels:
            for channel_id, channel in loaded_channels.items():
                if 'adult' not in channel:
                    channel['adult'] = False
            self.channels.update(loaded_channels)
        else:
            self.channels = {}        

        if not self.channels or self.valid_to < int(time.time()):
            self.valid_to = -1
            self.merge_channels()
            self.save_channels()

    def save_channels(self):
        """Uloží data kanálů"""
        settings = Settings()
        filename = settings._get_path(self.CHANNELS_FILE['filename'])
        if os.path.exists(filename):
            self.backup_channels()            
        self.valid_to = int(time.time()) + 60*60*24 # jeden den
        data = json.dumps({'channels' : self.channels, 'favorites' : self.favorites, 'valid_to' : self.valid_to})
        settings.save_json_data(file_info=self.CHANNELS_FILE, data=data)

    def _full_reset(self):
        """Privátní metoda pro provedení fyzického resetu souborů a paměti."""
        settings = Settings()
        self.backup_channels()
        settings.reset_json_data(self.CHANNELS_FILE)
        self.channels = {}
        self.valid_to = -1
        self.load_channels()
        xbmcgui.Dialog().notification('Oneplay', 'Seznam kanálů byl resetován', xbmcgui.NOTIFICATION_INFO, 3000)

    def reset_channels(self):
        """Interaktivní reset s výběrem typu aktualizace."""
        addon = xbmcaddon.Addon()
        is_full_reset = xbmcgui.Dialog().yesno('Aktualizace kanálů', 'Provést kompletní reset nebo jen aktualizovat stávající seznam kanálů?', 'Aktualizovat', 'Kompletní reset')
        if is_full_reset:
            self._full_reset()
        else:
            self.valid_to = -1
            self.merge_channels()
            self.save_channels()
            xbmcgui.Dialog().notification('Oneplay', 'Seznam kanálů byl aktualizován', xbmcgui.NOTIFICATION_INFO, 5000)
        output_dir = addon.getSetting('output_dir')
        if output_dir:
            from resources.lib.iptvsc import generate_playlist
            generate_playlist()

    def reset_channels_full(self):
        """Kompletní reset kanálů"""
        self._full_reset()

    def get_backups(self):
        """Vrátí seřazený seznam cest k zálohám kanálů"""
        settings = Settings()
        pattern = os.path.join(settings.addon_userdata_dir, 'channels_backup_*.txt')
        return sorted(glob.glob(pattern))

    def backup_channels(self):
        """Vytvoří zálohu channels.txt a smaže nejstarší, pokud jich je více než 10"""
        max_backups = 10
        settings = Settings()
        channels = settings._get_path('channels.txt')
        if not os.path.exists(channels):
            return
        backups = self.get_backups()
        if len(backups) >= max_backups:
            for old_backup in backups[:len(backups) - max_backups + 1]:
                try:
                    os.remove(old_backup)
                except OSError:
                    pass
        suffix = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        backup = settings._get_path(f'channels_backup_{suffix}.txt')
        shutil.copyfile(channels, backup)

    def restore_channels(self, backup):
        """Obnoví kanály ze zálohy a prodlouží jejich platnost."""
        if not os.path.exists(backup):
            xbmcgui.Dialog().notification('Oneplay', 'Záloha nenalezena', xbmcgui.NOTIFICATION_ERROR, 3000)
            return

        try:
            with open(backup, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'channels' in data:
                data['valid_to'] = int(time.time() + 86400)
                settings = Settings()
                settings.save_json_data(self.CHANNELS_FILE, json.dumps(data))
                xbmcgui.Dialog().notification('Oneplay', 'Seznam kanálů byl obnoven', xbmcgui.NOTIFICATION_INFO, 3000)
            else:
                raise ValueError("Neplatný formát zálohy")

        except (json.JSONDecodeError, ValueError, IOError) as e:
            xbmc.log(f"Oneplay > Chyba při obnově: {str(e)}")
            xbmcgui.Dialog().notification('Oneplay', 'Chyba při načtení zálohy', xbmcgui.NOTIFICATION_ERROR, 3000)

    def merge_channels(self):
        """Merguje data z API s lokálně uloženými"""
        oneplay_channels, self.favorites = self.get_channels()
        max_number = 0
        if self.channels:
            max_number = max(channel['channel_number'] for channel in self.channels.values())

        for channel_id, channel in oneplay_channels.items():
            if channel_id in self.channels:
                self.channels[channel_id].update({'name': channel['name'], 'oneplay_number': channel['oneplay_number'], 'logo': channel['logo'], 'logosq': channel['logosq'], 'adult': channel['adult'], 'liveOnly': channel['liveOnly']})
            else:
                max_number += 1
                channel['channel_number'] = max_number
                self.channels[channel_id] = channel            
        active_ids = set(oneplay_channels.keys())
        self.channels = {channel_id: data for channel_id, data in self.channels.items() if channel_id in active_ids}

class Channels_groups:
    CHANNELS_GROUPS_FILE = {'filename': 'channels_groups.txt', 'description': 'skupiny kanálů'}
    def __init__(self):
        self.groups = []
        self.channels = {}
        self.selected = None
        self.load_channels_groups()

    def add_channel_to_group(self, channel_name, group):
        """Přidá kanál do seznamu skupiny (pokud tam ještě není)"""
        if group not in self.channels:
            self.channels[group] = []
        if channel_name not in self.channels[group]:
            self.channels[group].append(channel_name)
            self.save_channels_groups()
            if group == self.selected:
                self.select_group(group)

    def add_all_channels_to_group(self, group):
        """Naplní skupinu všemi aktuálními kanály"""
        ch_obj = Channels()
        self.channels[group] = [channel['name'] for channel in ch_obj.channels.values()]
        self.save_channels_groups()
        if group == self.selected:
            self.select_group(group)

    def delete_channel_from_group(self, channel, group):
        """Smaže kanál ze skupiny"""
        if group in self.channels and channel in self.channels[group]:
            self.channels[group].remove(channel)
            self.save_channels_groups()
            if group == self.selected:
                self.select_group(group)

    def add_channels_group(self, group):
        """Vytvoří novou skupinu kanálů"""
        if group not in self.groups:
            self.groups.append(group)
            self.save_channels_groups()

    def delete_channels_group(self, group):
        """Smaže skupinu kanálů"""
        if group in self.groups:
            self.groups.remove(group)
            self.channels.pop(group, None)
            if self.selected == group:
                self.selected = None
                self.select_group('all')
            else:
                self.save_channels_groups()

    def select_group(self, group):
        """Nastaví viditelnost kanálů na základě vybrané skupiny"""
        ch_obj = Channels()
        self.selected = None if group == 'all' else group
        visible = set(self.channels.get(group, [])) if self.selected else None
        for channel in ch_obj.channels.values():
            channel['visible'] = True if visible is None else (channel['name'] in visible)
        ch_obj.save_channels()
        self.save_channels_groups()

    def load_channels_groups(self):
        """Načte uložená data skupin kanálů"""
        settings = Settings()
        filename = settings._get_path(self.CHANNELS_GROUPS_FILE['filename'])
        if not os.path.exists(filename):
            return
        try:
            with codecs.open(filename, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if ';' in line:
                        group_name, channel_name = line.split(';', 1)
                        if group_name not in self.channels:
                            self.channels[group_name] = []
                        self.channels[group_name].append(channel_name)
                    else:
                        if line.startswith('*'):
                            name = line[1:]
                            self.selected = name
                            self.groups.append(name)
                        else:
                            self.groups.append(line)
        except IOError:
            pass

    def save_channels_groups(self):
        """Uloží data v původním formátu."""
        settings = Settings()
        filename = settings._get_path(self.CHANNELS_GROUPS_FILE['filename'])
        if not self.groups:
            if os.path.exists(filename):
                os.remove(filename)
            return
        try:
            with codecs.open(filename, 'w', encoding='utf-8') as f:
                for group in self.groups:
                    prefix = '*' if group == self.selected else ''
                    f.write(f"{prefix}{group}\n")
                for group in self.groups:
                    for channel_name in self.channels.get(group, []):
                        f.write(f"{group};{channel_name}\n")
        except IOError:
            xbmcgui.Dialog().notification('Oneplay', 'Chyba uložení skupiny', xbmcgui.NOTIFICATION_ERROR, 3000)
