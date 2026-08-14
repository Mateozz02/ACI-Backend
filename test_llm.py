from src.agents.llm import get_chat_llm
from langchain_core.messages import HumanMessage

llm = get_chat_llm(temperature=0)
response = llm.invoke([HumanMessage(content="Hola, decime solo la palabra 'funciona'")])
print("Respuesta:", response.content[:100])
print("OK - API funciona")
