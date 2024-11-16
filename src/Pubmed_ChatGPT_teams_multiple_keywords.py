import openai
from openai import OpenAI
import os
import requests
import xmltodict
from datetime import datetime, timedelta
import pymsteams
from dotenv import load_dotenv
import time

# Load environment variables from .env file
load_dotenv()

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Microsoft Teams Webhook URL
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL")

# PubMed search settings
PUBMED_QUERIES = os.getenv("PUBMED_QUERIES").split(',')

PUBMED_PUBTYPES = [
    "Journal Article",
    "Books and Documents",
    "Clinical Trial",
    "Meta-Analysis",
    "Randomized Controlled Trial",
    "Review",
    "Systematic Review",
]
PUBMED_TERM = 1

PROMPT_PREFIX = (
    "You are a highly educated and trained researcher. Please explain the following paper in Japanese, separating the title and summary with line breaks. Be sure to write the main points in bullet-point format."
)

def main():
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    today = datetime.now()
    yesterday = today - timedelta(days=PUBMED_TERM)
    MAX_ARTICLES_PER_MESSAGE = 6

    for query in PUBMED_QUERIES:
        while True:
            try:
                ids = get_paper_ids_on(yesterday, query)
                print(f"Number of paper IDs for {query}: {len(ids)}")
                output = ""
                paper_count = 0
                message_count = 0
                for i, id in enumerate(ids):
                    summary = get_paper_summary_by_id(id)
                    pubtype_check_result = check_pubtype(summary["pubtype"])
                    print(f"ID {id} pubtype: {summary['pubtype']}, check result: {pubtype_check_result}")
                    if not pubtype_check_result:
                        continue
                    paper_count += 1
                    abstract = get_paper_abstract_by_id(id)
                    print(f"ID {id} title: {summary['title']}")
                    print(f"ID {id} abstract: {abstract}\n")
                    input_text = f"\ntitle: {summary['title']}\nabstract: {abstract}"

                    response = client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": PROMPT_PREFIX + "\n" + input_text,
                            },
                        ],
                        model="gpt-4",  # Specify the correct available model name
                    )
                    
                    # Modified to match new API response structure
                    content = response.choices[0].message.content.strip()
                    
                    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{id}"
                    output += f"New PubMed Paper Notification ({query})\n\n{content}\n\n{pubmed_url}\n\n\n"
                    if paper_count % MAX_ARTICLES_PER_MESSAGE == 0:
                        message_count += 1
                        post_to_teams(TEAMS_WEBHOOK_URL, output, query, to_yyyymmdd(yesterday), message_count)
                        output = ""
                if paper_count % MAX_ARTICLES_PER_MESSAGE != 0 or paper_count == 0:
                    message_count += 1
                    post_to_teams(TEAMS_WEBHOOK_URL, output, query, to_yyyymmdd(yesterday), message_count)
                if paper_count == 0:
                    output += f"New PubMed Paper Notification ({query})\n\nNo new papers found\n\n"

                break
                
            except openai.RateLimitError as e:
                print("Rate limit exceeded. Waiting for 300 seconds before retrying.")
                time.sleep(300)
            except Exception as e:
                print(f"An error occurred: {e}")
                time.sleep(60)  # Wait in case of other errors

def to_yyyymmdd(date):
    return date.strftime("%Y/%m/%d")

def get_paper_ids_on(date, query):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&sort=pub_date&term={query}&mindate={to_yyyymmdd(date)}&maxdate={to_yyyymmdd(date)}&retmax=1000&retstart=0"
    res = requests.get(url).json()
    return res["esearchresult"]["idlist"]

def get_paper_summary_by_id(id):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id={id}"
    res = requests.get(url).json()
    return res["result"][id]

def get_paper_abstract_by_id(id):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id={id}"
    res = requests.get(url).text
    xml_dict = xmltodict.parse(res)
    abstract = xml_dict["PubmedArticleSet"]["PubmedArticle"]["MedlineCitation"]["Article"].get("Abstract", {}).get("AbstractText", "")
    return abstract if abstract else ""

def check_pubtype(pubtypes):
    return any(pubtype in PUBMED_PUBTYPES for pubtype in pubtypes)

def post_to_teams(webhook_url, text, query, search_date, message_count):
    my_teams_message = pymsteams.connectorcard(webhook_url)
    my_teams_message.text(f"New Paper Notification ({query}) - Search Date: {search_date}")

    if not text.strip():
        text = "No new papers found"

    card = pymsteams.cardsection()
    card.title(f"New Paper Notification - Message {message_count}")
    card.text(text)
    my_teams_message.addSection(card)
    my_teams_message.send()

if __name__ == "__main__":
    main()