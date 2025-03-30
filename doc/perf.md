
# Perf

```
perf script
perf report
perf annotate

sudo perf record -ag -F 999 -- sleep 2
sudo perf script

sudo strace -o strace perf script

```
### 差分火焰图
```
# 第一次Profiling结果
perf record -ag -F 999 -- sleep 20
perf script > A.stacks

# 第二次Profiling结果
perf record -ag -F 999 -- sleep 20
perf script > B.stacks


# 下载FlameGraph仓库
git clone --depth 1 http://github.com/brendangregg/FlameGraph 
# 折叠A.stacks和B.stacks
cd FlameGraph 
./stackcollapse-perf.pl ../A.stacks > A.folded
./stackcollapse-perf.pl ../B.stacks > B.folded

# 基于折叠结果做差
./difffolded.pl A.folded B.folded > diff.folded

# 生成差分火焰图
./flamegraph.pl diff.folded > diff.svg
```

# strace