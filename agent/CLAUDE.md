# CLAUDE.md - Development Guidelines for iconfucius

This document contains critical development guidelines, patterns, and best practices learned from building the funnai_django application.

## What is iconfucius

iconfucius is a Python CLI & SDK for trading Bitcoin Runes on Odin.fun.
IConfucius | Wisdom for Bitcoin Markets.

# 🚨 Critical Instructions (MUST FOLLOW)

**YOU MUST follow these rules at all times:**
- ✅ Do what has been asked; nothing more, nothing less
- ✅ NEVER create files unless absolutely necessary for achieving your goal
- ✅ ALWAYS prefer editing existing files to creating new ones
- ✅ NEVER proactively create documentation files (*.md) or README files unless explicitly requested

---

## 🎯 Core Design Principles

**Apply these principles to ALL code you write:**

- **DRY (Don't Repeat Yourself)**: Extract repeated logic into reusable functions, methods, or model properties. If you're writing the same code twice, refactor it.

- **YAGNI (You Aren't Gonna Need It)**: Only implement what's explicitly requested. Don't add "nice to have" features, future-proofing, or speculative abstractions.

- **KISS (Keep It Simple, Stupid)**: Prefer simple, straightforward solutions over clever or complex ones. Simple code is easier to test, debug, and maintain.

- **SOLID Principles**:
  - **Single Responsibility**: Each class/function should do one thing well
  - **Open/Closed**: Extend behavior through composition, not modification
  - **Liskov Substitution**: Subtypes must be substitutable for their base types
  - **Interface Segregation**: Don't force clients to depend on unused methods
  - **Dependency Inversion**: Depend on abstractions, not concrete implementations

**When in doubt, ask for clarification before implementing. Simple, clear code beats clever code every time.**

