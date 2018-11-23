#!/bin/csh
# Format is "<host1-name>:<number of cores> <host2-name>:<number of cores> ..."
setenv DPS_HOSTS "HPC1608-001:112 HPC1608-002:112 HPC1608-002:112"
setenv DPS_PATH /cmcf_apps/AutoProcess-4

set path=($path $DPS_PATH/bin)
setenv LC_ALL en_US.UTF8