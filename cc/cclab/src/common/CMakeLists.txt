message(STATUS "link_libs=${link_libs}")

add_library(
   cc_common
   consistent_hash.cc
   skiplist/SkipList.cc
   btree/bplustree.cc
)

set(ALL_OBJECT_FILES
    ${ALL_OBJECT_FILES} $<TARGET_OBJECTS:cc_common>
    PARENT_SCOPE)
