#!/bin/bash

# scp ./starrocks-fe.jar sr@<ip>:/home/disk1/sr/fe/
#scp ./starrocks-fe.jar sr@172.26.95.251:/home/disk1/sr/fe/
file=$1
ip=$2
scp $1 sr@$2:/home/disk1/sr/fe/