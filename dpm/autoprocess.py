#!/usr/bin/env python


import sys
import os
import warnings
warnings.simplefilter("ignore") # ignore deprecation warnings
    
from dpm.engine.process import Manager
from dpm.utils.log import log_to_console, log_to_file
from dpm.utils.options import process_options

def main():
    # Parse options
    options = process_options(sys.argv[1:])        
    app = Manager(options)
    app.run()      
       
if __name__ == "__main__":
    try:
        log_to_console()
        main()
    except KeyboardInterrupt:
        sys.exit(1)
