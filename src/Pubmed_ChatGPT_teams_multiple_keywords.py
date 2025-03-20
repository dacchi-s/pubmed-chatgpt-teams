import openai
from openai import OpenAI
import os
import requests
import xmltodict
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
import time

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL")

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
    "あなたは高度に教育と訓練をした研究者です。以下の論文を、タイトルと要約の2点をそれぞれ改行で分けて日本語で説明してください。要点は必ず箇条書き形式で書いてください。"
)

def main():
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    today = datetime.now()
    yesterday = today - timedelta(days=PUBMED_TERM)
    MAX_ARTICLES_PER_MESSAGE = 6

    for query in PUBMED_QUERIES:
        api_retry_count = 0
        max_api_retries = 3
        
        while api_retry_count < max_api_retries:
            try:
                ids = get_paper_ids_on(yesterday, query)
                print(f"{query} の論文ID数: {len(ids)}")
                output = ""
                paper_count = 0
                message_count = 0
                
                for i, id in enumerate(ids):
                    summary = get_paper_summary_by_id(id)
                    pubtype_check_result = check_pubtype(summary["pubtype"])
                    print(f"ID {id} のpubtype: {summary['pubtype']}, チェック結果: {pubtype_check_result}")
                    if not pubtype_check_result:
                        continue
                    paper_count += 1
                    abstract = get_paper_abstract_by_id(id)
                    print(f"ID {id} のタイトル: {summary['title']}")
                    print(f"ID {id} の要約: {abstract}\n")
                    input_text = f"\ntitle: {summary['title']}\nabstract: {abstract}"

                    response = client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": PROMPT_PREFIX + "\n" + input_text,
                            },
                        ],
                        model="gpt-4o-mini",
                    )
                    
                    content = response.choices[0].message.content.strip()
                    
                    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{id}"
                    output += f"PubMed の新着論文のお知らせ ({query})\n\n{content}\n\n{pubmed_url}\n\n\n"
                    
                    if paper_count % MAX_ARTICLES_PER_MESSAGE == 0:
                        message_count += 1
                        post_with_retry(output, query, to_yyyymmdd(yesterday), message_count)
                        output = ""
                
                if paper_count % MAX_ARTICLES_PER_MESSAGE != 0 or paper_count == 0:
                    message_count += 1
                    if paper_count == 0:
                        output += f"PubMed の新着論文のお知らせ ({query})\n\nありません\n\n"
                    post_with_retry(output, query, to_yyyymmdd(yesterday), message_count)
                
                break
                
            except openai.RateLimitError as e:
                api_retry_count += 1
                if api_retry_count < max_api_retries:
                    print(f"Rate limit exceeded. Waiting for 300 seconds before retrying. Retry {api_retry_count}/{max_api_retries}")
                    time.sleep(300)
                else:
                    print(f"Maximum retries reached for query {query}. Skipping to next query.")
                    break
            except Exception as e:
                api_retry_count += 1
                if api_retry_count < max_api_retries:
                    print(f"An error occurred: {e}. Waiting for 60 seconds before retrying. Retry {api_retry_count}/{max_api_retries}")
                    time.sleep(60)
                else:
                    print(f"Maximum retries reached for query {query}. Skipping to next query.")
                    break

def post_with_retry(text, query, search_date, message_count, max_webhook_retries=3):
    webhook_retry_count = 0
    
    while webhook_retry_count < max_webhook_retries:
        post_result = post_to_teams(TEAMS_WEBHOOK_URL, text, query, search_date, message_count)
        if post_result:
            # 成功したら終了
            return True
        
        webhook_retry_count += 1
        if webhook_retry_count < max_webhook_retries:
            print(f"Webhook failed. Retrying in 10 seconds. Webhook retry {webhook_retry_count}/{max_webhook_retries}")
            time.sleep(10)
        else:
            print(f"Maximum webhook retries reached for message {message_count}, query {query}. Giving up on this message.")
    
    return False

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
    try:
        title = f"新着論文のお知らせ ({query}) - 検索対象日: {search_date}"
        subtitle = f"新着論文のお知らせ - Message {message_count}"
        
        if not text.strip():
            text = "ありません"
        
        payload = {
            'type': 'message',
            'attachments': [
                {
                    'contentType': 'application/vnd.microsoft.card.adaptive',
                    'contentUrl': None,
                    'content': {
                        '$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
                        'type': 'AdaptiveCard',
                        'version': '1.2',
                        'width': 'full',
                        'body': [
                            {
                                'type': 'TextBlock',
                                'text': title,
                                'weight': 'bolder',
                                'size': 'medium',
                                'wrap': True
                            },
                            {
                                'type': 'TextBlock',
                                'text': subtitle,
                                'weight': 'bolder',
                                'size': 'medium',
                                'wrap': True
                            },
                            {
                                'type': 'TextBlock',
                                'text': text,
                                'wrap': True
                            }
                        ]
                    }
                }
            ]
        }
        
        response = requests.post(
            webhook_url,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(payload)
        )
        
        # レスポンスをチェック
        if response.status_code < 200 or response.status_code >= 300:
            print(f"Teams Webhookエラー: HTTP {response.status_code} - {response.text}")
            return False
            
        return True
    except Exception as e:
        print(f"Teamsへの投稿中にエラーが発生しました: {e}")
        return False

if __name__ == "__main__":
    main()
