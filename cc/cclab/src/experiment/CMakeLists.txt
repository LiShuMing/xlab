message(STATUS "link_libs=${link_libs}")

add_library(
   experiment
   helloworld.cc
)

set(ALL_OBJECT_FILES
    ${ALL_OBJECT_FILES} $<TARGET_OBJECTS:experiment>
    PARENT_SCOPE)
