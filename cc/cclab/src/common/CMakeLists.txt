message(STATUS "link_libs=${link_libs}")

add_library(
   cc_common
   consistent_hash.cpp
   skiplist/SkipList.cpp
)

set(ALL_OBJECT_FILES
    ${ALL_OBJECT_FILES} $<TARGET_OBJECTS:cc_common>
    PARENT_SCOPE)
