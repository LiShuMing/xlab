export module helloworld; // module declaration
 
// import <iostream>;        // import declaration
#include <iostream>
 
export void hello()       // export declaration
{
    std::cout << "Hello world!\n";
}