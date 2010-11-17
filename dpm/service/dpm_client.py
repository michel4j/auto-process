from twisted.internet import glib2reactor
glib2reactor.install()

from twisted.spread import pb
from twisted.internet import reactor
from twisted.python import log
from bcm.utils import mdns
import sys, os
from dpm.service.common import InvalidUser, CommandFailed

log.FileLogObserver(sys.stdout).start()

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
        self.factory.getRootObject().addCallback(self.on_dpm_connected).addErrback(self.dump_error)
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
        _service_data = {'user': 'cmcfadmin', 
                         'uid': 500, 
                         'gid': 500, 
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
        self.dpm.callRemote('setUser', 'cmcfadmin').addCallback(self.dump_results).addErrback(self.dump_error)
        
        # Try one that will succeed
        self.dpm.callRemote('analyseImage',
                            '/users/cmcfadmin/Sep29-2010/c12test/data/c12test_001.img', 
                            '/users/cmcfadmin/Sep29-2010/c12test/scrn',
                            ).addCallback(self.dump_results).addErrback(self.dump_error)
        
        # Try one that will fail
        self.dpm.callRemote('analyseImage',
                            '/users/cmcfadmin/Sep29-2010/c12test/data/c12test_abc.img', 
                            '/users/cmcfadmin/Sep29-2010/c12test/scrn',
                            'cmcfadmin',
                            ).addCallback(self.dump_results).addErrback(self.dump_error)
                            
        _info = {'anomalous':False,
                 'mad': False,
                 'file_names': 
                    ('/users/cmcfadmin/Sep29-2010/c12test/data/c12test_001.img',),
                }
        self.dpm.callRemote('screenDataset',
                            _info, 
                            '/users/cmcfadmin/Sep29-2010/c12test/proc',
                            'cmcfadmin'
                            ).addCallback(self.dump_results).addErrback(self.dump_error)

    def on_connection_failed(self, reason):
        log.msg('Could not connect to DPM Server: %', reason)
          

    def dump_results(self, data):
        """pretty print the data received from the server"""
        import pprint
        pp = pprint.PrettyPrinter(indent=4, depth=4)
        log.msg('Server sent: %s' % pp.pformat(data))

    def dump_error(self, failure):
        r = failure.trap(InvalidUser, CommandFailed)
        log.err('<%s -- %s>.' % (r, failure.getErrorMessage()))

app = App()    
reactor.callWhenRunning(app.setup)
reactor.run()