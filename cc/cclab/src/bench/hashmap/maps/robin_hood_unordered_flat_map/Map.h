#pragma once

#include "Hash.h"
#include "common/map/robin_hood_map.h"

static const char* MapName = "robin_hood::unordered_flat_map";

template <class Key, class Val>
using Map = robin_hood::unordered_flat_map<Key, Val, Hash<Key>>;
