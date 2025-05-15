"""The IConfucius Python Library for odin.fun"""

# pylint: disable=invalid-name, too-few-public-methods, no-member, too-many-statements

import sys
import json
import requests
from pathlib import Path
from typing import List
import pprint
from dotenv import load_dotenv
import os
import random
import tweepy
from datetime import datetime
from pytz import timezone
import cbor2
from ic.candid import Types, encode, decode

ROOT_PATH = Path(__file__).parent.parent

#  0 - none
#  1 - minimal
#  2 - a lot
DEBUG_VERBOSE = 1

# The Odin.Fun API endpoint
ODIN_FUN_API = "https://api.odin.fun"

# Tell odin.fun who is calling the API
USER_AGENT = "IConfucius Python Library"

# Load the environment variables from the .env file
load_dotenv() 

# Get BTC > USD price from an API
def get_btc_usd_price():
    """
    Fetches the current BTC to USD price from the CoinGecko API.

    Returns:
        float: The current BTC to USD price.
    """
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        return data["bitcoin"]["usd"]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching BTC price: {e}")
        return None

BTC2USD = get_btc_usd_price()

def odin_get_user_data(odin_user_id) -> dict:
    """
    Fetches user data from the API and returns the data as a Python dictionary.
    Non-authenticated API call.

    Returns:
        A Python dictionary representing the user data, or None if an error occurred.

    Use as:
        # The user ID, which is the same as it's principal ID
        # eg. IConfucius (Agent)
        ODIN_USER_ID = "fiskt-oaazh-d2ekf-qennf-6y3hg-vbkvx-b44nd-zogxb-rztmx-4xv3n-sqe"
        user_data = odin_get_user_data(ODIN_USER_ID)
        if user_data:
            print("User data retrieved and processed successfully:")
            pprint.pprint(user_data)
        else:
            print("Error retrieving user data")
    """

    url = f"{ODIN_FUN_API}/v1/user/{odin_user_id}"
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


def odin_get_token_comments(odin_jwt, odin_token_id, page, limit):
    """
    Fetches comments for a specific token from the api.odin.fun API.
    This is an authenticated API call. Currently it does not seem to work

    Args:
        odin_jwt (str): The user's JWT token to authenticate the request.
        odin_token_id (str): The ID of the token to comment on (e.g., "29m8" for the IConfucius token).
        page (int): The page number of the results to retrieve.
        limit (int): The number of comments per page.

    Returns:
        dict: The JSON response from the API, or None if an error occurred.

    Use as:
        ODIN_JWT = os.getenv("ODIN_JWT") # for security, use environment variables & do not print!!!
        ODIN_TOKEN_ID = "29m8" # eg. the ICONFUCIUS token
        
        try:
            comments = odin_get_token_comments(ODIN_JWT, ODIN_TOKEN_ID, page=1, limit=20)
            if comments:
                pprint.pprint(comments)
            else:
                print("Error fetching comments, or there are no comments")
        except requests.exceptions.RequestException as e:
            print(f"Odin: An exception has occurred. Request Failed: {e}")
        except ValueError as e:
            print(f"Odin: An exception has occurred: {e}")
    """
    method="GET"
    url = f"{ODIN_FUN_API}/v1/token/{odin_token_id}/comments"
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "authorization": f"Bearer {odin_jwt}",
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
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        print(f"Response content: {response.content}")
        return None

def odin_post_a_comment(odin_user_id, odin_jwt, odin_token_id, comment_data):
    """
    Posts a comment to a specific token on the Odin API.

    Args:
        odin_jwt (str): The user's JWT token to authenticate the request.
        odin_token_id (str): The ID of the token to comment on (e.g., "29m8" for the IConfucius token).
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

    Use as:
        ODIN_USER_ID = "..."
        ODIN_JTW = os.getenv("ODIN_JTW") # for security, use environment variables & do not print!!!
        ODIN_TOKEN_ID = "29m8" # eg. the ICONFUCIUS token
        comment_data = {"message": message}
        try:
            response = odin_post_a_comment(
                ODIN_USER_ID, ODIN_JTW, ODIN_TOKEN_ID, comment_data
            )
            print(f"Odin Response Status Code: {response.status_code}")
            if response.status_code == 201:
                print(f"Odin Response JSON: {response.json()}")
        except requests.exceptions.RequestException as e:
            print(f"Odin: An exception has occurred. Request Failed: {e}")
        except ValueError as e:
            print(f"Odin: An exception has occurred: {e}")
    """

    method = "POST"
    url = url = f"{ODIN_FUN_API}/v1/token/{odin_token_id}/comment?user={odin_user_id}"
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
        raise e

def odin_get_user_tokens(odin_user_id, odin_jwt):
    """
    Retrieves user tokens from the specified endpoint.
    Reformats the response with less data and more readable keys.

    Args:
        odin_user_id (str): The user ID.
        odin_jwt (str): The authorization token for the request.

    Returns:
        dict: The JSON response from the API if the request is successful.
        None: If the request fails.
    """

    url = f"https://api.odin.fun/v1/user/{odin_user_id}/tokens"
    params = {
        "sort": "holding_value:desc",
        "page": 1,
        "limit": 30
    }
    headers = {
        "Authorization": odin_jwt,
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "",
        "Referer": "",
        "User-Agent": USER_AGENT
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user tokens: {e}")
        return None

    result = response.json()
    if "data" in result.keys():
        odin_tokens_from_api = result["data"]
    else:
        print("Error fetching user tokens")
        print(result)
        sys.exit(1)
    # pprint.pprint(odin_tokens_from_api[0])

    # extract the data we use:
    odin_tokens = []
    for data in odin_tokens_from_api:
        odin_token_id = data["token"]["id"]
        token_name = data["token"]["ticker"]

        balance_microtokens = data["balance"]
        price_msats = data["token"]["price"] # millisats
        value_ksats = (balance_microtokens * price_msats) / 1e17 # in Ksats
        num_tokens = balance_microtokens / 1e6

        odin_tokens.append(
            {
                "odin_token_id": odin_token_id,
                "token_name": token_name,
                "value_ksats": value_ksats,
                "price_sats": price_msats*1e-3,
                "num_tokens": num_tokens,
                "marketcap": data["token"]["marketcap"],
            }
        )
 
    print_odin_tokens_table(odin_tokens)    
    return odin_tokens
    

def print_odin_tokens_table(tokens):
    headers = ["Token Name", "Token ID", "marketcap", "Num Tokens", "Price (sats)", "Value (ksats)"]

    rows = []
    marketcap_btc_strs = []
    marketcap_usd_strs = []

    for token in tokens:
        mc_btc = f"{token['marketcap'] / 1e11:.2f}"
        mc_usd = f"{token['marketcap'] * BTC2USD / 1e11:,.0f}"
        marketcap_btc_strs.append(mc_btc)
        marketcap_usd_strs.append(mc_usd)

        rows.append([
            token["token_name"],
            token["odin_token_id"],
            mc_btc,
            mc_usd,
            f"{token['num_tokens']:,.0f}",
            f"{token['price_sats']:,.0f} sats",
            f"{token['value_ksats']:,.0f}K sats",
        ])

    # Fake row to use header labels for width calc
    header_row = [
        headers[0],
        headers[1],
        "BTC",
        "$",
        headers[3],
        headers[4],
        headers[5],
    ]

    # Compute max widths across real + header rows
    col_widths = [
        max(len(str(row[0])) for row in rows + [header_row]),
        max(len(str(row[1])) for row in rows + [header_row]),
        max(len(str(row[2])) for row in rows + [header_row]),
        max(len(str(row[3])) for row in rows + [header_row]),
        max(len(str(row[4])) for row in rows + [header_row]),
        max(len(str(row[5])) for row in rows + [header_row]),
        max(len(str(row[6])) for row in rows + [header_row]),
    ]

    def separator():
        marketcap_width = col_widths[2] + len(" BTC ($") + col_widths[3] + len(")")
        return "+-" + "-+-".join(
            [
                "-" * col_widths[0],  # Token Name
                "-" * col_widths[1],  # Token ID
                "-" * marketcap_width,  # marketcap total width
                "-" * col_widths[4],  # Num Tokens
                "-" * col_widths[5],  # Price
                "-" * col_widths[6],  # Value
            ]
        ) + "-+"

    def format_row(row, is_header=False):
        if is_header:
            marketcap = f"{'BTC'.rjust(col_widths[2])} BTC (${'USD'.rjust(col_widths[3])})"
        else:
            marketcap = f"{row[2].rjust(col_widths[2])} BTC (${row[3].rjust(col_widths[3])})"
        return "| " + " | ".join([
            row[0].rjust(col_widths[0]),
            row[1].rjust(col_widths[1]),
            marketcap,
            row[4].rjust(col_widths[4]),
            row[5].rjust(col_widths[5]),
            row[6].rjust(col_widths[6]),
        ]) + " |"

    # Print full table
    print(separator())
    print(format_row(header_row, is_header=True))
    print(separator())
    for row in rows:
        print(format_row(row))
    print(separator())

def calculate_trades_to_rebalance(
    odin_tokens: List[dict],
    no_trade_tokens: List[str],
    trade_fee_rate_percent: float,
    fund_value_target: float,
    fund_value_lower_bound: float,
    fund_value_upper_bound: float,
    liquidity_token_name = None
):
    
    trade_fee_rate = trade_fee_rate_percent / 100.0

    # Filter out tokens that are not in the no_trade_tokens list
    print("Filtering out tokens that are not in the no_trade_tokens list")
    print(f"no_trade_tokens = {no_trade_tokens}")
    odin_tokens = [token for token in odin_tokens if token["token_name"] not in no_trade_tokens]

    # Filter out tokens that have a market cap below 200,000 Ksats
    print("Filtering out tokens that have a market cap below 1.5 BTC (We do no chase tokens to the bottom)")
    odin_tokens = [token for token in odin_tokens if token['marketcap'] / 1e11 >= 1.5]

    print("\n\n THE TOKENS WE REBALANCE:")
    print_odin_tokens_table(odin_tokens) 
    print("\n\n")

    total_fund_before = sum(t["value_ksats"] for t in odin_tokens)
    n_tokens = len(odin_tokens)
    max_affordable_target = total_fund_before / n_tokens

    if fund_value_target < max_affordable_target:
        print(f"🚀 Enough capital to target {max_affordable_target:.2f}")

    if fund_value_target > max_affordable_target:
        print(f"⚠️ Not enough capital to target {fund_value_target}, adjusting to {max_affordable_target:.2f}")

    if fund_value_target > max_affordable_target:
        print(f"⚠️  Not enough capital to target {fund_value_target}, adjusting to {max_affordable_target:.2f}")
        fund_value_target = max_affordable_target

    # fund_value_lower_bound = max(30, fund_value_target * 0.70)
    # fund_value_upper_bound = fund_value_target * 1.30
    fund_value_lower_bound = max(30, fund_value_target * 0.80)
    fund_value_upper_bound = fund_value_target * 1.20

    print(f"fund_value_target      = {fund_value_target:.2f}")
    print(f"fund_value_lower_bound = {fund_value_lower_bound:.2f}")
    print(f"fund_value_upper_bound = {fund_value_upper_bound:.2f}")

    trades = []    
    total_fees = 0.0

    for token in odin_tokens:
        fv = token["value_ksats"]
        price_per_token_sats = token["price_sats"]
        price_per_token = price_per_token_sats * 1e-3 # convert to ksats

        if price_per_token <= 0:
            continue  # skip invalid token

        if fv < fund_value_lower_bound:
            amount_to_buy = (fund_value_target - fv) / (1 - trade_fee_rate)
            if amount_to_buy > 1: # 1 ksats is the minimum amount to buy
                fee = amount_to_buy * trade_fee_rate
                num_tokens = amount_to_buy / price_per_token
                trades.append({
                    "odin_token_id": token["odin_token_id"],
                    "token_name": token["token_name"],
                    "action": "BUY",
                    "amount": round(amount_to_buy, 2),
                    "fee": round(fee, 4),
                    "num_tokens": round(num_tokens, 4)
                })
                total_fees += fee

        elif fv > fund_value_upper_bound:
            amount_to_sell = fv - fund_value_target
            if amount_to_sell > 1: # 1 ksats is the minimum amount to buy
                fee = amount_to_sell * trade_fee_rate
                num_tokens = amount_to_sell / price_per_token
                trades.append({
                    "odin_token_id": token["odin_token_id"],
                    "token_name": token["token_name"],
                    "action": "SELL",
                    "amount": round(amount_to_sell, 2),
                    "fee": round(fee, 4),
                    "num_tokens": round(num_tokens, 4)
                })
                total_fees += fee

    final_fund_value = sum(
        fund_value_target if (t["value_ksats"] < fund_value_lower_bound or t["value_ksats"] > fund_value_upper_bound) else t["value_ksats"]
        for t in odin_tokens
    )
    
    sells = [trade for trade in trades if trade["action"] == "SELL"]
    buys  = [trade for trade in trades if trade["action"] == "BUY"]
    sells_tokens = [trade for trade in sells]
    buys_tokens = [trade for trade in buys]

    total_sells = sum(t["amount"] for t in sells)
    total_buys = sum(t["amount"] for t in buys)
    profit = total_sells - total_buys - total_fees

    tokens_to_buy_for_liquidity = 0.0
    if liquidity_token_name is not None:
        if profit > 0:
            # How many tokens to of the liquidity_token_name

            # get price of liquidity token from odin_tokens
            price_liquidity_token = next(
                (token["price_sats"] * 1e-3 for token in odin_tokens if token["token_name"] == liquidity_token_name),
                None
            )
            if price_liquidity_token is None or price_liquidity_token <= 0:
                raise ValueError("Invalid or missing price for the liquidity token")
            tokens_to_buy_for_liquidity = 0.5*profit*(1.0-trade_fee_rate) / price_liquidity_token

    

    return (
        total_fund_before,
        final_fund_value,
        profit,
        tokens_to_buy_for_liquidity,
        trades,
        sells,
        buys,
        sells_tokens,
        buys_tokens
    )
   
def generate_rebalance_message(
    odin_user_name,
    total_fund_before,
    final_fund_value,
    profit,
    sells,
    buys,
    sells_tokens,
    buys_tokens,
    tokens_to_buy_for_liquidity,
    liquidity_token_name=None,
    liquidity_token_url=None
) -> str:
    def format_trade_line(token_name, num_tokens, amount, fee, sign):
        return f"• {token_name:<10} {amount:>6.1f}K sats ({amount*0.00001:.5f} BTC) ({num_tokens:>10,.1f} tokens) ({fee:>6.2f} fee)"

    lines = []
    if liquidity_token_name is None:
        lines.append(f"(🤖) 📊 Odin.Fun Token Holding Rebalance for account: {odin_user_name} \n")
    else:
        lines.append(f"(🤖) 📊 Odin.Fun Token Holding Rebalance & Liquidity Generation for account: {odin_user_name} \n")
        if liquidity_token_url is not None:
            lines.append(f"👉 {liquidity_token_url}")

    total_sell_amount = 0.0
    for t in sells_tokens:
        total_sell_amount += t['amount']
    lines.append(f"\n💰 SELL: ")
    total_sell_amount = 0.0
    total_sell_tokens = 0.0
    total_sell_fees = 0.0
    if sells_tokens:
        for t in sells_tokens:
            lines.append(format_trade_line(t['token_name'], t['num_tokens'], t['amount'], t['fee'], sign="-"))
            total_sell_tokens += t['num_tokens']
            total_sell_amount += t['amount']
            total_sell_fees += t['fee']

    total_buy_amount = 0.0
    for t in buys_tokens:
        total_buy_amount += t['amount']
    lines.append(f"\n🛒 BUY: ")
    total_buy_amount = 0.0
    total_buy_tokens = 0.0
    total_buy_fees = 0.0
    if buys_tokens:
        for t in buys_tokens:
            lines.append(format_trade_line(t['token_name'], t['num_tokens'], t['amount'], t['fee'], sign="+"))
            total_buy_tokens += t['num_tokens']
            total_buy_amount += t['amount']
            total_buy_fees += t['fee']

    if liquidity_token_name is None:
        if profit > 0:
            lines.append(f"\n📈 ckBTC remaining from trades (uninvested for now): {profit:.4f}K sats")
    else:
        lines.append(f"\n💧 Liquidity added to {liquidity_token_name}: {profit:.4f}K sats")

    return "\n".join(lines)