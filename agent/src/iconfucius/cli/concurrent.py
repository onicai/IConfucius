"""
iconfucius.cli.concurrent — Run per-bot operations concurrently

Uses ThreadPoolExecutor for I/O-bound bot operations (SIWB login,
IC canister queries, REST API calls).
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from iconfucius.logging_config import get_logger

# Module-level progress callback set by the chat spinner.
# Signature: on_progress(done: int, total: int)
_progress_callback = None


def set_progress_callback(callback):
    """Set the module-level progress callback (or None to clear)."""
    global _progress_callback
    _progress_callback = callback


def run_per_bot(fn, bot_names, max_workers=5):
    """Run fn(bot_name) concurrently for each bot.

    Args:
        fn: Callable that takes a bot_name string.
        bot_names: List of bot name strings.
        max_workers: Max concurrent threads (default 5).

    Returns:
        List of (bot_name, result_or_exception) in original bot_names order.
        Exceptions are caught per-bot so one failure doesn't kill the rest.
    """
    if not bot_names:
        return []

    logger = get_logger()
    total = len(bot_names)
    results = {}
    done_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fn, name): name for name in bot_names}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                results[name] = e
            done_count += 1
            logger.info("  [%d/%d] %s done", done_count, total, name)
            if _progress_callback:
                _progress_callback(done_count, total)

    return [(name, results[name]) for name in bot_names]
