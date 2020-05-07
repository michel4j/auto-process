import re
import socket

from autoprocess.utils.log import get_module_logger
from twisted.internet import reactor
from twisted.spread import pb

logger = get_module_logger(__name__)


class ServerClientFactory(pb.PBClientFactory):
    def buildProtocol(self, addr):
        broker = pb.PBClientFactory.buildProtocol(self, addr)
        pb.PBClientFactory.clientConnectionMade(self, broker)
        return broker


class PBClient(object):
    """
    A Perspective Broker Client

    :param address:  string representing the <address>:<port> of the server
    """
    NAME = 'PB Server'

    def __init__(self, address):
        super().__init__()
        self.address = address
        self.name = self.NAME
        self.connection = None
        self.factory = None
        self.service_data = {}

        self.retry_delay = 5.0
        self.retry_count = 0
        self.max_retries = 8640
        self.retrying = False

        m = re.match(r'([\w.\-_]+):(\d+)', address)
        if m:
            try:
                addr = socket.gethostbyname(m.group(1))
            except socket.gaierror as err:
                logger.error(err)
                addr = m.group(1)

            data = {
                'name': self.name,
                'host': m.group(1),
                'address': addr,
                'port': int(m.group(2)),
            }
            self.setup_service(data)

    def retry(self):
        self.retrying = True
        if self.retry_count < self.max_retries and not self.active:
            logger.debug('Re-trying connection to {} [{host}:{port}]'.format(self.name, **self.service_data))
            self.setup_service(self.service_data)
            self.retry_count += 1
            return True
        self.retrying = False

    def setup_service(self, data):
        self.service_data = data
        if not self.active:
            self.factory = ServerClientFactory()
            self.factory.getRootObject().addCallback(self.on_connect).addErrback(self.on_failure)
            reactor.connectTCP(self.service_data['address'], self.service_data['port'], self.factory)

    def on_connect(self, perspective):
        """
        I am called when a connection to the AutoProcess Server has been established.
        I expect to receive a remote perspective which will be used to call remote methods
        on the DPM server.
        """
        logger.info('{} {host}:{port} connected.'.format(self.name, **self.service_data))
        self.service = perspective
        self.service.notifyOnDisconnect(self.on_disconnect)
        self.active=True
        self.retry_count = 0

    def on_disconnect(self, obj):
        """Used to detect disconnections if MDNS is not being used."""
        self.active = False
        logger.warning('Connection to {} disconnected'.format(self.name))
        reactor.callLater(self.retry_delay, self.retry)

    def on_failure(self, reason):
        if not self.retrying:
            logger.error('Connection to {} failed'.format(self.name))
            logger.error(reason)
            reactor.callLater(self.retry_delay, self.retry)


class DPClient(PBClient):
    """
    Data Processing Server Client
    """
    NAME = 'Data Analysis Server Client'

    def analyse_frame(self, frame_path, user_name, rastering=False):
        """
        Analyse diffraction frame

        :param frame_path: full path to frame
        :param user_name: user name to run as
        :params rastering: If True, perform scoring for rastering
        :return: a dictionary representing the processing report
        """
        return self.service.callRemote('analyse_frame', frame_path, user_name, rastering=rastering)

    def process_xrd(self, info, directory, user_name):
        """
        Process an XRD dataset

        :param info: dictionary containing parameters
        :param directory: directory for output
        :param user_name: user name to run as
        :return: a dictionary of the report
        """

        return self.service.callRemote('process_xrd', info, directory, user_name)

    def process_mx(self, info, directory, user_name):
        """
        Process an MX dataset

        :param info: dictionary containing parameters
        :param directory: directory for output
        :param user_name: user name to run as
        :return: dictionary containing the report
        """
        return self.service.callRemote('process_mx', info, directory, user_name)

    def process_misc(self, *args, **kwargs):
        return self.service.callRemote('process_misc', *args, **kwargs)

