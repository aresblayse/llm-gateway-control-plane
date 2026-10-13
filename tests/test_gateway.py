from llm_gateway_control_plane.gateway import Gateway,Request
def test_capability_filter():
 g=Gateway.demo(); r=g.route(Request("hello","text",.03,1000,"p")); assert r["status"]=="success"
def test_budget_rejection():
 g=Gateway.demo()
 try: g.route(Request("hello","text",.00001,1000,"p")); assert False
 except ValueError: assert True
def test_deterministic_cache():
 g=Gateway.demo(); a=g.route(Request("hello","text",.03,1000,"p")); b=g.route(Request("hello","text",.03,1000,"p")); assert b["response"]==a["response"]
def test_arbitrary_prompt_invariant():
 g=Gateway.demo()
 for prompt in ["a","longer prompt","special: [] {}", "x"*50]: assert g.route(Request(prompt,"text",.03,1000,"p"))["status"]=="success"
