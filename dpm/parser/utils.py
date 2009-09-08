"""\
Utilties used by the Parser

Scanf: Small scanf-implementation.
  
"""

import re
import sys
from scipy import interpolate
from dpm.utils.configobj import ConfigObj
import numpy
import os

INI_DIR = os.path.join(os.path.dirname(__file__), 'data')

DEBUG = False

# Cache formats
SCANF_CACHE_SIZE = 1000
scanf_cache = {}


scanf_translate = [
    (re.compile(_token), _pattern, _cast) for _token, _pattern, _cast in [
    ("%c", "(.)", lambda x:x),
    ("%(\d+)c", "(.{%s})", lambda x:x),
    ("%(\d+)[di]", "([-+ \d]{%s})", int),
    ("%[di]", "([-+]?\d+)", int),
    ("%u", "(\d+)", int),
    ("%f", "(\d+\.\d+)", float),
    ("%[geE]", "(\s*-?\d+\.\d+[eE][-+]?\d+])", float),
    ("%(\d+)f", "([-+ \d.]{%s})", float),
    ("%(\d+)e", "([-+ \d\.eE]{%s})", float),
    ("%s", "(\S+)", lambda x:x),
    ("%([xX])", "(0%s[\dA-Za-f]+)", lambda x:int(x, 16)),
    ("%o", "(0[0-7]*)", lambda x:int(x, 7)),
    ]]


def _scanf_compile(format):
    """
    This is an internal function which translates the format into regular expressions
    
    For example:
    >>> format_re, casts = _scanf_compile('%s - %d errors, %d warnings')
    >>> print format_re.pattern
    (\S+) \- ([+-]?\d+) errors, ([+-]?\d+) warnings
    
    Translated formats are cached for faster use
    
    """
    compiled = scanf_cache.get(format)
    if compiled:
        return compiled

    format_pat = ""
    cast_list = []
    i = 0
    length = len(format)
    while i < length:
        found = None
        for token, pattern, cast in scanf_translate:
            found = token.match(format, i)
            if found:
                cast_list.append(cast)
                groups = found.groupdict() or found.groups()
                if groups:
                    pattern = pattern % groups
                format_pat += pattern
                i = found.end()
                break
        if not found:
            char = format[i]
            # escape special characters
            if char in "()[]-.+*?{}<>\\":
                format_pat += "\\"
            format_pat += char
            i += 1
    if DEBUG:
        print "DEBUG: %r -> %s" % (format, format_pat)
    format_re = re.compile(format_pat)
    if len(scanf_cache) > SCANF_CACHE_SIZE:
        scanf_cache.clear()
    scanf_cache[format] = (format_re, cast_list)
    return format_re, cast_list



def scanf(format, s, position=0):
    """
    scanf supports the following formats:
      %c       One character
      %5c      5 characters
      %d       int value
      %7d      int value with length 7
      %f       float value
      %5f      float value of length 5
      %o       octal value
      %X, %x   hex value
      %s       string terminated by whitespace

    Examples:
    >>> scanf("%s - %d errors, %d warnings", "/usr/sbin/sendmail - 0 errors, 4 warnings")
    ('/usr/sbin/sendmail', 0, 4)
    >>> scanf("%o %x %d", "0123 0x123 123")
    (66, 291, 123)

    If the parameter s is a file-like object, s.readline is called.
    If s is not specified, stdin is assumed.

    The function returns the tuple (a tuple of found values, position)
    or the tuple (None, position) if the format does not match.
    
    """
            
    if hasattr(s, "readlines"): s = ''.join(s.readlines())

    format_re, casts = _scanf_compile(format)
        
    found= format_re.search(s, position)
    if found:
        groups = found.groups()
        result = tuple([casts[i](groups[i]) for i in range(len(groups))])
        return result, found.end()
    else:
        return None, position


def load_file(filename):
    """ 
    Read a text file into a string
    
    """
    try:
        f = open(filename,'r')
        data = ''.join(f.readlines())
        f.close()
    except:
        print 'ERROR: Could not open', filename
        data = ''
    return data

def cut_section(start, end, s, position=0):
    """
    extract the piece of text between start pattern and end pattern starting at
    position <position>
    returns a tuple (subsection, end-position)
    
    """
    result = ('', 0)        
    start_re = re.compile(start)
    end_re = re.compile(end)

    start_m = start_re.search(s, position)
    if start_m:
        position = start_m.start()
        end_m = end_re.search(s, position)
        if end_m:
            result = (s[start_m.start():end_m.start()], end_m.end())
        else:
            result = (s[start_m.start():start_m.end()], start_m.end())
    else:
        result = ('', position)
    return result
   
def cast_params(param_list, values):
    """
    takes a list of tuples containing a variable name and tuple length
    and a tuple or list of values
    returns a dictionary with names mapped to values and tuples as specified
    example: cast_params( [('name',1),('date',3')], ('michel', 10,10,2008) )
    will return {'name': 'michel', 'date': (10,10,2008)}
    
    """
    pos = 0
    params = {}
    for key, length in param_list:
        length = int(length)
        if length == 1:
            params[key] = values[pos]
            pos += 1
        else:
            params[key] = tuple(values[pos:pos+length])
            pos += length
    return params

def interp_array(a, size=25):
    x, y = numpy.mgrid[-1:1:9j,-1:1:9j]
    z = a
    xnew, ynew = numpy.mgrid[-1:1:size*j,-1:1:size*j]
    tck = interpolate.bisplrep(x,y,z,s=0)
    znew = interpolate.bisplev(xnew[:,0], ynew[0,:], tck)
    return znew

def parse_file(filename, config):
    info = {}
    conf = ConfigObj(os.path.join(INI_DIR, config))    
    data = load_file(filename)
    
    for section in conf.keys():
        if section == '_top_':
            for k, pat in conf['_top_'].items():
                _v, _p = scanf(pat, data)
                if _v is not None:
                    if len(_v) == 1:
                        info[k] = _v[0]
                    else:
                        info[k] = _v
                else:
                    info[k] = None
        else:
            params = conf[section]['keys'].items()
            chunk, pos = cut_section(conf[section]['start'], conf[section]['end'], data)
            is_table = conf[section].get('table', None) == "1"
            _v, _p = scanf(conf[section]['body'], chunk)
            if is_table:
                entry = []
                while _v:
                    entry.append( cast_params(params, _v) )
                    _v, _p = scanf(conf[section]['body'], chunk, _p)
                info[section] = entry
            else:
                if _v is not None:
                    entry = cast_params(params, _v)
                    info[section] = entry
    return info

class Table(object):
    def __init__(self, t):
        self._table = t

    def __getitem__(self, s):
        vals = [r[s] for r in self._table]
        return vals
        
