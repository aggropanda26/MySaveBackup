import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from PySide6.QtCore import QObject, Signal, QTimer, QEventLoop, QBuffer, QIODevice, QCoreApplication, QEvent
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication
from mysavebackup.core import Game
from mysavebackup.covers import CoverLoader, cover_app_id, decode_image, MAX_BYTES

class Reply(QObject):
    readyRead=Signal();finished=Signal()
    def __init__(self, status, data, parent):
        super().__init__(parent);self.status=status;self.data=data;self.aborted=False;self.done=False
        QTimer.singleShot(0,self.deliver)
    def deliver(self):
        self.readyRead.emit()
        if not self.done:self.done=True;self.finished.emit()
    def read(self,n):
        chunk=self.data[:n];self.data=self.data[n:];return chunk
    def setReadBufferSize(self,n):pass
    def error(self):
        return QNetworkReply.NetworkError.OperationCanceledError if self.aborted else QNetworkReply.NetworkError.NoError
    def attribute(self,key):return self.status
    def abort(self):
        self.aborted=True
        if not self.done:self.done=True;self.finished.emit()

class Manager(QObject):
    def __init__(self,responses):super().__init__();self.responses=list(responses);self.urls=[]
    def get(self,request):
        self.urls.append(request.url().toString())
        return Reply(*self.responses.pop(0),self)

def png():
    image=QImage(24,36,QImage.Format.Format_RGB32);image.fill(0x225588)
    buf=QBuffer();buf.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buf,'PNG')
    return bytes(buf.data())

class CoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def wait(self,loader):
        loop=QEventLoop();loader.ready.connect(loop.quit);loader.unavailable.connect(loop.quit)
        timer=QTimer(loop);timer.setSingleShot(True);timer.timeout.connect(loop.quit);timer.start(1500)
        loop.exec();timer.stop()
        loader.ready.disconnect(loop.quit);loader.unavailable.disconnect(loop.quit)
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    def test_download_then_offline_cache_and_request_dedup(self):
        with tempfile.TemporaryDirectory() as t:
            manager=Manager([(200,png())]);loader=CoverLoader(Path(t),manager=manager,steam_roots=[])
            result=[];loader.ready.connect(lambda aid,img:result.append(aid))
            loader.request('3008130');loader.request('3008130');self.wait(loader)
            self.assertEqual(result,['3008130']);self.assertEqual(len(manager.urls),1)
            self.assertTrue((Path(t)/'3008130.png').is_file())
            offline=Manager([]);cached=CoverLoader(Path(t),manager=offline,steam_roots=[])
            cached.ready.connect(lambda aid,img:result.append(aid));cached.request('3008130')
            self.assertEqual(len(result),2);self.assertEqual(offline.urls,[])
            loader.close();cached.close()
    def test_invalid_image_falls_back_without_caching_bad_data(self):
        with tempfile.TemporaryDirectory() as t:
            manager=Manager([(200,b'<html>no image</html>'),(200,png())])
            loader=CoverLoader(t,manager=manager,steam_roots=[]);loader.request('123');self.wait(loader)
            self.assertIn('123',loader.images);self.assertEqual(len(manager.urls),2)
            self.assertTrue(manager.urls[-1].endswith('/header.jpg'));loader.close()
    def test_failure_and_oversize_leave_app_usable(self):
        with tempfile.TemporaryDirectory() as t:
            loader=CoverLoader(t,manager=Manager([(200,b'x'*(MAX_BYTES+1)),(404,b'not found')]),steam_roots=[])
            result=[];loader.unavailable.connect(result.append);loader.request('123');self.wait(loader)
            self.assertEqual(result,['123']);self.assertFalse(list(Path(t).iterdir()))
            self.assertFalse(loader.pending);loader.close()
    def test_invalid_id_never_requested_and_close_cancels_queue(self):
        with tempfile.TemporaryDirectory() as t:
            manager=Manager([]);loader=CoverLoader(t,manager=manager,steam_roots=[])
            loader.request('../../private');loader.request('123');loader.close()
            self.app.processEvents();self.assertEqual(manager.urls,[])
    def test_local_steam_artwork_needs_no_network(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); asset=root/'steam/appcache/librarycache/123/hash/library_capsule.jpg'
            asset.parent.mkdir(parents=True);asset.write_bytes(png())
            manager=Manager([])
            loader=CoverLoader(root/'cache',manager=manager,steam_roots=[root/'steam'])
            result=[];loader.ready.connect(lambda aid,img:result.append(aid))
            loader.request('123')
            self.assertEqual(result,['123']);self.assertEqual(manager.urls,[]);loader.close()

    def test_game_id_and_known_external_title(self):
        self.assertEqual(cover_app_id(Game('Bodycam'),{}),'2406770')
        self.assertEqual(cover_app_id(Game('Unknown',app_id='123'),{}),'123')
        self.assertEqual(cover_app_id(Game('Unknown'),{}),'')
        self.assertEqual(cover_app_id(Game('Unknown'),{'Unknown':'456'}),'456')
        self.assertTrue(decode_image(b'not an image').isNull())

if __name__=='__main__':unittest.main()
