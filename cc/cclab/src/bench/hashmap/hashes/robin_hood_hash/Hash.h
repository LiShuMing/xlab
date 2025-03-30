#pragma once

#include "common/map/robin_hood_map.h"

static const char* HashName = "robin_hood::hash";

template <class Key>
using Hash = robin_hood::hash<Key>;
