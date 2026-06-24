import ast
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from myDefaultChat import myDefaultChat, web_search
from rich import print

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


tools = [web_search, calculator]
model = myDefaultChat(temperature=0.1).bind_tools(tools)


class State(TypedDict):
    messages: Annotated[list, add_messages]


def model_node(state: State) -> State:
    res = model.invoke(state["messages"])
    return {"messages": res}


builder = StateGraph(State)
builder.add_node("model", model_node)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "model")
builder.add_conditional_edges("model", tools_condition)
builder.add_edge("tools", "model")

graph = builder.compile()

# Example usage

input = {
    "messages": [
        HumanMessage(
            "How old was the 30th president of the United States when he died?"
        )
    ]
}

for c in graph.stream(input):
    print(c)
