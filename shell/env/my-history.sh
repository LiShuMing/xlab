# sudo docker run 172.26.92.142:5000/xianpengshen/clang-tools:19 clang-format --version
# sudo docker run -it -v ~/.m2:/root/.m2 -v $(pwd)/work:/root/work --name clang-dev -d 172.26.92.142:5000/xianpengshen/clang-tools:19
# sudo docker pull 172.26.92.142:5000/xianpengshen/clang-tools:19
# sudo docker run -it -v ~/.m2:/root/.m2 -v $(pwd)/work:/root/work --name clang-dev -d xianpengshen/clang-tools:19
sudo docker run --cap-add SYS_ADMIN -it -v ~/.m2:/root/.m2 -v $(pwd)/work:/root/work --name lism-dev -d 172.26.92.142:5000/starrocks/dev-env-ubuntu

wget https://github.com/Kitware/CMake/releases/download/v3.25.0/cmake-3.25.0-linux-x86_64.sh
chmod +x cmake-3.25.0-linux-x86_64.sh
./cmake-3.25.0-linux-x86_64.sh --prefix=/usr/local --skip-license

/usr/bin/cmake
/usr/local/bin/cmake --version

update-alternatives --install /usr/bin/cc cc /usr/bin/clang-19 100
update-alternatives --install /usr/bin/c++ c++ /usr/bin/clang++-19 100