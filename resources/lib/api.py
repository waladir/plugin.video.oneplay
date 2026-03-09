# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon

import json
import gzip 
import socket

from websocket import create_connection
import uuid

from urllib.request import urlopen, Request
from urllib.error import HTTPError

from resources.lib.utils import appVersion

class API:
    def __init__(self):
        self.headers = {'User-Agent' : 'Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0', 'Accept-Encoding' : 'gzip', 'Accept' : '*/*', 'Content-type' : 'application/json;charset=UTF-8'} 

    def call_api(self, url, data, session = None, sensitive = False):
        addon = xbmcaddon.Addon()
        if session is not None:
            self.headers['Authorization'] = 'Bearer ' + session.token
        if addon.getSetting('log_request_url') == 'true':
            xbmc.log('Oneplay > ' + str(url))
        if addon.getSetting('log_request_url') == 'true' and data != None and sensitive == False:
            xbmc.log('Oneplay > ' + str(data))
        try:
            requestId = str(uuid.uuid4())
            clientId = str(uuid.uuid4())
            ws = create_connection('wss://ws.cms.jyxo.cz/websocket/' + clientId)
            ws_data = ws.recv()
            ws_data = json.loads(ws_data)
            post = {"deviceInfo":{"deviceType":"web","appVersion":appVersion,"deviceManufacturer":"Unknown","deviceOs":"Linux"},"capabilities":{"async":"websockets"},"context":{"requestId":requestId,"clientId":clientId,"sessionId":ws_data['data']['serverId'],"serverId":ws_data['data']['serverId']}}
            if data is not None:
                post = {**data, **post}
            post = json.dumps(post).encode("utf-8")
            request = Request(url = url , data = post, headers = self.headers)
            response = urlopen(request, timeout = 20)
            if response.getheader("Content-Encoding") == 'gzip':
                gzipFile = gzip.GzipFile(fileobj = response)
                data = gzipFile.read()
            else:
                data = response.read()
            if len(data) > 0:
                data = json.loads(data)
            if 'result' not in data or 'status' not in data['result'] or data['result']['status'] != 'Ok':
                xbmc.log('Oneplay > Chyba při volání '+ str(url))
                ws.close()
                return { 'err' : 'Chyba při volání API' }  
            else:
                if addon.getSetting('log_response') == 'true':
                    if len(str(data)) > 5000 and addon.getSetting('skip_long') == 'true':
                        xbmc.log('Oneplay > odpověď obdržena (' + str(len(str(data))) + ')')
                    else:
                        xbmc.log('Oneplay > ' + str(data))
                if 'result' not in data or 'status' not in data['result'] or data['result']['status'] != 'Ok' or data['context']['requestId'] != requestId:
                    xbmc.log('Oneplay > Chyba při volání '+ str(url))
                    ws.close()
                    if 'result' in data and 'message' in data['result']:
                        return { 'err' : data['result']['message']}
                    else:
                        return { 'err' : 'Chyba při volání API' }  
                ws.close()
                if 'data' in data:
                    return data['data']
                return []
        except HTTPError as e:
            xbmc.log('Oneplay > Chyba při volání '+ str(url) + ': ' + e.reason)
            ws.close()
            return { 'err' : e.reason }  
        except socket.timeout:
            xbmc.log('Oneplay > Timout volání '+ str(url))
            xbmc.log('Oneplay > Timout volání '+ str(data))
            ws.close()
            return { 'err' : 'timeout' }  
        except socket.error:
            xbmc.log('Oneplay > Timout volání '+ str(url))
            xbmc.log('Oneplay > Timout volání '+ str(data))
            ws.close()
            return { 'err' : 'timeout' }  
