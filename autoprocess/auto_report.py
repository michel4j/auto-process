#!/usr/bin/env python


import os
import sys
import warnings

warnings.simplefilter("ignore")  # ignore deprecation warnings
from autoprocess.utils import log, misc
from autoprocess.engine import reporting

_logger = log.get_module_logger('auto.report')

REPORT_USAGE = """
auto.report [path/to/process.chkpt]

Description:  
    Generate HTML reports from a "process.chkpt" harvest file.

Arguments:
    Default (no argument): Tries to read "process.chkpt" from current directory.

Examples:
    auto.report
        If run within a directory which contains a process.chkpt file.        
    auto.report process.chkpt
    auto.report /foo/bar/process.chkpt

"""


def main():
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = 'process.chkpt'

    try:
        data = misc.load_chkpt()
        options = {'command_dir': os.getcwd()}
        reporting.save_report(data['datasets'], data['options'])
        # reporting.save_html(report_list, options)
    except IOError:
        _logger.error('Harvest file "process.json" file does not exist.')
        print(REPORT_USAGE)
        sys.exit(1)


def run():
    try:
        log.log_to_console()
        main()
    except KeyboardInterrupt:
        sys.exit(1)
