#include <iostream>
#include <string>
#include <vector>

#ifdef SRLAB_USE_FMT
#include <fmt/core.h>
#endif

#ifdef SRLAB_USE_ABSL_STRINGS
#include <absl/strings/str_join.h>
#endif

int main()
{
    std::vector<std::string> words{"Hello", "from", "SR", "Lab"};

#ifdef SRLAB_USE_ABSL_STRINGS
    auto message = absl::StrJoin(words, " ");
#elif defined(SRLAB_USE_FMT)
    auto message = fmt::format("{} {} {} {}", words[0], words[1], words[2], words[3]);
#else
    std::string message;
    for(auto it = words.begin(); it != words.end(); ++it)
    {
        message += *it;
        if(std::next(it) != words.end())
        {
            message += ' ';
        }
    }
#endif

    std::cout << message << std::endl;
    return 0;
}

