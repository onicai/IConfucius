"""IConfucius agent as a python script - for bootstrapping purposes."""

# pylint: disable=invalid-name, too-few-public-methods, no-member, too-many-statements

import sys
import json
import requests
from pathlib import Path
from typing import List
from ic_py_canister import get_canister
import pprint
import jwt
from dotenv import load_dotenv
import os
import random
import tweepy
from datetime import datetime
from pytz import timezone
from my_odin_api import odin_get_user_tokens, odin_post_a_comment

ROOT_PATH = Path(__file__).parent.parent

#  0 - none
#  1 - minimal
#  2 - a lot
DEBUG_VERBOSE = 1

def IConfuciusSays(language: str, topic: str) -> str:
    """Calls the IConfuciusSays endpoint of the IConfucius canister."""

    network = "ic"
    canister_name = "iconfucius_ctrlb_canister"
    canister_id = "dpljb-diaaa-aaaaa-qafsq-cai" # ic mainnet
    candid_path = ROOT_PATH / "scripts/iconfucius_ctrlb_canister.did" # Keep this up to date

    print(
        f"Summary:"
        f"\n - network             = {network}"
        f"\n - canister_name       = {canister_name}"
        f"\n - canister_id         = {canister_id}"
        f"\n - candid_path         = {candid_path}"
    )

    # ---------------------------------------------------------------------------
    # get ic-py based Canister instance
    canister_instance = get_canister(canister_name, candid_path, network, canister_id)

    # check health (liveness)
    print("--\nChecking liveness of canister (did we deploy it!)")
    response = canister_instance.health()
    if "Ok" in response[0].keys():
        print("Ok!")
    else:
        print("Not OK, response is:")
        print(response)

    # ---------------------------------------------------------------------------
    # Generate a quote
    print(f"--\nGenerating a quote in {language} on the topic of {topic}...")

    quote = ""
    quoteLanguage = {language: None} # variant type QuoteLanguage: English, Chinese, ...

    try:
        response = canister_instance.IConfuciusSays(quoteLanguage, topic)
        if "Ok" in response[0].keys():
            return response[0]["Ok"]
        else:
            print("Something went wrong:")
            print(response)
            return None
    except Exception as e:
        print(f"An error occurred while calling IConfuciusSays: {e}")
        return None

if __name__ == "__main__":
    print("=======================================================")
    est = timezone('America/Detroit')
    current_time = datetime.now(est).strftime('%Y-%m-%d %I:%M:%S %p %Z')
    print(f"IConfucius agent as a python script - running at time: {current_time}")
    print("=======================================================")
    # Verify the Python interpreter
    print(sys.executable)

    # Load the environment variables from the .env file
    load_dotenv()

    # The user ID, which is the same as it's principal ID
    # IConfucius (Agent) in Odin.Fun
    ODIN_USER_NAME = "IConfucius (Agent)" 
    ODIN_USER_ID = os.getenv("ODIN_ICONFUCIUS_AGENT_USER_ID")
    ODIN_JWT = os.getenv("ODIN_ICONFUCIUS_AGENT_JWT") # Do NOT print this out. It's a secret.

    # IConfucius credentials from the X Developer Portal
    X_API_KEY = os.getenv("X_API_KEY") # Consumer Key
    X_API_SECRET = os.getenv("X_API_SECRET") # Consumer Secret
    X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
    X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")

    # Create a Client object for v2 API
    X_client = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_TOKEN_SECRET
    )

    # topics and icons for the quotes
    entries = [
        # Own topics that we came up with
        {"cn": "咖啡", "icon": "☕️", "en": "Coffee"},
        {"cn": "加密货币", "icon": "📈", "en": "Cryptocurrency"},
        {"cn": "天空", "icon": "🌤️", "en": "Sky"},
        {"cn": "花朵", "icon": "🌸", "en": "Flowers"},
        {"cn": "公正之神", "icon": "⚖️", "en": "Justice"},

        # Community requested topics
        {"cn": "进步的颠覆性本质", "icon": "🌱", "en": "The disruptive nature of progress"}, # Ok

        # AI generated topics for Confucian values
        {"cn": "修养", "icon": "🏋️", "en": "Discipline"}, # Ok
        {"cn": "耐心", "icon": "🕰️", "en": "Patience"},
        {"cn": "和谐", "icon": "☯️", "en": "Harmony"},
        {"cn": "礼仪", "icon": "🎎", "en": "Ritual and Courtesy"},
        {"cn": "诚信", "icon": "🤝", "en": "Integrity"},
        {"cn": "学习", "icon": "📖", "en": "Lifelong Learning"},
        {"cn": "反思", "icon": "🪞", "en": "Reflection"},
        {"cn": "顺其自然", "icon": "🍃", "en": "Acceptance of Nature"},
        {"cn": "简朴", "icon": "🍂", "en": "Simplicity"},
        {"cn": "平衡", "icon": "⚖️", "en": "Balance"},

        # AI generated topics for finance, crypto, business, life wisdom, creativity, technology)
        {"cn": "信任", "icon": "🤠", "en": "Trust"},
        {"cn": "积累", "icon": "💰", "en": "Accumulation of Wealth"},
        {"cn": "投资", "icon": "💵", "en": "Investment"},
        {"cn": "风险", "icon": "⚠️", "en": "Risk"},
        {"cn": "创新", "icon": "💡", "en": "Innovation"},
        {"cn": "适应", "icon": "🌌", "en": "Adaptation"},
        {"cn": "坚韧", "icon": "🗿", "en": "Resilience"},
        {"cn": "洞察", "icon": "🔍", "en": "Insight"},
        {"cn": "目标", "icon": "🎯", "en": "Goal Setting"},
        {"cn": "自由", "icon": "🌈", "en": "Freedom"},
        {"cn": "责任", "icon": "👷", "en": "Responsibility"},
        {"cn": "时间", "icon": "⏳", "en": "Time Management"},
        {"cn": "财富", "icon": "💸", "en": "Wealth"},
        {"cn": "节制", "icon": "🏋️", "en": "Moderation"},
        {"cn": "虚拟资产", "icon": "💹", "en": "Digital Assets"},
        {"cn": "共识", "icon": "🔀", "en": "Consensus"},
        {"cn": "去中心化", "icon": "🛠️", "en": "Decentralization"},
        {"cn": "透明", "icon": "👀", "en": "Transparency"},
        {"cn": "智慧", "icon": "🤔", "en": "Wisdom"},
        {"cn": "信用", "icon": "📈", "en": "Credit"},
        {"cn": "安全", "icon": "🔒", "en": "Security"},
        {"cn": "机遇", "icon": "🍀", "en": "Opportunity"},
        {"cn": "成长", "icon": "🌱", "en": "Growth"},
        {"cn": "合作", "icon": "🤝", "en": "Collaboration"},
        {"cn": "选择", "icon": "🔀", "en": "Choice"},
        {"cn": "敬业", "icon": "💼", "en": "Professionalism"},
        {"cn": "审慎", "icon": "📊", "en": "Prudence"},
        {"cn": "理性", "icon": "🤖", "en": "Rationality"},
        {"cn": "契约", "icon": "📑", "en": "Contract"},
        {"cn": "区块链", "icon": "🛠️", "en": "Blockchain"},
        {"cn": "匿名", "icon": "🔎", "en": "Anonymity"},
        {"cn": "竞争", "icon": "🏆", "en": "Competition"},
        {"cn": "领导", "icon": "👑", "en": "Leadership"},
        {"cn": "市场", "icon": "🏢", "en": "Market"},
        {"cn": "社区", "icon": "🏞️", "en": "Community"},
        {"cn": "自我实现", "icon": "🌟", "en": "Self-Actualization"},
        {"cn": "善良", "icon": "💖", "en": "Kindness"},
        {"cn": "信念", "icon": "✨", "en": "Belief"},
        {"cn": "忠诚", "icon": "🦁", "en": "Loyalty"},
        {"cn": "美德", "icon": "🌿", "en": "Virtue"},
        {"cn": "远见", "icon": "🔮", "en": "Vision"},
        {"cn": "成就", "icon": "🌟", "en": "Achievement"},
        {"cn": "共享", "icon": "👥", "en": "Sharing"},
        {"cn": "交流", "icon": "📢", "en": "Communication"},
        {"cn": "执行力", "icon": "🔄", "en": "Execution"},
        {"cn": "算法", "icon": "🔢", "en": "Algorithm"},
        {"cn": "冷静", "icon": "🌧️", "en": "Calmness"},
        {"cn": "奋斗", "icon": "⚔️", "en": "Struggle"},
        {"cn": "信号", "icon": "📶", "en": "Signal"},
        {"cn": "贪婪", "icon": "💶", "en": "Greed"},
        {"cn": "慈善", "icon": "💜", "en": "Charity"},
        {"cn": "艺术", "icon": "🎨", "en": "Art"},
        {"cn": "科技", "icon": "📱", "en": "Technology"},
        {"cn": "策略", "icon": "🔫", "en": "Strategy"},
        {"cn": "耐力", "icon": "🌼", "en": "Endurance"},
        {"cn": "梦想", "icon": "🌟", "en": "Dreams"},
        {"cn": "节奏", "icon": "🎵", "en": "Rhythm"},
        {"cn": "健康", "icon": "🏥", "en": "Health"},
        {"cn": "家庭", "icon": "🏡", "en": "Family"},
        {"cn": "教育", "icon": "🎓", "en": "Education"},
        {"cn": "旅行", "icon": "🛰", "en": "Travel"},
        {"cn": "幸福", "icon": "🎉", "en": "Happiness"},
        {"cn": "机密", "icon": "🔒", "en": "Confidentiality"},
        {"cn": "原则", "icon": "🔄", "en": "Principles"},
        {"cn": "法律", "icon": "🏛️", "en": "Law"},
        {"cn": "效率", "icon": "⏳", "en": "Efficiency"},
        {"cn": "反脆弱", "icon": "💪", "en": "Antifragility"},
        {"cn": "道德", "icon": "📍", "en": "Morality"},
        {"cn": "灵感", "icon": "💡", "en": "Inspiration"},
        {"cn": "公平", "icon": "⚖️", "en": "Fairness"},
        {"cn": "未来", "icon": "🌟", "en": "Future"},
        {"cn": "传统", "icon": "🎐", "en": "Tradition"},
        {"cn": "关系", "icon": "👨‍👨‍👦", "en": "Relationships"}
    ]

    odin_tokens = odin_get_user_tokens(ODIN_USER_ID, ODIN_JWT)
    if odin_tokens is None:
        print("Error fetching user tokens")
        sys.exit(1)

 
    live_LLM = True # if True, we will generate a new quote
    live_odin = True  # if True, we will post the quotes to the Odin.Fun API
    live_X = True  # if True, we will post the quotes to X (Twitter)

    print(f"live_LLM  = {live_LLM}")
    print(f"live_odin = {live_odin}")
    print(f"live_X    = {live_X}")

    # Randomly select an entry from the list
    random_index = random.randint(0, len(entries) - 1)
    entry = entries[random_index]
    icon = entry["icon"]
    for language_code in ["cn", "en"]:
        topic = entry[language_code]

        prefix = f"{language_code} 🤖"
        
        if language_code == "cn":
            quoteLanguage = "Chinese"
        elif language_code == "en":
            quoteLanguage = "English"
        else:
            print(f"Unsupported language code: {language_code}")
            continue

        if live_LLM:
            print("-------------------------------------------------------")
            print(f"Generating a quote in {quoteLanguage} on the topic of {topic}...")
            quote = IConfuciusSays(quoteLanguage, topic)
            if not quote:
                print("Error generating the quote.")
                continue
        else:
            quote = "Testing the IConfucius agent"

        message = f"({prefix}) {icon} {quote}"

        if live_odin:

            print("-------------------------------------------------------")
            print(f"Posting a {quoteLanguage} quote to the Odin.Fun API")


            # Post to the ICONFUCIUS token and one other token
            iconfucius_token = next(token for token in odin_tokens if token['token_name'] == 'ICONFUCIUS')
            other_tokens = [token for token in odin_tokens if token['token_name'] != 'ICONFUCIUS']
            random_token = random.choice(other_tokens)
            tokens_to_post = [iconfucius_token, random_token]

            for token in tokens_to_post:
                odin_token_id = token["odin_token_id"]
                print(f"Posting to token: {token['token_name']} (ID: {odin_token_id})")

                comment_data = {"message": message}
                try:
                    response = odin_post_a_comment(
                        ODIN_USER_ID, ODIN_JWT, odin_token_id, comment_data
                    )
                    print(f"Odin Response Status Code: {response.status_code}")
                    if response.status_code == 201:
                        print(f"Odin Response JSON: {response.json()}")
                except requests.exceptions.RequestException as e:
                    print(f"Odin: An exception has occurred. Request Failed: {e}")
                except ValueError as e:
                    print(f"Odin: An exception has occurred: {e}")

        if live_X:
            print("-------------------------------------------------------")
            print(f"Posting a {quoteLanguage} quote to the X API")
            try:
                text = (
                    f"{message}\n\n"
                    f"👉odin.fun/token/29m8"
                )
                
                response = X_client.create_tweet(text=text)
                print("X: Successfully posted to X!")
                print(f"X Tweet ID: {response.data['id']}")
            except tweepy.TweepyException as e:
                print(f"X: Error: {e}")

    print("-------------------------------------------------------")
    current_time = datetime.now(est).strftime('%Y-%m-%d %I:%M:%S %p %Z')
    print(f"IConfucius agent as a python script - done at time: {current_time}")




    