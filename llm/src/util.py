from typing import Any
import logging
import re
import json

def convert_json_response_to_dict(generated_response: str) -> tuple[dict[str, Any], int]:
  """
  Extract and parse JSON content from an AI-generated response.

  This method identifies and parses JSON-like content embedded within the model's response.
  If the response contains invalid JSON or no JSON at all, it attempts to extract the most
  plausible JSON segment and returns a default structure for errors.

  Args:
      generated_response (str): The AI-generated response containing JSON-like content.

  Returns:
      Tuple[Dict[str, Any], int]:
          - The parsed JSON object as a dictionary.
          - A status code:
              - 0: Successfully parsed JSON.
              - 1: Empty response or no JSON found.
              - 2: JSON parsing failed.
              - 3: Other unexpected errors.

  Notes:
      - This function is designed for scenarios where the AI response might contain
        additional non-JSON text before or after the JSON content.
  """
  # Handle empty response
  if not generated_response:
      logging.error("Empty or invalid response received.")
      return {"error": "Empty response"}, 1

  # Attempt to extract JSON-like content
  try:
      # Find the first JSON curly brace
      first_pos = generated_response.find('{')
      if first_pos != -1:
          generated_response = generated_response[first_pos:]
      
      comments_pos = generated_response.find('"comments":')
      
      # Find the first JSON curly brace after comments tag
      last_pos = generated_response.find('}', comments_pos)
      if last_pos != -1 and comments_pos != -1:
          generated_response = generated_response[:last_pos + 1]

      # TODO: Escape all non-terminal double quotes
      pattern = r'{\s*"test bench":\s*"(.*?)",\s*"comments":\s*"(.*?)"\s*}'
      matches = re.match(pattern, generated_response, re.DOTALL)
      if matches:
          parsed_response = matches.group(1)
      else:
          raise RuntimeError(f"Could not parse the response:\n{generated_response}")

      # Parse JSON
      #decoder = json.JSONDecoder(strict=False)
      #parsed_response = decoder.raw_decode(generated_response)
      return {"test bench": parsed_response}, 0

  except json.JSONDecodeError as e:
      logging.error(f"JSONDecodeError: {e}. Response: {generated_response}")
      return {"error": f"Malformed JSON content\n\n{generated_response}"}, 2

  except Exception as e:
      logging.error(f"Unexpected error during JSON parsing: {e}")
      return {"error": f"Unexpected error\n\n{generated_response}"}, 3
  
def extract_verilog_module_header(design_path: str) -> str:
  # Read the file line by line to identify the header
  with open(design_path, 'r') as f:
      lines = f.readlines()

  start_line = None
  end_line = None
  inside_module = False
  capturing_ports = False

  # Loop through lines to find the module declaration and subsequent I/O declarations
  for i, line in enumerate(lines):
      # Look for the start of the module declaration
      if re.match(r"\s*module\s+\w+", line) and start_line is None:
          start_line = i
          inside_module = True

      # If we're inside the module header, check for the end of the main header
      if inside_module:
          # Detect the end of the main module header (closing parenthesis with semicolon)
          if re.search(r"\);\s*$", line):
              end_line = i
              inside_module = False
              capturing_ports = True  # Start capturing additional ports after the header ends
              continue

      # Capture subsequent input/output/inout declarations
      if capturing_ports:
          if re.match(r"\s*(input|output|inout|parameter)\s+", line):
              end_line = i  # Update end line for each I/O declaration line

  # Slice the lines to get only the module header and subsequent I/O declarations
  if start_line is not None and end_line is not None:
      module_header = "".join(lines[start_line:end_line + 1])
      return module_header.strip()
  else:
      return "No module header found."

