# Summary: Removal of p2023/p2024 Partitions from 1.json

## Task
Read the `1.json` file and remove all partitions related to p2023/p2024, while preserving the JSON format.

## Solution
Created a Python script (`remove_p2023_p2024_partitions_v3.py`) that:
1. Reads the content of `1.json`
2. Uses regex patterns to identify and remove all partitions with names starting with "p2023" or "p2024"
3. Preserves all other content and formatting
4. Writes the cleaned content to `1_cleaned.json`

## Results
- Successfully removed all partitions related to p2023/p2024 (e.g., `PARTITION p20230601 VALUES [("20230601"), ("20230602"))`)
- Preserved partitions for other years (e.g., 2025)
- Maintained the JSON format and structure
- Output saved to `1_cleaned.json`

## Verification
- Confirmed that `grep -c "PARTITION p2023\|PARTITION p2024" 1_cleaned.json` returns 0
- Confirmed that `grep -c "PARTITION p2025" 1_cleaned.json` returns 1