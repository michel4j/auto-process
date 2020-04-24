import atexit
import ipaddress

from zeroconf import Zeroconf, ServiceInfo

ZCONF = Zeroconf()


class Provider(object):
    """
    Multi-cast DNS Service Provider

    Provide a multicast DNS service with the given name and type listening on the given
    port with additional information in the data record.

    :param name: Name of service
    :param service_type: Service Type string
    :param port: Service port

    Kwargs:
        - data: Additional data to make available to clients
        - unique: bool, only one permitted, collisoin if more than one
    """

    def __init__(self, name, service_type, port, data=None, unique=False, delay=1):
        super().__init__()
        self.name = name
        data = data or {}
        self.info = ServiceInfo(
            service_type,
            "{}.{}".format(name, service_type),
            addresses=[ipaddress.ip_address("127.0.0.1").packed],
            port=port,
            properties=data
        )
        self.add_service(unique)

    def add_service(self, unique=False):
        """
        Add a the service
        """
        try:
            ZCONF.register_service(self.info, allow_name_change=not unique)
        except:
            print('Collision')

    def __del__(self):
        ZCONF.unregister_service(self.info)


def cleanup_zeroconf():
    ZCONF.close()


atexit.register(cleanup_zeroconf)

__all__ = ['Provider']
