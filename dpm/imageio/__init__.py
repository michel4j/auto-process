from dpm.utils import magic
import marccd, smv
_magic_map = {
    'SMV Area Detector Image' : smv.read_header,
    'MAR Area Detector Image' : smv.read_header,
}

def read_header(filename):
    full_id = magic.from_file(filename).strip()
    key = full_id.split(', ')[0]
    if _magic_map.get(key) is not None:
        func = _magic_map.get(key)
        info = func(filename)
        return info
    else:
        print 'AutoXDS|File format not recognized'
        sys.exit(1)
