'''
Created on Dec 17, 2010

@author: michel
'''
import re, numpy
import os
import utils

def parse_ctruncate(filename='ctruncate.log'):
    return utils.parse_file(filename, config='ctruncate.ini')
