
import os
from dpm.utils import dataset
from dpm.utils import odict
from dpm.utils.log import get_module_logger
import dpm.errors

_logger = get_module_logger(__name__)

class DataSet(object):
    def __init__(self, filename, overwrites={}):
        self.parameters = dataset.get_parameters(filename)
        self.parameters.update(overwrites)
        self.name = self.parameters['name']
    
    def __str__(self):
        return "<DataSet: %s, %s, first=%d, n=%d>" % (self.name, self.parameters['file_template'],
                                             self.parameters['first_frame'], 
                                             self.parameters['frame_count'])
    

class Manager(object):
    def __init__(self, options={}, overwrites={}):
        self.options = options
        self.datasets = odict.SortedDict()
        for img in options.get('images', []):
            dset = DataSet(img, overwrites)
            self.add_dataset(dset)
        
        # prepare top level working directory
        if self.options.get('directory', None) is None:
            if self.options.get('mode', 'simple') == 'screen':
                _suffix = 'scrn'
            else: 
                _suffix = 'proc'
            _prefix = os.path.commonprefix(self.datasets.keys())
            if _prefix == '':
                _prefix = '_'.join(self.datasets.keys())
            elif _prefix[-1] == '_':
                _prefix = _prefix[:-1]
                
            self.options['directory'] = os.path.join(os.getcwd(), '%s-%s' % (_prefix, _suffix))
        
        # Check if top_level directory exists and act accordingly
        if not os.path.isdir(self.options['directory']) or self.options.get('backup', False):
            try:
                dataset.prepare_dir(self.options['direcoty'], self.options.get('backup', False))
            except:
                _logger.error("Could not prepare working directory '%s'." % self.options['directory'])                  
                raise dpm.errors.FilesystemError('Could not prepare working directory')
    
    def add_dataset(self, obj):
        self.datasets[obj.name] = obj
    
    def run(self):
        for dset in self.datasets.values():
            print dset
            