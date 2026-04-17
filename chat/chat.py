import os
import click
import requests
import sys
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL")

@click.command()
@click.option('--message', '-m', required=True, help='The message to send to the chatbot.')
@click.option('--verbose', '-v', is_flag=True, help='Print full JSON response.')
def chat(message, verbose):
    """Simple CLI for interacting with the LangGraph Chat API."""
    
    payload = {
        "message": message,
    }

    try:
        response = requests.post(API_URL, json=payload)
        response.raise_for_status()
        
        data = response.json()

        if verbose:
            click.echo(data)
        else:
            # Adjust 'response' key based on actual API output schema
            answer = data.get('response') or data.get('message') or data
            click.secho(f"Bot: ", fg='green', nl=False)
            click.echo(answer)

    except requests.exceptions.RequestException as e:
        click.secho(f"Error: {e}", fg='red', err=True)
        sys.exit(1)

if __name__ == '__main__':
    chat()