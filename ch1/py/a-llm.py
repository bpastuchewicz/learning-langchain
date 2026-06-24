from myDefaultChat import copilotChat

model = copilotChat()

response = model.invoke("The sky is")
print(response.content)
