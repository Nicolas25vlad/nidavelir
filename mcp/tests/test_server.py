from nidavelir_mcp import server


def test_server_module_imports() -> None:
    assert server.mcp is not None
