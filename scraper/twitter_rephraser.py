import requests
import os
import time
import json
from urllib.parse import urlparse
from .logger import Logger

logger = Logger("TwitterRephraser", "twitter_rephraser.log")
# Rephrase Text using Ollama with llama3.2 locally
def rephrase_text_with_ollama(text):
    OLLAMA_API_URL = "http://localhost:11434/api/generate"  # Default Ollama API endpoint
    
    # Prepare the prompt for the rephrasing task
    prompt = f"Rephrase the following tweet while keeping its meaning intact. Do not add any extra text, explanations, or headers—just return the rephrased tweet, make sure the rephrased tweet doesn't exceed 270 characters long. Here is the tweet: {text}"
    
    payload = {
        "model": "llama3.2",  # Specify the model name
        "prompt": prompt,
        "stream": False  # We want the complete response at once
    }
    
    try:
        # Convert payload to JSON string
        payload_json = json.dumps(payload)
        
        # Use requests library with explicit JSON content
        headers = {"Content-Type": "application/json"}
        response = requests.post(OLLAMA_API_URL, data=payload_json, headers=headers)
        
        # Check for errors in the HTTP response
        if response.status_code != 200:
            logger.error(f"Ollama API returned status code {response.status_code}")
            logger.error(f"Response: {response.text}")
            return text
        
        # Parse the JSON response
        try:
            result = response.json()
            if "response" in result:
                rephrased_text = result["response"].strip()
                logger.info("Successfully rephrased text.")
                return rephrased_text
            else:
                logger.error("Unexpected response format from Ollama API.")
                logger.debug(f"Response: {result}")
                return text
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON response from Ollama API")
            logger.debug(f"Raw response: {response.text}")
            return text
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Ollama: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.debug(f"Error details: {e.response.text}")
        return text  # Return original text if rephrasing fails
