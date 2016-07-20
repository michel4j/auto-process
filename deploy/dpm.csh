#!/bin/csh

# Set DPM_PATH to the top-level directory containing the DPM modules

setenv DPM_PATH /cmcf_apps/autoprocess-3.3.1

# Set the name of the .login or .profile file which prepares the environment to 
#be able to find all  programs required and set up the paths as appropriate

setenv DPM_ENVIRONMENT ${HOME}/.login

# Configure a list nodes in data processing cluster <hostname-or-ip>:<number of cores>
# Each machine in this list must support password-less private key ssh authentication for the user"

setenv DPM_HOSTS "srv-cmcf-dp1:32 srv-cmcf-dp2:32 srv-cmcf-dp3:32"

# Do not change below here
set path=($path $DPM_PATH/bin)
if ($?PYTHONPATH) then
	setenv PYTHONPATH ${PYTHONPATH}:${DPM_PATH}
else
	setenv PYTHONPATH ${DPM_PATH}
endif
setenv LC_ALL en_US.UTF8