"""
DISTL Parser functions

"""
import utils


def parse_distl(filename):
    return utils.parse_file(filename, 'distl.ini')

def parse_distl_string(text):
    return utils.parse_data(text, 'distl.ini')