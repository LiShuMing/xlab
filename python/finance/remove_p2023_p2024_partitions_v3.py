import json
import re

def remove_p2023_p2024_partitions(file_path, output_path):
    """
    Read a JSON fragment file, remove partitions related to p2023/p2024, and save the result to a new file.
    
    Args:
        file_path (str): Path to the input JSON fragment file
        output_path (str): Path to the output JSON fragment file
    """
    # Read the file content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to match partitions from p20230101 to p20241231
    # This pattern matches: PARTITION p2023**** VALUES [("***"), ("****")),
    # and: PARTITION p2024**** VALUES [("***"), ("****")),
    partition_pattern = r'PARTITION p202[34]\d{4} VALUES \[\([^)]+\), \([^)]+\)\)[,]*\s*'
    
    # Remove the matched partitions
    modified_content = re.sub(partition_pattern, '', content)
    
    # Also need to handle the last partition which might not have a comma at the end
    # Pattern for the last partition in the sequence
    last_partition_pattern = r'PARTITION p202[34]\d{4} VALUES \[\([^)]+\), \([^)]+\)\)\s*'
    modified_content = re.sub(last_partition_pattern, '', modified_content)
    
    # Write the modified content to the output file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    print(f"Partitions related to p2023/p2024 have been removed. Output saved to {output_path}")

def main():
    input_file = "1.json"
    output_file = "1_cleaned.json"
    
    remove_p2023_p2024_partitions(input_file, output_file)

if __name__ == "__main__":
    main()