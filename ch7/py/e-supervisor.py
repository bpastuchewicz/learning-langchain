import argparse
import os
import re
import sys
import subprocess
from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import MessagesState, StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from myDefaultChat import copilotChat  
from rich import print

# ==========================================
# 0. OBSŁUGA ARGUMENTÓW LINII POLECEŃ (CLI)
# ==========================================
DEFAULT_TASK = "I need to build a simple Python script that scrapes weather data from an API. First research how to do it safely, then write the code."

parser = argparse.ArgumentParser(description="Multi-Agent Explicit Graph with Sandbox and Finite Loop Guardrails")
parser.add_argument(
    "-t", "--task", 
    type=str, 
    default=DEFAULT_TASK, 
    help="Treść zadania do wykonania przez agentów (w cudzysłowie)"
)

parser.add_argument(
    "-f", "--file", 
    type=str, 
    nargs="+", 
    default=None, 
    help="Lista plików tekstowych załączanych jako kontekst"
)

parser.add_argument(
    "-o", "--output",
    type=str,
    default="generated_output.py",
    help="Ścieżka do pliku wyjściowego"
)

args = parser.parse_args()

# ==========================================
# 1. INICJALIZACJA STANU I MODELU
# ==========================================
base_model = copilotChat(model="gpt-4.1", temperature=0)

# NOWOŚĆ: Rozszerzamy stan o licznik powtórzeń poprawek kodu
class AgentState(MessagesState):
    critic_retry_count: int

# ==========================================
# FUNKCJA POMOCNICZA: PARSOWANIE KODU
# ==========================================
def extract_python_code(text: str) -> str:
    pattern = r"```python\s*(.*?)\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[-1].strip()
    return text.strip()

# ==========================================
# 2. DEFINICJA WĘZŁÓW (AGENCI)
# ==========================================
def researcher_node(state: AgentState):
    print("\n[bold magenta]➔ Pracuje: RESEARCHER[/bold magenta]")
    response = base_model.invoke([
        ("system", "You are a research assistant. Provide clear facts, documentation endpoints, or libraries needed. Do NOT write code. Provide raw data and stop."),
        *state["messages"]
    ])
    response.name = "researcher"
    return {"messages": [response]}

def coder_node(state: AgentState):
    print("\n[bold blue]➔ Pracuje: CODER[/bold blue]")
    response = base_model.invoke([
        ("system", (
            "You are an expert coder. Write complete, clean, and production-ready Python code based on the provided research. "
            "You CAN use the interactive input() function to make the script user-friendly. "
            "CRITICAL: You MUST provide test inputs in the very first line of your code using a special comment format: '# SANDBOX_INPUT: <values>' "
            "so the automated environment can test it. Example: # SANDBOX_INPUT: 10\\n"
            "Output ONLY the code block and brief instructions, then stop."
        )),
        *state["messages"]
    ])
    response.name = "coder"
    return {"messages": [response]}

def sandbox_node(state: AgentState):
    print("\n[bold cyan]➔ Pracuje: SANDBOX (Uruchamianie kodu...)[/bold cyan]")
    
    coder_msg = None
    for msg in reversed(state["messages"]):
        if getattr(msg, "name", None) == "coder":
            coder_msg = msg.content
            break
            
    if not coder_msg:
        err_report = "ERROR: No code block found from coder to execute."
        return {"messages": [AIMessage(content=err_report, name="sandbox")]}
        
    code_to_run = extract_python_code(coder_msg)
    
    # Wyciąganie wartości testowych dla input()
    extracted_input = ""
    match = re.search(r"#\s*SANDBOX_INPUT:\s*(.*)", code_to_run)
    if match:
        extracted_input = match.group(1).replace("\\n", "\n") + "\n"
        print(f"[bold json]🤖 Mockowanie wejścia (stdin):[/bold json] {repr(extracted_input)}")
    else:
        extracted_input = "5\n"
        print("[bold yellow]⚠️ Brak komentarza # SANDBOX_INPUT. Fallback na: '5'[/bold yellow]")

    sandbox_filename = "sandbox_runtime.py"
    with open(sandbox_filename, "w", encoding="utf-8") as f:
        f.write(code_to_run)
        
    try:
        result = subprocess.run(
            [sys.executable, sandbox_filename],
            capture_output=True,
            text=True,
            input=extracted_input,
            timeout=5
        )
        
        execution_report = (
            f"EXIT CODE: {result.returncode}\n\n"
            f"STDOUT:\n{result.stdout if result.stdout else '[Empty]'}\n\n"
            f"STDERR:\n{result.stderr if result.stderr else '[Empty]'}"
        )
        if result.returncode == 0:
            print("[bold green]✅ Sandbox: Kod wykonał się pomyślnie.[/bold green]")
        else:
            print("[bold red]❌ Sandbox: Wykryto błędy wykonania kodu.[/bold red]")
            
    except subprocess.TimeoutExpired:
        execution_report = "ERROR: Execution timed out after 5 seconds."
        print("[bold red]⏳ Sandbox: Przekroczono limit czasu![/bold red]")
    except Exception as e:
        execution_report = f"ERROR during runtime: {str(e)}"

    response_content = f"--- SANDBOX EXECUTION REPORT ---\n{execution_report}\n--------------------------------"
    return {"messages": [AIMessage(content=response_content, name="sandbox")]}

def critic_node(state: AgentState):
    print("\n[bold red]➔ Pracuje: CRITIC[/bold red]")
    response = base_model.invoke([
        ("system", (
            "You are a strict code critic and QA engineer. Review the Python code provided by 'coder' "
            "AND inspect the runtime logs provided by 'sandbox'. "
            "If the code looks production-ready and functions correctly, start your message with 'CRITIC_PASSED'. "
            "If the code has flaws or crashed, start your message with 'CRITIC_FAILED' and list corrections required."
        )),
        *state["messages"]
    ])
    response.name = "critic"
    
    # Zarządzanie licznikiem pętli wewnątrz stanu grafu
    current_retries = state.get("critic_retry_count", 0)
    if "CRITIC_FAILED" in response.content.upper():
        current_retries += 1
        print(f"[bold orange3]⚠️ Liczba nieudanych podejść do krytyka: {current_retries}/3[/bold orange3]")
        
    return {"messages": [response], "critic_retry_count": current_retries}

def human_node(state: AgentState):
    print("\n[bold yellow]🔍 KOD PRZESZEDŁ INTERNAL REVIEWS. WYMAGANA AKCEPTACJA CZŁOWIEKA![/bold yellow]")
    user_input = input("👉 Czy akceptujesz ten kod? (wpisz 'y' aby zatwierdzić, lub opisz poprawki): ").strip()
    
    if user_input.lower() == 'y':
        feedback = "APPROVED: The code is fully accepted by the human."
    else:
        feedback = f"REJECTED BY HUMAN: {user_input}"
    
    return {"messages": [AIMessage(content=feedback, name="human")]}

def exporter_node(state: AgentState):
    print(f"\n[bold green]➔ Pracuje: EXPORTER (Zapisywanie kodu do {args.output})...[/bold green]")
    coder_msg = None
    for msg in reversed(state["messages"]):
        if getattr(msg, "name", None) == "coder":
            coder_msg = msg.content
            break
            
    if coder_msg:
        final_code = extract_python_code(coder_msg)
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(final_code)
            print(f"[bold green]💾 Pomyślnie zapisano plik źródłowy:[/bold green] {args.output}")
            msg = f"SUCCESS: Saved to {args.output}"
        except Exception as e:
            msg = f"FAILURE: Write error: {str(e)}"
    return {"messages": [AIMessage(content=msg, name="exporter")]}

# ==========================================
# 3. DETERMINISTYCZNA LOGIKA ROUTINGU
# ==========================================
def route_after_critic(state: AgentState):
    """Sprawdza werdykt krytyka lub stan licznika bezpieczeństwa."""
    last_msg = state["messages"][-1].content.upper()
    retries = state.get("critic_retry_count", 0)
    
    if "CRITIC_PASSED" in last_msg:
        return "human"
        
    if retries >= 3:
        print("\n[bold red]🚨 Przekroczono bezpieczny limit 3 poprawek AI. Wymuszona interwencja człowieka![/bold red]")
        return "human"
        
    return "coder"

def route_after_human(state: AgentState):
    """Sprawdza decyzję podjętą przez człowieka."""
    last_msg = state["messages"][-1].content.upper()
    if "APPROVED" in last_msg:
        return "exporter"
    return "coder"

# ==========================================
# 4. BUDOWANIE STRUKTURY GRAFU (BEZ SUPERVISORA LLM)
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("researcher", researcher_node)
builder.add_node("coder", coder_node)
builder.add_node("sandbox", sandbox_node)
builder.add_node("critic", critic_node)
builder.add_node("human", human_node)
builder.add_node("exporter", exporter_node)

# Sztywne połączenia etapów przygotowawczych
builder.add_edge(START, "researcher")
builder.add_edge("researcher", "coder")
builder.add_edge("coder", "sandbox")
builder.add_edge("sandbox", "critic")

# Automatyczny routing na bazie funkcji Pythonowych
builder.add_conditional_edges(
    "critic",
    route_after_critic,
    {
        "coder": "coder",
        "human": "human"
    }
)

builder.add_conditional_edges(
    "human",
    route_after_human,
    {
        "coder": "coder",
        "exporter": "exporter"
    }
)

builder.add_edge("exporter", END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# ==========================================
# 5. URUCHOMIENIE SESJI
# ==========================================
task_content = args.task
if args.file:
    task_content += "\n\n=== ATTACHED FILES CONTEXT ==="
    for file_path in args.file:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                task_content += f"\n\n[FILE: {file_path}]\n{f.read()}\n"

# Inicjalizacja licznika na 0 zapobiega błędom braku klucza
initial_state = {
    "messages": [HumanMessage(content=task_content)],
    "critic_retry_count": 0
}
config = {"recursion_limit": 100, "configurable": {"thread_id": "production_stable_session"}}

print(f"\n[bold blue]📋 Zadanie:[/bold blue] {args.task}")
print(f"[bold green]🚀 Uruchamianie stabilnego grafu jPhone...[/bold green]\n")

while True:
    events = graph.stream(initial_state, config=config, stream_mode="updates")
    for output in events:
        node_name = list(output.keys())[0]
        if "messages" in output[node_name]:
            print(f"\n[bold green][{node_name.upper()}]:[/bold green] {output[node_name]['messages'][-1].content}")
            print("-" * 60)
            
    initial_state = None
    current_state = graph.get_state(config)
    if not current_state.next:
        print("\n[bold green]🏁 Proces zakończony powodzeniem. Kod wyeksportowany![/bold green]")
        break