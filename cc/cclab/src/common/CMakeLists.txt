message(STATUS "link_libs=${link_libs}")

add_library_unity(
   common
   common/consistent_hash.cpp
)

set(ALL_OBJECT_FILES
    ${ALL_OBJECT_FILES} $<TARGET_OBJECTS:common>
    PARENT_SCOPE)
