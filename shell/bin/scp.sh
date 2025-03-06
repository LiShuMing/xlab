#!/bin/bash

# scp ./starrocks-fe.jar sr@<ip>:/home/disk1/sr/fe/
#scp ./starrocks-fe.jar sr@172.26.95.251:/home/disk1/sr/fe/
dir=$1
file=$2
ip=$3
scp $2 sr@$3:/home/disk1/sr/$1
