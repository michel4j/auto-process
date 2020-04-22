"""
DISTL Parser functions

"""
from . import parser


def parse_distl(filename):
    return parser.parse(filename, 'distl')


def parse_distl_string(text):
    return parser.parse_text(text, 'distl')
