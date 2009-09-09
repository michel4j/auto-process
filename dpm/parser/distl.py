"""
DISTL Parser functions

"""
import utils


def parse_distl(filename):
    return utils.parse_file(filename, 'distl.ini')
   