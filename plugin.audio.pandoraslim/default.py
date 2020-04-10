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
        self.lock = threading.Lock()
        self.play = False
        self.tracks = 0 # number of tracks in this playlist so far
        self.high = 0.0 # not sure wtf this is for
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

        self.log("Auth OK")
        return True


    def DisplayStations(self):
        '''add stations to directory listing'''

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
        xbmc.log("%s.DisplayStations OK" % self.plugin, xbmc.LOGDEBUG)

    def Grabsongs(self):
        '''Grab a list of songs from Pandora'''
        if type(self.station) is not Station: self.station = self.pandora.get_station_by_id(self.station[0])

        try: psongs = self.station.get_playlist()
        except (PandoraTimeout, PandoraNetError): pass
        except (PandoraAuthTokenInvalid, PandoraAPIVersionError, PandoraError) as e:
            xbmcgui.Dialog().ok(_name, e.message, '', e.submsg)
            exit()

        for psong in psongs:
            song = PandoraSlimSong(self,psong) # passing PandoraSlim and a song
            threading.Timer(0.01, song.Whereis).start() 

        xbmc.log("%s.Grabsongs  OK (%13s,%8d)          '%s - %s'" % (self.plugin, self.stamp, len(psongs), self.station.id[-4:], self.station.name), xbmc.LOGDEBUG)

    def Play(self):

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

        for file in list: if reg.match(file): file = "%s/%s" % (m4a, file)

                if xbmcvfs.Stat(file).st_mtime() < exp:
                    xbmcvfs.delete(file)
                    self.log("ExpireFiles %s" % (file))

    def CheckAuth(self):
        '''authenticate in a loop until success'''
        while not self.Auth():
            if xbmcgui.Dialog().yesno(_name, '          Login Failed', 'Bad User / Pass / Proxy', '       Check Settings?'):
                self.settings.openSettings()
            else: exit()

    def StationSelected(self):
        if self.station is None: return False
        self.log("station %s selected" % self.station)
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
        return False

    def GrabSongs(self,count=3):
        '''complete rewrite'''
        
        if self.playlist.size == 0:

           

        pass

    def SongNotPlaying(self):
        '''returns True if no song is currently playing'''
        if self.player.isPlayingAudio(): return False
        return True

    def PlayNextSong(self):
        '''play the next song'''

        curr = self.playlist.getposition()
        self.player.playselected(curr+1) # will this play just one song???
         
        # cleanup as needed 
        self.ExpireFiles()
        self.ExpireFromPlaylist()

    def log(self,string,level=xbmc.LOGDEBUG):
        xbmc.log("%s %s" % (self.plugin,string),level)

    def start(self):
        self.log("started") 
        if not self.StationSelected(): 
            self.DisplayStations()
            exit()

        while (not xbmc.abortRequested):
            xbmc.sleep(1000)
            if self.OutOfSongs(): self.GrabSongs()
            if self.SongNotPlaying(): self.PlayNextSong()

        self.log("exit")

class PandoraSlimSong(object):
    def __init__(self,pslim,psong):
        self.pslim = pslim
        self.plugin = self.pslim.plugin
        self.stamp = self.pslim.stamp
        self.brain = self.pslim.brain
        self.psong = psong
        self.badc = '\\/?%*:|"<>.'
        self.title = ''.join(c for c in self.psong.title if c not in self.badc)
        self.artist = ''.join(c for c in self.psong.artist if c not in self.badc)
        self.album = ''.join(c for c in self.psong.album if c not in self.badc)
        self.artUrl = self.psong.artUrl
        self.audioUrl = self.psong.audioUrl
        self.songId = self.psong.songId
        self.stationId = self.psong.stationId
        self.wtf = self.songId[:4]
        self.rating = None #never gets set anywhere
        self.track = 0 #track number for this specific song in current playlist


    def Tag(self,path):
        '''add tags for name, artist, and title to a song and save em'''
        tag = MP4(path)
        dur = str(int(tag.info.length * 1000))
        res = self.brain.search_recordings(limit = 1, query = self.title, artist = self.artist, release = self.album, qdur = dur)['recording-list'][0]
        sco = res['ext:score']

        if sco == '100':
            tag['----:com.apple.iTunes:MusicBrainz Track Id'] = res['id']
            tag['\xa9ART'] = self.artist
            tag['\xa9alb'] = self.album
            tag['\xa9nam'] = self.title

            tag.save()
            xbmc.log("%s.Tag   OK (%13s,%4s %%)    '%s - %s - %s'" % (self.plugin, self.stamp, sco, song.wtf, song.artist, song.title), xbmc.LOGDEBUG)
            return True
        else:
            xbmc.log("%s.Tag FAIL (%13s,%4s %%)    '%s - %s - %s'" % (self.plugin, self.stamp, sco, song.wtf, song.artist, song.title), xbmc.LOGDEBUG)
            return False


    def Save(self):
        '''save song, tags, album and artist art'''
        if self.pslim.settings.getSetting('mode') != '1': return	# do not Save to Library because of user setting

        # copy song to temporary directory
        tmp = "%s.temp" % (self.path)
        xbmcvfs.copy(self.path, tmp)

        if self.Tag(tmp):
            lib = self.pslim.settings.getSetting('lib')
            dir = xbmc.translatePath(("%s/%s/%s - %s"             % (lib, self.artist, self.artist, self.album))                         ).decode("utf-8")
            dst = xbmc.translatePath(("%s/%s/%s - %s/%s - %s.m4a" % (lib, self.artist, self.artist, self.album, self.artist, self.title))).decode("utf-8")
            alb = xbmc.translatePath(("%s/%s/%s - %s/folder.jpg"  % (lib, self.artist, self.artist, self.album))                         ).decode("utf-8")
            art = xbmc.translatePath(("%s/%s/folder.jpg"          % (lib, self.artist))                                                  ).decode("utf-8")

            xbmcvfs.mkdirs(dir)
            xbmcvfs.rename(tmp, dst)

            # fetch and save the album and artist images
            # it's ok if these fail, best effort
            try:
                if not xbmcvfs.exists(alb): urllib.urlretrieve(self.artUrl, alb)
                if not xbmcvfs.exists(art): urllib.urlretrieve(self.artUrl, art)
            except IOError: pass

        # clean up temporary file
        else: xbmcvfs.delete(tmp)

        xbmc.log("%s.Save  OK (%13s) '%s - %s - %s'" % (self.plugin, self.stamp, self.wtf, self.artist, self.title), xbmc.LOGDEBUG)

    # FIXME - this whole funtion needs to move to Pandoraslim
    def Queue(self,path):
        '''add song to the queue'''
        # these globals work across threads? not sure. leaving here.
        self.pslim.tracks += 1
        self.track = self.pslim.tracks 

        li = xbmcgui.ListItem(self.artist, self.title, self.artUrl, self.artUrl)
        li.setProperty(self.plugin, self.stamp)
        li.setProperty('mimetype', 'audio/aac')
        li.setInfo('music', { 'artist' : self.artist, 'album' : self.album, 'title' : self.title, 'rating' : self.rating, 'tracknumber' : self.track })

        self.pslim.play = True
        self.pslim.lock.acquire()
        self.pslim.playlist.add(path, li)
        self.pslim.lock.release()

        xbmc.log("%s.Queue OK (%13s)           '%s - %s - %s'" % (self.plugin, self.stamp, self.wtf, self.artist, self.title), xbmc.LOGDEBUG)


    def Msg(self,msg):
        '''pandora message? ad? not sure'''
        self.title = msg
        self.artist = 'Pandora'
        self.artUrl = "special://home/addons/%s/icon.png" % self.plugin
        self.album = self.rating = None
        self.Queue(song, "special://home/addons/%s/silent.m4a" % self.plugin)

    def Fetch(self,path):
        '''fetch a song, save it'''
        # FIXME - this def is too big

        # after initial installation isad='' which bombed out here
        try:
            isad = int(self.pslim.settings.getSetting('isad')) * 1024
        except ValueError:
            isad = 256
        
        # this likely would cause the same error, fixing it too
        try:
            wait = int(self.pslim.settings.getSetting('delay'))
        except ValueError:
            wait = 5

        qual = self.pslim.settings.getSetting('quality')
        skip = self.pslim.settings.getSetting('skip')

        # this bombed out too. not sure returning None here is right
        if qual not in self.audioUrl:
            return None

        # how big is the file
        url  = urlparse.urlsplit(song.audioUrl[qual])
        conn = httplib.HTTPConnection(url.netloc, timeout = 9)
        conn.request('GET', "%s?%s" % (url.path, url.query))
        strm = conn.getresponse()
        size = int(strm.getheader('content-length'))

        if size in (341980, 173310): # empty song cause requesting to fast
            xbmc.log("%s.Fetch MT (%13s,%8d)  '%s - %s - %s'" % (self.plugin, self.stamp, size, self.wtf, self.artist, self.title), xbmc.LOGDEBUG)
            self.Msg(song, 'Too Many Songs Requested')
            return None

        xbmc.log("%s.Fetch %s (%13s,%8d)  '%s - %s - %s'" % (self.plugin, strm.reason, self.stamp, size, self.wtf, self.artist, self.title))


        # save the file
        totl = 0
        qued = False
        last = time.time()
        file = open(path, 'wb', 0)

        while (totl < size) and (not xbmc.abortRequested):
            try: data = strm.read(min(4096, size - totl))
            except socket.timeout:
                xbmc.log("%s.Fetch TO (%13s,%8d)  '%s - %s - %s'" % (_plugin, _stamp, totl, self.wtf, song.artist, song.title), xbmc.LOGDEBUG)
                break

            # this is the only place pslim.high gets set... 
            if self.pslim.high < (time.time() - last): self.pslim.high = time.time() - last
            last = time.time()

            file.write(data)
            totl += len(data)

            if (not qued) and (size > isad):
                threading.Timer(wait, self.Queue, (self, path)).start()
                qued = True

        file.close()
        conn.close()
        
        if totl < size:	        # incomplete file
            xbmc.log("%s.Fetch RM (%13s)           '%s - %s - %s'" % (self.plugin, self.stamp, self.wtf, self.artist, self.title), xbmc.LOGDEBUG)
            xbmcvfs.delete(path)
            return None

        if size <= isad:        # looks like an ad
            if skip == 'true':
                xbmc.log("%s.Fetch AD (%13s)           '%s - %s - %s'" % (self.plugin, self.stamp, self.wtf, self.artist, self.title), xbmc.LOGDEBUG)
                xbmcvfs.delete(path)
                return None

            if qued == False:   # play it anyway
                song.artist = song.album = song.title = 'Advertisement'
                dest = path + '.ad.m4a'
                xbmcvfs.rename(path, dest)
                self.Queue(dest)
                return None

        self.Save(path)


    def Whereis(self):
        '''if we have song already, use that'''
        lib = xbmc.translatePath(("%s/%s/%s - %s/%s - %s.m4a" % (self.pslim.settings.getSetting('lib'), self.artist, self.artist, self.album, self.artist, self.title))).decode("utf-8")
        m4a = xbmc.translatePath(("%s/%s.m4a" % (self.pslim.settings.getSetting('m4a'), self.songId))).decode("utf-8")

        # set station thumbnail
        if not self.pslim.settings.getSetting("img-%s" % self.stationId): #FIXME - sometime try making name img-station-%s here
            self.pslim.settings.setSetting("img-%s" % self.stationId, self.artUrl)

        # Found in Library
        if xbmcvfs.exists(lib): # Found in Library
            xbmc.log("%s.Song LIB (%13s)           '%s - %s - %s'" % (self.plugin, self.stamp, self.wtf, self.safe_str(self.artist), self.safe_str(self.title)))
            self.Queue(lib)
         
        elif xbmcvfs.exists(m4a): # Found in Cache
            xbmc.log("%s.Song M4A (%13s)           '%s - %s - %s'" % (self.plugin, self.stamp, self.wtf, self.safe_str(self.artist), self.safe_str(self.title)))
            self.Queue(m4a)

        elif self.pslim.settings.getSetting('mode') == '0': # Stream Only
            xbmc.log("%s.Song PAN (%13s)           '%s - %s - %s'" % (self.plugin, self.stamp, self.wtf, self.safe_str(self.artist), self.safe_str(self.title))) 
            qual = self.pslim.settings.getSetting('quality')
            if qual in self.audioUrl:
                self.Queue(self.audioUrl[qual]) #FIXME this can probably be moved and set as the default for Queue
            else:
                xbmc.log("%s.Song (%13s) quality of that song not available to stream" % (self.plugin, self.stamp))
        else:					# Cache / Save
            self.Fetch(m4a)

    def safe_str(self,obj):
        try: return str(obj)
        except UnicodeEncodeError:
            return obj.encode('ascii', 'ignore').decode('ascii')
        return ""


# main
addon = PandoraSlim()
addon.start()
