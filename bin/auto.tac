#!/usr/bin/env python

# Invoke this script with:
# $ twistd -ny auto.tac

from twisted.application import service
from autoprocess.services.server import get_service
from autoprocess.utils import mdns

# publish service
provider = mdns.Provider('Data Processing Server', '_autoprocess._tcp.local.', 9991)

# prepare service for twistd
application = service.Application('Data Processing Server')
service = get_service()
service.setServiceParent(application)


