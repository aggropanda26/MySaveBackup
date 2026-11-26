"""Asynchronous Steam artwork downloads, shared with SteamDB's image source."""
from collections import deque
from pathlib import Path
import re
from PySide6.QtCore import QObject, Signal, Qt, QUrl, QBuffer, QIODevice, QSize, QTimer, QSaveFile
from PySide6.QtGui import QImage, QImageReader
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

MAX_BYTES = 2 * 1024 * 1024
# Exact-title fallbacks for externally installed games without a Steam manifest.
KNOWN_IDS = {
    'arksurvivalascended': '2399830',
    'assassinscreedshadows': '3159330',
    'assassinscreedblackflagresynced': '3751950',
    'bodycam': '2406770',
}

def valid_app_id(value):
    value = str(value)
    return bool(re.fullmatch(r'[1-9][0-9]{0,9}', value))

def cover_app_id(game, overrides):
    key = re.sub(r'[^a-z0-9]', '', game.name.casefold())
    value = overrides.get(game.name) or game.app_id or KNOWN_IDS.get(key, '')
    return str(value) if valid_app_id(value) else ''

def cover_urls(app_id):
    if not valid_app_id(app_id):
        raise ValueError('Ungültige Steam-App-ID')
    base = f'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{app_id}'
    return [base + '/library_600x900.jpg', base + '/header.jpg']

def decode_image(data):
    if not data or len(data) > MAX_BYTES:
        return QImage()
    buffer = QBuffer(); buffer.setData(data); buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    size = reader.size()
    if not size.isValid() or size.width() * size.height() > 16_000_000:
        return QImage()
    reader.setScaledSize(size.scaled(QSize(300, 450), Qt.AspectRatioMode.KeepAspectRatio))
    return reader.read()

class CoverLoader(QObject):
    ready = Signal(str, QImage)
    unavailable = Signal(str)

    def __init__(self, cache_dir, parent=None, manager=None, steam_roots=None):
        super().__init__(parent)
        self.cache_dir = Path(cache_dir)
        self.steam_roots = steam_roots if steam_roots is not None else [
            Path.home()/'.local/share/Steam', Path.home()/'.steam/steam',
            Path.home()/'.var/app/com.valvesoftware.Steam/data/Steam']
        self.manager = manager if manager is not None else QNetworkAccessManager(self)
        self.queue = deque(); self.active = {}; self.pending = set()
        self.images = {}; self.failed = set(); self.stopped = False

    def request(self, app_id):
        if self.stopped or not valid_app_id(app_id):
            return
        if app_id in self.images:
            self.ready.emit(app_id, self.images[app_id]); return
        if app_id in self.failed:
            self.unavailable.emit(app_id); return
        if app_id in self.pending:
            return
        path = self.cache_dir/f'{app_id}.png'
        try:
            if path.is_file() and path.stat().st_size <= MAX_BYTES:
                image = decode_image(path.read_bytes())
                if not image.isNull():
                    self.images[app_id] = image; self.ready.emit(app_id, image); return
        except OSError:
            pass
        # Steam caches current artwork under hash subdirectories on newer clients.
        for root in self.steam_roots:
            library = Path(root)/'appcache/librarycache'
            for pattern in (f'{app_id}/*/library_capsule.jpg', f'{app_id}_library_600x900.jpg',
                            f'{app_id}/*/library_header.jpg', f'{app_id}_header.jpg'):
                for candidate in sorted(library.glob(pattern)):
                    try:
                        if candidate.is_file() and candidate.stat().st_size <= MAX_BYTES:
                            image = decode_image(candidate.read_bytes())
                            if not image.isNull():
                                self.images[app_id] = image
                                self.ready.emit(app_id, image)
                                return
                    except OSError:
                        continue
        self.pending.add(app_id); self.queue.append((app_id, 0))
        QTimer.singleShot(0, self._pump)

    def _pump(self):
        if self.stopped:
            return
        while self.queue and len(self.active) < 3:
            app_id, attempt = self.queue.popleft()
            request = QNetworkRequest(QUrl(cover_urls(app_id)[attempt]))
            request.setTransferTimeout(12000)
            request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                                 QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
            request.setRawHeader(b'User-Agent', b'MySaveBackup/0.1')
            reply = self.manager.get(request)
            self.active[reply] = {'id':app_id, 'attempt':attempt, 'data':bytearray(), 'oversize':False}
            reply.setReadBufferSize(MAX_BYTES + 1)
            reply.readyRead.connect(lambda r=reply: self._read(r))
            reply.finished.connect(lambda r=reply: self._finished(r))

    def _read(self, reply):
        state = self.active.get(reply)
        if state is None or state['oversize']:
            return
        state['data'].extend(bytes(reply.read(MAX_BYTES + 1 - len(state['data']))))
        if len(state['data']) > MAX_BYTES:
            state['oversize'] = True
            reply.abort()

    def _finished(self, reply):
        if reply not in self.active:
            return
        self._read(reply)
        state = self.active.pop(reply, None)
        if state is None:
            return
        app_id = state['id']
        ok = (reply.error() == QNetworkReply.NetworkError.NoError
              and reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) == 200
              and not state['oversize'])
        image = decode_image(bytes(state['data'])) if ok else QImage()
        reply.deleteLater()
        if self.stopped:
            return
        if not image.isNull():
            self.pending.discard(app_id); self.images[app_id] = image
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                output = QSaveFile(str(self.cache_dir/f'{app_id}.png'))
                if output.open(QIODevice.OpenModeFlag.WriteOnly):
                    if image.save(output, 'PNG'): output.commit()
                    else: output.cancelWriting()
            except OSError:
                pass
            self.ready.emit(app_id, image)
        elif state['attempt'] + 1 < len(cover_urls(app_id)):
            self.queue.append((app_id, state['attempt']+1))
        else:
            self.pending.discard(app_id); self.failed.add(app_id)
            self.unavailable.emit(app_id)
        self._pump()

    def close(self):
        self.stopped = True; self.queue.clear(); self.pending.clear()
        for reply in list(self.active):
            reply.abort()
