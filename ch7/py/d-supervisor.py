from typing import Literal, Annotated
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from pydantic import BaseModel
from myDefaultChat import myDefaultChat
from rich import print

# ==========================================
# 1. DEFINICJA STRUKTURY DECYZJI SUPERVISORA
# ==========================================
class SupervisorDecision(BaseModel):
    next: Literal["researcher", "coder", "FINISH"]

# ==========================================
# 2. INICJALIZACJA MODELI (ROZDZIELNYCH)
# ==========================================
base_model = myDefaultChat(model="gpt-4o", temperature=0)
# Supervisor potrzebuje wymuszenia struktury wyjściowej (Structured Output)
supervisor_model = base_model.with_structured_output(SupervisorDecision)

agents = ["researcher", "coder"]

# Prompty dla Supervisora – maksymalnie precyzyjne, blokujące pętle
system_prompt_part_1 = f"""You are a strict supervisor managing a team of workers: {agents}. 
Your only job is to analyze the conversation and decide who should act next.
CRITICAL RULES:
- If the user's request requires research and it has NOT been done yet, assign 'researcher'.
- If research is done but the Python code/script has NOT been written yet, assign 'coder'.
- As soon as the code has been successfully written and provided by the coder, you MUST immediately respond with FINISH.
- Do NOT let workers talk in circles. Ignore polite closing phrases like 'feel free to ask' and focus only on whether the code is delivered.
"""

system_prompt_part_2 = f"Given the history above, who should act next? Select one of: {', '.join(agents)}, or FINISH."

# ==========================================
# 3. STAN GRAFU
# ==========================================
class AgentState(MessagesState):
    next: Literal["researcher", "coder", "FINISH"]

# ==========================================
# 4. DEFINICJE WĘZŁÓW (NODES)
# ==========================================
def supervisor(state: AgentState):
    messages = [
        ("system", system_prompt_part_1),
        *state["messages"],
        ("system", system_prompt_part_2),
    ]
    decision = supervisor_model.invoke(messages)
    return {"next": decision.next}

def researcher(state: AgentState):
    response = base_model.invoke([
        ("system", "You are a research assistant. Provide clear facts, documentation, or steps required. End your message immediately after providing the facts. Do NOT ask follow-up questions and do NOT say 'let me know if you need anything else'."),
        *state["messages"]
    ])
    return {"messages": [response]}

def coder(state: AgentState):
    response = base_model.invoke([
        ("system", "You are an expert coder. Write the complete, clean Python code requested based on the research. Once the code is written, stop. Do NOT include polite conversational sign-offs like 'feel free to ask'."),
        *state["messages"]
    ])
    return {"messages": [response]}

# ==========================================
# 5. BUDOWANIE I KOMPILACJA GRAFU
# ==========================================
builder = StateGraph(AgentState)
builder.add_node("supervisor", supervisor)
builder.add_node("researcher", researcher)
builder.add_node("coder", coder)

builder.add_edge(START, "supervisor")

# Mapowanie decyzji ze stanu grafu na konkretne przejścia do węzłów
builder.add_conditional_edges(
    "supervisor",
    lambda state: state["next"],
    {
        "researcher": "researcher",
        "coder": "coder",
        "FINISH": END
    }
)

builder.add_edge("researcher", "supervisor")
builder.add_edge("coder", "supervisor")

graph = builder.compile()

# ==========================================
# 6. URUCHOMIENIE I STRUMIENIOWANIE (STREAM)
# ==========================================
initial_state = {
    "messages": [
        {
            "role": "user",
            "content": "I need to build a simple Python script that scrapes weather data from an API. First research how to do it safely, then write the code.",
        }
    ]
}

# Dodajemy 'recursion_limit', aby skrypt w razie błędu nie przekroczył budżetu API
config = {"recursion_limit": 15}

print("[bold green]🚀 Uruchamianie Multi-Agent Graph...[/bold green]\n")

for output in graph.stream(initial_state, config=config):
    node_name = list(output.keys())[0]
    print(f"\n[bold cyan]➔ Wykonano węzeł:[/bold cyan] [yellow]{node_name}[/yellow]")
    
    if "supervisor" in output:
        decyzja = output["supervisor"].get("next")
        kolor = "red" if decyzja == "FINISH" else "magenta"
        print(f"[bold {kolor}]Decyzja supervisora (Kolejny krok):[/bold {kolor}] {decyzja}")
        
    if node_name in ["researcher", "coder"] and "messages" in output[node_name]:
        last_msg = output[node_name]["messages"][-1]
        print(f"[green]Treść odpowiedzi agenta (fragment):[/green]\n{last_msg.content}")
        print("-" * 60)