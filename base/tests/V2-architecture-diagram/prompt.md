The attached image is an architecture diagram. Boxes are services. An arrow points from the caller to the service it calls. The legend in the image explains the two arrow styles.

Reply with one JSON object in a fenced `json` block, in exactly this shape:

```json
{
  "nodes": ["every service name, exactly as labelled"],
  "edges": [{"from": "caller", "to": "callee", "style": "sync"}],
  "if_event_bus_down": "in at most 60 words: what a customer placing an order experiences if event-bus is down, and what does not happen"
}
```

`style` is `"sync"` for a synchronous call and `"async"` for an asynchronous event. List every arrow in the diagram once, and only arrows that are in the diagram.
