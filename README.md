<!-- omit in toc -->
# AI Desktop
Simple AI Desktop that uses the OmniParser and Vision-Language Model to interact with the system. It can perform various tasks like opening applications, searching the web, and answering questions.

User Query: `Open Google Chrome and search for google stock price`

https://github.com/user-attachments/assets/c5f6a2ea-ded8-4663-b937-252d0af4c9e2

<!-- omit in toc -->
## Table of Contents
- [Installation](#installation)
- [OmniParser Setup](#omniparser-setup)
- [Configuration](#configuration)
- [Running the AI Desktop](#running-the-ai-desktop)

## Installation

Clone the repository and install the dependencies:

```bash
git clone https://github.com/FareedKhan-dev/ai-desktop
```

To install the dependencies, run the following command:

```bash
cd ai-desktop/OmniParser
pip install -r requirements.txt
```

AI-Dekstop does not require any additional dependencies.

## OmniParser Setup

Navigate to the `OmniParser` directory

```bash
cd OmniParser
```

Download the model checkpoints:

```bash
# Download the model checkpoints to the local directory OmniParser/weights/
mkdir -p weights/icon_detect weights/icon_caption_florence

for file in icon_detect/{train_args.yaml,model.pt,model.yaml} \
            icon_caption/{config.json,generation_config.json,model.safetensors}; do
    huggingface-cli download microsoft/OmniParser-v2.0 "$file" --local-dir weights
done

mv weights/icon_caption weights/icon_caption_florence
```

make sure the weights are downloaded in the `weights` directory and it should be called `icon_detect` and `icon_caption_florence` respectively.

To start the gradio api of `omniparser`, run the following command:

```bash
python gradio_demo.py
```

The gradio api will start at `localhost:<port>` and live sharaing link will be generated.

## Configuration

Modify the `config.py` file to set up the API URLs, model names, and authentication keys.  

```python
OMNIPARSER_API_URL = "OMNIPARSER_Gradio_link"  # Set the OmniParser Gradio API link  (Follow the Usage section to get the link)
VLM_MODEL_NAME = "OPENAI/LOCAL_MODEL_NAME"  # Define the vision-language model  
BASE_URL = "BASE_URL"  # Set the base URL for the API  
API_KEY = "API_KEY"  # Provide the API key  
```

The `SYSTEM_PROMPT` in `config.py` defines the AI agent behavior, guiding it to interact with the system using various actions like mouse movements, clicks, typing, and screenshots. Modify it as needed for custom AI interactions.

## Running the AI Desktop

To start the AI Desktop, run the following command:

```bash
python main.py
```

you can modify the `user_query` in `main.py` to test different queries.

