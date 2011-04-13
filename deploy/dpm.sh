#!/bin/sh

# Set DPM_PATH to the top-level directory containing the DPM modules

export DPM_PATH=/cmcf_apps/dpm-2.1.0
export DPM_CORES=96
export DPM_HOSTS="srv-cmcf-dp1 srv-cmcf-dp2 srv-cmcf-dp3"

export PATH=${PATH}:$DPM_PATH/bin
if [ $PYTHONPATH ]; then
	export PYTHONPATH=${PYTHONPATH}:${DPM_PATH}
else
	export PYTHONPATH=${DPM_PATH}
fi

