#!/bin/sh

export DPS_NODES="HPC1608-001:112 HPC1608-002:112 HPC1608-002:112"
export DPS_PATH=/cmcf_apps/AutoProcess-4

export PATH=${PATH}:$DPS_PATH/bin
export LC_ALL=en_US.UTF8