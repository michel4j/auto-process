#!/bin/sh
alias () { eval `echo $1; shift; echo '() { ' $*; echo '; }'` ; }

# Set DPM_PATH to the top-level directory containing the DPM modules

export DPM_PATH=/opt/cmcf_apps/dpm
PATH=${PATH}:${DPM_PATH}
alias autoxds 'autoprocess.py'
alias autoprocess 'autoprocess.py'

