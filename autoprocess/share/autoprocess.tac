#!/usr/bin/env python

# Invoke this script with:
# $ twistd -ny autoprocess.tac

from twisted.application import service
from autoprocess.services.server import get_service

# prepare service for twistd
application = service.Application('Data Processing Server')
service = get_service()
service.setServiceParent(application)


