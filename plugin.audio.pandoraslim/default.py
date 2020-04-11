import httplib, socket, threading, time, urllib, urllib2, urlparse
import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs
import musicbrainzngs as _brain
from mutagen.mp4 import MP4
from pithos.pithos import *

class PandoraSlim(object):
    def __init__(self):
        self.settings = xbmcaddon.Addon()
        self.plugin = self.settings.getAddonInfo('id')
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
        self.SetCacheDirs()

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

        self.CheckAuth()

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
        if type(self.station) is not Station: self.station = self.pandora.get_station_by_id(self.station[0])

        try: psongs = self.station.get_playlist()
        except (PandoraTimeout, PandoraNetError): pass
        except (PandoraAuthTokenInvalid, PandoraAPIVersionError, PandoraError) as e:
            xbmcgui.Dialog().ok(_name, e.message, '', e.submsg)
            exit()

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

            self.pslim.playlist.add(path, li)
            self.log("OK added song %s" % title)

        self.log("OK GrabSongs station=%s, songs=%d" % (self.station.name, len(psongs)))

    def Play(self):
        # FIXME - this whole def goes away...

        # not sure why this exists
        li = xbmcgui.ListItem(self.station[0])
        li.setPath("special://home/addons/%s/silent.m4a" % self.plugin)
        li.setProperty(self.plugin, self.stamp)
        li.setProperty('mimetype', 'audio/aac')


        # not sure about his stuff either
        xbmcplugin.setResolvedUrl(self.handle, True, li)
        self.player.play(self.playlist)
        xbmc.executebuiltin('ActivateWindow(10500)')

        xbmc.log("%s.Play  OK (%13s)           '%s - %s'" % (self.plugin, self.stamp, self.station.id[-4:], self.station.name))


    def ExpireFromPlaylist(self):
        '''Remove the first item from the playlist'''
        while (self.playlist.size() > int(self.settings.getSetting('listmax'))) and (self.playlist.getposition() > 0):
            xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"Playlist.Remove", "params":{"playlistid":' + str(xbmc.PLAYLIST_MUSIC) + ', "position":0}}')

    def ExpireFiles(self):
        '''remove files from the filesystem per settings'''
        m4a = xbmc.translatePath(self.settings.getSetting('m4a')).decode("utf-8")
        exp = time.time() - (float(self.settings.getSetting('expire')) * 3600.0)
        reg = re.compile('^[a-z0-9]{32}\.')
        (dirs, list) = xbmcvfs.listdir(m4a)

        for file in list:
            if reg.match(file):
                file = "%s/%s" % (m4a, file)
                if xbmcvfs.Stat(file).st_mtime() < exp:
                    xbmcvfs.delete(file)
                    self.log("OK ExpireFiles %s" % (file))

    def CheckAuth(self):
        '''authenticate in a loop until success'''
        while not self.Auth():
            if xbmcgui.Dialog().yesno(_name, '          Login Failed', 'Bad User / Pass / Proxy', '       Check Settings?'):
                self.settings.openSettings()
            else: exit()

    def StationSelected(self):
        if self.station is None: return False
        self.log("OK StationSelected %s" % self.station)
        self.SetStationThumb()
        return True
  
    def SetCacheDirs(self):
        '''set cache directories, runs once at startup'''
        for dir in [ 'm4a', 'lib' ]:
            dir = xbmc.translatePath(self.settings.getSetting(dir)).decode("utf-8")
            xbmcvfs.mkdirs(dir)

    def SetStationThumb(self):
        '''set thumbnail for station to first song in playlist'''
        # stations initially have a default thumb
        # only once it is selected can we give it a thumb 
        # from the first song in the playlist
        if self.thumb: return

        # set station thumbnail
        img = self.playlist[0].artUrl #not sure this is possible (may need to use the following...
        # img = self.playlist[0].getProperty(artUrl)
        self.settings.setSetting("img-%s" % station.id, img)

    def OutOfSongs(self):
        '''are we out of songs in the cache'''
        # I think we can have kodi grab songs while the current song is still playing
        # FIXME - static lookahead of 3 here needs to be configurable
        if self.playlist.size() == 0: return True
        if (self.playlist.size() - self.playlist.getposition()) <= 2: return True
        self.log("OK OutOfSongs")
        return False

    def SongNotPlaying(self):
        '''returns True if no song is currently playing'''
        if self.player.isPlayingAudio(): return False
        self.log("OK SongNotPlaying")
        return True

    def PlayNextSong(self):
        '''play the next song'''
        curr = self.playlist.getposition()
        # will this play just one song???
        # not a blocking call
        self.player.playselected(curr+1)
         
        # cleanup as needed 
        self.ExpireFiles()
        self.ExpireFromPlaylist()

    def log(self,string,level=xbmc.LOGDEBUG):
        xbmc.log("%s %s" % (self.plugin,string),level)

    def start(self):
        self.log("OK started") 
        if not self.StationSelected(): 
            self.DisplayStations()
            exit()

        while (not xbmc.abortRequested):
            if self.OutOfSongs(): self.GrabSongs()
            if self.SongNotPlaying(): self.PlayNextSong()
            xbmc.sleep(1000)
            time.sleep(.5) 
        self.log("OK exit")

# main
addon = PandoraSlim()
addon.start()
