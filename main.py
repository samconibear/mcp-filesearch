"""
File search MCP server — zero third-party dependencies, cross-platform.

Lets a client search a designated root directory by filename pattern,
content (grep-style), file extension, or modification time, plus get
basic metadata. All operations are scoped to ROOT_DIR — paths are
resolved and checked to prevent escaping it via "../" traversal.

Run with: python3 file_search_mcp_server.py /path/to/your/directory
(defaults to the current working directory if no argument given)
"""

import fnmatch
import os
import sys
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("file-search-server")

ROOT_DIR = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()

if not ROOT_DIR.is_dir():
    print(f"Error: {ROOT_DIR} is not a directory", file=sys.stderr)
    sys.exit(1)

# Directories to skip during walks — version control internals, dependency
# trees, and build outputs that are rarely what someone is searching for
_SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", ".next", ".nuxt", ".idea",
    "__pycache__", ".venv", ".env", "site-packages", "*.egg-info",
    "target", ".gradle", ".mvn", ".build", ".terraform", "cdk.out", ".DS_Store",
}
# Hard cap on results returned in one call, to avoid flooding the model's
# context with thousands of matches from a broad pattern
_MAX_RESULTS = 200


def _resolve_within_root(relative_path: str) -> Path | None:
    candidate = (ROOT_DIR / relative_path).resolve()
    if ROOT_DIR not in candidate.parents and candidate != ROOT_DIR:
        return None
    return candidate


def _iter_files():
    for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            yield Path(dirpath) / name


@mcp.tool()
def find_by_name(pattern: str, case_sensitive: bool = False) -> list[dict]:
    """
    Find files by FILENAME pattern (not file content — use search_content for that).
    Use this when the user names a specific filename, prefix, or suffix pattern,
    e.g. "find config.json", "find files starting with test_", "find anything called README".
    Accepts glob syntax: '*' for any characters, '?' for one character.
    Examples: 'config.*' matches config.json/config.yaml; 'test_*.py' matches test_main.py.
    If the user is asking for "all .py files" or "all markdown files" with no other
    qualifier, prefer find_by_extension instead — it's the more direct match for that phrasing."""  
    matches = []
    match_pattern = pattern if case_sensitive else pattern.lower()
    for path in _iter_files():
        name = path.name if case_sensitive else path.name.lower()
        if fnmatch.fnmatch(name, match_pattern):
            matches.append({
                "path": str(path.relative_to(ROOT_DIR)),
                "size_bytes": path.stat().st_size,
            })
            if len(matches) >= _MAX_RESULTS:
                break
    return matches


@mcp.tool()
def find_by_extension(extension: str) -> list[dict]:
    """
    Find ALL files of a given file type across the whole directory tree.
    Use this for requests phrased by file TYPE rather than filename, e.g.
    "find all Python files", "list every markdown file", "show me the JSON files".
    Pass just the extension, with or without a leading dot: 'py', '.py', 'docx', '.md'.
    This is preferred over find_by_name when the request has no filename pattern,
    just a type — find_by_name is for when the user names or describes the filename itself.
    """
    ext = extension if extension.startswith(".") else f".{extension}"
    return find_by_name(f"*{ext}")


@mcp.tool()
def search_content(
    query: str,
    file_glob: str = "*",
    case_sensitive: bool = False,
    max_matches_per_file: int = 5,
) -> list[dict]:
    """
    Search INSIDE files for a piece of text (not filenames — use find_by_name/find_by_extension
    for that. Use this when the user wants to know which files mention or contain something,
    e.g. "which files mention TODO", "find where the function 'connect' is defined",
    "search my notes for 'budget'". Returns matching lines with line numbers, not whole files —
    use read_file afterward if the user then wants full file content.
    query is a PLAIN SUBSTRING match, not a regex — special characters like '.' or '*' are
    matched literally, not as wildcards. file_glob narrows which files are searched
    (default '*' searches everything); pass e.g. '*.py' to search only Python files.
    """
    results = []
    needle = query if case_sensitive else query.lower()

    for path in _iter_files():
        if not fnmatch.fnmatch(path.name, file_glob):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                file_matches = []
                for line_num, line in enumerate(f, start=1):
                    haystack = line if case_sensitive else line.lower()
                    if needle in haystack:
                        file_matches.append({"line": line_num, "text": line.strip()[:200]})
                        if len(file_matches) >= max_matches_per_file:
                            break
        except (UnicodeDecodeError, PermissionError, OSError):
            continue  # non-text files

        if file_matches:
            results.append({"path": str(path.relative_to(ROOT_DIR)), "matches": file_matches})
            if len(results) >= _MAX_RESULTS:
                break

    return results


@mcp.tool()
def list_directory(relative_path: str = ".") -> dict:
    """
    List what's directly inside ONE folder — not recursive, not a search.
    Use this for browsing requests like "what's in my downloads folder",
    "show me the contents of src/", "what's in the root directory" (use relative_path="." for that).
    If the user instead wants files matching a name/type ANYWHERE in the tree, use
    find_by_name or find_by_extension instead — those search recursively, this does not.
    """
    target = _resolve_within_root(relative_path)
    if target is None:
        return {"error": f"path escapes root directory: {relative_path}"}
    if not target.is_dir():
        return {"error": f"not a directory: {relative_path}"}

    entries = []
    for entry in sorted(target.iterdir()):
        if entry.name in _SKIP_DIRS:
            continue
        entries.append({
            "name": entry.name,
            "type": "directory" if entry.is_dir() else "file",
            "size_bytes": entry.stat().st_size if entry.is_file() else None,
        })
    return {"path": relative_path, "entries": entries}


@mcp.tool()
def get_file_info(relative_path: str) -> dict:
    """
    Get METADATA about one file — size, last-modified time, extension — WITHOUT reading its
    content. Use this for questions like "how big is X", "when was X last changed",
    "is X a file or a folder". If the user wants the actual file CONTENT, use read_file instead —
    this tool never returns what's inside the file.
    """
    target = _resolve_within_root(relative_path)
    if target is None:
        return {"error": f"path escapes root directory: {relative_path}"}
    if not target.exists():
        return {"error": f"file not found: {relative_path}"}

    stat = target.stat()
    return {
        "path": relative_path,
        "size_bytes": stat.st_size,
        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
        "extension": target.suffix,
        "is_directory": target.is_dir(),
    }


@mcp.tool()
def find_recently_modified(within_hours: float = 24, file_glob: str = "*") -> list[dict]:
    """
    Find files changed recently, ranked newest-first. Use this for time-based requests like
    "what have I changed today", "what's new in this folder", "files modified in the last hour".
    within_hours sets the lookback window (24 = last day, 1 = last hour, 168 = last week).
    Optional file_glob narrows by type, e.g. '*.py' for only recently changed Python files.
    Not for filename or content search — use find_by_name/search_content for those instead.
    """
    cutoff = time.time() - (within_hours * 3600)
    matches = []
    for path in _iter_files():
        if not fnmatch.fnmatch(path.name, file_glob):
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime >= cutoff:
            matches.append({
                "path": str(path.relative_to(ROOT_DIR)),
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)),
            })
            if len(matches) >= _MAX_RESULTS:
                break
    matches.sort(key=lambda m: m["modified"], reverse=True)
    return matches


@mcp.tool()
def read_file(relative_path: str, max_chars: int = 5000) -> dict:
    """
    Read the FULL TEXT CONTENT of one specific file you already know the path to.
    Use this when the user wants to see, review, or have you analyze/summarize what's
    actually written inside a file, e.g. "show me main.py", "what does the README say",
    "read notes.md and summarize it". relative_path must be the path WITHIN the root
    directory (e.g. "src/main.py"), not an absolute filesystem path.
    Do NOT use this to merely check if a file exists or how big it is — use get_file_info
    for that. Do NOT use this to search across many files for a keyword — use
    search_content for that; this tool only reads one named file at a time.
    """
    target = _resolve_within_root(relative_path)
    if target is None:
        return {"error": f"path escapes root directory: {relative_path}"}
    if not target.is_file():
        return {"error": f"not a file: {relative_path}"}

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"error": "file appears to be binary, not text"}
    except PermissionError:
        return {"error": "permission denied"}

    truncated = len(content) > max_chars
    return {
        "path": relative_path,
        "content": content[:max_chars],
        "truncated": truncated,
        "total_chars": len(content),
    }


if __name__ == "__main__":
    print(f"File search server rooted at: {ROOT_DIR}", file=sys.stderr)
    mcp.run(transport="stdio")