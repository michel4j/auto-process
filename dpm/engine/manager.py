'''
Created on Jun 20, 2011

@author: michel
'''
from dpm.utils import 
class DataSet(object):
    def __init__(self, params={}):
        self.parameters = params
    
    def get_from_file(self, filename):
        