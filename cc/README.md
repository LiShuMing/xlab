# C++ Code Collection

A collection of C++ projects, experiments, and reference implementations covering algorithms, data structures, system programming, and more.

## Submodules

### Core Projects

- **[algo/](algo/README.md)** - Algorithm implementations including LeetCode solutions, LCR problems, and common algorithm patterns
- **[cclab/](cclab/README.md)** - C++ laboratory with data structures, benchmarks, and utilities
- **[cpython/](cpython/README.md)** - Python C extensions and embedding examples
- **[interpreter/](interpreter/README.md)** - Custom interpreter implementation with lexer, parser, and AST
- **[io_uring/](io_uring/README.md)** - C++20 wrapper for Linux io_uring with coroutines support
- **[srlab/](srlab/README.md)** - CMake-based C++ project scaffold with third-party dependencies
- **[write-a-C-interpreter/](write-a-C-interpreter/README.md)** - C interpreter that interprets itself (tutorial project)
- **[gpt-extension/](gpt-extension/README.md)** - Chrome extension for AI side panel

### Third-Party Dependencies

The `thirdparty/` directory contains various third-party libraries and dependencies used across projects.

## Reference Links

### Libraries
- https://github.com/yhirose/cpp-httplib
- https://github.com/taskflow/taskflow
- https://github.com/greg7mdp/parallel-hashmap
- https://github.com/q191201771/libchef

### External Repositories
- git clone git@github.com:TheAlgorithms/C-Plus-Plus.git
- git clone git@github.com:sgmarz/osblog.git
- git clone git@github.com:baidu/babylon.git
- git clone git@github.com:tontinton/dbeel.git
- git clone git@github.com:simd-everywhere/simde.git

## Directory Structure

```
cc/
├── algo/              # Algorithm implementations
├── cclab/             # C++ lab experiments
├── cpython/           # Python C extensions
├── gpt-extension/     # Chrome extension
├── interpreter/       # Custom interpreter
├── io_uring/          # io_uring wrapper
├── srlab/             # CMake scaffold project
├── write-a-C-interpreter/  # C interpreter tutorial
└── thirdparty/        # Third-party dependencies
```

## Getting Started

Each submodule has its own README with specific build and usage instructions. Navigate to the submodule directory and refer to its README.md for details.

## Requirements

- C++17/20 compiler (GCC or Clang)
- CMake 3.12+ (for most projects)
- Linux (for io_uring)
- Python 3.x (for cpython module)
