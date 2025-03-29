# IConfucius as an OpenChat bot

IConfucius is deployed as a bot in the [OpenChat IConfucius Community](https://oc.app/community/e5qnd-hqaaa-aaaac-any5a-cai/channel/2411296919/?ref=45j3b-nyaaa-aaaac-aokma-cai)

You can ask it to generate a quote for you, by entering:

```bash
/IConfucius
```

TODO: describe it further... with a demo

# References

The following repos serve as a reference for bot implementation in OpenChat:

- [open-chat](https://github.com/open-chat-labs/open-chat)
- [open-chat-bots](https://github.com/open-chat-labs/open-chat-bots.git)
- [motoko_oc_bot_sdk](https://github.com/edjCase/motoko_oc_bot_sdk.git)

# Deploy your own IConfucius as an OpenChat bot

The instructions in this section cover how you can deploy everything locally on your computer.

## Upgrade dfx, compatible with OpenChat

OpenChat is often using a dfx version that is in beta mode. Pleae ensure to upgrade your dfx to
the version mentioned in the [open-chat](https://github.com/open-chat-labs/open-chat) repo:

```bash
dfxvm install <the open-chat dfx version>
dfxvm <the open-chat dfx version>

# Verify with
dfx --version
```

## Install rust

OpenChat is written in rust, so you must install it on your system:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env  # Or restart your terminal
rustc --version
cargo --version
```

## Deploy & Run open-chat

First deploy [open-chat](https://github.com/open-chat-labs/open-chat):

```bash
# Clone the open-chat repo as a child repo of IConfucius.
git clone https://github.com/open-chat-labs/open-chat

# from folder: open-chat
rm -rf .dfx
dfx start --clean
./scripts/deploy-local.sh
```

Start serving the website of your local OpenChat:

```bash
npm install # if not yet done
npm --prefix frontend run dev
```

Open the website at http://localhost:5001/

## Clone motoko_oc_bot_sdk

We are using the very latest version of the [motoko_oc_bot_sdk](https://github.com/edjCase/motoko_oc_bot_sdk.git), so clone it:

```bash
# from root folder of repo
git clone https://github.com/edjCase/motoko_oc_bot_sdk.git

# Then, from folder: src/IConfucius
mops install
```

## Deploy IConfucius

Then, deploy IConfucius, as described in the README.

## Set the OpenChat public key in IConfucius

We need to provide the OpenChat public key to IConfucius, so it can verify
that messages indeed come from OpenChat.

Get the public key of your locally running Open Chat instance, by going to:

`Profile settings` > `Advanced` > `Bot client config`

Copy the OpenChat public key and update the variable `openChatPublicKey`.

```JS
// file: src/IConfucius/src/Main.mo

// Update this based on your open chat instance public key
let openChatPublicKey = Text.encodeUtf8("MF...==");
```

## IConfucius as a command type bot

**Verify IConfucius is up, using dfx**

```bash
# from folder: src/IConfucius
dfx canister call iconfucius_ctrlb_canister health
```

**Register the bot with OpenChat**

Follow the instructions in [Registering the bot](https://github.com/open-chat-labs/open-chat-bots?tab=readme-ov-file#installing-the-bot)

- Create two users
- Login as the first user, and search for the second user
- In the Direct Chats chat box, type in `/register_bot` and fill out these fields:
  - Principal = canister_id of IConfucius
    - local: see src/IConfucius/.env
    - ic: see src/IConfucius/canister_ids.json
  - Bot name = IConfucius
  - Bot endpoint
    - local: http://<canister_id>.raw.localhost:8080
      - Note: Check port with `dfx info webserver-port`
    - ic: https://<canister_id>.raw.icp0.io/
