import json
path = "/home/disk1/lishuming/work/StarRocks/clangd_diagnostics.json"

"""
[
  {
    "file": "/home/disk1/lishuming/work/StarRocks/be/test/util/coding_test.cpp",
    "line": 18,
    "column": 0,
    "level": "error",
    "error_code": "pp_file_not_found",
    "message": "'util/coding.h' file not found"
  },
  {
    "file": "/home/disk1/lishuming/work/StarRocks/be/test/util/coding_test.cpp",
    "line": 19,
    "column": 0,
    "level": "error",
    "error_code": "pp_file_not_found",
    "message": "'util/coding.h' file not found"
  }
]
"""

# group by file, sum
grouped_data = {}
with open(path, 'r') as f:
    data = json.load(f)
    for item in data:
        key = (item['file'])
        content = (item['line'], item['column'], item['level'], item['error_code'], item['message'])    
        if key not in grouped_data:
            grouped_data[key] = []
        grouped_data[key].append(content)

# to json  
with open('grouped_data.json', 'w') as f:
    json.dump(grouped_data, f)