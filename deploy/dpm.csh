#!/bin/csh

# Set DPM_PATH to the top-level directory containing the DPM modules

setenv DPM_PATH $HOME/Code/eclipse-ws/data-analysis-module
setenv DPM_CORES 96
setenv DPM_HOSTS "srv-cmcf-dp1 srv-cmcf-dp2 srv-cmcf-dp3"

set path=($path $DPM_PATH/bin)
if ($?PYTHONPATH) then
	setenv PYTHONPATH ${PYTHONPATH}:${DPM_PATH}
else
	setenv PYTHONPATH ${DPM_PATH}
endif
