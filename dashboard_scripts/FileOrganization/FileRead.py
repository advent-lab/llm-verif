import re

def remove_verilog_comments(content):
    # Remove single-line comments (starting with //)
    content = re.sub(r'//.*', '', content)
    
    # Remove multi-line comments (starting with /* and ending with */)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    
    return content

'''
Return list of regex pattern found in file
'''
def find_all_regex(file_path, regex):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:

            # Remove comments from the content
            content = remove_verilog_comments(file.read())

            return regex.findall(content)
        
    except (UnicodeDecodeError, FileNotFoundError) as e:
        print(f"{type(e).__name__}: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return []

'''
Return True if instance of <string> found in file
and not <excluded_word string>
'''
def find_instance(file_path, string):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:

            # Remove comments from the content
            content = remove_verilog_comments(file.read())

            # Check if target string exists followed by white space or double colon
            target = re.compile(rf'\b{string}\b(?=\s|::)')

            # Return True if the target word is found
            return re.search(target, content)
        
    except (UnicodeDecodeError, FileNotFoundError) as e:
        print(f"{type(e).__name__}: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return False
