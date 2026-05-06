import sys
import os
import urllib.parse

addon_id = "plugin.audio.pandora"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "resources", "lib"))

try:
    import xbmcgui
    import xbmcplugin
    import xbmcaddon
    import xbmc
except ImportError as e:
    print(f"FATAL: {e}")
    raise

def klog(msg, level=xbmc.LOGINFO):
    try:
        xbmc.log(f"[PANDORA] {msg}", level)
    except:
        pass

try:
    from pandora_api import PandoraAPI
except ImportError as e:
    klog(f"Import failed: {e}", xbmc.LOGERROR)
    xbmcgui.Dialog().ok("Pandora Error", f"Import error: {e}")
    raise

def parse_query(query):
    params = {}
    if query:
        if query.startswith('?'):
            query = query[1:]
        for item in query.split('&'):
            if '=' in item:
                key, value = item.split('=', 1)
                params[key] = urllib.parse.unquote(value)
    return params

def main():
    try:
        handle = int(sys.argv[1])
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        params = parse_query(query)
        mode = params.get("mode", "")
        
        addon = xbmcaddon.Addon()
        username = addon.getSetting("username").strip()
        password = addon.getSetting("password").strip()
        
        if not username or not password:
            xbmcgui.Dialog().ok("Pandora", "Please configure username/password in settings")
            addon.openSettings()
            return
        
        api = PandoraAPI()
        
        if not api.connect(username, password):
            klog("Login failed", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("Pandora", "Login failed")
            return
        
        if mode == "station":
            station_token = params.get("token", "")
            tracks = api.get_playlist(station_token, count=24)
            
            if not tracks:
                xbmcgui.Dialog().ok("Pandora", "No songs available")
                xbmcplugin.endOfDirectory(handle)
                return
            
            music_playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            music_playlist.clear()
            current_size = 0
            
            for item in tracks:
                title = item.get("songName", "Unknown")
                artist = item.get("artistName", "Unknown")
                album = item.get("albumName", "")
                album_art = item.get("albumArtUrl", "")
                
                audio_url_map = item.get("audioUrlMap", {})
                if audio_url_map:
                    high_quality = audio_url_map.get("highQuality", {})
                    audio_url = high_quality.get("audioUrl", "")
                else:
                    audio_url = item.get("audioUrl", "")
                
                if not audio_url:
                    continue
                
                list_item = xbmcgui.ListItem(label=f"{title} - {artist}")
                music_tag = list_item.getMusicInfoTag()
                music_tag.setTitle(title)
                music_tag.setArtist(artist)
                music_tag.setAlbum(album)
                
                if album_art:
                    list_item.setArt({"thumb": album_art})
                list_item.setProperty("IsPlayable", "true")
                
                xbmcplugin.addDirectoryItem(handle, audio_url, list_item, isFolder=False)
                music_playlist.add(audio_url, list_item)
            
            xbmcplugin.endOfDirectory(handle)
            
            xbmc.sleep(300)
            xbmc.Player().play(music_playlist)
            xbmc.sleep(500)
            if xbmc.Player().isPlayingAudio():
                addon.setSetting("current_station_token", station_token)
                klog(f"Playing {music_playlist.size()} songs")
            
        else:
            stations = api.get_stations()
            
            if not stations:
                xbmcgui.Dialog().ok("Pandora", "No stations found")
                xbmcplugin.endOfDirectory(handle)
                return
            
            for station in stations:
                label = station.get("stationName", "Unknown")
                token = station.get("stationToken", "")
                url = f"plugin://{addon_id}/?mode=station&token={token}&user={username}"
                item = xbmcgui.ListItem(label=label)
                xbmcplugin.addDirectoryItem(handle, url, item, isFolder=True)
            
            xbmcplugin.endOfDirectory(handle)
        
    except Exception as e:
        klog(f"Error: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Pandora Error", str(e))

if __name__ == "__main__":
    main()
