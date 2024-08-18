#!/bin/bash

# scp ./starrocks-fe.jar sr@<ip>:/home/disk1/sr/fe/
#scp ./starrocks-fe.jar sr@172.26.95.251:/home/disk1/sr/fe/
set -e
set -x
commond=$1
ip=$2
ssh sr@$2 "$commond"