import argparse
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

parser = argparse.ArgumentParser(description="Multi-Agent Explicit Graph with Critic CLI")
parser.add_argument("-t", "--task", type=str, default=DEFAULT_TASK, help="Treść zadania")
args = parser.parse_args()

# ==========================================
# 1. INICJALIZACJA MODELU (Copilot Edition)
# ==========================================
base_model = copilotChat(model="gpt-4o", temperature=0)

# Rozszerzamy dozwolone kroki o "critic"
class AgentState(MessagesState):
    next_step: Literal["researcher", "coder", "critic", "human", "FINISH"]

# ==========================================
# 2. DEFINICJA WĘZŁÓW (AGENCI)
# ==========================================
def researcher_node(state: AgentState):
    print("\n[bold magenta]➔ Pracuje: RESEARCHER[/bold magenta]")
    response = base_model.invoke([
        ("system", "You are a research assistant. Provide clear facts or libraries needed. Do NOT write code. Provide raw data and stop."),
        *state["messages"]
    ])
    response.name = "researcher"
    return {"messages": [response]}

def coder_node(state: AgentState):
    print("\n[bold blue]➔ Pracuje: CODER[/bold blue]")
    response = base_model.invoke([
        ("system", "You are an expert coder. Write complete, clean Python code based on research and critic feedback. Output ONLY the code block and brief instructions, then stop."),
        *state["messages"]
    ])
    response.name = "coder"
    return {"messages": [response]}

# NOWY AGENT: KRYTYK (CRITIC)
def critic_node(state: AgentState):
    print("\n[bold red]➔ Pracuje: CRITIC[/bold red]")
    response = base_model.invoke([
        ("system", (
            "You are a strict code critic and QA engineer. Review the Python code provided by the 'coder'. "
            "Check for security issues, syntax errors, missing exception handling, or anti-patterns. "
            "If the code is excellent, start your message with 'CRITIC_PASSED' and list why. "
            "If the code has flaws, start your message with 'CRITIC_FAILED' and provide a bulletproof list of required corrections."
        )),
        *state["messages"]
    ])
    response.name = "critic"
    return {"messages": [response]}

def human_node(state: AgentState):
    last_msg = state["messages"][-1] if state.get("messages") else None
    
    # Człowiek ogląda kod zweryfikowany przez krytyka
    print("\n[bold yellow]🔍 KOD PRZESZEDŁ TESTY KRYTYKA. WYMAGANA OSTATECZNA AKCEPTACJA CZŁOWIEKA![/bold yellow]")
    user_input = input("👉 Czy akceptujesz ten kod? (wpisz 'y' aby zatwierdzić, lub wpisz poprawki): ").strip()
    
    if user_input.lower() == 'y':
        feedback = "APPROVED: The code is fully accepted by the human. You can finish now."
    else:
        feedback = f"REJECTED BY HUMAN: {user_input}"
    
    return {"messages": [AIMessage(content=feedback, name="human")]}

# ==========================================
# 3. LOGIKA DECYZYJNA SUPERVISORA
# ==========================================
def supervisor_node(state: AgentState):
    print("\n[bold yellow]➔ Analizuje: SUPERVISOR[/bold yellow]")
    
    # Budujemy historię dla managera
    history = ""
    for msg in state["messages"]:
        speaker = getattr(msg, "name", msg.type)
        history += f"\n[{speaker}]: {msg.content[:200]}...\n"

    prompt = f"""You are a manager. Analyze the history and choose the next step.
Current History:
{history}

Rules for routing (Follow exactly):
1. If 'researcher' has NOT spoken yet -> respond exactly with: TO_RESEARCHER
2. If 'researcher' spoke, but 'coder' has NOT spoken yet -> respond exactly with: TO_CODER
3. If 'coder' just posted code -> you MUST send it to the critic next. Respond exactly with: TO_CRITIC
4. If 'critic' said 'CRITIC_FAILED' -> the code is broken. Send it back to the coder. Respond exactly with: TO_CODER
5. If 'critic' said 'CRITIC_PASSED' and 'human' has NOT reviewed it yet -> respond exactly with: TO_HUMAN
6. If 'human' rejected the code -> send it back to the coder to fix. Respond exactly with: TO_CODER
7. If 'human' approved the code (APPROVED) -> respond exactly with: TO_FINISH

Your response MUST be exactly one of the tokens above, nothing else."""

    response = base_model.invoke([("user", prompt)])
    content = response.content.upper()

    if "TO_RESEARCHER" in content:
        return {"next_step": "researcher"}
    elif "TO_CODER" in content:
        return {"next_step": "coder"}
    elif "TO_CRITIC" in content:
        return {"next_step": "critic"}
    elif "TO_HUMAN" in content:
        return {"next_step": "human"}
    else:
        return {"next_step": "FINISH"}

# ==========================================
# 4. BUDOWANIE STRUKTURY GRAFU
# ==========================================
builder = StateGraph(AgentState)

builder.add_node("supervisor", supervisor_node)
builder.add_node("researcher", researcher_node)
builder.add_node("coder", coder_node)
builder.add_node("critic", critic_node)
builder.add_node("human", human_node)

builder.add_edge(START, "supervisor")

# Routing warunkowy na podstawie decyzji tekstowej Supervisora
builder.add_conditional_edges(
    "supervisor",
    lambda state: state["next_step"],
    {
        "researcher": "researcher",
        "coder": "coder",
        "critic": "critic",
        "human": "human",
        "FINISH": END
    }
)

# Powroty do managera po zakończeniu pracy przez dowolnego agenta
builder.add_edge("researcher", "supervisor")
builder.add_edge("coder", "supervisor")
builder.add_edge("critic", "supervisor")
builder.add_edge("human", "supervisor")

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# ==========================================
# 5. URUCHOMIENIE
# ==========================================
initial_state = {"messages": [HumanMessage(content=args.task)]}
config = {"recursion_limit": 40, "configurable": {"thread_id": "3"}}

print(f"[bold blue]📋 Zadanie dla zespołu:[/bold blue] {args.task}\n")

while True:
    events = graph.stream(initial_state, config=config, stream_mode="updates")
    for output in events:
        node_name = list(output.keys())[0]
        if "messages" in output[node_name] and node_name != "supervisor":
            print(f"[green][{node_name}]:[/green] {output[node_name]['messages'][-1].content}")
            
    initial_state = None
    current_state = graph.get_state(config)
    if not current_state.next:
        print("\n[bold green]🏁 Proces zakończony sukcesem i kod wdrożony![/bold green]")
        break