# -*- coding: utf-8 -*-
import xbmc
from resources.lib.utils import plugin_id, parsedatetime

channel = xbmc.getInfoLabel('ListItem.ChannelName')
date = xbmc.getInfoLabel('ListItem.Date')
start_time = xbmc.getInfoLabel('ListItem.StartDate')
startdatetime = parsedatetime(date, start_time)
if channel and startdatetime:
    xbmc.executebuiltin(f"RunPlugin(plugin://{plugin_id}?action=iptv_sc_rec&channel={channel}&startdatetime={startdatetime})")
