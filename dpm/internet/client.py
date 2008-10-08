from twisted.spread import pb
from twisted.internet import reactor
import sys, os
from gnosis.xml import pickle

def gotObject(object):
    print 'Connection to DPM Server Established', object
    object.callRemote('setUser', os.getuid(), os.getgid()).addCallback(gotData)
    object.callRemote('analyseImage', '/users/cmcfadmin/reference_data/insul1/insul_0.2_1_E0_0287.img', '/tmp').addCallback(printResults)
    #object.callRemote('screenCrystal', '/users/cmcfadmin/reference_data/insul1/insul_0.2_1_E0_0287.img', '/tmp').addCallback(printResults2)
    #object.callRemote('processDataset', '/users/cmcfadmin/reference_data/insul1/insul_0.2_1_E0_0287.img', '/tmp').addCallback(printResults2)
    
def gotData(data):
    print 'server sent:', data

def printResults(data):
    results = pickle.loads(data)
    print results

def printResults2(data):
    print data
        
def gotNoObject(reason):
    print 'no object:', reason


factory = pb.PBClientFactory()
reactor.connectTCP('ioc1608-301', 8889, factory)
factory.getRootObject().addCallbacks(gotObject,gotNoObject)
reactor.run()
