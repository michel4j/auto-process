#!/bin/sh

# Set DPM_PATH to the top-level directory containing the DPM modules

export DPM_PATH=/cmcf_apps/autoprocess-3.3.1

# Set the name of the .bash_profile or .profile file which prepares the environment to 
# be able to find all  programs required and set up the paths as appropriate

export DPM_ENVIRONMENT=${HOME}/.bash_profile

# Configure a list nodes in data processing cluster <hostname-or-ip>:<number of cores>
# Each machine in this list must support password-less private key ssh authentication for the user"

export DPM_HOSTS="srv-cmcf-dp1:32 srv-cmcf-dp2:32 srv-cmcf-dp3:32"

# Do not change below here
export PATH=${PATH}:$DPM_PATH/bin
if [ $PYTHONPATH ]; then
	export PYTHONPATH=${PYTHONPATH}:${DPM_PATH}
else
	export PYTHONPATH=${DPM_PATH}
fi
export LC_ALL=en_US.UTF8
