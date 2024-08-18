#pragma once

#include <string>
#include <stdlib.h>

namespace xlab {

  class EnvVar {
    public:
      static bool getenv(const std::string &k, std::string *v);

      static bool setenv(const std::string &k, const std::string &v);

      static bool unsetenv(const std::string &k);

    private:
      EnvVar();
      EnvVar(const EnvVar &);
      EnvVar &operator=(const EnvVar &);

  }; // class EnvVar

} // namespace xlab

namespace xlab {

inline bool EnvVar::getenv(const std::string &k, std::string *v) {
  char *p = ::getenv(k.c_str());
  if (!p) { return false; }

  if (v) { *v = p; }

  return true;
}

inline bool EnvVar::setenv(const std::string &k, const std::string &v) {
  return ::setenv(k.c_str(), v.c_str(), 1) == 0;
}

inline bool EnvVar::unsetenv(const std::string &k) {
  return ::unsetenv(k.c_str()) == 0;
}

} // namespace xlab
