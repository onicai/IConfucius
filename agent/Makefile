# Makefile for iconfucius Python package

.PHONY: help install install-dev install-blst build clean publish-test publish test lint \
       e2e-setup e2e-fund-check-ckbtc e2e-fund-check-btc \
       e2e-trade-bot-1 e2e-trade-all-bots \
       e2e-wallet-balance-all-bots e2e-withdraw-bot-1 e2e-sweep \
       e2e-send-ckbtc e2e-send-check-ckbtc \
       e2e-send-btc e2e-send-check-btc e2e-clean

help:
	@echo "iconfucius development commands:"
	@echo ""
	@echo "  make install       Install package in current environment"
	@echo "  make install-dev   Install package with dev dependencies"
	@echo "  make build         Build sdist and wheel distributions"
	@echo "  make clean         Remove build artifacts"
	@echo "  make test          Run pytest"
	@echo "  make install-blst  Install blst for IC certificate verification"
	@echo "  make publish-test  Upload to TestPyPI"
	@echo "  make publish       Upload to PyPI (production)"
	@echo ""
	@echo "E2E testing (testing network, real ckBTC and BTC):"
	@echo ""
	@echo "  make e2e-setup               Step 1: init project, create wallet, save return addresses"
	@echo "  make e2e-fund-check-ckbtc    Step 2a: verify ckBTC funding arrived"
	@echo "  make e2e-fund-check-btc      Step 2b: verify BTC-to-ckBTC conversion"
	@echo "  make e2e-trade-bot-1         Step 3a: fund bot-1, buy, sell"
	@echo "  make e2e-trade-all-bots      Step 3b: fund all bots, buy, sell"
	@echo "  make e2e-wallet-balance-all-bots  wallet balance --all-bots"
	@echo "  make e2e-withdraw-bot-1      Step 4: withdraw from bot-1 back to wallet"
	@echo "  make e2e-sweep               Step 5: sweep all bots (sell all tokens + withdraw all)"
	@echo "  make e2e-send-ckbtc        Step 6a: send ckBTC back to return principal"
	@echo "  make e2e-send-check-ckbtc  verify ckBTC send completed"
	@echo "  make e2e-send-btc          Step 6b: send ckBTC as BTC to return address"
	@echo "  make e2e-send-check-btc    verify BTC send completed"
	@echo "  make e2e-clean               Remove e2e-bots-<network>/ directory"
	@echo ""

# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

BLST_VERSION ?= v0.3.16
BLST_COMMIT  ?= e7f90de551e8df682f3cc99067d204d8b90d27ad

install-blst:
	@echo "Installing blst $(BLST_VERSION) from source..."
	$(eval BLST_DIR := $(shell mktemp -d))
	git clone --branch $(BLST_VERSION) --depth 1 https://github.com/supranational/blst $(BLST_DIR)
	@cd $(BLST_DIR) && \
		ACTUAL=$$(git rev-parse HEAD) && \
		if [ "$$ACTUAL" != "$(BLST_COMMIT)" ]; then \
			echo "ERROR: commit mismatch! expected $(BLST_COMMIT), got $$ACTUAL"; \
			rm -rf $(BLST_DIR); \
			exit 1; \
		fi
	(cd $(BLST_DIR)/bindings/python && python3 run.me) || true
	cp $(BLST_DIR)/bindings/python/blst.py \
		$$(python3 -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")/
	cp $(BLST_DIR)/bindings/python/_blst*.so \
		$$(python3 -c "import sysconfig; print(sysconfig.get_paths()['platlib'])")/
	rm -rf $(BLST_DIR)
	@python3 -c "import blst; print('✓ blst installed successfully')"

# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

build: clean
	pip install --quiet build
	python -m build

clean:
	rm -rf dist/
	rm -rf src/*.egg-info/
	rm -rf build/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------

publish-test: build
	pip install --quiet twine
	twine upload --config-file .pypirc --repository testpypi dist/*

publish: build
	pip install --quiet twine
	twine upload --config-file .pypirc dist/*

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

test:
	pytest -v

lint:
	@echo "No linter configured yet"

# ---------------------------------------------------------------------------
# E2E Testing (testing network, real ckBTC and BTC)
#
# Flow:
#   1. make e2e-setup               — init, wallet, return addresses
#   2. (manual) fund wallet with ckBTC (20000 sats) and BTC (20000 sats)
#   3. make e2e-fund-check-ckbtc    — verify ckBTC arrived
#      make e2e-fund-check-btc      — verify BTC → ckBTC conversion
#   4. make e2e-trade-bot-1         — fund bot-1, buy, sell
#      make e2e-trade-all-bots     — fund all bots, buy, sell
#   5. make e2e-withdraw-bot-1      — withdraw from bot-1 back to wallet
#   6. make e2e-sweep               — fund, buy, then sweep
#   7. make e2e-send-ckbtc          — send ckBTC back to principal
#      make e2e-send-check-ckbtc
#      make e2e-send-btc            — send ckBTC as BTC to bc1 address
#      make e2e-send-check-btc
#   8. make e2e-clean               — remove e2e-bots-<network>/
# ---------------------------------------------------------------------------

E2E_NETWORK         ?= testing
E2E_DIR             := e2e-bots-$(E2E_NETWORK)
E2E_BOT             := bot-1
E2E_TOKEN           := 29m8
E2E_FUND_WALLET_AMT := 20000
E2E_FUND_BOTS_AMT  := 5000
E2E_TRADE_AMT      := 1000
E2E_RETURN_CKBTC := $(E2E_DIR)/.e2e-return-ckbtc
E2E_RETURN_BTC   := $(E2E_DIR)/.e2e-return-btc
AMT              ?= all

ODIN := cd $(E2E_DIR) && iconfucius --network $(E2E_NETWORK)

# -- Step 1: Setup -------------------------------------------------------------

e2e-setup:
	@echo "==========================================="
	@echo " E2E Setup: testing network"
	@echo "==========================================="
	@echo ""
	mkdir -p $(E2E_DIR)
	@echo "--- init ---"
	$(ODIN) init
	@echo ""
	@echo "--- wallet create ---"
	$(ODIN) wallet create
	@echo ""
	@echo "--- config ---"
	$(ODIN) config
	@echo ""
	@echo "--- wallet balance ---"
	$(ODIN) wallet balance
	@echo ""
	@echo "--- wallet receive ---"
	$(ODIN) wallet receive
	@echo ""
	@read -p "Enter ckBTC return address (IC principal): " addr; \
		echo "$$addr" > $(E2E_RETURN_CKBTC)
	@read -p "Enter BTC return address (bc1...): " addr; \
		echo "$$addr" > $(E2E_RETURN_BTC)
	@echo ""
	@echo "==========================================="
	@echo " Setup complete"
	@echo " ckBTC return address saved to $(E2E_RETURN_CKBTC)"
	@echo " BTC return address saved to $(E2E_RETURN_BTC)"
	@echo ""
	@echo " Next:"
	@echo "   1. Send $(E2E_FUND_WALLET_AMT) sats ckBTC to the wallet principal"
	@echo "   2. Send $(E2E_FUND_WALLET_AMT) sats BTC to the Bitcoin deposit address"
	@echo "   3. Run: make e2e-fund-check-ckbtc"
	@echo "   4. Run: make e2e-fund-check-btc  (after 6+ confirmations)"
	@echo "==========================================="

# -- Step 2a: Check ckBTC funding ----------------------------------------------

e2e-fund-check-ckbtc:
	@test -d $(E2E_DIR) || (echo "ERROR: Run 'make e2e-setup' first"; exit 1)
	@echo "==========================================="
	@echo " E2E Fund Check: ckBTC"
	@echo "==========================================="
	@echo ""
	$(ODIN) wallet balance
	@echo ""
	@echo "==========================================="
	@echo " If ckBTC balance >= $(E2E_FUND_WALLET_AMT) sats, run: make e2e-trade-bot-1"
	@echo "==========================================="

# -- Step 2b: Check BTC funding ------------------------------------------------

e2e-fund-check-btc:
	@test -d $(E2E_DIR) || (echo "ERROR: Run 'make e2e-setup' first"; exit 1)
	@echo "==========================================="
	@echo " E2E Fund Check: BTC → ckBTC conversion"
	@echo " Monitors until BTC is converted to ckBTC."
	@echo "==========================================="
	@echo ""
	$(ODIN) wallet balance --monitor

# -- Step 3a: Trade with bot-1 only -------------------------------------------

e2e-trade-bot-1:
	@test -d $(E2E_DIR) || (echo "ERROR: Run 'make e2e-setup' first"; exit 1)
	@echo "==========================================="
	@echo " E2E Trade: bot-1 — fund, buy, sell"
	@echo " Network:         $(E2E_NETWORK)"
	@echo " Token:           $(E2E_TOKEN)"
	@echo " Bot fund amount: $(E2E_FUND_BOTS_AMT) sats"
	@echo " Trade amount:    $(E2E_TRADE_AMT) sats"
	@echo "==========================================="
	@echo ""
	@echo "--- 1/5: config ---"
	$(ODIN) config
	@echo ""
	@echo "--- 2/5: fund bot ($(E2E_FUND_BOTS_AMT) sats) ---"
	$(ODIN) fund $(E2E_FUND_BOTS_AMT) --bot $(E2E_BOT)
	@echo ""
	@echo "--- 3/5: trade buy $(E2E_TOKEN) $(E2E_TRADE_AMT) sats ---"
	$(ODIN) trade buy $(E2E_TOKEN) $(E2E_TRADE_AMT) --bot $(E2E_BOT)
	@echo ""
	@echo "Waiting 10s for query replica to sync..."
	@sleep 10
	@echo ""
	@echo "--- 4/5: trade sell $(E2E_TOKEN) all ---"
	$(ODIN) trade sell $(E2E_TOKEN) all --bot $(E2E_BOT)
	@echo ""
	@echo "--- 5/5: balance ---"
	$(ODIN) wallet balance --bot $(E2E_BOT) --token $(E2E_TOKEN)
	@echo ""
	@echo "==========================================="
	@echo " E2E Trade bot-1: COMPLETE"
	@echo ""
	@echo " Next:"
	@echo "   make e2e-trade-all-bots  (trade with all bots)"
	@echo "   make e2e-withdraw-bot-1        (withdraw from bot back to wallet)"
	@echo "   make e2e-sweep           (buy token, then sell all + withdraw all)"
	@echo "==========================================="

# -- Step 3b: Trade with all bots --------------------------------------------

e2e-trade-all-bots:
	@test -d $(E2E_DIR) || (echo "ERROR: Run 'make e2e-setup' first"; exit 1)
	@echo "==========================================="
	@echo " E2E Trade: all bots — fund, buy, sell"
	@echo " Network:         $(E2E_NETWORK)"
	@echo " Token:           $(E2E_TOKEN)"
	@echo " Bot fund amount: $(E2E_FUND_BOTS_AMT) sats (per bot)"
	@echo " Trade amount:    $(E2E_TRADE_AMT) sats (per bot)"
	@echo "==========================================="
	@echo ""
	@echo "--- 1/5: config ---"
	$(ODIN) config
	@echo ""
	@echo "--- 2/5: fund all bots ($(E2E_FUND_BOTS_AMT) sats each) ---"
	$(ODIN) fund $(E2E_FUND_BOTS_AMT) --all-bots
	@echo ""
	@echo "--- 3/5: trade buy $(E2E_TOKEN) $(E2E_TRADE_AMT) sats ---"
	$(ODIN) trade buy $(E2E_TOKEN) $(E2E_TRADE_AMT) --all-bots
	@echo ""
	@echo "Waiting 10s for query replica to sync..."
	@sleep 10
	@echo ""
	@echo "--- 4/5: trade sell $(E2E_TOKEN) all ---"
	$(ODIN) trade sell $(E2E_TOKEN) all --all-bots
	@echo ""
	@echo "--- 5/5: balance ---"
	$(ODIN) wallet balance --all-bots
	@echo ""
	@echo "==========================================="
	@echo " E2E Trade all bots: COMPLETE"
	@echo ""
	@echo " Next:"
	@echo "   make e2e-withdraw-bot-1   (withdraw from bot back to wallet)"
	@echo "   make e2e-sweep      (buy token, then sell all + withdraw all)"
	@echo "==========================================="

# -- Wallet balance all bots ---------------------------------------------------

e2e-wallet-balance-all-bots:
	@test -d $(E2E_DIR) || (echo "ERROR: Run 'make e2e-setup' first"; exit 1)
	@echo "==========================================="
	@echo " E2E Wallet Balance: all bots"
	@echo "==========================================="
	@echo ""
	$(ODIN) wallet balance --all-bots

# -- Step 4: Withdraw (bot-1 → wallet) ----------------------------------------

e2e-withdraw-bot-1:
	@test -d $(E2E_DIR) || (echo "ERROR: Run 'make e2e-setup' first"; exit 1)
	@echo "==========================================="
	@echo " E2E Withdraw: bot-1 → wallet"
	@echo "==========================================="
	@echo ""
	$(ODIN) withdraw all --bot bot-1
	@echo ""
	@echo "==========================================="
	@echo " E2E Withdraw bot-1: COMPLETE"
	@echo ""
	@echo " Next: send funds back"
	@echo "   make e2e-send-ckbtc   (send as ckBTC to principal)"
	@echo "   make e2e-send-btc     (send as BTC to bc1 address)"
	@echo "==========================================="

# -- Step 5: Sweep (fund, buy, then sell all + withdraw all) -------------------

e2e-sweep:
	@test -d $(E2E_DIR) || (echo "ERROR: Run 'make e2e-setup' first"; exit 1)
	@echo "==========================================="
	@echo " E2E Sweep: sell all tokens + withdraw all (all bots)"
	@echo "==========================================="
	@echo ""
	$(ODIN) sweep --all-bots
	@echo ""
	@echo "==========================================="
	@echo " E2E Sweep: COMPLETE"
	@echo ""
	@echo " Next: send funds back"
	@echo "   make e2e-send-ckbtc   (send as ckBTC to principal)"
	@echo "   make e2e-send-btc     (send as BTC to bc1 address)"
	@echo "==========================================="

# -- Step 6a: Send ckBTC -------------------------------------------------------

e2e-send-ckbtc:
	@test -f $(E2E_RETURN_CKBTC) || (echo "ERROR: Run 'make e2e-setup' first"; exit 1)
	$(eval RETURN_ADDR := $(shell cat $(E2E_RETURN_CKBTC)))
	@echo "==========================================="
	@echo " E2E Send: ckBTC → $(RETURN_ADDR)  (amount: $(AMT))"
	@echo "==========================================="
	@echo ""
	$(ODIN) wallet send $(AMT) $(RETURN_ADDR)
	@echo ""
	@echo "==========================================="
	@echo " ckBTC send initiated."
	@echo " Run: make e2e-send-check-ckbtc"
	@echo "==========================================="

e2e-send-check-ckbtc:
	@test -d $(E2E_DIR) || (echo "ERROR: Run 'make e2e-setup' first"; exit 1)
	@echo "==========================================="
	@echo " E2E Send Check: ckBTC"
	@echo "==========================================="
	@echo ""
	$(ODIN) wallet balance
	@echo ""
	@echo "==========================================="
	@echo " Wallet should show zero ckBTC balance."
	@echo "==========================================="

# -- Step 6b: Send BTC ---------------------------------------------------------

e2e-send-btc:
	@test -f $(E2E_RETURN_BTC) || (echo "ERROR: Run 'make e2e-setup' first"; exit 1)
	$(eval RETURN_ADDR := $(shell cat $(E2E_RETURN_BTC)))
	@echo "==========================================="
	@echo " E2E Send: BTC → $(RETURN_ADDR)  (amount: $(AMT))"
	@echo "==========================================="
	@echo ""
	$(ODIN) wallet send $(AMT) $(RETURN_ADDR)
	@echo ""
	@echo "==========================================="
	@echo " BTC send initiated via ckBTC minter."
	@echo " Run: make e2e-send-check-btc"
	@echo "==========================================="

e2e-send-check-btc:
	@test -d $(E2E_DIR) || (echo "ERROR: Run 'make e2e-setup' first"; exit 1)
	@echo "==========================================="
	@echo " E2E Send Check: BTC"
	@echo " Monitors until BTC send completes."
	@echo "==========================================="
	@echo ""
	$(ODIN) wallet balance --monitor

# -- Cleanup -------------------------------------------------------------------

e2e-clean:
	rm -rf $(E2E_DIR)
