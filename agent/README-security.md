# Security Considerations

iconfucius handles Bitcoin funds via ckBTC. This document covers security considerations and best practices.

## 1. IC Response Verification

**Status: Optional (disabled by default but highly recommended to activate)**

The Internet Computer uses BLS threshold signatures to certify canister responses. All communication with IC boundary nodes is already protected by HTTPS/TLS. For additional protection against man-in-the-middle attacks at the network level, certificate verification can be enabled. This cryptographically proves that each response genuinely came from the target canister on the IC.

When disabled, update calls (trades, transfers, withdrawals) are still protected by IC consensus signatures. Certificate verification adds protection for query calls (balance checks, fee estimates, address lookups).

### Enabling certificate verification

Certificate verification requires the [`blst`](https://github.com/supranational/blst) library (BLS12-381 signatures). Since `blst` is not available on PyPI, it is built from source. This requires a C compiler and [SWIG](https://www.swig.org/) (Simplified Wrapper and Interface Generator).

**Step 1: Install C compiler and SWIG**

macOS:
```bash
xcode-select --install
brew install swig
```

Linux (Debian/Ubuntu):
```bash
sudo apt-get install build-essential swig python3-dev
```

Linux (Fedora/RHEL):
```bash
sudo dnf install gcc gcc-c++ make swig python3-devel
```

Windows: Use WSL2 with Ubuntu and follow the Linux instructions above.

**Step 2: Build and install `blst`**

Activate the Python environment where iconfucius is installed before running these commands.

```bash
BLST_VERSION=v0.3.16
BLST_DIR=$(mktemp -d)
git clone --branch $BLST_VERSION --depth 1 https://github.com/supranational/blst $BLST_DIR
(cd $BLST_DIR/bindings/python && python3 run.me) || true
cp $BLST_DIR/bindings/python/blst.py \
    $(python3 -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")/
cp $BLST_DIR/bindings/python/_blst*.so \
    $(python3 -c "import sysconfig; print(sysconfig.get_paths()['platlib'])")/
rm -rf $BLST_DIR
python3 -c "import blst; print('blst installed successfully')"
```

Note: On macOS you may see a `P1_Affines_as_memory returned NULL` error during the build's self-tests. This can be safely ignored — the library is installed correctly if the final line prints `blst installed successfully`.

On Apple Silicon (M1/M2/M3), if you encounter ABI issues, set `export BLST_PORTABLE=1` before running the commands above.

**Step 3: Enable in iconfucius**

Add to your `iconfucius.toml`:
```toml
[settings]
verify_certificates = true
```

When enabled, all IC canister responses are cryptographically verified. If `blst` is not installed, iconfucius will exit with an error explaining how to install it.

## 2. Credential Storage

iconfucius stores two types of credentials on disk. Both are excluded from version control via `.gitignore`.

### Wallet Identity (`.wallet/identity-private.pem`)

Your Ed25519 private key. This is the master key that controls your wallet and all bot identities derived from it.

| Property     | Value                                                     |
|--------------|-----------------------------------------------------------|
| Permissions  | `0600` (owner-only read/write)                            |
| Encryption   | None (plaintext PEM, same model as `~/.ssh/id_ed25519`)   |
| Lifetime     | Permanent (until deleted or regenerated)                  |
| Git excluded | Yes (`.gitignore`)                                        |

**Best practices:**
- Back up this file securely (encrypted USB, password manager, etc.)
- If lost, you lose access to your wallet and all funds
- If leaked, anyone can control your wallet
- Never commit to version control
- Never share with anyone

### Session Cache (`.cache/session_*.json`)

Ephemeral session credentials created during SIWB login. Each bot gets its own session file.

| Property     | Value                                                     |
|--------------|-----------------------------------------------------------|
| Permissions  | `0600` (owner-only read/write)                            |
| Encryption   | None (plaintext JSON)                                     |
| Lifetime     | 24 hours (JWT expiry), auto-regenerated                   |
| Git excluded | Yes (`.gitignore`)                                        |
| Contains     | JWT token, session private key, delegation chain           |

**What's inside:** A session file contains a JWT (for Odin.fun REST API), an ephemeral Ed25519 session key, and a signed delegation chain from the SIWB canister. Together these allow acting as the bot's principal for up to 24 hours.

**Disabling session caching:** On shared hosts or high-security environments, session caching can be disabled entirely. This forces a fresh SIWB login for every command — no bot credentials are written to disk.

```toml
[settings]
cache_sessions = false
```

**Best practices:**
- Treat session files as sensitive (they contain private keys)
- On shared systems, verify `.cache/` is not readable by other users
- Sessions expire automatically — no manual cleanup needed
- Deleting a session file simply triggers a fresh SIWB login on the next command

## 3. SIWB Phishing Advisory

DFINITY published a [security advisory](https://forum.dfinity.org/t/security-advisory-sign-in-with-ethereum-bitcoin-solana-siw-e-b-s-prone-to-phishing/64050) about Sign In With Bitcoin/Ethereum/Solana (SIW*) implementations being prone to phishing. The vulnerability allows a malicious website to trick a user into signing a login message, granting the attacker a delegation to act as that user's principal.

### Does this affect iconfucius CLI users?

**No.** The phishing attack requires:

1. A browser environment where the attacker can spoof a domain
2. A wallet popup where the user manually approves a signature
3. Social engineering (the phishing site looks like a legitimate site)

iconfucius is a CLI tool. The SIWB login is performed programmatically — the ckSigner canister signs the challenge message autonomously. There is no browser, no wallet popup, and no domain to spoof.

### Does this affect developers using the iconfucius SDK?

**No**, with one edge case:

- **Python scripts and AI agents calling the SDK:** Not affected. Same as the CLI — no browser, no user interaction with the signing flow.
- **Web frontends using SIWB with bot principals:** If you build a browser-based UI that uses SIWB to authenticate the same bot identity that iconfucius uses, the phishing attack applies to your web frontend. This is an unusual architecture — iconfucius is designed as a headless CLI/SDK, not a browser dApp.

If you are building a browser-based application, refer to the [DFINITY advisory](https://forum.dfinity.org/t/security-advisory-sign-in-with-ethereum-bitcoin-solana-siw-e-b-s-prone-to-phishing/64050) for mitigation steps including origin verification, passkey second factors, and ICRC-21 consent messages.
