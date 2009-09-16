#!/bin/csh

# Set DPM_PATH to the top-level directory containing the DPM modules

setenv DPM_PATH $HOME/Code/eclipse-ws/data-analysis-module

set path=($path $DPM_PATH/bin)
if ($?PYTHONPATH) then
	setenv PYTHONPATH ${PYTHONPATH}:${DPM_PATH}
else
	setenv PYTHONPATH ${DPM_PATH}
endif
