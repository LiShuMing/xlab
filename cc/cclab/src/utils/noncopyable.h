#pragma once

namespace xlab {

  class NonCopyable {
    protected:
      NonCopyable() {}
      ~NonCopyable() {}

    private:
      NonCopyable (const NonCopyable&);
      NonCopyable &operator=(const NonCopyable&);
  };

  class Copyable {};

  class StaticClass {
    protected:
      ~StaticClass() {}

    private:
      StaticClass();
      StaticClass(const StaticClass &);
      StaticClass &operator=(const StaticClass &);
  };

} // namespace xlab