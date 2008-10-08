from twisted.spread import pb
from twisted.internet import reactor
import sys, os
from gnosis.xml import pickle

def gotObject(object):
    print 'Connection to DPM Server Established', object
    object.callRemote('setUser', os.getuid(), os.getgid()).addCallback(gotData)
    object.callRemote('analyseImage', '/home/michel/data/Mof/Mof_Se6_3_peak_0001.img', '/tmp/2').addCallback(printResults)
    object.callRemote('screenCrystal', '/home/michel/data/Mof/Mof_Se6_3_peak_0001.img', '/tmp/2').addCallback(printResults2)
    object.callRemote('processDataset', '/home/michel/data/h14/h14_1_peak_0302.img', '/tmp/1').addCallback(printResults2)
    object.callRemote('analyseImage', '/home/michel/data/h14/h14_1_peak_0302.img', '/tmp/1').addCallback(printResults)

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
reactor.connectTCP('localhost', 8889, factory)
factory.getRootObject().addCallbacks(gotObject,gotNoObject)
reactor.run()
