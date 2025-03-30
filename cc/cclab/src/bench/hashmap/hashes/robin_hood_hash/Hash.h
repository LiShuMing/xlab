#pragma once

#include "common/hash/robin_hood.h"

static const char* HashName = "robin_hood::hash";

template <class Key>
using Hash = robin_hood::hash<Key>;
