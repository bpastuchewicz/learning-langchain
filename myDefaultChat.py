from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import os
from langchain_core.tools import tool
from ddgs import DDGS
import ast
import operator
import httpx
import time

# Cache dla session tokena
_session_token_cache = {
    "token": None,
    "expires_at": 0
}

def _exchange_github_token_to_session(github_token: str) -> dict:
    """Wymienia GitHub PAT na tymczasowy session token (ważny ~25-30 minut)"""
    response = httpx.get(
        "https://api.github.com/copilot_internal/v2/token",
        headers={
            "Authorization": f"Bearer {github_token}",
            "User-Agent": "GithubCopilot/1.155.0",
            "Accept": "application/json",
        },
        timeout=10.0
    )
    response.raise_for_status()
    return response.json()

def _get_valid_session_token(github_token: str) -> str:
    """Pobiera ważny session token, wymienia jeśli potrzeba"""
    current_time = time.time()
    
    # Sprawdzenie czy cached token jest jeszcze ważny (z marginesem 60s)
    if (_session_token_cache["token"] and 
        current_time < _session_token_cache["expires_at"] - 60):
        return _session_token_cache["token"]
    
    # Wymiana tokena
    result = _exchange_github_token_to_session(github_token)
    
    _session_token_cache["token"] = result["token"]
    _session_token_cache["expires_at"] = result.get("expires_at", current_time + 1500)
    
    return _session_token_cache["token"]

def copilotChat(*args, **kwargs):
    kwargs.setdefault("model", "gpt-4o")
    kwargs.setdefault("base_url", "https://api.githubcopilot.com")
    
    # Pobierz GitHub token (PAT)
    github_token = kwargs.pop("github_token", None) or os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise ValueError(
            "GitHub PAT token jest wymagany. Podaj jako github_token=... lub GITHUB_TOKEN env var"
        )
    
    # Wymień PAT na session token
    session_token = _get_valid_session_token(github_token)
    kwargs.setdefault("api_key", session_token)
    
    # Definiujemy nagłówki wymagane przez zaporę Copilota
    copilot_headers = {
        "Editor-Version": "vscode/1.95.3",
        "Editor-Plugin-Version": "copilot/1.250.0",
        "User-Agent": "GithubCopilot/1.250.0",
        "Accept": "*/*",
    }
    
    # === POPRAWKA: Przekazujemy nagłówki przez dedykowany klient HTTP ===
    kwargs["http_client"] = httpx.Client(headers=copilot_headers)
    # ===================================================================
    
    print("[DEBUG] Inicjalizacja copilotChat z własnym httpx.Client...")
    
    return ChatOpenAI(*args, **kwargs)

def myDefaultChat(*args, **kwargs):
    # Ustawia gpt-4o jako domyślny, chyba że wskażesz inny model przy wywołaniu
    kwargs.setdefault("model", "gpt-4o")
    kwargs.setdefault("base_url", "https://models.inference.ai.azure.com")
    return ChatOpenAI(*args, **kwargs)

def MyDefaultEmbeddings(*args, **kwargs):
    kwargs.setdefault("model", "text-embedding-3-small")
    # GitHub używa dedykowanego endpointu dla embeddingów
    kwargs.setdefault("base_url", "https://models.github.ai/inference")
    return OpenAIEmbeddings(*args, **kwargs)

@tool
def web_search(query: str) -> str:
    """Przeszukuje internet za pomocą DuckDuckGo, aby znaleźć aktualne informacje."""
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=3)
            if not results:
                return "Brak wyników wyszukiwania."
            
            # Łączymy wyniki w czytelny dla LLM blok tekstu
            return "\n\n".join([
                f"Tytuł: {res['title']}\nLink: {res['href']}\nTreść: {res['body']}"
                for res in results
            ])
    except Exception as e:
        return f"Błąd podczas wyszukiwania: {str(e)}"


operators = {
    ast.Add: operator.add, 
    ast.Sub: operator.sub, 
    ast.Mult: operator.mul,
    ast.Div: operator.truediv, 
    ast.Pow: operator.pow, 
    ast.USub: operator.neg
}

def eval_expr(node):
    if isinstance(node, ast.Num):  # Dla starszych wersji Pythona
        return node.n
    elif isinstance(node, ast.Constant):  # Python 3.8+
        return node.value
    elif isinstance(node, ast.BinOp):
        return operators[type(node.op)](eval_expr(node.left), eval_expr(node.right))
    elif isinstance(node, ast.UnaryOp):
        return operators[type(node.op)](eval_expr(node.operand))
    else:
        raise TypeError(node)

@tool
def calculator(query: str) -> str:
    """A simple calculator tool. Input should be a mathematical expression like '2+2' or '1933-1872'."""
    try:
        # Usuwamy ewentualne zbędne znaki/spacje
        clean_query = query.strip().replace(" ", "")
        tree = ast.parse(clean_query, mode='eval')
        return str(eval_expr(tree.body))
    except Exception as e:
        return f"Error: Could not compute expression. {str(e)}"