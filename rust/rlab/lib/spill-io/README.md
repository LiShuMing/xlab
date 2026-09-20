# spill-io

`spill-io` 是 Join、Aggregate、Sort 等外存算法共享的物理 I/O 层，不包含任何具体算子的状态机或记录格式。

公共职责：

- `SpillDirectory`：创建唯一临时目录并在 Drop 时清理；
- `SpillFile`：受目录管理的文件句柄；
- `SpillCodec<T>`：由算子实现的逻辑记录编解码协议；
- `SpillWriter<T, C>` / `SpillReader<T, C>`：缓冲顺序 I/O；
- `SpillWriteStats` / `SpillReadStats`：记录数和编码字节数。

算法层仍负责：

- Hash Join/Aggregate 的分区函数、恢复顺序和递归策略；
- Sort 的 run generation、排序与多路归并；
- 内存预算、倾斜处理、压缩选择和调度。

基本用法：

```rust
use spill_io::{SpillCodec, SpillDirectory, SpillReader, SpillWriter};
use std::io::{self, Read, Write};

struct U64Codec;

impl SpillCodec<u64> for U64Codec {
    fn encode<W: Write>(&self, value: &u64, out: &mut W) -> io::Result<()> {
        out.write_all(&value.to_le_bytes())
    }

    fn decode<R: Read>(&self, input: &mut R) -> io::Result<Option<u64>> {
        let mut bytes = [0_u8; 8];
        if input.read(&mut bytes[..1])? == 0 {
            return Ok(None);
        }
        input.read_exact(&mut bytes[1..])?;
        Ok(Some(u64::from_le_bytes(bytes)))
    }
}

let mut directory = SpillDirectory::new("sort")?;
let run = directory.create_file("run-0")?;
let mut writer = SpillWriter::create(&run, U64Codec)?;
writer.write(&42)?;
writer.finish()?;

let mut reader = SpillReader::open(&run, U64Codec)?;
assert_eq!(reader.read_next()?, Some(42));
# Ok::<(), io::Error>(())
```
