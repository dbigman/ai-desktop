import pyautogui
import time
import ast
import base64
from gradio_client import Client, handle_file
from openai import OpenAI
from config import OMNIPARSER_API_URL, VLM_MODEL_NAME, BASE_URL, API_KEY, SYSTEM_PROMPT
import json
import re

# Initialize clients OUTSIDE the functions
omni_client = Client(OMNIPARSER_API_URL)
vlm_client = OpenAI(base_url=BASE_URL, api_key=API_KEY)


def take_screenshot(filename: str = "screenshot.png") -> str | None:
    """Takes a screenshot and saves it.

    Args:
        filename: The name of the file to save the screenshot to.

    Returns:
        The filename if the screenshot was taken successfully, None otherwise.
    """
    try:
        screenshot = pyautogui.screenshot()
        screenshot.save(filename)
        return filename
    except Exception as e:
        print(f"Error taking screenshot: {e}")
        return None


def get_element_center(box_id: int, parsed_output: list[dict]) -> tuple[int, int] | None:
    """Finds element by box_id, returns center coordinates.

    Args:
        box_id: The ID of the element to find.
        parsed_output: The parsed output from OmniParser.

    Returns:
        A tuple containing the (x, y) coordinates of the center of the element,
        or None if the element is not found.
    """
    print(f"Searching for Box ID: {box_id}")  # Debug print 1
    # print(f"Available Box IDs: {[element['id'] for element in parsed_output]}")  # Debug print 2

    for element in parsed_output:
        if element['id'] == "icon " + str(box_id):
            x1, y1, x2, y2 = element['bbox']
            center_x = int(((x1 + x2) / 2) * pyautogui.size()[0])
            center_y = int(((y1 + y2) / 2) * pyautogui.size()[1])
            return center_x, center_y
    return None


def call_omni_parser(image_path: str) -> str | None:
    """Calls OmniParser API, returns raw result.

    Args:
        image_path: The path to the image to process.

    Returns:
        The raw result string from OmniParser, or None if an error occurred.
    """
    try:
        result = omni_client.predict(
            image_input=handle_file(image_path),
            box_threshold=0.05,
            iou_threshold=0.1,
            use_paddleocr=True,
            imgsz=640,
            api_name="/process"
        )
        return result
    except Exception as e:
        print(f"Error calling OmniParser: {e}")
        return None

def parse_omni_parser_output(omni_parser_output_string: str) -> list[dict]:
    """
    Parses complex OmniParser output with error resilience.

    Args:
        omni_parser_output_string: The raw string output from OmniParser.

    Returns:
        A list of dictionaries, each representing a parsed element.  Returns
        an empty list on critical parsing errors.
    """
    parsed_content_list = []
    try:
        lines = omni_parser_output_string.strip().split('\n')
        for line_num, line in enumerate(lines, 1):
            # Split line into prefix and JSON part
            if ':' not in line:
                print(f"Skipping line {line_num}: No colon found. Line: '{line}'", "bot")
                continue
            prefix, json_str = line.split(':', 1)
            prefix, json_str = prefix.strip(), json_str.strip()

            # Parse JSON using ast.literal_eval (handles single quotes)
            try:
                content_dict = ast.literal_eval(json_str)
                if not isinstance(content_dict, dict):
                    print(f"Skipping line {line_num}: Not a dictionary. Line: '{line}'", "bot")
                    continue
            except (SyntaxError, ValueError) as e:
                print(f"Skipping line {line_num}: Invalid syntax. Error: {e}. Line: '{line}'", "bot")
                continue

            # Validate required fields
            required_keys = {'type', 'bbox', 'interactivity', 'content'}
            missing_keys = required_keys - content_dict.keys()
            if missing_keys:
                print(
                    f"Skipping line {line_num}: Missing keys {missing_keys}. Line: '{line}'", "bot"
                )
                continue

            # Add metadata (optional: include prefix as 'id')
            content_dict['id'] = prefix  # e.g., "icon 0"
            parsed_content_list.append(content_dict)

    except Exception as e:
        print(f"Critical error parsing OmniParser output: {e}", "bot")
        return []
    return parsed_content_list

def call_vlm(system_prompt: str, user_query: str, parsed_omni_output: list[dict], image_base64: str, action_history: list[dict]) -> str | None:
    """Constructs VLM prompt, sends it, returns JSON response.

    Args:
        system_prompt: The system prompt for the VLM.
        user_query: The user's query.
        parsed_omni_output: The parsed output from OmniParser.
        image_base64: The base64 encoded image.
        action_history: A list of previous actions and their results.

    Returns:
        The VLM's response as a JSON string, or None if an error occurred.
    """
    try:
        prompt_text = (
            f"{system_prompt}\n\nUser Query:\n{user_query}\n\n"
            f"Parsed Screen Content:\n{str(parsed_omni_output)}\n\n"
            f"Action History (Most Recent First):\n{str(action_history)}"  # Use action_history directly
        )
        response = vlm_client.chat.completions.create(
            model=VLM_MODEL_NAME,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                    ]
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling VLM: {e}")
        return None

def execute_action(vlm_response: str, parsed_omni_output: list[dict]) -> dict:
    """Parses VLM response, executes action, returns a descriptive action result.

    Args:
        vlm_response: The raw JSON response string from the VLM.
        parsed_omni_output: The parsed output from OmniParser.

    Returns:
        A dictionary containing the action taken, the result, a message
        describing the action, and a list of previous actions.
    """
    try:
        response_json = json.loads(vlm_response)
    except json.JSONDecodeError:
        print("Initial JSON parsing failed. Attempting to extract JSON.")
        potential_jsons = re.findall(r"\{[^{}]*\}", vlm_response)
        parsed = False
        for potential_json in potential_jsons:
            try:
                response_json = json.loads(potential_json)
                parsed = True
                break
            except json.JSONDecodeError:
                continue
        if not parsed:
            print("No valid JSON found in VLM response.")
            return {"action": "None", "result": "Error: Invalid JSON", "message": "Failed to parse VLM response.", "previous_actions": []}

    action = response_json.get("Next Action")
    reasoning = response_json.get("Reasoning")
    print(f"Reasoning: {reasoning}")

    box_id = response_json.get("Box ID")

    action_result = {"action": action, "previous_actions": []}  # Initialize with empty previous_actions

    if action == "mouse_move":
        coordinates = response_json.get("coordinate")
        if box_id is not None:
            coords = get_element_center(box_id, parsed_omni_output)
            if coords:
                x, y = coords
                pyautogui.moveTo(x, y, duration=0.5)
                action_result["result"] = "Success"
                action_result["message"] = f"Moved mouse to element with Box ID {box_id} at coordinates ({x}, {y})."
            else:
                action_result["result"] = f"Error: Could not find element with Box ID '{box_id}'."
                action_result["message"] = action_result["result"]
                print(action_result["result"])
        elif coordinates:
            x, y = coordinates
            pyautogui.moveTo(x, y, duration=0.5)
            action_result["result"] = "Success"
            action_result["message"] = f"Moved mouse to coordinates ({x}, {y})."
        else:
            action_result["result"] = "Error: No coordinates or Box ID provided."
            action_result["message"] = action_result["result"]


    elif action in ["left_click", "right_click", "double_click", "hover"]:
        if box_id is not None:
            coords = get_element_center(box_id, parsed_omni_output)
            if coords:
                x, y = coords
                if action == "left_click":
                    pyautogui.click(x, y)
                    action_result["message"] = f"Left-clicked on element with Box ID {box_id} at ({x}, {y})."
                elif action == "right_click":
                    pyautogui.rightClick(x, y)
                    action_result["message"] = f"Right-clicked on element with Box ID {box_id} at ({x}, {y})."
                elif action == "double_click":
                    pyautogui.doubleClick(x, y)
                    action_result["message"] = f"Double-clicked on element with Box ID {box_id} at ({x}, {y})."
                elif action == "hover":
                    pyautogui.moveTo(x, y, duration=0.5)  # Hover is like mouse_move
                    action_result["message"] = f"Hovered over element with Box ID {box_id} at ({x}, {y})."
                action_result["result"] = "Success"
            else:
                action_result["result"] = f"Error: Could not find element with Box ID '{box_id}'."
                action_result["message"] = action_result["result"]
                print(action_result["result"])
        else:  # No box_id
            if action == "left_click":
                pyautogui.click()  # Click at current position
                action_result["message"] = "Left-clicked at the current mouse position."
            elif action == "right_click":
                pyautogui.rightClick()
                action_result["message"] = "Right-clicked at the current mouse position."
            elif action == "double_click":
                pyautogui.doubleClick()
                action_result["message"] = "Double-clicked at the current mouse position."
            #  No hover if no box_id.
            action_result["result"] = "Success"

    elif action == "type":
        text = response_json.get("value")
        if text:
            pyautogui.write(text)
            action_result["result"] = "Success"
            action_result["message"] = f"Typed the text: '{text}'."
        else:
            action_result["result"] = "Error: No text to type."
            action_result["message"] = action_result["result"]

    elif action == "key":
        key_name = response_json.get("value")
        if key_name:
            pyautogui.press(key_name)
            action_result["result"] = "Success"
            action_result["message"] = f"Pressed the key: '{key_name}'."
        else:
            action_result["result"] = "Error: No key specified."
            action_result["message"] = action_result["result"]

    elif action == "screenshot":
        take_screenshot()
        action_result["result"] = "Success"
        action_result["message"] = "Took a screenshot."

    elif action == "scroll_up":
        pyautogui.scroll(20)
        action_result["result"] = "Success"
        action_result["message"] = "Scrolled up."

    elif action == "scroll_down":
        pyautogui.scroll(-20)
        action_result["result"] = "Success"
        action_result["message"] = "Scrolled down."

    elif action == "wait":
        time.sleep(2)
        action_result["result"] = "Success"
        action_result["message"] = "Waited for 2 seconds."

    elif action == "None":
        action_result["result"] = "Task completed."
        action_result["message"] = "The task was marked as completed."
        print("Task completed.")

    else:
        action_result["result"] = f"Error: Unknown action '{action}'."
        action_result["message"] = action_result["result"]
        print(action_result["result"])

    return action_result


def convert_to_base64(image_path: str) -> str:
    """Converts an image to base64.

    Args:
        image_path: The path to the image.

    Returns:
        The base64 encoded image as a string.
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")