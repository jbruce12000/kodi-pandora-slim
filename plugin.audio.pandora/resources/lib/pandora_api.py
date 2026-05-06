import json
import urllib.request
import urllib.parse
import struct
import binascii
import time
import re
import sys
import os
import shutil
import subprocess

def klog(msg):
    try:
        import xbmc
        xbmc.log(f"[COMPLETE-STATION-PLAYER] {msg}", xbmc.LOGINFO)
    except:
        pass

try:
    from version import BUILD_ID, BUILD_DATE
except ImportError:
    BUILD_ID = "unknown"
    BUILD_DATE = "unknown"

class BlowfishCrypt:
    """Blowfish ECB encryption/decryption using pure Python blowfish."""
    def __init__(self, key):
        self._key = key if isinstance(key, (bytes, bytearray)) else key.encode()
        from blowfish import Cipher
        self._cipher = Cipher(self._key)

    def encrypt(self, data):
        return b''.join(self._cipher.encrypt_ecb(data))

    def decrypt(self, data):
        return b''.join(self._cipher.decrypt_ecb(data))

class PandoraAPI:
    def __init__(self):
        self.tuner_host = "tuner.pandora.com"
        self.partner_key = b"R=U!LH$O2B#"
        self.pw_key = b"6#26FRL$ZWD"
        self.user_agent = "pianobar-2022.04.01"
        self.partner_token = None
        self.partner_id = None
        self.user_token = None
        self.user_id = None
        self.sync_time = None
        self.time_offset = 0

    def _encrypt_payload(self, payload_json):
        """Encrypt a JSON string using the partner outkey, hex-encoded like pithos/pianobar"""
        payload_bytes = payload_json.encode()
        
        # Pad to 8-byte boundary
        padded_len = ((len(payload_bytes) + 7) // 8) * 8
        padded_bytes = payload_bytes + b'\x00' * (padded_len - len(payload_bytes))
        
        # Encrypt with partner outkey
        cipher = BlowfishCrypt(self.pw_key)
        encrypted = cipher.encrypt(padded_bytes)
        
        # Hex-encode each 8-byte block (like pithos does)
        hex_encoded = binascii.hexlify(encrypted).decode()
        return hex_encoded.encode()
    
    def _http_request(self, url, payload, encrypt=False):
        try:
            if encrypt:
                if isinstance(payload, str):
                    post_data = self._encrypt_payload(payload)
                else:
                    import json as json_module
                    post_data = self._encrypt_payload(json_module.dumps(payload))
                content_type = "text/plain"
            else:
                post_data = json.dumps(payload)
                content_type = "application/json"
                
            req = urllib.request.Request(
                url,
                data=post_data if isinstance(post_data, bytes) else post_data.encode(),
                headers={"Content-Type": content_type, "User-Agent": self.user_agent}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                response_data = r.read().decode()
                return json.loads(response_data)
        except Exception as e:
            klog(f"HTTP request failed: {e}")
            return {"stat": "fail"}

    def connect(self, username, password):
        resp = self._http_request(
            "https://tuner.pandora.com/services/json/?method=auth.partnerLogin",
            {"username": "android", "password": "AC7IBG09A3DTSYM4R41UJWL07VLN8JI7", "deviceModel": "android-generic", "version": "5", "includeUrls": True}
        )
        
        if resp.get("stat") != "ok":
            klog(f"Partner login failed")
            return False
        
        self.partner_token = resp["result"]["partnerAuthToken"]
        self.partner_id = resp["result"]["partnerId"]
        sync_hex = resp["result"]["syncTime"]
        
        try:
            cipher = BlowfishCrypt(self.partner_key)
            decrypted = cipher.decrypt(binascii.unhexlify(sync_hex))
            sync_bytes = decrypted[4:]
            sync_str = sync_bytes.decode("utf-8", "ignore").strip("\x00").strip()
            match = re.search(r"(\d+)", sync_str)
            if match:
                self.sync_time = match.group(1)
                self.time_offset = int(time.time()) - int(self.sync_time)
            else:
                self.sync_time = str(int(time.time()))
                self.time_offset = 0
        except Exception as e:
            klog(f"Sync decryption failed: {e}")
            self.sync_time = str(int(time.time()))
            self.time_offset = 0
        
        corrected_time = int(time.time()) - self.time_offset
        
        import json as json_module
        payload = {
            "loginType": "user",
            "username": username,
            "password": password,
            "partnerAuthToken": self.partner_token,
            "syncTime": corrected_time
        }
        payload_json = json_module.dumps(payload, separators=(',', ':'))
        
        auth_token_encoded = urllib.parse.quote_plus(self.partner_token)
        resp = self._http_request(
            f"https://{self.tuner_host}/services/json/?method=auth.userLogin&partner_id={self.partner_id}&auth_token={auth_token_encoded}",
            payload_json,
            encrypt=True
        )
        
        if resp.get("stat") != "ok":
            klog(f"User login failed")
            return False
        
        self.user_token = resp["result"]["userAuthToken"]
        self.user_id = resp["result"]["userId"]
        return True

    def get_stations(self):
        if not self.user_token:
            return []
        try:
            corrected_time = int(time.time()) - self.time_offset
            url = f"https://tuner.pandora.com/services/json/?method=user.getStationList&user_id={self.user_id}&auth_token={urllib.parse.quote(self.user_token)}&partner_id={self.partner_id}"
            payload = {
                "userAuthToken": self.user_token,
                "syncTime": corrected_time,
                "returnAllStations": True
            }
            resp = self._http_request(url, payload, encrypt=True)
            if resp.get("stat") == "ok":
                return resp["result"].get("stations", [])
        except Exception as e:
            klog(f"get_stations failed: {e}")
        return []

    def get_playlist(self, station_token, count=10):
        if not self.user_token:
            return []
        all_items = []
        seen_tokens = set()
        
        while len(all_items) < count:
            remaining = count - len(all_items)
            fetch_count = min(4, remaining)
            
            try:
                corrected_time = int(time.time()) - self.time_offset
                url = f"https://tuner.pandora.com/services/json/?method=station.getPlaylist&user_id={self.user_id}&auth_token={urllib.parse.quote(self.user_token)}&partner_id={self.partner_id}"
                payload = {
                    "userAuthToken": self.user_token,
                    "syncTime": corrected_time,
                    "stationToken": station_token,
                    "includeTrackLength": True
                }
                resp = self._http_request(url, payload, encrypt=True)
                if resp.get("stat") == "ok":
                    items = resp["result"].get("items", [])
                    added = 0
                    for item in items:
                        track_token = item.get("trackToken", "")
                        if track_token and track_token not in seen_tokens:
                            seen_tokens.add(track_token)
                            all_items.append(item)
                            added += 1
                            if len(all_items) >= count:
                                break
                    if added == 0:
                        break
                else:
                    klog(f"get_playlist failed")
                    break
            except Exception as e:
                klog(f"get_playlist failed: {e}")
                break
        
        return all_items[:count]
