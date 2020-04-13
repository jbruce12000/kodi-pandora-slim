import httplib, socket, threading, time, urllib, urllib2, urlparse,sys
import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs
import musicbrainzngs as _brain
from mutagen.mp4 import MP4
from pithos.pithos import *

# FIXME 
# - clean up settings
# - try max songs
# - final cleanup of variables (class globals)
# - remove AlreadyRunning
# - probably don't need SetCacheDirs anymore

class PandoraSlim(object):
    def __init__(self):
        self.juststarted = True
        self.settings = xbmcaddon.Addon()
        self.plugin = self.settings.getAddonInfo('id')
        self.log("OK started")
        self.maxsongs = int(self.settings.getSetting('listmax'))
        self.name = self.settings.getAddonInfo('name')
        self.version = self.settings.getAddonInfo('version')
        self.proxy = self.settings.getSetting('proxy')
        self.path = xbmc.translatePath(self.settings.getAddonInfo("profile")).decode("utf-8")
        self.base = sys.argv[0]
        self.handle = int(sys.argv[1])
        self.query = urlparse.parse_qs(sys.argv[2][1:])
        self.station = self.query.get('station', None)
        self.thumb = self.query.get('thumb', None)
        self.playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        self.playlist.clear() # FIXME - probably not needed
        self.player = xbmc.Player()
        self.pandora = Pandora()  # from pithos.pithos
        self.tracks = 0 # number of tracks in this playlist so far
        self.started = str(time.time())
        self.stamp = self.started
        self.brain = _brain
        self.brain.set_useragent("xbmc.%s" % self.plugin, self.version)

        if self.AlreadyRunning(): sys.exit()

        self.SetCacheDirs()
        self.CheckAuth()       
        if (self.station):
            self.log("OK station is set to %s, %s" % (self.station,self.station[0]))
            if type(self.station) is not Station: self.station = self.pandora.get_station_by_id(self.station[0])

    def AlreadyRunning(self):
        '''check if this plugin is already running'''
        win = xbmcgui.Window(10000)
        if win.getProperty('%s.running' % self.name) == 'True':
            self.log("OK Already running")
            return True
        return False

    def ShowXBMCPlaylist(self):
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        xbmc.executebuiltin('ActivateWindow(musicplaylist)')
        xbmc.executebuiltin("Container.Update")
        xbmc.executebuiltin("Container.Refresh")

    def Proxy(self):
        '''set pandoras url opener'''
        if self.proxy == '0':	# Global
            open = urllib2.build_opener()
        elif self.proxy == '1':	# None
            hand = urllib2.ProxyHandler({})
            open = urllib2.build_opener(hand)
        elif self.proxy == '2':	# Custom
            host = _settings.getSetting('proxy_host')
            port = _settings.getSetting('proxy_port')
            user = _settings.getSetting('proxy_user')
            word = _settings.getSetting('proxy_pass')
            prox = "http://%s:%s@%s:%s" % (user, word, host, port)
            hand = urllib2.ProxyHandler({ 'http' : prox })
            open = urllib2.build_opener(hand)
        self.pandora.set_url_opener(open)

    def Auth(self):
        '''authenticate to Pandora or Pandora One'''
        self.Proxy()

        one  = self.settings.getSetting('pandoraone')
        name = self.settings.getSetting('username')
        word = self.settings.getSetting('password')

        try: self.pandora.connect(one, name, word)
        except PandoraError:
            xbmc.log("%s.Auth FAILED" % self.plugin, xbmc.LOGERROR)
            return False;

        self.log("OK Auth")
        return True

    def DisplayStations(self):
        '''add stations to directory listing and display them'''

        sort = self.settings.getSetting('sort')
        stations = self.pandora.stations
        quickmix = stations.pop(0)							# grab Quickmix off top
        if   sort == '0':	stations = stations					# Normal
        elif sort == '2':	stations = stations[::-1]				# Reverse
        else:		        stations = sorted(stations, key=lambda s: s.name)	# A-Z
        stations.insert(0, quickmix)						# Quickmix back on top

        for station in stations:
            li = xbmcgui.ListItem(station.name, station.id)
            li.setProperty('IsPlayable', 'true')

            img = self.settings.getSetting("img-%s" % station.id)
            li.setIconImage(img)
            li.setThumbnailImage(img)
            li.addContextMenuItems([('Select Thumb', "RunPlugin(plugin://%s/?thumb=%s)" % (self.plugin, station.id))])

            xbmcplugin.addDirectoryItem(self.handle, "%s?station=%s" % (self.base, station.id), li)

        xbmcplugin.endOfDirectory(self.handle, cacheToDisc = False)
        self.log("OK DisplayStations")

    def GrabSongs(self):
        '''Grab some songs from Pandora'''

        try: psongs = self.station.get_playlist()
        except (PandoraTimeout, PandoraNetError): pass
        except (PandoraAuthTokenInvalid, PandoraAPIVersionError, PandoraError) as e:
            xbmcgui.Dialog().ok(_name, e.message, '', e.submsg)
            sys.exit()

        for song in psongs:

            qual = self.settings.getSetting('quality')
            path = song.audioUrl[qual]

            # set the track number for this song
            track = self.playlist.size()
            track = track + 1

            # cleanup title, artist, album
            badc = '\\/?%*:|"<>.'
            title = ''.join(c for c in song.title if c not in badc)
            artist = ''.join(c for c in song.artist if c not in badc)
            album = ''.join(c for c in song.album if c not in badc)

            li = xbmcgui.ListItem(song.artist, song.title, song.artUrl, song.artUrl)
            li.setProperty(self.plugin, self.stamp)
            li.setProperty('mimetype', 'audio/aac')
            li.setInfo('music', { 'artist' : artist, 'album' : album, 'title' : title, 'rating' : 1, 'tracknumber' : track })

            self.playlist.add(path, li)
            
            self.log("OK added song %s, track=%s" % (title,track))

        # gotta be at least one song in the playlist to set the station thumb
        self.SetStationThumb()

        self.log("OK GrabSongs station=%s, songs=%d" % (self.station.name, len(psongs)))

    def CheckAuth(self):
        '''authenticate in a loop until success'''
        while not self.Auth():
            if xbmcgui.Dialog().yesno(_name, '          Login Failed', 'Bad User / Pass / Proxy', '       Check Settings?'):
                self.settings.openSettings()
            else: sys.exit()

    def StationSelected(self):
        if self.station is None: return False
        self.log("OK StationSelected %s" % self.station.name)
        self.SetStationThumb()
        return True
  
    def SetCacheDirs(self):
        '''set cache directories, runs once at startup'''
        for dir in [ 'm4a', 'lib' ]:
            dir = xbmc.translatePath(self.settings.getSetting(dir)).decode("utf-8")
            xbmcvfs.mkdirs(dir)

    def SetStationThumb(self):
        '''set thumbnail for station to first song in playlist'''
        if self.playlist.size() == 0: return
        # stations initially have a default thumb
        # only once it is selected can we give it a thumb 
        # from the first song in the playlist
        if self.thumb: return

        # set station thumbnail
        img = self.playlist[0].getArt('thumb')
        self.settings.setSetting("img-%s" % self.station.id, img)
        self.log("OK SetStationThumb")

    def PlayFirstSong(self):
        self.ShowXBMCPlaylist()
        self.player.playselected(0)

    def GrabAllSongs(self):
        while(self.playlist.size() < self.maxsongs):
            self.GrabSongs()
            self.log("OK GrabAllSongs we have %s of %s" % (self.playlist.size(),self.maxsongs))
            xbmc.sleep(500)
        self.log("OK GrabAllSongs complete")

    def log(self,string,level=xbmc.LOGDEBUG):
        xbmc.log("%s %s" % (self.plugin,string),level)

    def start(self):

        # user must select a station first
        if not self.StationSelected(): 
            self.DisplayStations()
            sys.exit()

        # in 2nd invocation, get and play songs
        self.GrabAllSongs()
        self.PlayFirstSong()
        sys.exit()

# main
addon = PandoraSlim()
addon.start()

