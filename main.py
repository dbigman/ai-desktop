import pyautogui
from utils import (
    take_screenshot,
    call_omni_parser,
    parse_omni_parser_output,
    call_vlm,
    execute_action,
    convert_to_base64
)
from config import SYSTEM_PROMPT

def main() -> None:
    """Main loop of the AI agent."""
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.5

    import time
    time.sleep(2)

    action_history: list[dict] = []  # List of action result dictionaries

    while True:
        user_query: str = "Open Chrome and search google stock price"  #  Example query - will loop forever with this.

        screenshot_path: str | None = take_screenshot()
        if not screenshot_path:
            continue

        omni_result: str | None = call_omni_parser(screenshot_path)
        if not omni_result:
            continue
        _, raw_parse_output = omni_result  # Assuming omni_result is a tuple

        parsed_omni_output: list[dict] = parse_omni_parser_output(raw_parse_output)
        image_base64: str = convert_to_base64(screenshot_path)

        # Prepare previous actions for the VLM call
        previous_actions_for_prompt: list[str] = [action['message'] for action in action_history]

        vlm_response: str | None = call_vlm(SYSTEM_PROMPT, user_query, parsed_omni_output, image_base64, previous_actions_for_prompt)
        if not vlm_response:
            continue

        action_result: dict = execute_action(vlm_response, parsed_omni_output)

        # Update the action history
        action_history.append(action_result)
        action_history = action_history[-5:]  # Keep only the last 5 actions

if __name__ == "__main__":
    main()