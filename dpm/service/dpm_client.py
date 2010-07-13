from twisted.internet import glib2reactor
glib2reactor.install()

from twisted.spread import pb
from twisted.internet import reactor
from twisted.python import log
from bcm.utils import mdns
import sys, os

log.FileLogObserver(sys.stdout).start()

DIRECTORY = '/home/michel/tmp/testing'

class App(object):
    def __init__(self):
        self._service_found = False
    
    def on_dpm_service_added(self, obj, data):
        if self._service_found:
            return
        self._service_found = True
        self._service_data = data
        log.msg('DPM Server found on local network at %s:%s' % (self._service_data['host'], 
                                                                self._service_data['port']))
        self.factory = pb.PBClientFactory()
        self.factory.getRootObject().addCallbacks(self.on_dpm_connected, self.on_connection_failed)
        reactor.connectTCP(self._service_data['address'],
                           self._service_data['port'], self.factory)
        
    def on_dpm_service_removed(self, obj, data):
        if not self._service_found and self._service_data['host']==data['host']:
            return
        self._service_found = False
        log.msg('DPM Service no longer available on local network at %s:%s' % (self._service_data['host'], 
                                                                self._service_data['port']))
        
    def setup(self):
        """Find out the connection details of the DPM Server using mdns
        and initiate a connection"""
        import time
        _service_data = {#'user': os.getlogin(), 
                         'uid': os.getuid(), 
                         'gid': os.getgid(), 
                         'started': time.asctime(time.localtime())}
        self.browser = mdns.Browser('_cmcf_dpm._tcp')
        self.browser.connect('added', self.on_dpm_service_added)
        self.browser.connect('removed', self.on_dpm_service_removed)
        
    def on_dpm_connected(self, perspective):
        """ I am called when a connection to the DPM Server has been established.
        I expect to receive a remote perspective which will be used to call remote methods
        on the DPM server."""
        log.msg('Connection to DPM Server Established')
        self.dpm = perspective
        

        # Test a few functions
        self.dpm.callRemote('setUser', os.getuid(), os.getgid())
        self.dpm.callRemote('analyseImage',
                            'test-5_1_001.img', 
                            DIRECTORY,
                            ).addCallback(self.dump_results)
                            
        _info = {'anomalous':False, 'file_name': 'test-5_1_001.img'}
        self.dpm.callRemote('screenDataset', _info, DIRECTORY).addCallback(self.dump_results)

    def on_connection_failed(self, reason):
        log.msg('Could not connect to DPM Server: %', reason)
          

    def dump_results(self, data):
        """pretty print the data received from the server"""
        log.msg('Server sent: %s' % str(data))


app = App()    
reactor.callWhenRunning(app.setup)
reactor.run()