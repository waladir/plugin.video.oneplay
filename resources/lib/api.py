# -*- coding: utf-8 -*-
import sys

import xbmc
import xbmcaddon
import xbmcgui

import json
import gzip 
import socket
import re

from websocket import create_connection
import uuid

from urllib.request import urlopen, Request
from urllib.error import HTTPError

class API:
    def __init__(self):
        self.APIURL = 'https://http.cms.jyxo.cz/api/'
        self.UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0'
        self.HEADERS = {'User-Agent' : self.UA, 'Accept-Encoding' : 'gzip', 'Accept' : '*/*', 'Content-type' : 'application/json;charset=UTF-8'} 
        self.APPVERSION = 'R9.18'
        self.APIVERSION = 'v1.9'

    def call_api(self, api, data, session=None, sensitive=False):
        """Volání API Oneplay včetně ošetření logování"""
        addon = xbmcaddon.Addon()
        url = f"{self.APIURL}{self.APIVERSION}/{api}"
        if session is not None and session.token:
            self.HEADERS['Authorization'] = f"Bearer {session.token}"
        if addon.getSetting('log_request_url') == 'true':
            xbmc.log(f"Oneplay > {url}")
        if addon.getSetting('log_request_url') == 'true' and data != None and sensitive == False:
            xbmc.log(f"Oneplay > {data}")
        try:
            ws = None
            requestId = str(uuid.uuid4())
            clientId = str(uuid.uuid4())
            ws = create_connection(f"wss://ws.cms.jyxo.cz/websocket/{clientId}", timeout = 10)
            ws_init = json.loads(ws.recv())
            serverId = ws_init['data']['serverId']
            post = {"deviceInfo": {"deviceType": "web", "appVersion": self.APPVERSION, "deviceManufacturer": "Unknown", "deviceOs": "Linux"}, "capabilities": {"async": "websockets"}, "context": {"requestId": requestId, "clientId": clientId, "sessionId": serverId, "serverId": serverId}}
            if data:
                post.update(data)
            post = json.dumps(post).encode("utf-8")
            request = Request(url=url , data=post, headers=self.HEADERS)
            with urlopen(request, timeout = 20) as response:
                if response.getheader("Content-Encoding") == 'gzip':
                    data = gzip.decompress(response.read())
                else:
                    data = response.read()
            data = json.loads(data) if data else {}
            status = data.get('result', {}).get('status')
            if status not in ['OkAsync', 'Ok']:
                xbmc.log(f"Oneplay > Chyba při volání {url}")
                return {'result' : {'status' : 'Error', 'message' : 'Chyba při volání API'}}
            final_data = {}
            if status == 'OkAsync': # asychronní odpověď z websocketu
                ws_resp = ws.recv()
                if ws_resp:
                    ws_data = json.loads(ws_resp)
                    if ws_data.get('response', {}).get('context', {}).get('requestId') != requestId: # ověření requestId, pokud nesouhlasí, přečte se další zpráva
                        ws_resp = ws.recv()
                        ws_data = json.loads(ws_resp)
                    final_data = ws_data.get('response')
            elif status == 'Ok': # synchronni volani
                final_data = data
            if addon.getSetting('log_response') == 'true':
                if len(str(final_data)) > 5000 and addon.getSetting('skip_long') == 'true':
                    xbmc.log(f"Oneplay > odpověď obdržena ({len(str(final_data))})")
                else:
                    xbmc.log(f"Oneplay > {final_data}")
            if final_data.get('result', {}).get('status', {}) != 'Ok' or final_data.get('context', {}).get('requestId', {}) != requestId:
                xbmc.log(f"Oneplay > Chyba při volání {url}")
                return {'result': {'status': 'Error', 'message': final_data.get('result', {}).get('message', 'Chyba při volání API')}}  
            return {'result': {'status': 'Ok', 'data': final_data.get('data', {})}}
        except (HTTPError, socket.timeout, socket.error) as e:
            xbmc.log(f"Oneplay > Network Error: {str(e)}")
            return {'result': {'status': 'Error', 'message': 'Síťová chyba nebo timeout'}}
        except Exception as e:
            xbmc.log(f"Oneplay > Neočekávaná chyba: {str(e)}")
            return {'result': {'status': 'Error', 'message': 'Interní chyba doplňku'}}
        finally:
            if ws:
                ws.close()        
    
    def error_handling(self, message):
        """Ošetření chyb z volání API"""
        xbmcgui.Dialog().notification('Oneplay', message, xbmcgui.NOTIFICATION_ERROR, 3000)
        sys.exit()

    def _check_response(self, response, error_msg, fatal = True):
        """Kontrola chyb"""
        if response.get('result', {}).get('status') != 'Ok':
            error_detail = response.get('result', {}).get('message', 'Neznámá chyba')
            if fatal:
                xbmcgui.Dialog().notification('Oneplay', error_msg, xbmcgui.NOTIFICATION_ERROR, 2000)
                self.error_handling(error_detail)
        return response.get('result', {}).get('data')

    def user_login_step(self, username, password):
        """Přihlášení s podporou výběru účtu (ShowAccountChooserStep)"""
        post = {"payload": {"command": {"schema": "LoginWithCredentialsCommand", "email": username, "password": password}}}
        data = self._check_response(self.call_api('user.login.step', data=post, sensitive=True), 'Problém při přihlášení')
        if data.get('step', {}).get('schema') == 'ShowAccountChooserStep': # pokud je vyžadovaný výběr účtu
            from resources.lib.profiles import get_account_id
            auth_token = data['step']['authToken']
            accounts_map = {}
            accounts_list = []
            for acc in data['step'].get('accounts', []):
                if acc.get('extId') or acc.get('isActive'):
                    suffix = acc.get('extId') or acc.get('accountProvider', 'Unknown')
                    display_name = f"{acc['name']}|{suffix}"
                    accounts_map[display_name] = acc['accountId']
                    accounts_list.append(display_name)
            selected_name = get_account_id(accounts_list)
            account_id = accounts_map.get(selected_name)
            if not account_id:
                 account_id = next((id for name, id in accounts_map.items() if name.startswith(selected_name)), None)
            post_account = {"payload": {"command": {"schema": "LoginWithAccountCommand", "accountId": account_id, "authCode": auth_token}}}
            return self._check_response(self.call_api('user.login.step', data=post_account), 'Problém při výběru účtu')
        return data        

    def user_device_change(self, id, name, session):
        """Přejmenování zařízení"""
        post = {"payload": {"id": id, "name": name}}
        return self.call_api('user.device.change', data=post, session=session)        

    def user_device_remove(self, id, session):
        """Odstranění zařízení"""
        post = {"payload": {"criteria": {"schema": "UserDeviceIdCriteria", "id": id}}}
        return self.call_api('user.device.remove', data=post, session=session)

    def setting_display(self, screen, session):
        """Načtení nastavení z Oneplay"""
        post = {"payload": {"screen": screen}}
        return self._check_response(self.call_api('setting.display', data=post, session=session), 'Problém při načtení nastavení')

    def user_profiles_display(self, session):
        """Načtení  profilů"""
        return self._check_response(self.call_api('user.profiles.display', data=None, session=session), 'Chyba při načtení profilů')
        
    def user_profile_select(self, profileId, profile_pin, session, is_retry=False):
        """Výběr profilu"""
        if not profileId:
            return None        
        post = {"payload": {"profileId": profileId}}
        if profile_pin:
            post["authorization"] = [{"schema": "PinRequestAuthorization", "pin": str(profile_pin), "type": "profile"}]
        response = self.call_api('user.profile.select', data=post, session=session)
        result = response.get('result', {})
        if result.get('status') == 'Ok':
            return result.get('data')
        if result.get('message') == 'Profil nenalezen' and not is_retry:
            from resources.lib.profiles import get_profile_id, reset_profiles
            reset_profiles()
            new_profile_id = get_profile_id(session)
            return self.user_profile_select(new_profile_id, profile_pin, session, is_retry=True)
        error_detail = response.get('result', {}).get('message', 'Neznámá chyba')
        xbmcgui.Dialog().notification('Oneplay', 'Chyba při výběru profilu', xbmcgui.NOTIFICATION_ERROR, 2000)
        self.error_handling(error_detail)

    def epg_channels_display(self, profileId, session):
        """Načtení seznamu kanálů pro daný profil"""
        post = {"payload": {"profileId": str(profileId)}}
        return self._check_response(self.call_api('epg.channels.display', data=post, session=session), 'Problém při načtení kanálů')
       
    def content_play(self, post, session, is_retry=False, is_next=False):
        """Získání URL streamu včetně ošetření některých chybových stavů"""
        response = self.call_api('content.play' if not is_next else 'content.playnext', data=post, session=session)
        result = response.get('result', {})
        if result.get('status') == 'Ok':
            return result.get('data')
        message = result.get('message', '')
        if message == 'Kdo se dívá?' and not is_retry: # pri chybe Kdo se diva se znovu vybere profil
            session.reload_profile()
            return self.content_play(post, session, is_retry=True)
        elif message == 'Potvrďte spuštění dalšího videa': # osetreni omezeneho tarifu 
            if xbmcgui.Dialog().yesno('Potvrzení spuštění', 'Máte limitovaný počet přehrání. Opravdu chcete pořad přehrát?'):
                post['authorization'] = [{"schema": "UserConfirmAuthorization", "type": "tasting"}]
                return self.content_play(post, session)
        elif message == 'Zadejte kód rodičovského zámku': # osetreni rodicovskeho zamku
            addon = xbmcaddon.Addon()
            pin = addon.getSetting('pin')
            if pin in ('1621', ''): # pokud neni PIN nastaveny, nebo ma vychozi hodnotu, zobrazi se dotaz 
                pin = xbmcgui.Dialog().numeric(type=0, heading='Zadejte PIN', bHiddenInput=True)
                if len(str(pin)) != 4:
                    xbmcgui.Dialog().notification('Oneplay', 'Nesprávný PIN', xbmcgui.NOTIFICATION_ERROR, 5000)
                    pin = '1621'
            post['authorization'] = [{"schema": "PinRequestAuthorization", "pin": str(pin), "type": "parental"}]
            return self.content_play(post, session)
        else:
            if not is_next:
                xbmcgui.Dialog().notification('Oneplay', 'Chyba při přehrání', xbmcgui.NOTIFICATION_ERROR, 2000)
                xbmcgui.Dialog().notification('Oneplay', message, xbmcgui.NOTIFICATION_ERROR, 3000)
            return None        

    def page_content_display(self, post, session):
        """Stažení detailů o pořadu (payload i metadata)"""
        seasons = []
        episodes = []
        response = self.call_api('page.content.display', post, session)
        data = self._check_response(response, "Chyba načtení dat o pořadu", fatal=False)
        payload = None
        meta = data.get('metadata', {})
        for block in data.get('layout', {}).get('blocks', []):
            schema = block.get('schema')
            if not payload and schema == 'ContentHeaderBlock':
                action = block.get('mainAction', {}).get('action', {})
                if action.get('call') == 'content.play':
                    payload = action.get('params', {}).get('payload')
            if not meta: # pokud se blok neobsahuje přimo metadata (např. TV pořady), pokusí se je načíst z bloku
                meta = block
        # nacitani sezon a epizod                    
        # skontroluje se, ze je aktivni zalozka cele dily a pokud ne, aktivuje se
        for block in data.get('layout', {}).get('blocks', []):
            if block.get('schema') == 'TabBlock' and block.get('template') == 'tabs':
                for tab in block.get('tabs', []):
                    if tab.get('label', {}).get('name') == 'Celé díly':
                        if tab.get('isActive') == True:
                            data = block
                        else:
                            post = {"payload": {"tabId": tab.get('id')}}
                            response = self.call_api('tab.display', post, session)
                            data = self._check_response(response, "Chyba načtení dat o pořadu")
        # prochazi blok se seznamem dilu a sezon
        for block in data.get('layout', {}).get('blocks', []):
            carousels = block.get('carousels', []) # Vracíme prázdný seznam, ne slovník
            if not carousels: continue
            carousel = carousels[0]
            # epizody
            for tile in carousel.get('tiles', []): 
                episodes.append(tile)
            # sezony
            criteria = carousel.get('criteria', [{}])[0]
            if criteria.get('template') == 'showSeason':
                for item in criteria.get('items', []): 
                    seasons.append({'label': item['label'], 'carouselId': carousel['id'], 'criteria': item['criteria']})
            # seradi sezony sestupne, nezavisle na poradi z API
            seasons.sort(key=lambda x: int(re.search(r'\d+', x['label']).group()) if re.search(r'\d+', x['label']) else 0, reverse=True)
        info = {
            'title': meta.get('title', ''),
            'plot': meta.get('description') or meta.get('plot', ''),
            'original_title': meta.get('originalTitle', ''),
            'year': str(meta.get('year', '')),
            'duration': meta.get('duration', 0),
            'genre': meta.get('genres', []) or [],
            'director': meta.get('directors', []) or [],
            'cast': meta.get('actors', []) or meta.get('cast', []) or [],
            'country': meta.get('countries', []) or meta.get('country', '')
        }
        return {'payload': payload, 'info': info, 'seasons': seasons, 'episodes': episodes}

    def page_category_display(self, post, session):
        """Načtení kategorie"""
        response = self.call_api('page.category.display', data=post, session=session)
        data = self._check_response(response, 'Problém při načtení kategorie')
        return data.get('layout', {}).get('blocks', [])

    def carousel_display(self, post, session, silent=False):
        """Načtení kategorie"""
        response = self.call_api('carousel.display', data=post, session=session)
        if silent and response.get('result', {}).get('status') != 'Ok':
            return {}
        data = self._check_response(response, 'Problém při načtení kategorie')
        return data.get('carousel', [])

    def app_init(self, session):
        """Načtení menu kategorií"""
        post = {"payload": {"reason": "start"}}
        return self._check_response(self.call_api('app.init', data=post, session=session), 'Problém při načtení kategorií')

    def user_list_change(self, id, operation, session):
        """Načtení kategorie"""
        post = {"payload": {"changes": [{"schema": "UserMyListChange","ref": {"schema": "MyListRef", "id": id},"type": operation}]}}
        response = self.call_api('user.list.change', data=post, session=session)
        return response.get('result', {}).get('status') == 'Ok'
    
    def page_search_display(self, query, session):
        """Vyhledávání"""
        post = {"payload":{"query":query}}
        return self._check_response(self.call_api('page.search.display', data=post, session=session), 'Problém při vyhledávání')


