## Quickstart

To get started with _semantic-router_ we install it like so:

```
pip install -qU semantic-router[local]
```

We begin by defining a set of `Route` objects. These are the decision paths that the semantic router can decide to use, let's try two simple routes for now — one for talk on _politics_ and another for _chitchat_:

```python
from semantic_router import Route

# we could use this as a guide for our chatbot to avoid political conversations
politics = Route(
    name="politics",
    utterances=[
        "isn't politics the best thing ever",
        "why don't you tell me about your political opinions",
        "don't you just love the president",
        "they're going to destroy this country!",
        "they will save the country!",
    ],
)

# this could be used as an indicator to our chatbot to switch to a more
# conversational prompt
chitchat = Route(
    name="chitchat",
    utterances=[
        "how's the weather today?",
        "how are things going?",
        "lovely weather today",
        "the weather is horrendous",
        "let's go to the chippy",
    ],
)

# we place both of our decisions together into single list
routes = [politics, chitchat]

# Define Route Layer with Ollama
from semantic_router.layer import RouteLayer
from semantic_router.llms.ollama import OllamaLLM
from semantic_router.encoders import HuggingFaceEncoder
import ollama

os.environ["OLLAMA_ROUTER_MODEL"] = "qwen3.5:9b"
encoder = HuggingFaceEncoder()
ollama.pull(OLLAMA_ROUTER_MODEL)

llm = OllamaLLM(
    llm_name=OLLAMA_ROUTER_MODEL
)

rl = RouteLayer(encoder=encoder,
                routes=routes,
                llm=llm)
```

With our `routes` and `encoder` defined we now create a `RouteLayer`. The route layer handles our semantic decision making.

```python
from semantic_router.routers import SemanticRouter

rl = SemanticRouter(encoder=encoder, routes=routes, auto_sync="local")
```

We can now use our route layer to make super fast decisions based on user queries. Let's try with two queries that should trigger our route decisions:

```python
rl("don't you love politics?").name
```

```
[Out]: 'politics'
```

Correct decision, let's try another:

```python
rl("how's the weather today?").name
```

```
[Out]: 'chitchat'
```

We get both decisions correct! Now lets try sending an unrelated query:

```python
rl("I'm interested in learning about llama 2").name
```

```
[Out]:
```

In this case, no decision could be made as we had no matches — so our route layer returned `None`!


# To Install & Run Ollama

```shell
pip install --upgrade ollama
curl https://ollama.ai/install.sh | sh
```