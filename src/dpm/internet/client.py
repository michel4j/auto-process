from twisted.spread import pb
from twisted.internet import reactor
import sys

def gotObject(object):
    print 'got object:', object
    object.callRemote('setUser',1, 1).addCallback(gotData)
    object.callRemote('analyseImage', 'insulin_1_E0_0060.img', '/home/michel/Code/auto_process_sandbox/data').addCallback(printResults)

def gotData(data):
    print 'server sent:', data
    print data.firstName, data.lastName, data.dateOfBirth

def printResults(data):
    print data[0], data[1]
    reactor.stop()
    
def gotNoObject(reason):
    print 'no object:', reason
    reactor.stop()


factory = pb.PBClientFactory()
reactor.connectTCP('localhost', 8889, factory)
factory.getRootObject().addCallbacks(gotObject,gotNoObject)
reactor.run()
