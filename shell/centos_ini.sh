#!/bin/bash
yum update

# todo: how to compile with gcc 10
yum install -y protobuf-devel protobuf-compiler
yum install -y gflags-devel
yum install -y libasan libasan8
yum install -y libunwind-devel pkg-config libssl-devel
yum install -y libboost-atomic-devel
yum install -y pip 
#yum install -y zsh screen


# # Install GCC 10
export LD_LIBRARY_PATH=/opt/rh/gcc-toolset-10/root/usr/lib64:$LD_LIBRARY_PATH
