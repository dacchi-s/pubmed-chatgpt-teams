
# Daily PubMed Search with AI Summaries - Automated Microsoft teams Notifications

This tool is for medical researchers who need daily updates on PubMed articles. It automates searches, summarizes new research, and sends results to a Teams channel using OpenAI's GPT model.

## Overview

The tool performs daily searches with specific keywords, generates AI-powered summaries in Japanese, and posts results every morning at 7 AM to a designated Slack channel. This helps researchers stay updated efficiently.

## Features

- **Automated PubMed Searches**: Define keywords for specific topics to search daily.
- **AI Summaries**: Generates concise summaries in Japanese for easy understanding.
- **Teams Integration**: Posts results to Teams via Incoming Webhook.

## Requirements

- Raspberry Pi (or other server)
- Python 3.x
- OpenAI API Key
- Teams Webhook URL

## Installation

1. **Set up Python Environment**:
    ```bash
    python -V
    python3 -m venv project_env
    source project_env/bin/activate
    ```

2. **Install Required Libraries**:
    ```bash
    pip install -r requirements.txt
    ```

3. **Set Up Teams Webhook**: Follow instructions to create an Incoming Webhook URL.

Please refer to the following URL:
https://zenn.dev/headwaters/articles/880a05a3bdb930

4. **Set Up OpenAI API Key**: Create an OpenAI account and get your API key.

Please refer to the following URL:
https://platform.openai.com/docs/quickstart

## Usage

### Environment Variable Configuration

Create a .env file with the following content:
```
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Microsoft teams Webhook URL
TEAMS_WEBHOOK_URL=https://your_teams_webhook_url

# PubMed search queries, separated by commas
PUBMED_QUERIES=keyword1 keyword2, keyword3, keyword4, keyword5 keyword6 keyword7
```

### Crontab Configuration
```
crontab -e
```

add a following line:
```
0 7 * * * /home/user/hoge/venv/bin/python /home/user/fuga/huge/Pubmed_ChatGPT_teams_multiple_keywords.py
```

This will cause the script to run every morning at 7:00 AM.
