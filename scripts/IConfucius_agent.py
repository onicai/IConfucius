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

ROOT_PATH = Path(__file__).parent.parent

#  0 - none
#  1 - minimal
#  2 - a lot
DEBUG_VERBOSE = 1

# The user ID, which is the same as it's principal ID
# IConfucius (Agent)
USER_ID = "fiskt-oaazh-d2ekf-qennf-6y3hg-vbkvx-b44nd-zogxb-rztmx-4xv3n-sqe"

# The IConfucius token ID
TOKEN_ID = "29m8"

# Tell odin.fun who is calling the API
USER_AGENT = "IConfucius (Agent)"

# The Odin.Fun API endpoint
ODIN_FUN_API = "https://api.odin.fun"

# Load the environment variables from the .env file
load_dotenv() 

def get_odin_jwt(jwt_name: str) -> str:
    """Get ODIN_JWT from environment variable."""   
    return os.getenv(jwt_name)

def odin_get_user_data() -> dict:
    """
    Fetches user data from the API and returns the data as a Python dictionary.

    Returns:
        A Python dictionary representing the user data, or None if an error occurred.
    """

    url = f"{ODIN_FUN_API}/v1/user/{USER_ID}"
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9",
        "origin": "",
        "referer": "",
        "user-agent": USER_AGENT,
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Check if the response is Brotli-compressed
        if response.headers.get("content-encoding") == "br":
            # Decompress the data using brotli.decompress() - already done by requests
            # decompressed_data = brotli.decompress(response.content)
            # decoded_data = decompressed_data.decode("utf-8")
            decoded_data = response.content.decode("utf-8")
        else:
            # Decode the decompressed data as UTF-8
            decoded_data = response.content.decode("utf-8")

        # Parse the decoded data (string) as JSON
        user_data = json.loads(decoded_data)

        return user_data

    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        return None


def odin_get_token_comments(jwt_, page, limit):
    """
    Fetches comments for a specific token from the api.odin.fun API.

    Args:
        page (int): The page number of the results to retrieve.
        limit (int): The number of comments per page.

    Returns:
        dict: The JSON response from the API, or None if an error occurred.
    """
    method="GET"
    url = f"{ODIN_FUN_API}/v1/token/{TOKEN_ID}/comments"
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "authorization": f"Bearer {jwt_}",
        "user-agent": USER_AGENT,
    }
    params = {
        "page": page,
        "limit": limit,
    }
    timeout=5

    print(f"\nurl: {url}")
    print("\nheaders:")
    pprint.pprint(headers)
    print("\nparams:")
    pprint.pprint(params)
    print(f"\ntimeout: {timeout}")

    try:
        # Add timeout for security
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        response.raise_for_status()  # Raise an exception for bad status codes
        # Decompress if required, requests handle this automatically
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        print(f"Response content: {response.content}")
        return None

def odin_post_a_comment(odin_jwt, token_id, comment_data):
    """
    Posts a comment to a specific token on the Odin API.

    Args:
        token_id (str): The ID of the token to comment on (e.g., "29m8").
        comment_data (dict): The data to include in the comment.
        live_odin (bool): If True, the request will be made to the API.
                     If False, the request will be printed to the console instead.

    Returns:
        requests.Response: The response object from the API.
            It will be a succesful response if it has status code 201.
            Otherwise it will be an error status code.
            Check the response.status_code.

    Raises:
        requests.exceptions.RequestException: If there's an issue with the HTTP request.
        ValueError: if the url is not well formatted.
    """

    method = "POST"
    url = url = f"{ODIN_FUN_API}/v1/token/{token_id}/comment?user={USER_ID}"
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9",
        "authorization": f"Bearer {odin_jwt}",
        "content-type": "application/json",
        "origin": "",
        "referer": "",
        "user-agent": USER_AGENT,
    }
    timeout = 5

    try:
        # Add timeout for security
        response = requests.request(
            method=method, url=url, headers=headers, json=comment_data, timeout=timeout
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error during the request: {e}")
        raise

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
    # Verify the Python interpreter
    print(sys.executable)

    # Get secrets from the .env file

    # The ODIN_JWT provides full access to the IConfucius account.
    # - Do not share it with anyone.
    # - Do not print it, not even in this notebook, because you might check it into source control by accident
    ODIN_JWT = os.getenv("ODIN_JWT")

    # Your credentials from the X Developer Portal
    X_API_KEY = os.getenv("X_API_KEY") # Consumer Key
    X_API_SECRET = os.getenv("X_API_SECRET") # Consumer Secret
    X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
    X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")

    # Create a Client object for v2 API
    client = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_TOKEN_SECRET
    )

    # ODIN: Get user data (Just for testing, don't need it)
    # user_data = odin_get_user_data()
    # if user_data:
    #     print("User data retrieved and processed successfully:")
    #     pprint.pprint(user_data)
    # else:
    #     print("Error retrieving user data")

    # This does not work - giving unauthorized error
    # ODIN: Get comments for the token
    # comments = odin_get_token_comments(ODIN_JWT, page=1, limit=20)
    # if comments:
    #     pprint.pprint(comments)
    # else:
    #     print("Error fetching comments, or there are no comments")

    # Candidate topics and icons for the quotes
    entries = [
        # Own topics that we came up with
        {"cn": "咖啡", "icon": "☕️", "en": "Coffee"}, # Ok
        {"cn": "加密货币", "icon": "📈", "en": "Cryptocurrency"}, # Ok
        {"cn": "天空", "icon": "🌤️", "en": "Sky"}, # Ok
        {"cn": "花朵", "icon": "🌸", "en": "Flowers"}, # Ok

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

    # Market cap is in sats - last updated on Sunday 2025-03-23
    # Top 10 - All these tokens have a market cap of $100k USD or more
    odin_tokens = [
        {"token_id": "29m8", "token_name": "ICONFUCIUS", "market_cap": 21.6},
        {"token_id": "2jjj", "token_name": "ODINDOG", "market_cap": 396},
        {"token_id": "2b2w", "token_name": "ODINAPE", "market_cap": 348},
        {"token_id": "2hci", "token_name": "BITCAT", "market_cap": 101},
        {"token_id": "2h3b", "token_name": "ODINGOLD", "market_cap": 77.0},
        {"token_id": "2jjh", "token_name": "SATOSHI", "market_cap": 66.6},
        {"token_id": "2jj2", "token_name": "ODINCAT", "market_cap": 43.6},
        {"token_id": "2n8d", "token_name": "PI", "market_cap": 19.8},
        {"token_id": "2jzc", "token_name": "GHOSTNODE", "market_cap": 17.2},
        {"token_id": "229u", "token_name": "SPARKS", "market_cap": 15.5},
        {"token_id": "2m1q", "token_name": "SUPEREX", "market_cap": 9.14},
    ]
    
    live_LLM = True # if True, we will generate a new quote
    live_odin = True  # if True, we will post the quotes to the Odin.Fun API
    live_X = True  # if True, we will post the quotes to X (Twitter)

    # Randomly select an entry from the list
    random_index = random.randint(0, len(entries) - 1)
    entry = entries[random_index]
    icon = entry["icon"]
    for language_code in ["cn", "en"]:
        topic = entry[language_code]
        
        print("-------------------------------------------------------")
        print(f"live_odin = {live_odin}")

        prefix = f"{language_code} 🤖"
        
        if language_code == "cn":
            quoteLanguage = "Chinese"
        elif language_code == "en":
            quoteLanguage = "English"
        else:
            print(f"Unsupported language code: {language_code}")
            continue

        if live_LLM:
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

            # Post to the first token in the list, which is ICONFUCIUS token
            tokens_to_post = [odin_tokens[0]]

            # Add one randomly selected token (excluding the first one)
            tokens_to_post.extend(random.sample(odin_tokens[1:], 1))

            for token in tokens_to_post:
                token_id = token["token_id"]
                print(f"Posting to token: {token['token_name']} (ID: {token_id})")

                comment_data = {"message": message}
                try:
                    response = odin_post_a_comment(
                        ODIN_JWT, token_id=token_id, comment_data=comment_data
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
                
                response = client.create_tweet(text=text)
                print("X: Successfully posted to X!")
                print(f"X Tweet ID: {response.data['id']}")
            except tweepy.TweepyException as e:
                print(f"X: Error: {e}")




    