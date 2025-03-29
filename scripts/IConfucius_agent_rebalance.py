"""IConfucius agent implementation for maintaining his own index fund of the top 10 Odin.Fun tokens."""

# pylint: disable=invalid-name, too-few-public-methods, no-member, too-many-statements

import sys
import json
import requests
from pathlib import Path
from typing import List, Dict, Tuple
from ic_py_canister import get_canister
import pprint
import jwt
from dotenv import load_dotenv
import os
import random
import tweepy
from datetime import datetime
from pytz import timezone
from my_odin_api import odin_post_a_comment, odin_get_user_tokens, print_odin_tokens_table, calculate_trades_index_fund_rebalance, generate_rebalance_message

ROOT_PATH = Path(__file__).parent.parent

#  0 - none
#  1 - minimal
#  2 - a lot
DEBUG_VERBOSE = 1

from typing import List, Dict, Tuple

if __name__ == "__main__":
    print("=======================================================")
    est = timezone('America/Detroit')
    current_time = datetime.now(est).strftime('%Y-%m-%d %I:%M:%S %p %Z')
    print(f"Start time: {current_time}")
    print("=======================================================")
    # Verify the Python interpreter
    print(sys.executable)

    # Load the environment variables from the .env file
    load_dotenv()

    # The account that holds the tokens
    ODIN_USER_NAME = "IConfucius (Agent)" 
    ODIN_USER_ID = os.getenv("ODIN_ICONFUCIUS_AGENT_USER_ID")
    ODIN_JWT = os.getenv("ODIN_ICONFUCIUS_AGENT_JWT") # Do NOT print this out. It's a secret.

    LIQUIDITY_TOKEN_NAME = "ICONFUCIUS"
    LIQUIDITY_TOKEN_ID = "29m8"
    LIQUIDITY_TOKEN_URL = f"https://odin.fun/token/{LIQUIDITY_TOKEN_ID}"

    # Your credentials from the X Developer Portal
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

    live_odin = False  # if True, we will post the trades to the Odin.Fun API
    live_X = False  # if True, we will post the trades to X (Twitter)

    print(f"live_odin = {live_odin}")
    print(f"live_X    = {live_X}")

    odin_tokens = odin_get_user_tokens(ODIN_USER_ID, ODIN_JWT)
    if odin_tokens is None:
        print("Error fetching user tokens")
        sys.exit(1)

    TRADE_FEE_RATE_PERCENT = 0.5  # % after bonding (So, we make a litte error if we own non-bonded tokens, which have a higher fee)
    FUND_VALUE_TARGET = 50.0
    FUND_VALUE_LOWER_BOUND = 40.0
    FUND_VALUE_UPPER_BOUND = 60.0

    no_trade_tokens = [
        "FORSETI",
    ]
    
    (
        total_fund_before,
        final_fund_value,
        profit,
        tokens_to_buy_for_liquidity,
        trades,
        sells,
        buys,
        sells_tokens,
        buys_tokens
    ) = calculate_trades_index_fund_rebalance(
            odin_tokens, no_trade_tokens,
            TRADE_FEE_RATE_PERCENT, 
            FUND_VALUE_TARGET, FUND_VALUE_LOWER_BOUND, FUND_VALUE_UPPER_BOUND, 
            liquidity_token_name=LIQUIDITY_TOKEN_NAME
        )


    print("-------------------------------------------------------")
    message = generate_rebalance_message(
        ODIN_USER_NAME,
        total_fund_before,
        final_fund_value,
        profit,
        sells,
        buys,
        sells_tokens,
        buys_tokens,
        tokens_to_buy_for_liquidity,
        liquidity_token_name=LIQUIDITY_TOKEN_NAME,
        liquidity_token_url=LIQUIDITY_TOKEN_URL
    )
    print(message)

    # Tell user to manually execute the trades
    print("-------------------------------------------------------")
    print("Please execute the trades manually")
    print("Press any key upon completion of the trades to continue.")
    answer = input().strip().lower()
    print("-------------------------------------------------------")

    # Ask user if they want to post the trades to X
    print("-------------------------------------------------------")
    print("Do you want to post the above message to X? (y/n)")
    answer = input().strip().lower()
    if answer == "y":
        live_X = True

    if live_X:
        print("-------------------------------------------------------")
        print(f"Posting trades to the X API")
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
    
    # Ask user if they want to post the trades to Odin.Fun
    print("-------------------------------------------------------")
    print("Do you want to post the above message to Odin.Fun? (y/n)")
    answer = input().strip().lower()
    if answer == "y":
        live_odin = True

    if live_odin:

        print("-------------------------------------------------------")
        print(f"Posting trades to the Odin.Fun API")

        # Post to theICONFUCIUS token
        print(f"Posting to token: LIQUIDITY_TOKEN_NAME (ID: {LIQUIDITY_TOKEN_ID})")

        comment_data = {"message": message}
        try:
            response = odin_post_a_comment(
                ODIN_USER_ID, ODIN_JWT, odin_token_id=LIQUIDITY_TOKEN_ID, comment_data=comment_data
            )
            print(f"Odin Response Status Code: {response.status_code}")
            if response.status_code == 201:
                print(f"Odin Response JSON: {response.json()}")
        except requests.exceptions.RequestException as e:
            print(f"Odin: An exception has occurred. Request Failed: {e}")
        except ValueError as e:
            print(f"Odin: An exception has occurred: {e}")


    print("-------------------------------------------------------")
    current_time = datetime.now(est).strftime('%Y-%m-%d %I:%M:%S %p %Z')
    print(f"End time: {current_time}")




    