"""Tests for iconfucius.skills.definitions — Tool schemas and metadata."""

from iconfucius.skills.definitions import (
    TOOLS,
    get_tool_metadata,
    get_tools_for_anthropic,
)


class TestToolSchemas:
    def test_tools_not_empty(self):
        assert len(TOOLS) > 0

    def test_each_tool_has_required_fields(self):
        for t in TOOLS:
            assert "name" in t, f"Missing 'name' in {t}"
            assert "description" in t, f"Missing 'description' in {t.get('name')}"
            assert "input_schema" in t, f"Missing 'input_schema' in {t['name']}"
            assert "requires_confirmation" in t, f"Missing 'requires_confirmation' in {t['name']}"
            assert "category" in t, f"Missing 'category' in {t['name']}"

    def test_categories_are_valid(self):
        for t in TOOLS:
            assert t["category"] in ("read", "write"), (
                f"Invalid category '{t['category']}' for {t['name']}"
            )

    def test_write_tools_require_confirmation(self):
        for t in TOOLS:
            if t["category"] == "write":
                assert t["requires_confirmation"] is True, (
                    f"Write tool '{t['name']}' should require confirmation"
                )

    def test_read_tools_no_confirmation(self):
        for t in TOOLS:
            if t["category"] == "read":
                assert t["requires_confirmation"] is False, (
                    f"Read tool '{t['name']}' should not require confirmation"
                )

    def test_input_schema_is_object_type(self):
        for t in TOOLS:
            schema = t["input_schema"]
            assert schema["type"] == "object", (
                f"Tool '{t['name']}' input_schema must be object type"
            )

    def test_unique_tool_names(self):
        names = [t["name"] for t in TOOLS]
        assert len(names) == len(set(names)), "Duplicate tool names found"


class TestGetToolsForAnthropic:
    def test_strips_metadata(self):
        tools = get_tools_for_anthropic()
        for t in tools:
            assert "requires_confirmation" not in t
            assert "category" not in t

    def test_keeps_required_fields(self):
        tools = get_tools_for_anthropic()
        for t in tools:
            assert "name" in t
            assert "description" in t
            assert "input_schema" in t

    def test_same_count_as_tools(self):
        assert len(get_tools_for_anthropic()) == len(TOOLS)


class TestGetToolMetadata:
    def test_finds_existing_tool(self):
        meta = get_tool_metadata("wallet_balance")
        assert meta is not None
        assert meta["name"] == "wallet_balance"
        assert "requires_confirmation" in meta

    def test_returns_none_for_unknown(self):
        assert get_tool_metadata("nonexistent_tool") is None

    def test_finds_write_tool(self):
        meta = get_tool_metadata("trade_buy")
        assert meta is not None
        assert meta["requires_confirmation"] is True
        assert meta["category"] == "write"


class TestMemoryToolDefinitions:
    def test_memory_read_strategy_exists(self):
        meta = get_tool_metadata("memory_read_strategy")
        assert meta is not None
        assert meta["requires_confirmation"] is False
        assert meta["category"] == "read"

    def test_memory_read_learnings_exists(self):
        meta = get_tool_metadata("memory_read_learnings")
        assert meta is not None
        assert meta["requires_confirmation"] is False
        assert meta["category"] == "read"

    def test_memory_update_exists(self):
        meta = get_tool_metadata("memory_update")
        assert meta is not None
        assert meta["requires_confirmation"] is True
        assert meta["category"] == "write"

    def test_memory_update_schema_has_file_enum(self):
        meta = get_tool_metadata("memory_update")
        props = meta["input_schema"]["properties"]
        assert "file" in props
        assert props["file"]["enum"] == ["strategy", "learnings"]

    def test_memory_tools_in_anthropic_format(self):
        tools = get_tools_for_anthropic()
        names = [t["name"] for t in tools]
        assert "memory_read_strategy" in names
        assert "memory_read_learnings" in names
        assert "memory_update" in names


class TestTokenPriceDefinition:
    """Tests for the token_price tool definition."""

    def test_token_price_exists(self):
        meta = get_tool_metadata("token_price")
        assert meta is not None
        assert meta["requires_confirmation"] is False
        assert meta["category"] == "read"

    def test_token_price_schema_has_query(self):
        meta = get_tool_metadata("token_price")
        props = meta["input_schema"]["properties"]
        assert "query" in props
        assert meta["input_schema"]["required"] == ["query"]

    def test_token_price_in_anthropic_format(self):
        tools = get_tools_for_anthropic()
        names = [t["name"] for t in tools]
        assert "token_price" in names
