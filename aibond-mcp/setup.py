from setuptools import setup

setup(
    name="aibond-mcp",
    version="1.3.0",
    description="aibond MCP Server - 企业级人机协同平台 MCP 接口",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="aibond",
    author_email="aibond@aib2b.bond",
    url="https://aib2b.bond",
    project_urls={
        "Repository": "https://github.com/fenix19830717a-sudo/aibond",
    },
    license="MIT",
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords=["mcp", "agent", "workflow", "multi-agent", "ai", "collaboration"],
)