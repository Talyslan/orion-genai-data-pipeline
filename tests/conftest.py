import pytest


@pytest.fixture
def sample_html() -> str:
    return """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body><p>Hello</p></body>
</html>"""
