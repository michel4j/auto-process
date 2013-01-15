#!/bin/sh

# Set DPM_PATH to the top-level directory containing the DPM modules

export DPM_PATH=/cmcf_apps/dpm-3
export DPM_HOSTS="srv-cmcf-dp1:32 srv-cmcf-dp2:32 srv-cmcf-dp3:32"

export PATH=${PATH}:$DPM_PATH/bin
if [ $PYTHONPATH ]; then
	export PYTHONPATH=${PYTHONPATH}:${DPM_PATH}
else
	export PYTHONPATH=${DPM_PATH}
fi

