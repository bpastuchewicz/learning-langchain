from myDefaultChat import myDefaultChat

model = myDefaultChat()

response = model.invoke("The sky is")
print(response.content)
