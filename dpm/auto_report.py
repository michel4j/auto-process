#!/usr/bin/env python


import sys
import os
import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings
from dpm.utils import log, misc
from dpm.engine import reporting

_logger = log.get_module_logger('auto.report')

REPORT_USAGE = """
auto.report [path/to/process.json]

Description:  
    Generate HTML reports from a "process.json" harvest file.

Arguments:
    Default (no argument): Tries to read "process.json" from current directory.

Examples:
    auto.report
        If run within a directory which contains a process.json file.        
    auto.report process.json
    auto.report /foo/bar/process.json

"""

def main():
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        json_file = 'process.json'
        
    try:
        data = misc.json.load(file(json_file))
        report_list = data.get('result', [])
        options = {'command_dir': os.getcwd()}
        reporting.save_html(report_list, options)
    except IOError:
        _logger.error('Harvest file "process.json" file does not exist.')
        print REPORT_USAGE
        sys.exit(1)  
     
if __name__ == "__main__":
    try:
        log.log_to_console()
        main()
    except KeyboardInterrupt:
        sys.exit(1)