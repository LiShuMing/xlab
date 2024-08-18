docker build \
  --build-arg HTTP_PROXY= \
  --build-arg HTTPS_PROXY= \
  -t ubuntu-clang20-env .

docker run --cap-add SYS_ADMIN -it -v ~/.m2:/root/.m2 -v /Users/lishuming/work/:/root/work --name starrocks-dev -d ubuntu-clang20-env

docker exec -it starrocks-dev /bin/bash

