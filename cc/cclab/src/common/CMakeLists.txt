message(STATUS "link_libs=${link_libs}")

add_library(common
   consistent_hash/consistent_hash.cc
   skiplist/SkipList.cc
   btree/bplustree.cc
)

target_link_libraries(common PRIVATE ${link_libs})

set(ALL_OBJECT_FILES
    ${ALL_OBJECT_FILES} $<TARGET_OBJECTS:common>
    PARENT_SCOPE)
