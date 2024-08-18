import json
import re

def remove_p2023_p2024_partitions(file_path, output_path):
    """
    Read a JSON file, remove partitions related to p2023/p2024, and save the result to a new file.
    
    Args:
        file_path (str): Path to the input JSON file
        output_path (str): Path to the output JSON file
    """
    # Read the JSON file
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Pattern to match partitions from p20230101 to p20241231
    partition_pattern = r'PARTITION p202[34]\d{4} VALUES \[\([^)]+\), \([^)]+\)\)[,]*\s*'
    
    # Iterate through all table definitions
    for table_name, table_def in data.get("table_meta", {}).items():
        # Remove p2023/p2024 partitions from the table definition
        cleaned_def = re.sub(partition_pattern, '', table_def)
        
        # Also handle the case where the last partition might not have a comma
        last_partition_pattern = r'PARTITION p202[34]\d{4} VALUES \[\([^)]+\), \([^)]+\)\)\s*'
        cleaned_def = re.sub(last_partition_pattern, '', cleaned_def)
        
        # Update the table definition in the data
        data["table_meta"][table_name] = cleaned_def
    
    # Write the modified data to the output file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Partitions related to p2023/p2024 have been removed. Output saved to {output_path}")

def main():
    input_file = "1.json"
    output_file = "1_cleaned.json"
    
    remove_p2023_p2024_partitions(input_file, output_file)

if __name__ == "__main__":
    main()